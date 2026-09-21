"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    pinecone_api_key: str | None
    pinecone_index_name: str
    database_url: str
    tesseract_cmd: str
    embedding_model: str
    chat_model: str
    use_local_vectorstore: bool
    cors_origins: list[str]


def get_settings() -> Settings:
    cors = os.getenv("CORS_ORIGINS", "*")
    origins = [o.strip() for o in cors.split(",") if o.strip()]
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        pinecone_api_key=os.getenv("PINECONE_API_KEY"),
        pinecone_index_name=os.getenv("PINECONE_INDEX_NAME", "docsage-lite"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./test.db"),
        tesseract_cmd=os.getenv("TESSERACT_CMD", "/usr/bin/tesseract"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        chat_model=os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        use_local_vectorstore=os.getenv("USE_LOCAL_VECTORSTORE", "false").lower()
        in {"1", "true", "yes"},
        cors_origins=origins,
    )
