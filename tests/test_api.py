"""API integration tests using the local memory/FAISS vector store."""

from __future__ import annotations

import io


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["vectorstore"] in {"memory", "faiss", "pinecone", "unavailable"}


def test_reject_non_pdf(client):
    response = client.post(
        "/ingest",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_ingest_and_ask(client, sample_pdf_bytes):
    ingest = client.post(
        "/ingest",
        files={"file": ("policy.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert ingest.status_code == 200, ingest.text
    payload = ingest.json()
    assert payload["pages"] >= 1
    assert payload["chunks"] >= 1
    assert payload["filename"] == "policy.pdf"
    document_id = payload["document_id"]

    docs = client.get("/documents")
    assert docs.status_code == 200
    assert any(d["id"] == document_id for d in docs.json())

    ask = client.post(
        "/ask",
        json={
            "question": "Is MRI covered and what is the copay?",
            "k": 4,
            "document_id": document_id,
        },
    )
    assert ask.status_code == 200, ask.text
    result = ask.json()
    assert "MRI" in result["answer"] or "50" in result["answer"]
    assert result["latency_ms"] >= 0
    assert isinstance(result["sources"], list)


def test_ask_validation(client):
    response = client.post("/ask", json={"question": "", "k": 4})
    assert response.status_code == 422


def test_empty_pdf_rejected(client):
    import fitz

    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()

    response = client.post(
        "/ingest",
        files={"file": ("blank.pdf", buf.getvalue(), "application/pdf")},
    )
    assert response.status_code == 400
