"""Hybrid retrieval helpers: keyword boost + query expansion."""

from __future__ import annotations

import re
from typing import Any, Iterable

# Expand common insurance abbreviations so keyword matching hits policy wording.
QUERY_SYNONYMS: dict[str, list[str]] = {
    "er": ["emergency room", "emergency"],
    "ed": ["emergency room", "emergency department"],
    "oop": ["out-of-pocket", "out of pocket", "out-of-pocket maximum"],
    "mri": ["mri", "imaging", "magnetic resonance"],
    "pcp": ["primary care", "primary care physician", "primary care visit"],
    "rx": ["prescription", "pharmacy", "drug"],
    "pt": ["physical therapy"],
    "deductible": ["deductible", "annual deductible"],
    "copay": ["copay", "co-pay", "copayment"],
}


def expand_query(query: str) -> str:
    """Append synonym phrases for known insurance shorthand."""
    lowered = query.lower()
    extras: list[str] = []
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    for key, values in QUERY_SYNONYMS.items():
        # Short keys (er/ed/pt) must be whole tokens — never substrings of
        # words like "covered" / "needed" / "department".
        if key in tokens:
            extras.extend(values)
        elif len(key) > 3 and re.search(rf"\b{re.escape(key)}\b", lowered):
            extras.extend(values)
    if not extras:
        return query
    # Keep original query first for embeddings; synonyms help keyword scoring.
    return query + " " + " ".join(dict.fromkeys(extras))

def tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9$]+", text.lower()) if len(t) > 1}


def keyword_score(query: str, text: str) -> float:
    """
    Lightweight lexical score favoring exact benefit phrases and dollar amounts.
    """
    q = query.lower()
    t = text.lower()
    q_tokens = tokenize(query)
    t_tokens = tokenize(text)
    if not q_tokens:
        return 0.0

    overlap = len(q_tokens & t_tokens) / max(len(q_tokens), 1)

    phrase_bonus = 0.0
    phrases = [
        "emergency room",
        "out-of-pocket",
        "out of pocket",
        "annual deductible",
        "primary care",
        "physical therapy",
        "prior authorization",
        "prescription",
    ]
    for phrase in phrases:
        if phrase in q and phrase in t:
            phrase_bonus += 0.35

    # Exact short benefit terms
    for term in ("mri", "ct", "er", "copay", "deductible"):
        if term in q_tokens and term in t_tokens:
            phrase_bonus += 0.15

    # Shared dollar amounts ($250, 1500, etc.)
    q_money = set(re.findall(r"\$?\d[\d,]*(?:\.\d+)?", q))
    t_money = set(re.findall(r"\$?\d[\d,]*(?:\.\d+)?", t))
    money_bonus = 0.25 * len(q_money & t_money)

    return overlap + phrase_bonus + money_bonus


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[Any]],
    *,
    k: int = 60,
    id_fn=None,
) -> list[Any]:
    """
    Merge ranked doc lists with RRF. `id_fn` extracts a stable id from each doc.
    """
    id_fn = id_fn or (lambda d: id(d))
    scores: dict[Any, float] = {}
    reps: dict[Any, Any] = {}
    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked):
            key = id_fn(doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            reps[key] = doc
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    fused = []
    for key, score in ordered:
        doc = reps[key]
        meta = dict(getattr(doc, "metadata", {}) or {})
        meta["hybrid_score"] = round(float(score), 4)
        # Prefer hybrid_score as displayed score when present
        meta["score"] = meta.get("score") or meta["hybrid_score"]
        doc.metadata = meta
        fused.append(doc)
    return fused
