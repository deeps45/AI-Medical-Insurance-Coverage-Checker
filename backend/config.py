"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

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


def get_settings() -> Settings:
    cors = os.getenv("CORS_ORIGINS", "*")
    origins = [o.strip() for o in cors.split(",") if o.strip()]

    tamus_key = os.getenv("TAMUS_AI_CHAT_API_KEY") or None
    openai_key = os.getenv("OPENAI_API_KEY") or None

    # Sensible defaults: TAMU models when TAMU key is present
    if tamus_key:
        default_chat = "protected.gemini-2.5-flash-lite"
        default_embed = "protected.text-embedding-3-small"
    else:
        default_chat = "gpt-4o-mini"
        default_embed = "text-embedding-3-small"

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
    )
