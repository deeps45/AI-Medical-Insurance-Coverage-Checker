"""Question-answering over retrieved policy context."""

from __future__ import annotations

import logging
from typing import Any

from config import Settings, get_settings
from services.llm import chat_completion, resolve_provider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a careful medical insurance coverage assistant.
Answer ONLY using the provided policy context.
Cite page numbers like [p3] when evidence supports the answer.
If the context is insufficient, say you don't know and suggest what to look for in the policy.
Do not invent coverage amounts, copays, or exclusions.
Be concise and clear.
End with a one-line reminder that this is not official benefits advice."""


def build_prompt(question: str, context: str) -> str:
    """Legacy single-string prompt (used by extractive/tests)."""
    return f"""{SYSTEM_PROMPT}

Context:
{context}

Question: {question}

Answer:"""


def build_messages(question: str, context: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Policy context:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Answer using only the context above."
            ),
        },
    ]


def dedupe_sources(docs: list[Any]) -> list[dict[str, Any]]:
    """Unique (source, page, document_id) triples preserving retrieval order."""
    seen: set[tuple] = set()
    sources: list[dict[str, Any]] = []
    for doc in docs:
        if not hasattr(doc, "metadata"):
            continue
        meta = doc.metadata or {}
        key = (meta.get("source"), meta.get("page"), meta.get("document_id"))
        if key in seen:
            continue
        seen.add(key)
        snippet = (getattr(doc, "page_content", "") or "")[:180].replace("\n", " ")
        sources.append(
            {
                "page": meta.get("page", "Unknown"),
                "source": meta.get("source", "Unknown"),
                "document_id": meta.get("document_id"),
                "score": meta.get("score"),
                "snippet": snippet or None,
            }
        )
    return sources


def generate_answer(
    question: str,
    docs: list[Any],
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    context = "\n\n".join(doc.page_content for doc in docs) if docs else ""
    if not context.strip():
        return (
            "I couldn't find relevant information in the uploaded policy. "
            "Try rephrasing your question or uploading a clearer document."
        )

    provider = resolve_provider(settings)
    if provider == "none":
        return _extractive_answer(question, docs)

    return chat_completion(
        build_messages(question, context),
        settings,
        temperature=0.2,
        max_tokens=600,
    )


def _extractive_answer(question: str, docs: list[Any]) -> str:
    """Fallback answer builder for tests without calling an LLM API."""
    snippets = []
    for doc in docs[:3]:
        page = doc.metadata.get("page", "?")
        snippets.append(f"[p{page}] {doc.page_content[:400]}")
    joined = "\n\n".join(snippets)
    return (
        f"Based on the policy text related to '{question}':\n\n{joined}\n\n"
        "(Extractive mode — set TAMUS_AI_CHAT_API_KEY or OPENAI_API_KEY for full AI answers.)"
    )
