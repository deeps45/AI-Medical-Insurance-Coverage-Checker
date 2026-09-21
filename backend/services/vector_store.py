"""Vector store abstraction with Pinecone or local FAISS fallback."""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Lazy-initialized vector store supporting Pinecone or in-memory FAISS."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._lock = threading.Lock()
        self._embeddings = None
        self._store = None
        self._backend_name = "uninitialized"
        self._local_texts: list[dict[str, Any]] = []

    @property
    def backend_name(self) -> str:
        self._ensure_initialized()
        return self._backend_name

    @property
    def is_ready(self) -> bool:
        self._ensure_initialized()
        return self._backend_name in {"memory", "faiss", "pinecone"}

    def _ensure_initialized(self) -> None:
        if self._backend_name != "uninitialized":
            return
        with self._lock:
            if self._backend_name != "uninitialized":
                return
            self._initialize()

    def _initialize(self) -> None:
        from services.llm import has_llm_credentials, resolve_provider

        provider = resolve_provider(self.settings)

        # Offline / test path: keyword memory store needs no API keys
        if self.settings.use_local_vectorstore and not has_llm_credentials(self.settings):
            self._backend_name = "memory"
            logger.info("Using in-memory keyword vector store (no LLM key)")
            return

        if not has_llm_credentials(self.settings):
            logger.warning("No TAMUS/OpenAI key set; vector store unavailable")
            self._backend_name = "unavailable"
            return

        try:
            from langchain_openai import OpenAIEmbeddings

            embed_kwargs: dict[str, Any] = {
                "model": self.settings.embedding_model,
                # TAMU Chat API expects string inputs, not token-id arrays
                "check_embedding_ctx_length": False,
            }
            if provider == "tamu":
                base = self.settings.tamus_api_endpoint.rstrip("/")
                embed_kwargs["api_key"] = self.settings.tamus_api_key
                embed_kwargs["base_url"] = f"{base}/api"
            else:
                embed_kwargs["api_key"] = self.settings.openai_api_key

            self._embeddings = OpenAIEmbeddings(**embed_kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not initialize embeddings: %s", exc)
            if self.settings.use_local_vectorstore:
                self._backend_name = "memory"
                return
            self._backend_name = "unavailable"
            return

        if self.settings.use_local_vectorstore or not self.settings.pinecone_api_key:
            self._init_faiss()
            return

        try:
            self._init_pinecone()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pinecone init failed (%s); falling back to FAISS", exc)
            self._init_faiss()

    def _init_pinecone(self) -> None:
        from langchain_pinecone import Pinecone as LangchainPinecone
        from pinecone import Pinecone

        pc = Pinecone(api_key=self.settings.pinecone_api_key)
        index_name = self.settings.pinecone_index_name
        existing = [idx.name for idx in pc.list_indexes()]
        if index_name not in existing:
            raise RuntimeError(
                f"Pinecone index '{index_name}' not found. "
                "Create it in the Pinecone console or set USE_LOCAL_VECTORSTORE=true."
            )

        self._store = LangchainPinecone.from_existing_index(
            index_name=index_name,
            embedding=self._embeddings,
        )
        self._backend_name = "pinecone"
        logger.info("Using Pinecone index: %s", index_name)

    def _init_faiss(self) -> None:
        try:
            from langchain_community.vectorstores import FAISS

            # Empty FAISS store seeded on first add_texts
            self._store = None
            self._faiss_cls = FAISS
            self._backend_name = "faiss"
            logger.info("Using local FAISS vector store")
        except Exception as exc:  # noqa: BLE001
            logger.warning("FAISS unavailable (%s); using simple memory store", exc)
            self._store = None
            self._backend_name = "memory"

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self._ensure_initialized()
        if self._backend_name == "unavailable":
            raise RuntimeError("Vector store is not available")

        if self._backend_name == "memory":
            for text, meta in zip(texts, metadatas):
                self._local_texts.append({"text": text, "metadata": meta})
            return

        if self._backend_name == "faiss":
            if self._store is None:
                self._store = self._faiss_cls.from_texts(
                    texts, self._embeddings, metadatas=metadatas
                )
            else:
                self._store.add_texts(texts, metadatas=metadatas)
            return

        assert self._store is not None
        self._store.add_texts(texts, metadatas=metadatas)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        document_id: Optional[str] = None,
    ) -> list[Any]:
        self._ensure_initialized()
        if self._backend_name == "unavailable":
            raise RuntimeError("Vector store is not available")

        if self._backend_name == "memory":
            return self._memory_search(query, k, document_id)

        filter_dict = {"document_id": document_id} if document_id else None

        if self._backend_name == "faiss":
            if self._store is None:
                return []
            docs = self._store.similarity_search(query, k=k * 3 if document_id else k)
            if document_id:
                docs = [d for d in docs if d.metadata.get("document_id") == document_id][:k]
            return docs

        assert self._store is not None
        if filter_dict:
            try:
                return self._store.similarity_search(query, k=k, filter=filter_dict)
            except Exception:  # noqa: BLE001 - some backends reject filters
                docs = self._store.similarity_search(query, k=k * 3)
                return [d for d in docs if d.metadata.get("document_id") == document_id][:k]
        return self._store.similarity_search(query, k=k)

    def _memory_search(
        self,
        query: str,
        k: int,
        document_id: Optional[str],
    ) -> list[Any]:
        """Simple keyword-overlap retrieval for offline/unit tests."""
        from types import SimpleNamespace

        tokens = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[tuple[float, dict]] = []
        for item in self._local_texts:
            if document_id and item["metadata"].get("document_id") != document_id:
                continue
            text_tokens = {t.lower() for t in item["text"].split()}
            score = len(tokens & text_tokens)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, item in scored[:k]:
            results.append(
                SimpleNamespace(page_content=item["text"], metadata=item["metadata"])
            )
        return results


_vector_service: VectorStoreService | None = None


def get_vector_store() -> VectorStoreService:
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorStoreService()
    return _vector_service


def reset_vector_store(service: VectorStoreService | None = None) -> VectorStoreService:
    """Replace the singleton (used by tests)."""
    global _vector_service
    _vector_service = service if service is not None else VectorStoreService()
    return _vector_service
