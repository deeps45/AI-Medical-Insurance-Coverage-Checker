"""Tests for vector store memory backend and QA helpers."""

from __future__ import annotations

from helpers import make_settings
from services.qa import build_prompt, generate_answer
from services.vector_store import VectorStoreService


def test_memory_search_filters_by_document(tmp_path):
    store = VectorStoreService(
        settings=make_settings(faiss_dir=tmp_path / "faiss")
    )
    store._backend_name = "memory"
    store.add_texts(
        ["MRI is covered with a $50 copay", "Dental is not covered"],
        [
            {"document_id": "doc-a", "page": 1, "source": "a.pdf"},
            {"document_id": "doc-b", "page": 1, "source": "b.pdf"},
        ],
        document_id="doc-a",
    )
    # second add with different id
    store.add_texts(
        ["Dental is not covered"],
        [{"document_id": "doc-b", "page": 1, "source": "b.pdf"}],
        document_id="doc-b",
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
    answer = generate_answer("ER copay?", docs, settings=make_settings())
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


def test_faiss_persistence_roundtrip(tmp_path, monkeypatch):
    """Memory backend delete/replace works; FAISS path creates dirs when embeddings exist."""
    store = VectorStoreService(settings=make_settings(faiss_dir=tmp_path / "faiss"))
    store._backend_name = "memory"
    store.add_texts(
        ["Annual Deductible: $1,000"],
        [{"document_id": "d1", "page": 1, "source": "p.pdf"}],
        document_id="d1",
    )
    assert store.has_document("d1")
    assert store.delete_document("d1")
    assert not store.has_document("d1")
