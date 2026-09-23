"""SQLAlchemy database setup and models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    page_count = Column(Integer, nullable=False)
    chunk_count = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="ready")  # ready|processing|error
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Query(Base):
    __tablename__ = "queries"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sources_json = Column(Text, nullable=True)  # JSON list of sources
    latency_ms = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Best-effort additive migrations for existing DBs."""
    alters = []
    if DATABASE_URL.startswith("sqlite"):
        alters = [
            "ALTER TABLE documents ADD COLUMN status VARCHAR DEFAULT 'ready'",
            "ALTER TABLE queries ADD COLUMN sources_json TEXT",
        ]
    elif "postgresql" in DATABASE_URL:
        alters = [
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'ready'",
            "ALTER TABLE queries ADD COLUMN IF NOT EXISTS sources_json TEXT",
        ]

    if not alters:
        return

    with engine.begin() as conn:
        for stmt in alters:
            try:
                conn.execute(text(stmt))
            except Exception:  # noqa: BLE001 - column may already exist on sqlite
                pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
