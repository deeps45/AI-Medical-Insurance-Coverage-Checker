"""Tests for section-aware chunking and hybrid retrieval helpers."""

from __future__ import annotations

from services.pdf_extractor import PageText, chunk_pages
from services.retrieval import expand_query, keyword_score


def test_chunk_pages_keeps_er_line_together():
    text = (
        "NETWORK BENEFITS\n"
        "- Annual Deductible (Individual): $1,500\n"
        "- Emergency Room: $250 copay (waived if admitted)\n"
        "- MRI / CT Imaging: Covered with $100 copay after deductible\n"
        "MENTAL HEALTH\n"
        "- Outpatient therapy: $30 copay per session\n"
    )
    chunks = chunk_pages([PageText(page_number=1, text=text)], chunk_size=450, chunk_overlap=40)
    assert chunks
    er_chunks = [c for c, _, _ in chunks if "Emergency Room" in c and "$250" in c]
    assert er_chunks, f"ER line should stay intact; got: {chunks}"
    best = max(er_chunks, key=lambda c: ("Emergency Room" in c) + ("$250" in c))
    assert "Emergency Room: $250" in best
    # Benefit bullets should not share a chunk with unrelated lines
    assert "Annual Deductible" not in best
    assert "MENTAL HEALTH" not in best
    assert any("MRI" in c and "Annual Deductible" not in c for c, _, _ in chunks)
    assert any(sec == "NETWORK BENEFITS" for _, _, sec in chunks)


def test_expand_query_er_synonyms():
    expanded = expand_query("What is the ER copay?").lower()
    assert "emergency room" in expanded


def test_expand_query_ignores_er_substring_in_covered():
    expanded = expand_query("Is MRI covered and what is the copay?").lower()
    assert "emergency room" not in expanded
    assert "mri" in expanded or "imaging" in expanded


def test_keyword_score_prefers_er_line():
    query = "What is the ER copay? emergency room"
    er = "Emergency Room: $250 copay (waived if admitted)"
    mental = "MENTAL HEALTH - Outpatient therapy: $30 copay per session"
    assert keyword_score(query, er) > keyword_score(query, mental)
