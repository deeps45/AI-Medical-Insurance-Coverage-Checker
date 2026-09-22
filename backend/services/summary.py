"""Coverage summary extraction from retrieved policy chunks."""

from __future__ import annotations

import re
from typing import Any

from config import Settings, get_settings
from services.llm import chat_completion, resolve_provider
from services.qa import build_messages, dedupe_sources

SUMMARY_FIELDS = [
    ("annual_deductible", "annual deductible"),
    ("out_of_pocket_maximum", "out-of-pocket maximum / OOP max"),
    ("emergency_room_copay", "emergency room / ER copay"),
    ("mri_coverage", "MRI coverage and copay"),
    ("specialist_copay", "specialist visit copay"),
    ("prescription_drugs", "prescription drug coverage / copays"),
]


def _regex_scan(text: str) -> dict[str, str | None]:
    patterns = {
        "annual_deductible": r"(?:annual\s+)?deductible[:\s]+\$?\s*([\d,]+)",
        "out_of_pocket_maximum": r"out[- ]of[- ]pocket(?:\s+maximum)?[:\s]+\$?\s*([\d,]+)",
        "emergency_room_copay": r"emergency\s+room[:\s]+\$?\s*([\d,]+)\s*copay",
        "mri_coverage": r"MRI[^.\n]{0,80}",
        "specialist_copay": r"specialist[^.\n]{0,60}\$?\s*([\d,]+)",
        "prescription_drugs": r"(?:prescription|generic|brand name)[^.\n]{0,80}",
    }
    found: dict[str, str | None] = {k: None for k in patterns}
    lower = text
    for key, pat in patterns.items():
        m = re.search(pat, lower, flags=re.IGNORECASE)
        if m:
            found[key] = m.group(0).strip()
    return found


def build_coverage_summary(
    docs: list[Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    context = "\n\n".join(doc.page_content for doc in docs) if docs else ""
    heuristic = _regex_scan(context)

    narrative = ""
    provider = resolve_provider(settings)
    if provider != "none" and context.strip():
        field_list = "; ".join(label for _, label in SUMMARY_FIELDS)
        question = (
            f"Extract a concise coverage summary covering: {field_list}. "
            "Use bullet points. Cite pages like [p3]. Say unknown if missing."
        )
        narrative = chat_completion(
            build_messages(question, context),
            settings,
            temperature=0.1,
            max_tokens=700,
        )
    elif context.strip():
        lines = ["Coverage snapshot (extractive):"]
        for key, label in SUMMARY_FIELDS:
            val = heuristic.get(key)
            lines.append(f"- {label}: {val or 'not found in retrieved text'}")
        narrative = "\n".join(lines)

    return {
        "summary": narrative,
        "fields": heuristic,
        "sources": dedupe_sources(docs),
    }
