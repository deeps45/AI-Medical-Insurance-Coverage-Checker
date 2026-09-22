"""Shared pytest fixtures."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import fitz
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

os.environ["USE_LOCAL_VECTORSTORE"] = "true"
os.environ["QA_MODE"] = "extractive"
os.environ["ENABLE_AUTH"] = "false"
os.environ["DATABASE_URL"] = "sqlite:///./pytest_coverage.db"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("PINECONE_API_KEY", None)
os.environ.pop("TAMUS_AI_CHAT_API_KEY", None)
os.environ.pop("APP_API_KEY", None)


@pytest.fixture()
def sample_policy_text() -> str:
    return (
        "MEDICAL INSURANCE POLICY\n"
        "Policy Number: TEST-12345\n"
        "Effective Date: January 1, 2024\n\n"
        "COVERAGE SUMMARY:\n"
        "- MRI Coverage: Covered with $50 copay after deductible\n"
        "- Emergency Room: $100 copay\n"
        "- Specialist Visits: $30 copay\n"
        "- Annual Deductible: $1,000\n"
        "- Out-of-Pocket Maximum: $5,000\n\n"
        "PRESCRIPTION DRUGS:\n"
        "- Generic: $10 copay\n"
        "- Brand Name: $25 copay\n"
        "- Specialty: $50 copay\n\n"
        "MENTAL HEALTH SERVICES:\n"
        "- Covered with $20 copay per session\n"
        "- 20 sessions per year\n\n"
        "PHYSICAL THERAPY:\n"
        "- Covered with $25 copay per session\n"
        "- 30 sessions per year\n"
    )


@pytest.fixture()
def sample_pdf_bytes(sample_policy_text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), sample_policy_text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


@pytest.fixture()
def multipage_ocr_pdf_bytes() -> bytes:
    """Page 1 text, page 2 blank, page 3 image-only (OCR path)."""
    from PIL import Image, ImageDraw

    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text((50, 72), "Page 1 text layer.\nAnnual Deductible: $1,000", fontsize=12)

    doc.new_page()  # blank page 2

    img = Image.new("RGB", (900, 300), "white")
    draw = ImageDraw.Draw(img)
    draw.text(
        (40, 80),
        "Emergency Room: $100 copay\nMRI Coverage: Covered with $50 copay",
        fill="black",
    )
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    p3 = doc.new_page(width=612, height=792)
    p3.insert_image(p3.rect, stream=img_buf.getvalue())

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("USE_LOCAL_VECTORSTORE", "true")
    monkeypatch.setenv("QA_MODE", "extractive")
    monkeypatch.setenv("ENABLE_AUTH", "false")
    monkeypatch.setenv("FAISS_DIR", str(tmp_path / "faiss"))
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.delenv("TAMUS_AI_CHAT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("APP_API_KEY", raising=False)

    import importlib

    import config
    import db

    importlib.reload(config)
    importlib.reload(db)

    from services.vector_store import VectorStoreService, reset_vector_store

    reset_vector_store(VectorStoreService(settings=config.get_settings()))

    import app as app_module

    importlib.reload(app_module)
    app_module.settings = config.get_settings()
    db.init_db()

    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as test_client:
        yield test_client
