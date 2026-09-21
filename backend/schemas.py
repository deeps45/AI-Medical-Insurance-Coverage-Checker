"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    k: Optional[int] = Field(default=4, ge=1, le=20)
    document_id: Optional[str] = None


class SourceInfo(BaseModel):
    page: int | str
    source: str
    document_id: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    latency_ms: float
    sources: list[SourceInfo]


class IngestResponse(BaseModel):
    document_id: str
    pages: int
    chunks: int
    filename: str


class DocumentInfo(BaseModel):
    id: str
    filename: str
    page_count: int
    chunk_count: int
    uploaded_at: str


class HealthResponse(BaseModel):
    status: str
    vectorstore: str
    database: str
    message: str
