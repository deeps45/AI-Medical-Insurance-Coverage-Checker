"""Question-answering over retrieved policy context."""

from __future__ import annotations

import logging
import os
from typing import Any

from config import Settings, get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a careful medical insurance coverage assistant.
Answer ONLY using the provided policy context.
Cite page numbers like [p3] when evidence supports the answer.
If the context is insufficient, say you don't know and suggest what to look for in the policy.
Do not invent coverage amounts, copays, or exclusions.
Be concise and clear."""


def build_prompt(question: str, context: str) -> str:
    return f"""{SYSTEM_PROMPT}

Context:
{context}

Question: {question}

Answer:"""


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

    prompt = build_prompt(question, context)

    # Offline / test mode: return a deterministic extractive answer
    if os.getenv("QA_MODE", "").lower() == "extractive" or not settings.openai_api_key:
        return _extractive_answer(question, docs)

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


def _extractive_answer(question: str, docs: list[Any]) -> str:
    """Fallback answer builder for tests without calling OpenAI."""
    snippets = []
    for doc in docs[:3]:
        page = doc.metadata.get("page", "?")
        snippets.append(f"[p{page}] {doc.page_content[:400]}")
    joined = "\n\n".join(snippets)
    return (
        f"Based on the policy text related to '{question}':\n\n{joined}\n\n"
        "(Extractive mode — set OPENAI_API_KEY for full AI answers.)"
    )
