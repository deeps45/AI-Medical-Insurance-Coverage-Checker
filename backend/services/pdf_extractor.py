"""PDF text extraction with OCR fallback."""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass

import fitz
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class PageText:
    page_number: int  # 1-indexed
    text: str


def extract_text_from_page(page: fitz.Page, page_num: int, tesseract_cmd: str) -> str:
    """Extract text from a PDF page, with Tesseract OCR fallback if needed."""
    text = page.get_text("text").strip()
    if text:
        return text

    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        ocr_text = pytesseract.image_to_string(img).strip()
        if ocr_text:
            logger.info("Used Tesseract OCR fallback for page %s", page_num + 1)
            return ocr_text
    except Exception as exc:  # noqa: BLE001 - OCR is best-effort
        logger.warning("Tesseract fallback failed for page %s: %s", page_num + 1, exc)

    return ""


def extract_pages_from_pdf(content: bytes, tesseract_cmd: str | None = None) -> list[PageText]:
    """Extract text from every page of a PDF."""
    cmd = tesseract_cmd or os.getenv("TESSERACT_CMD", "/usr/bin/tesseract")
    doc = fitz.open(stream=content, filetype="pdf")
    pages: list[PageText] = []
    try:
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = extract_text_from_page(page, page_num, cmd)
            if text:
                pages.append(PageText(page_number=page_num + 1, text=text))
    finally:
        doc.close()
    return pages


def chunk_pages(
    pages: list[PageText],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[tuple[str, int]]:
    """
    Split page texts into overlapping chunks.

    Returns list of (chunk_text, page_number) pairs with accurate page metadata.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )

    results: list[tuple[str, int]] = []
    for page in pages:
        # Prefix helps the LLM cite pages even when metadata is lost
        labeled = f"[Page {page.page_number}]\n{page.text}"
        for chunk in splitter.split_text(labeled):
            results.append((chunk, page.page_number))
    return results
