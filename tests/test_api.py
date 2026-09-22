"""API integration tests using the local memory vector store."""

from __future__ import annotations

import io


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["vectorstore"] in {"memory", "faiss", "pinecone", "unavailable"}
    assert "auth_enabled" in data


def test_reject_non_pdf(client):
    response = client.post(
        "/ingest",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_ingest_ask_delete(client, sample_pdf_bytes):
    ingest = client.post(
        "/ingest",
        files={"file": ("policy.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert ingest.status_code == 200, ingest.text
    payload = ingest.json()
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

    summary = client.post(
        "/summary",
        json={"document_id": document_id, "k": 6},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["summary"]

    deleted = client.delete(f"/documents/{document_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    docs_after = client.get("/documents")
    assert all(d["id"] != document_id for d in docs_after.json())


def test_reingest(client, sample_pdf_bytes):
    first = client.post(
        "/ingest",
        files={"file": ("policy.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert first.status_code == 200
    document_id = first.json()["document_id"]

    second = client.put(
        f"/documents/{document_id}/reingest",
        files={"file": ("policy-v2.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["document_id"] == document_id
    assert body["replaced"] is True
    assert body["filename"] == "policy-v2.pdf"


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


def test_ask_stream_extractive(client, sample_pdf_bytes):
    ingest = client.post(
        "/ingest",
        files={"file": ("policy.pdf", sample_pdf_bytes, "application/pdf")},
    )
    document_id = ingest.json()["document_id"]
    with client.stream(
        "POST",
        "/ask/stream",
        json={"question": "MRI copay?", "document_id": document_id, "k": 3},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "data:" in body
    assert "done" in body
