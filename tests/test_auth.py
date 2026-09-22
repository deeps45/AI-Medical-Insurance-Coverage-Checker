"""Auth and rate-limit behavior."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def test_auth_required_when_enabled(tmp_path, monkeypatch, sample_pdf_bytes):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("USE_LOCAL_VECTORSTORE", "true")
    monkeypatch.setenv("QA_MODE", "extractive")
    monkeypatch.setenv("ENABLE_AUTH", "true")
    monkeypatch.setenv("APP_API_KEY", "secret-test-key")
    monkeypatch.setenv("FAISS_DIR", str(tmp_path / "faiss"))
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.delenv("TAMUS_AI_CHAT_API_KEY", raising=False)

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

    with TestClient(app_module.app) as client:
        assert client.get("/health").status_code == 200
        denied = client.get("/documents")
        assert denied.status_code == 401
        ok = client.get("/documents", headers={"X-API-Key": "secret-test-key"})
        assert ok.status_code == 200
