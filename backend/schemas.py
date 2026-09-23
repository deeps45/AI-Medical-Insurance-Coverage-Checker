"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    k: Optional[int] = Field(default=4, ge=1, le=20)
    document_id: Optional[str] = None
    stream: bool = False


class SourceInfo(BaseModel):
    page: int | str
    source: str
    document_id: Optional[str] = None
    score: Optional[float] = None
    snippet: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    latency_ms: float
    sources: list[SourceInfo]


class IngestResponse(BaseModel):
    document_id: str
    pages: int
    chunks: int
    filename: str
    replaced: bool = False


class DocumentInfo(BaseModel):
    id: str
    filename: str
    page_count: int
    chunk_count: int
    status: str = "ready"
    uploaded_at: str


class QueryInfo(BaseModel):
    id: str
    document_id: Optional[str]
    question: str
    answer: str
    sources: list[SourceInfo] = []
    latency_ms: float
    created_at: str


class HealthResponse(BaseModel):
    status: str
    vectorstore: str
    database: str
    llm_provider: str
    chat_model: str
    message: str
    auth_enabled: bool = False


class SummaryRequest(BaseModel):
    document_id: str
    k: Optional[int] = Field(default=8, ge=1, le=20)


class SummaryResponse(BaseModel):
    summary: str
    fields: dict[str, Any]
    sources: list[SourceInfo]
    latency_ms: float


class DeleteResponse(BaseModel):
    document_id: str
    deleted: bool
    message: str
