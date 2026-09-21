"""Shared pytest fixtures."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import fitz
import pytest

# Ensure backend package root is importable
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Force offline-friendly settings before app import
os.environ["USE_LOCAL_VECTORSTORE"] = "true"
os.environ["QA_MODE"] = "extractive"
os.environ["DATABASE_URL"] = "sqlite:///./pytest_coverage.db"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("PINECONE_API_KEY", None)


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
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("USE_LOCAL_VECTORSTORE", "true")
    monkeypatch.setenv("QA_MODE", "extractive")

    # Re-import / reset modules that cache settings
    import importlib

    import config
    import db
    import services.vector_store as vs

    importlib.reload(config)
    importlib.reload(db)

    from services.vector_store import VectorStoreService, reset_vector_store

    reset_vector_store(
        VectorStoreService(
            settings=config.get_settings(),
        )
    )

    import app as app_module

    importlib.reload(app_module)
    db.init_db()

    from fastapi.testclient import TestClient

    with TestClient(app_module.app) as test_client:
        yield test_client
