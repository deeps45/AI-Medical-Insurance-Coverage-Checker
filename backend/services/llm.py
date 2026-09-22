"""Shared LLM client helpers (TAMU Chat API or OpenAI)."""

from __future__ import annotations

from openai import OpenAI

from config import Settings, get_settings


def resolve_provider(settings: Settings | None = None) -> str:
    """Return 'tamu', 'openai', or 'none'."""
    settings = settings or get_settings()
    if settings.qa_mode == "extractive":
        return "none"
    if settings.tamus_api_key:
        return "tamu"
    if settings.openai_api_key:
        return "openai"
    return "none"


def has_llm_credentials(settings: Settings | None = None) -> bool:
    return resolve_provider(settings) in {"tamu", "openai"}


def get_openai_compatible_client(settings: Settings | None = None) -> OpenAI:
    """
    Build an OpenAI SDK client pointed at TAMU Chat API or OpenAI.

    TAMU is OpenAI-compatible at {endpoint}/api (chat + embeddings).
    """
    settings = settings or get_settings()
    provider = resolve_provider(settings)
    if provider == "tamu":
        base = settings.tamus_api_endpoint.rstrip("/")
        return OpenAI(api_key=settings.tamus_api_key, base_url=f"{base}/api")
    if provider == "openai":
        return OpenAI(api_key=settings.openai_api_key)
    raise RuntimeError("No LLM credentials configured (set TAMUS_AI_CHAT_API_KEY or OPENAI_API_KEY)")


def chat_completion(
    messages: list[dict],
    settings: Settings | None = None,
    *,
    temperature: float = 0.2,
    max_tokens: int = 600,
) -> str:
    settings = settings or get_settings()
    client = get_openai_compatible_client(settings)
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    return response.choices[0].message.content.strip()


def stream_chat_completion(
    messages: list[dict],
    settings: Settings | None = None,
    *,
    temperature: float = 0.2,
    max_tokens: int = 600,
):
    """Yield text deltas from a streaming chat completion."""
    settings = settings or get_settings()
    client = get_openai_compatible_client(settings)
    stream = client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content
        except (AttributeError, IndexError):
            delta = None
        if delta:
            yield delta
