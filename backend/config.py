"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    tamus_api_key: str | None
    tamus_api_endpoint: str
    pinecone_api_key: str | None
    pinecone_index_name: str
    database_url: str
    tesseract_cmd: str
    embedding_model: str
    chat_model: str
    use_local_vectorstore: bool
    qa_mode: str
    cors_origins: list[str]
    api_key: str | None
    rate_limit_per_minute: int
    faiss_dir: Path
    enable_auth: bool


def get_settings() -> Settings:
    cors = os.getenv("CORS_ORIGINS", "*")
    origins = [o.strip() for o in cors.split(",") if o.strip()]

    tamus_key = os.getenv("TAMUS_AI_CHAT_API_KEY") or None
    openai_key = os.getenv("OPENAI_API_KEY") or None
    api_key = os.getenv("APP_API_KEY") or None

    if tamus_key:
        default_chat = "protected.gemini-2.5-flash-lite"
        default_embed = "protected.text-embedding-3-small"
    else:
        default_chat = "gpt-4o-mini"
        default_embed = "text-embedding-3-small"

    faiss_dir = Path(os.getenv("FAISS_DIR", "./data/faiss")).resolve()

    return Settings(
        openai_api_key=openai_key,
        tamus_api_key=tamus_key,
        tamus_api_endpoint=os.getenv(
            "TAMUS_AI_CHAT_API_ENDPOINT", "https://chat-api.tamu.ai"
        ),
        pinecone_api_key=os.getenv("PINECONE_API_KEY") or None,
        pinecone_index_name=os.getenv("PINECONE_INDEX_NAME", "docsage-lite"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./test.db"),
        tesseract_cmd=os.getenv("TESSERACT_CMD", "/usr/bin/tesseract"),
        embedding_model=os.getenv("EMBEDDING_MODEL", default_embed),
        chat_model=os.getenv("CHAT_MODEL", default_chat),
        use_local_vectorstore=os.getenv("USE_LOCAL_VECTORSTORE", "true").lower()
        in {"1", "true", "yes"},
        qa_mode=os.getenv("QA_MODE", "").lower(),
        cors_origins=origins,
        api_key=api_key,
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
        faiss_dir=faiss_dir,
        enable_auth=os.getenv("ENABLE_AUTH", "false").lower() in {"1", "true", "yes"},
    )
