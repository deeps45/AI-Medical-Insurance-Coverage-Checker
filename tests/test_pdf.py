"""Unit tests for PDF extraction and chunking."""

from __future__ import annotations

from services.pdf_extractor import PageText, chunk_pages, extract_pages_from_pdf


def test_extract_pages_from_pdf(sample_pdf_bytes):
    pages = extract_pages_from_pdf(sample_pdf_bytes)
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "MRI" in pages[0].text
    assert "deductible" in pages[0].text.lower()


def test_chunk_pages_preserves_page_numbers(sample_policy_text):
    pages = [
        PageText(page_number=1, text=sample_policy_text),
        PageText(page_number=2, text="Secondary page about dental exclusions only."),
    ]
    chunks = chunk_pages(pages, chunk_size=200, chunk_overlap=40)
    assert chunks
    assert all(isinstance(page, int) and page >= 1 for _, page, _ in chunks)
    page_nums = {page for _, page, _ in chunks}
    assert 1 in page_nums
    assert 2 in page_nums
    assert any(section for _, _, section in chunks)


def test_empty_pdf_returns_no_pages():
    import fitz
    import io

    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    pages = extract_pages_from_pdf(buf.getvalue())
    assert pages == []
