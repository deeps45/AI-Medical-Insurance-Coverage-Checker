"""Unit tests for LLM provider resolution."""

from __future__ import annotations

from config import Settings
from services.llm import resolve_provider


def _settings(**overrides) -> Settings:
    base = dict(
        openai_api_key=None,
        tamus_api_key=None,
        tamus_api_endpoint="https://chat-api.tamu.ai",
        pinecone_api_key=None,
        pinecone_index_name="test",
        database_url="sqlite:///./x.db",
        tesseract_cmd="/usr/bin/tesseract",
        embedding_model="protected.text-embedding-3-small",
        chat_model="protected.gemini-2.5-flash-lite",
        use_local_vectorstore=True,
        qa_mode="",
        cors_origins=["*"],
    )
    base.update(overrides)
    return Settings(**base)


def test_prefer_tamu_when_key_present():
    assert resolve_provider(_settings(tamus_api_key="sk-test")) == "tamu"


def test_openai_fallback():
    assert resolve_provider(_settings(openai_api_key="sk-openai")) == "openai"


def test_extractive_mode_disables_llm():
    assert (
        resolve_provider(_settings(tamus_api_key="sk-test", qa_mode="extractive"))
        == "none"
    )


def test_no_keys():
    assert resolve_provider(_settings()) == "none"
