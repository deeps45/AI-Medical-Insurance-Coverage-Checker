"""PDF text extraction with OCR fallback and section-aware chunking."""

from __future__ import annotations

import io
import logging
import os
import re
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


def _normalize_policy_text(text: str) -> str:
    """Normalize bullets/dashes so section splits are consistent."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("·", "-").replace("•", "-")
    # Ensure section headers sit on their own lines when jammed together
    text = re.sub(r"([a-z0-9\)])\s*([A-Z][A-Z][A-Z][A-Z]+)", r"\1\n\2", text)
    return text


def _is_section_header(line: str) -> bool:
    # ALL-CAPS benefit headers; allow digits, &, /, -, and parentheses
    return bool(re.match(r"^[A-Z][A-Z0-9 /&\-()]{3,}$", line)) and not line.startswith("-")


def _split_into_sections(text: str) -> list[str]:
    """
    Prefer one benefit fact per chunk.

    ALL-CAPS headers are repeated as a prefix on each bullet so retrieval can
    match "Emergency Room" without drowning it in deductible lines.
    """
    text = _normalize_policy_text(text)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    sections: list[str] = []
    header: str | None = None
    prose: list[str] = []

    def flush_prose() -> None:
        nonlocal prose
        if prose:
            sections.append("\n".join(prose))
            prose = []

    for line in lines:
        is_header = _is_section_header(line)
        is_bullet = line.startswith("-") or bool(re.match(r"^\d+[\.\)]\s", line))
        if is_header:
            flush_prose()
            header = line
            continue
        if is_bullet:
            flush_prose()
            if header:
                sections.append(f"{header}\n{line}")
            else:
                sections.append(line)
            continue
        # Non-bullet prose (title lines, etc.)
        if header and not prose:
            # Detach from prior benefit header once narrative resumes
            header = None
        prose.append(line)
        if len("\n".join(prose)) >= 420:
            flush_prose()
    flush_prose()
    return sections or [text]

def _section_name(section: str) -> str:
    first = section.split("\n", 1)[0].strip()
    if _is_section_header(first):
        return first
    return "GENERAL"


def chunk_pages(
    pages: list[PageText],
    chunk_size: int = 450,
    chunk_overlap: int = 60,
) -> list[tuple[str, int, str]]:
    """
    Split page texts into smaller, section-aware chunks.

    Returns list of (chunk_text, page_number, section) triples.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n- ", "\n", ". ", " ", ""],
    )

    results: list[tuple[str, int, str]] = []
    for page in pages:
        for section in _split_into_sections(page.text):
            section_name = _section_name(section)
            labeled = f"[Page {page.page_number}]\n{section}"
            if len(labeled) <= chunk_size:
                results.append((labeled, page.page_number, section_name))
                continue
            for chunk in splitter.split_text(labeled):
                if not chunk.startswith("[Page "):
                    chunk = f"[Page {page.page_number}]\n{chunk}"
                results.append((chunk, page.page_number, section_name))
    return results
