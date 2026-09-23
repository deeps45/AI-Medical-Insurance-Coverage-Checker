"""Vector store with Pinecone or per-document persistent FAISS."""

from __future__ import annotations

import json
import logging
import shutil
import threading
from pathlib import Path
from typing import Any, Optional

from config import Settings, get_settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Lazy-initialized vector store supporting Pinecone or on-disk FAISS."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._lock = threading.Lock()
        self._embeddings = None
        self._store = None  # shared pinecone / legacy single faiss
        self._backend_name = "uninitialized"
        self._local_texts: list[dict[str, Any]] = []
        self._faiss_cls = None
        self._doc_stores: dict[str, Any] = {}  # document_id -> FAISS

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

            self._faiss_cls = FAISS
            self._store = None
            self.settings.faiss_dir.mkdir(parents=True, exist_ok=True)
            self._backend_name = "faiss"
            logger.info("Using persistent FAISS at %s", self.settings.faiss_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning("FAISS unavailable (%s); using simple memory store", exc)
            self._store = None
            self._backend_name = "memory"

    def _doc_dir(self, document_id: str) -> Path:
        return self.settings.faiss_dir / document_id

    def _save_faiss(self, document_id: str, store: Any) -> None:
        path = self._doc_dir(document_id)
        path.mkdir(parents=True, exist_ok=True)
        store.save_local(str(path))
        meta_path = path / "meta.json"
        meta_path.write_text(json.dumps({"document_id": document_id}))

    def _load_faiss(self, document_id: str) -> Any | None:
        if document_id in self._doc_stores:
            return self._doc_stores[document_id]
        path = self._doc_dir(document_id)
        if not path.exists() or not (path / "index.faiss").exists():
            return None
        store = self._faiss_cls.load_local(
            str(path),
            self._embeddings,
            allow_dangerous_deserialization=True,
        )
        self._doc_stores[document_id] = store
        return store

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        *,
        document_id: str | None = None,
        replace: bool = False,
    ) -> None:
        self._ensure_initialized()
        if self._backend_name == "unavailable":
            raise RuntimeError("Vector store is not available")

        if document_id is None and metadatas:
            document_id = metadatas[0].get("document_id")

        if self._backend_name == "memory":
            if replace and document_id:
                self._local_texts = [
                    t
                    for t in self._local_texts
                    if t["metadata"].get("document_id") != document_id
                ]
            for text, meta in zip(texts, metadatas):
                self._local_texts.append({"text": text, "metadata": meta})
            return

        if self._backend_name == "faiss":
            if not document_id:
                raise ValueError("document_id is required for FAISS persistence")
            if replace:
                self.delete_document(document_id)
            store = self._faiss_cls.from_texts(
                texts, self._embeddings, metadatas=metadatas
            )
            self._doc_stores[document_id] = store
            self._save_faiss(document_id, store)
            return

        # Pinecone
        assert self._store is not None
        if replace and document_id:
            self.delete_document(document_id)
        ids = [f"{document_id}-{i}" for i in range(len(texts))] if document_id else None
        self._store.add_texts(texts, metadatas=metadatas, ids=ids)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        document_id: Optional[str] = None,
    ) -> list[Any]:
        """Return docs; attach approximate relevance score into metadata when available."""
        self._ensure_initialized()
        if self._backend_name == "unavailable":
            raise RuntimeError("Vector store is not available")

        if self._backend_name == "memory":
            return self._memory_search(query, k, document_id)

        if self._backend_name == "faiss":
            return self._faiss_search_with_scores(query, k, document_id)

        assert self._store is not None
        filter_dict = {"document_id": document_id} if document_id else None
        try:
            if filter_dict:
                pairs = self._store.similarity_search_with_score(
                    query, k=k, filter=filter_dict
                )
            else:
                pairs = self._store.similarity_search_with_score(query, k=k)
            return self._attach_scores(pairs)
        except Exception:  # noqa: BLE001
            if filter_dict:
                try:
                    return self._store.similarity_search(query, k=k, filter=filter_dict)
                except Exception:  # noqa: BLE001
                    docs = self._store.similarity_search(query, k=k * 3)
                    return [
                        d for d in docs if d.metadata.get("document_id") == document_id
                    ][:k]
            return self._store.similarity_search(query, k=k)

    def _attach_scores(self, pairs: list[tuple[Any, float]]) -> list[Any]:
        docs = []
        for doc, score in pairs:
            meta = dict(getattr(doc, "metadata", {}) or {})
            # FAISS L2: lower is better → convert to similarity-ish 1/(1+d)
            try:
                meta["score"] = round(float(1.0 / (1.0 + float(score))), 4)
            except (TypeError, ValueError):
                meta["score"] = None
            doc.metadata = meta
            docs.append(doc)
        return docs

    def _faiss_search_with_scores(
        self, query: str, k: int, document_id: Optional[str]
    ) -> list[Any]:
        if document_id:
            store = self._load_faiss(document_id)
            if store is None:
                return []
            pairs = store.similarity_search_with_score(query, k=k)
            return self._attach_scores(pairs)

        scored: list[tuple[Any, float]] = []
        for path in self.settings.faiss_dir.glob("*"):
            if not path.is_dir():
                continue
            store = self._load_faiss(path.name)
            if store is None:
                continue
            scored.extend(store.similarity_search_with_score(query, k=k))
        scored.sort(key=lambda x: x[1])  # lower distance first
        return self._attach_scores(scored[:k])

    def _memory_search(
        self,
        query: str,
        k: int,
        document_id: Optional[str],
    ) -> list[Any]:
        from types import SimpleNamespace

        tokens = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[tuple[float, dict]] = []
        for item in self._local_texts:
            if document_id and item["metadata"].get("document_id") != document_id:
                continue
            text_tokens = {t.lower() for t in item["text"].split()}
            overlap = len(tokens & text_tokens)
            scored.append((float(overlap), item))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, item in scored[:k]:
            meta = dict(item["metadata"])
            meta["score"] = score
            results.append(SimpleNamespace(page_content=item["text"], metadata=meta))
        return results

    def delete_document(self, document_id: str) -> bool:
        """Remove vectors for a document. Returns True if something was removed."""
        self._ensure_initialized()
        removed = False

        if self._backend_name == "memory":
            before = len(self._local_texts)
            self._local_texts = [
                t
                for t in self._local_texts
                if t["metadata"].get("document_id") != document_id
            ]
            return len(self._local_texts) < before

        if self._backend_name == "faiss":
            self._doc_stores.pop(document_id, None)
            path = self._doc_dir(document_id)
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                removed = True
            return removed

        try:
            index = getattr(self._store, "_index", None) or getattr(
                self._store, "index", None
            )
            if index is not None:
                index.delete(filter={"document_id": {"$eq": document_id}})
                removed = True
            else:
                ids = [f"{document_id}-{i}" for i in range(5000)]
                self._store.delete(ids=ids)  # type: ignore[attr-defined]
                removed = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pinecone delete failed for %s: %s", document_id, exc)
        return removed

    def has_document(self, document_id: str) -> bool:
        self._ensure_initialized()
        if self._backend_name == "memory":
            return any(
                t["metadata"].get("document_id") == document_id for t in self._local_texts
            )
        if self._backend_name == "faiss":
            return self._doc_dir(document_id).exists()
        return True


_vector_service: VectorStoreService | None = None


def get_vector_store() -> VectorStoreService:
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorStoreService()
    return _vector_service


def reset_vector_store(service: VectorStoreService | None = None) -> VectorStoreService:
    global _vector_service
    _vector_service = service if service is not None else VectorStoreService()
    return _vector_service
