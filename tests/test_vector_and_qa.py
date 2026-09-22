"""Tests for vector store memory backend and QA helpers."""

from __future__ import annotations

from config import Settings
from services.qa import build_prompt, generate_answer
from services.vector_store import VectorStoreService


def _settings(**overrides) -> Settings:
    base = dict(
        openai_api_key=None,
        tamus_api_key=None,
        tamus_api_endpoint="https://chat-api.tamu.ai",
        pinecone_api_key=None,
        pinecone_index_name="test",
        database_url="sqlite:///./x.db",
        tesseract_cmd="/usr/bin/tesseract",
        embedding_model="text-embedding-3-small",
        chat_model="gpt-4o-mini",
        use_local_vectorstore=True,
        qa_mode="extractive",
        cors_origins=["*"],
    )
    base.update(overrides)
    return Settings(**base)


def test_memory_search_filters_by_document():
    store = VectorStoreService(settings=_settings())
    # Force memory backend
    store._backend_name = "memory"
    store.add_texts(
        ["MRI is covered with a $50 copay", "Dental is not covered"],
        [
            {"document_id": "doc-a", "page": 1, "source": "a.pdf"},
            {"document_id": "doc-b", "page": 1, "source": "b.pdf"},
        ],
    )
    results = store.similarity_search("MRI copay", k=5, document_id="doc-a")
    assert results
    assert all(r.metadata["document_id"] == "doc-a" for r in results)


def test_build_prompt_includes_context():
    prompt = build_prompt("What is the deductible?", "Annual Deductible: $1,000")
    assert "deductible" in prompt.lower()
    assert "$1,000" in prompt


def test_extractive_generate_answer():
    from types import SimpleNamespace

    docs = [
        SimpleNamespace(
            page_content="Emergency Room: $100 copay",
            metadata={"page": 2, "source": "policy.pdf"},
        )
    ]
    answer = generate_answer("ER copay?", docs, settings=_settings())
    assert "100" in answer
    assert "[p2]" in answer


def test_dedupe_sources():
    from types import SimpleNamespace

    from services.qa import dedupe_sources

    docs = [
        SimpleNamespace(metadata={"page": 1, "source": "a.pdf", "document_id": "d1"}),
        SimpleNamespace(metadata={"page": 1, "source": "a.pdf", "document_id": "d1"}),
        SimpleNamespace(metadata={"page": 2, "source": "a.pdf", "document_id": "d1"}),
    ]
    sources = dedupe_sources(docs)
    assert len(sources) == 2
    assert sources[0]["page"] == 1
    assert sources[1]["page"] == 2


def test_build_messages_has_system_role():
    from services.qa import build_messages

    messages = build_messages("What is the deductible?", "Annual Deductible: $1,000")
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "$1,000" in messages[1]["content"]
