"""Unit tests for LLM provider resolution."""

from __future__ import annotations

from services.llm import resolve_provider
from helpers import make_settings


def test_prefer_tamu_when_key_present():
    assert resolve_provider(make_settings(tamus_api_key="sk-test", qa_mode="")) == "tamu"


def test_openai_fallback():
    assert resolve_provider(make_settings(openai_api_key="sk-openai", qa_mode="")) == "openai"


def test_extractive_mode_disables_llm():
    assert (
        resolve_provider(make_settings(tamus_api_key="sk-test", qa_mode="extractive"))
        == "none"
    )


def test_no_keys():
    assert resolve_provider(make_settings(qa_mode="")) == "none"
