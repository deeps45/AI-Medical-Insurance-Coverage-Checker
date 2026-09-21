"""FastAPI backend for AI Medical Insurance Coverage Checker."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db import Document, Query, SessionLocal, init_db
from schemas import (
    AskRequest,
    AskResponse,
    DocumentInfo,
    HealthResponse,
    IngestResponse,
    SourceInfo,
)
from services.llm import resolve_provider
from services.pdf_extractor import chunk_pages, extract_pages_from_pdf
from services.qa import generate_answer
from services.vector_store import get_vector_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
init_db()

app = FastAPI(
    title="AI Medical Insurance Coverage Checker",
    description="Upload insurance PDFs and ask coverage questions with RAG",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    )


@app.get("/documents", response_model=list[DocumentInfo])
async def list_documents():
    db = SessionLocal()
    try:
        rows = db.query(Document).order_by(Document.uploaded_at.desc()).limit(50).all()
        return [
            DocumentInfo(
                id=row.id,
                filename=row.filename,
                page_count=row.page_count,
                chunk_count=row.chunk_count or 0,
                uploaded_at=row.uploaded_at.isoformat(),
            )
            for row in rows
        ]
    finally:
        db.close()


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Soft size limit: 25 MB
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF must be 25MB or smaller")

    try:
        pages = extract_pages_from_pdf(content, settings.tesseract_cmd)
        if not pages:
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from PDF",
            )

        chunks = chunk_pages(pages)
        document_id = str(uuid.uuid4())
        filename = file.filename

        texts = [c[0] for c in chunks]
        metadatas = [
            {
                "source": filename,
                "page": page_num,
                "document_id": document_id,
            }
            for _, page_num in chunks
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
        store.add_texts(texts, metadatas)

        db = SessionLocal()
        try:
            db.add(
                Document(
                    id=document_id,
                    filename=filename,
                    page_count=len(pages),
                    chunk_count=len(chunks),
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
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error processing PDF")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {exc}") from exc


@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    store = get_vector_store()
    if not store.is_ready:
        raise HTTPException(status_code=503, detail="Vector store not available")

    start = time.time()
    try:
        docs = store.similarity_search(
            request.question,
            k=request.k or 4,
            document_id=request.document_id,
        )
        answer = generate_answer(request.question, docs, settings)
        latency_ms = (time.time() - start) * 1000

        sources = [
            SourceInfo(
                page=doc.metadata.get("page", "Unknown"),
                source=doc.metadata.get("source", "Unknown"),
                document_id=doc.metadata.get("document_id"),
            )
            for doc in docs
            if hasattr(doc, "metadata")
        ]

        db = SessionLocal()
        try:
            db.add(
                Query(
                    id=str(uuid.uuid4()),
                    document_id=request.document_id,
                    question=request.question,
                    answer=answer,
                    latency_ms=latency_ms,
                    created_at=datetime.utcnow(),
                )
            )
            db.commit()
        finally:
            db.close()

        return AskResponse(answer=answer, latency_ms=latency_ms, sources=sources)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error processing question")
        raise HTTPException(
            status_code=500, detail=f"Error processing question: {exc}"
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
