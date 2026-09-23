"""Document retention / TTL cleanup."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from config import Settings, get_settings
from db import Document, Query, SessionLocal

logger = logging.getLogger(__name__)


def cleanup_expired_documents(
    settings: Settings | None = None,
    *,
    vector_store: Any | None = None,
) -> dict[str, int]:
    """
    Delete documents (and related queries/vectors) older than DOCUMENT_TTL_HOURS.

    Returns counts of removed rows. No-op when TTL is 0 (disabled).
    """
    settings = settings or get_settings()
    if settings.document_ttl_hours <= 0:
        return {"documents": 0, "queries": 0, "skipped": 1}

    cutoff = datetime.utcnow() - timedelta(hours=settings.document_ttl_hours)
    removed_docs = 0
    removed_queries = 0

    db = SessionLocal()
    try:
        stale = db.query(Document).filter(Document.uploaded_at < cutoff).all()
        ids = [row.id for row in stale]
        if not ids:
            return {"documents": 0, "queries": 0, "skipped": 0}

        removed_queries = (
            db.query(Query).filter(Query.document_id.in_(ids)).delete(synchronize_session=False)
            or 0
        )
        for row in stale:
            db.delete(row)
            removed_docs += 1
        db.commit()
    finally:
        db.close()

    if vector_store is not None:
        for doc_id in ids:
            try:
                vector_store.delete_document(doc_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Vector cleanup failed for %s: %s", doc_id, exc)

    logger.info(
        "TTL cleanup removed %s documents / %s queries (older than %sh)",
        removed_docs,
        removed_queries,
        settings.document_ttl_hours,
    )
    return {"documents": removed_docs, "queries": int(removed_queries), "skipped": 0}
