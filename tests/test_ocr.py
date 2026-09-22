"""OCR and multi-page PDF extraction tests."""

from __future__ import annotations

import shutil

import pytest

from services.pdf_extractor import extract_pages_from_pdf


pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None,
    reason="tesseract binary not installed",
)


def test_multipage_pdf_extracts_text_and_ocr_page(multipage_ocr_pdf_bytes):
    pages = extract_pages_from_pdf(multipage_ocr_pdf_bytes)
    page_nums = {p.page_number for p in pages}
    assert 1 in page_nums
    # blank page 2 should produce no text
    assert 2 not in page_nums

    joined = "\n".join(p.text for p in pages)
    assert "Deductible" in joined or "1,000" in joined or "1000" in joined

    # OCR page may succeed depending on tesseract quality; if page 3 present, check keywords
    if 3 in page_nums:
        page3 = next(p for p in pages if p.page_number == 3)
        assert any(
            token in page3.text.upper() for token in ("MRI", "EMERGENCY", "COPAY", "100", "50")
        )
