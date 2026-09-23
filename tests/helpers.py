"""Settings helper shared by unit tests."""

from __future__ import annotations

from pathlib import Path

from config import Settings


def make_settings(**overrides) -> Settings:
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
        api_key=None,
        rate_limit_per_minute=1000,
        faiss_dir=Path("./data/faiss"),
        enable_auth=False,
        max_upload_mb=20,
        document_ttl_hours=168,
        ingest_rate_limit_per_minute=1000,
    )
    base.update(overrides)
    return Settings(**base)
