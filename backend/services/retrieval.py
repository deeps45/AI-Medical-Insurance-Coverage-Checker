"""Hybrid retrieval helpers: keyword boost + query expansion + section hints."""

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
    "exclusion": ["exclusion", "not covered", "exclusions"],
}

# Query cues → preferred policy section name substrings (uppercase)
SECTION_HINTS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("emergency", "er "), ("EMERGENCY", "NETWORK", "COST")),
    (("mri", "imaging", "x-ray", "ct ", "diagnostic"), ("DIAGNOSTIC", "NETWORK", "IMAGING")),
    (("deductible",), ("COST", "NETWORK", "DEDUCTIBLE")),
    (("out-of-pocket", "oop", "maximum"), ("COST", "NETWORK", "OUT-OF-POCKET")),
    (("prescription", "pharmacy", "rx", "drug"), ("PRESCRIPTION", "PHARMACY", "DRUG")),
    (("physical therapy", "pt "), ("PHYSICAL THERAPY", "REHAB")),
    (("mental", "therapy session"), ("MENTAL", "BEHAVIORAL")),
    (("not covered", "exclusion", "excluded", "cosmetic"), ("EXCLUSION", "NOT COVERED")),
    (("primary care", "pcp"), ("COST", "NETWORK", "PRIMARY")),
    (("specialist",), ("COST", "NETWORK", "SPECIALIST")),
]


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


def section_boost(query: str, section: str | None, text: str = "") -> float:
    """Small bonus when chunk section matches the question topic."""
    if not section and not text:
        return 0.0
    hay = f"{section or ''} {text[:80]}".upper()
    q = query.lower()
    bonus = 0.0
    for cues, needles in SECTION_HINTS:
        if any(cue in q for cue in cues):
            if any(n in hay for n in needles):
                bonus += 0.2
                break
    return bonus


def keyword_score(query: str, text: str, *, section: str | None = None) -> float:
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
        "not covered",
    ]
    for phrase in phrases:
        if phrase in q and phrase in t:
            phrase_bonus += 0.35

    # Exact short benefit terms
    for term in ("mri", "ct", "er", "copay", "deductible", "exclusion"):
        if term in q_tokens and term in t_tokens:
            phrase_bonus += 0.15

    # Negation / exclusion cues
    if any(x in q for x in ("not covered", "exclu", "cosmetic")) and any(
        x in t for x in ("not covered", "exclusion", "cosmetic", "experimental")
    ):
        phrase_bonus += 0.4

    # Shared dollar amounts ($250, 1500, etc.)
    q_money = set(re.findall(r"\$?\d[\d,]*(?:\.\d+)?", q))
    t_money = set(re.findall(r"\$?\d[\d,]*(?:\.\d+)?", t))
    money_bonus = 0.25 * len(q_money & t_money)

    return overlap + phrase_bonus + money_bonus + section_boost(query, section, text)


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
        meta["score"] = meta.get("score") or meta["hybrid_score"]
        doc.metadata = meta
        fused.append(doc)
    return fused


def weighted_hybrid_fuse(
    vector_docs: list[Any],
    keyword_ranked: list[Any],
    *,
    id_fn=None,
    keyword_weight: float = 0.55,
    vector_weight: float = 0.45,
) -> list[Any]:
    """
    Fuse vector + keyword rankings. When keyword evidence is strong, lean on it
    so benefit-line matches beat generic vector neighbors.
    """
    id_fn = id_fn or (lambda d: id(d))
    vec_rank = {id_fn(d): i for i, d in enumerate(vector_docs)}
    kw_rank = {id_fn(d): i for i, d in enumerate(keyword_ranked)}
    reps: dict[Any, Any] = {}
    for d in vector_docs:
        reps[id_fn(d)] = d
    for d in keyword_ranked:
        reps[id_fn(d)] = d

    scores: dict[Any, float] = {}
    for key, doc in reps.items():
        vr = vec_rank.get(key)
        kr = kw_rank.get(key)
        v_score = 1.0 / (60 + vr + 1) if vr is not None else 0.0
        k_score = 1.0 / (60 + kr + 1) if kr is not None else 0.0
        meta = getattr(doc, "metadata", {}) or {}
        kw_raw = float(meta.get("keyword_score") or 0.0)
        # Strong lexical hits get extra weight
        kw_w = keyword_weight + (0.15 if kw_raw >= 0.5 else 0.0)
        vec_w = vector_weight
        total_w = kw_w + vec_w
        scores[key] = (kw_w * k_score + vec_w * v_score) / total_w

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    fused = []
    for key, score in ordered:
        doc = reps[key]
        meta = dict(getattr(doc, "metadata", {}) or {})
        meta["hybrid_score"] = round(float(score), 4)
        meta["score"] = meta["hybrid_score"]
        doc.metadata = meta
        fused.append(doc)
    return fused
