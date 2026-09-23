"""FastAPI backend for AI Medical Insurance Coverage Checker."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import get_settings
from db import Document, Query, SessionLocal, init_db
from schemas import (
    AskRequest,
    AskResponse,
    CleanupResponse,
    DeleteResponse,
    DocumentInfo,
    HealthResponse,
    IngestResponse,
    QueryInfo,
    SourceInfo,
    SummaryRequest,
    SummaryResponse,
)
from services.auth import require_api_key
from services.cleanup import cleanup_expired_documents
from services.llm import resolve_provider, stream_chat_completion
from services.pdf_extractor import chunk_pages, extract_pages_from_pdf
from services.qa import build_messages, dedupe_sources, generate_answer
from services.summary import build_coverage_summary
from services.vector_store import get_vector_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
init_db()

app = FastAPI(
    title="AI Medical Insurance Coverage Checker",
    description="Upload insurance PDFs and ask coverage questions with RAG",
    version="3.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup_cleanup() -> None:
    try:
        cleanup_expired_documents(settings, vector_store=get_vector_store())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Startup TTL cleanup skipped: %s", exc)


def _validate_pdf_bytes(content: bytes, filename: str | None) -> None:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a .pdf policy document.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"PDF must be {settings.max_upload_mb}MB or smaller.",
        )
    if not content.lstrip().startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail="File does not look like a valid PDF (missing %PDF header).",
        )


def _db_status() -> str:
    try:
        db = SessionLocal()
        try:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
            return "ok"
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Database health check failed: %s", exc)
        return "error"


def _process_pdf(content: bytes, filename: str, document_id: str | None = None) -> IngestResponse:
    pages = extract_pages_from_pdf(content, settings.tesseract_cmd)
    if not pages:
        raise HTTPException(status_code=400, detail="No text could be extracted from PDF")

    chunks = chunk_pages(pages)
    replaced = document_id is not None
    document_id = document_id or str(uuid.uuid4())

    texts = [c[0] for c in chunks]
    metadatas = [
        {
            "source": filename,
            "page": page_num,
            "document_id": document_id,
            "section": section,
        }
        for _, page_num, section in chunks
    ]

    store = get_vector_store()
    if not store.is_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "Vector store unavailable. Set TAMUS_AI_CHAT_API_KEY or "
                "OPENAI_API_KEY (and optionally USE_LOCAL_VECTORSTORE=true)."
            ),
        )
    store.add_texts(texts, metadatas, document_id=document_id, replace=replaced)

    db = SessionLocal()
    try:
        existing = db.query(Document).filter(Document.id == document_id).first()
        if existing:
            existing.filename = filename
            existing.page_count = len(pages)
            existing.chunk_count = len(chunks)
            existing.status = "ready"
            existing.uploaded_at = datetime.utcnow()
        else:
            db.add(
                Document(
                    id=document_id,
                    filename=filename,
                    page_count=len(pages),
                    chunk_count=len(chunks),
                    status="ready",
                    uploaded_at=datetime.utcnow(),
                )
            )
        db.commit()
    finally:
        db.close()

    return IngestResponse(
        document_id=document_id,
        pages=len(pages),
        chunks=len(chunks),
        filename=filename,
        replaced=replaced,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    store = get_vector_store()
    provider = resolve_provider(settings)
    return HealthResponse(
        status="ok",
        vectorstore=store.backend_name,
        database=_db_status(),
        llm_provider=provider,
        chat_model=settings.chat_model if provider != "none" else "",
        message="Backend is running",
        auth_enabled=settings.enable_auth,
    )


@app.get("/documents", response_model=list[DocumentInfo])
async def list_documents(_: str | None = Depends(require_api_key)):
    db = SessionLocal()
    try:
        rows = db.query(Document).order_by(Document.uploaded_at.desc()).limit(50).all()
        return [
            DocumentInfo(
                id=row.id,
                filename=row.filename,
                page_count=row.page_count,
                chunk_count=row.chunk_count or 0,
                status=getattr(row, "status", None) or "ready",
                uploaded_at=row.uploaded_at.isoformat(),
            )
            for row in rows
        ]
    finally:
        db.close()


@app.get("/queries", response_model=list[QueryInfo])
async def list_queries(
    document_id: str | None = None,
    limit: int = 20,
    _: str | None = Depends(require_api_key),
):
    limit = max(1, min(limit, 100))
    db = SessionLocal()
    try:
        q = db.query(Query).order_by(Query.created_at.desc())
        if document_id:
            q = q.filter(Query.document_id == document_id)
        rows = q.limit(limit).all()
        results: list[QueryInfo] = []
        for row in rows:
            sources: list[SourceInfo] = []
            raw = getattr(row, "sources_json", None)
            if raw:
                try:
                    sources = [SourceInfo(**item) for item in json.loads(raw)]
                except Exception:  # noqa: BLE001
                    sources = []
            results.append(
                QueryInfo(
                    id=row.id,
                    document_id=row.document_id,
                    question=row.question,
                    answer=row.answer,
                    sources=sources,
                    latency_ms=row.latency_ms,
                    created_at=row.created_at.isoformat(),
                )
            )
        return results
    finally:
        db.close()


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    _: str | None = Depends(require_api_key),
):
    content = await file.read()
    try:
        _validate_pdf_bytes(content, file.filename)
    except HTTPException:
        raise
    try:
        return _process_pdf(content, file.filename or "policy.pdf")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error processing PDF")
        raise HTTPException(
            status_code=500,
            detail="Could not process this PDF. Try a text-based policy export, or a clearer scan.",
        ) from exc


@app.put("/documents/{document_id}/reingest", response_model=IngestResponse)
async def reingest_document(
    document_id: str,
    file: UploadFile = File(...),
    _: str | None = Depends(require_api_key),
):
    db = SessionLocal()
    try:
        existing = db.query(Document).filter(Document.id == document_id).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found. Upload a policy first.")
    finally:
        db.close()

    content = await file.read()
    _validate_pdf_bytes(content, file.filename)

    try:
        return _process_pdf(content, file.filename or "policy.pdf", document_id=document_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error re-ingesting PDF")
        raise HTTPException(
            status_code=500,
            detail="Re-ingest failed. Confirm the file is a readable PDF and try again.",
        ) from exc


@app.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    _: str | None = Depends(require_api_key),
):
    db = SessionLocal()
    try:
        row = db.query(Document).filter(Document.id == document_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        db.query(Query).filter(Query.document_id == document_id).delete()
        db.delete(row)
        db.commit()
    finally:
        db.close()

    removed = get_vector_store().delete_document(document_id)
    return DeleteResponse(
        document_id=document_id,
        deleted=True,
        message="Document and vectors removed" if removed else "Document removed (no local vectors found)",
    )


@app.post("/admin/cleanup", response_model=CleanupResponse)
async def admin_cleanup(_: str | None = Depends(require_api_key)):
    """Remove documents older than DOCUMENT_TTL_HOURS (0 disables TTL)."""
    result = cleanup_expired_documents(settings, vector_store=get_vector_store())
    return CleanupResponse(
        documents=result["documents"],
        queries=result["queries"],
        skipped=result.get("skipped", 0),
        message=(
            "TTL disabled"
            if result.get("skipped")
            else f"Removed {result['documents']} expired document(s)"
        ),
    )


@app.post("/ask", response_model=AskResponse)
async def ask_question(
    payload: AskRequest,
    _: str | None = Depends(require_api_key),
):
    store = get_vector_store()
    if not store.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Search index unavailable. Check LLM/embedding credentials and try again.",
        )
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Please enter a non-empty question.")

    start = time.time()
    try:
        docs = store.similarity_search(
            payload.question,
            k=payload.k or 4,
            document_id=payload.document_id,
        )
        answer = generate_answer(payload.question, docs, settings)
        latency_ms = (time.time() - start) * 1000
        sources = [
            SourceInfo(**item) for item in dedupe_sources(docs, query=payload.question)
        ]
        _save_query(payload.document_id, payload.question, answer, latency_ms, sources)
        return AskResponse(answer=answer, latency_ms=latency_ms, sources=sources)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error processing question")
        raise HTTPException(
            status_code=500,
            detail="Could not answer right now. Try again, or rephrase the question.",
        ) from exc


@app.post("/ask/stream")
async def ask_question_stream(
    payload: AskRequest,
    _: str | None = Depends(require_api_key),
):
    store = get_vector_store()
    if not store.is_ready:
        raise HTTPException(status_code=503, detail="Vector store not available")
    return await _ask_stream(payload)


async def _ask_stream(payload: AskRequest):
    store = get_vector_store()
    docs = store.similarity_search(
        payload.question,
        k=payload.k or 4,
        document_id=payload.document_id,
    )
    sources = dedupe_sources(docs, query=payload.question)
    context = "\n\n".join(doc.page_content for doc in docs) if docs else ""

    def event_gen():
        start = time.time()
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
        if not context.strip():
            msg = (
                "I couldn't find relevant information in the uploaded policy. "
                "Try rephrasing your question or uploading a clearer document."
            )
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'latency_ms': (time.time()-start)*1000})}\n\n"
            _save_query(
                payload.document_id,
                payload.question,
                msg,
                (time.time() - start) * 1000,
                [SourceInfo(**s) for s in sources],
            )
            return

        if resolve_provider(settings) == "none":
            answer = generate_answer(payload.question, docs, settings)
            yield f"data: {json.dumps({'type': 'token', 'content': answer})}\n\n"
            latency = (time.time() - start) * 1000
            yield f"data: {json.dumps({'type': 'done', 'latency_ms': latency})}\n\n"
            _save_query(
                payload.document_id,
                payload.question,
                answer,
                latency,
                [SourceInfo(**s) for s in sources],
            )
            return

        parts: list[str] = []
        try:
            for delta in stream_chat_completion(
                build_messages(payload.question, context),
                settings,
                temperature=0.2,
                max_tokens=600,
            ):
                parts.append(delta)
                yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
            return
        answer = "".join(parts).strip()
        latency = (time.time() - start) * 1000
        _save_query(
            payload.document_id,
            payload.question,
            answer,
            latency,
            [SourceInfo(**s) for s in sources],
        )
        yield f"data: {json.dumps({'type': 'done', 'latency_ms': latency})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/summary", response_model=SummaryResponse)
async def coverage_summary(
    payload: SummaryRequest,
    _: str | None = Depends(require_api_key),
):
    store = get_vector_store()
    if not store.is_ready:
        raise HTTPException(status_code=503, detail="Vector store not available")

    start = time.time()
    question = (
        "annual deductible out-of-pocket maximum emergency room copay "
        "MRI specialist prescription drugs coverage"
    )
    docs = store.similarity_search(
        question, k=payload.k or 8, document_id=payload.document_id
    )
    result = build_coverage_summary(docs, settings)
    latency_ms = (time.time() - start) * 1000
    return SummaryResponse(
        summary=result["summary"],
        fields=result["fields"],
        sources=[SourceInfo(**s) for s in result["sources"]],
        latency_ms=latency_ms,
    )


def _save_query(
    document_id: str | None,
    question: str,
    answer: str,
    latency_ms: float,
    sources: list[SourceInfo] | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            Query(
                id=str(uuid.uuid4()),
                document_id=document_id,
                question=question,
                answer=answer,
                sources_json=json.dumps([s.model_dump() for s in (sources or [])]),
                latency_ms=latency_ms,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
