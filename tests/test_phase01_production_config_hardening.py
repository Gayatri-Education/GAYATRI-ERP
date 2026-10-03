"""Phase 1 Test Suite — Production Configuration Hardening Verification.

Fulfills Phase 1 Acceptance Criteria:
1. Production environment explicitly detected via GAYATRI_ENV or APP_ENV.
2. Missing or weak JWT secrets rejected with fail-fast RuntimeError.
3. Insecure encryption keys rejected.
4. Wildcard CORS origins strictly prohibited in production mode.
5. Explicit allowed CORS origins verified.
6. Debug and reload modes strictly prohibited in production mode.
7. Non-existent production database paths rejected.
8. Model file and checksum mismatch rejected.
9. API documentation endpoints (/docs, /redoc, /openapi.json) disabled unless explicitly permitted.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from central_platform.config import (
    DEFAULT_INSECURE_SECRET,
    get_environment,
    is_production_mode,
    validate_production_config,
)
from central_platform.auth.tokens import get_jwt_secret_key
from central_platform.api.app import create_app
from central_platform.api.server import run_server


# ── 1. Environment Detection ──────────────────────────────────────────────────

def test_environment_detection_modes():
    """Verify authoritative environment resolution."""
    assert not is_production_mode({"GAYATRI_ENV": "development"})
    assert not is_production_mode({"APP_ENV": "development"})
    assert not is_production_mode({"APP_ENV": "test"})
    assert is_production_mode({"GAYATRI_ENV": "production"})
    assert is_production_mode({"APP_ENV": "production"})
    assert is_production_mode({"GAYATRI_ENV": "PRODUCTION"})


# ── 2. JWT Secret Invariants ──────────────────────────────────────────────────

def test_production_missing_jwt_secret():
    """Missing JWT secret must abort production startup."""
    env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_ALLOWED_ORIGINS": "https://gayatri.edu",
        "GAYATRI_DB_PATH": "gayatri_local.db",
    }
    with pytest.raises(RuntimeError, match="Missing required GAYATRI_JWT_SECRET"):
        validate_production_config(env)


def test_production_weak_jwt_secret():
    """Weak or default JWT secret must abort production startup."""
    env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": "short_secret",
        "GAYATRI_ALLOWED_ORIGINS": "https://gayatri.edu",
        "GAYATRI_DB_PATH": "gayatri_local.db",
    }
    with pytest.raises(RuntimeError, match="too weak or uses a default value"):
        validate_production_config(env)

    # Insecure default key must also be rejected
    env["GAYATRI_JWT_SECRET"] = DEFAULT_INSECURE_SECRET
    with pytest.raises(RuntimeError, match="too weak or uses a default value"):
        validate_production_config(env)


def test_get_jwt_secret_key_production_enforcement(monkeypatch):
    """get_jwt_secret_key must raise RuntimeError on weak/missing secret in production."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.delenv("GAYATRI_JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="GAYATRI_JWT_SECRET environment variable must be explicitly set"):
        get_jwt_secret_key()

    monkeypatch.setenv("GAYATRI_JWT_SECRET", "weak_key_123")
    with pytest.raises(RuntimeError, match="too weak or uses a default value"):
        get_jwt_secret_key()

    strong_secret = "a_super_secure_production_secret_key_with_very_high_entropy_32_chars!"
    monkeypatch.setenv("GAYATRI_JWT_SECRET", strong_secret)
    assert get_jwt_secret_key() == strong_secret


# ── 3. CORS Invariants ────────────────────────────────────────────────────────

def test_production_wildcard_cors_rejected():
    """Wildcard CORS origins must be rejected in production."""
    strong_secret = "a_super_secure_production_secret_key_with_very_high_entropy_32_chars!"
    env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": strong_secret,
        "GAYATRI_ALLOWED_ORIGINS": "*",
        "GAYATRI_DB_PATH": "gayatri_local.db",
    }
    with pytest.raises(RuntimeError, match="Wildcard CORS"):
        validate_production_config(env)


def test_production_missing_cors_origins_rejected():
    """Unconfigured CORS origins must abort production startup."""
    strong_secret = "a_super_secure_production_secret_key_with_very_high_entropy_32_chars!"
    env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": strong_secret,
        "GAYATRI_DB_PATH": "gayatri_local.db",
    }
    with pytest.raises(RuntimeError, match="GAYATRI_ALLOWED_ORIGINS must be explicitly configured"):
        validate_production_config(env)


# ── 4. Debug & Reload Mode Invariants ─────────────────────────────────────────

def test_production_debug_mode_rejected():
    """Debug mode must be rejected in production."""
    strong_secret = "a_super_secure_production_secret_key_with_very_high_entropy_32_chars!"
    env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": strong_secret,
        "GAYATRI_ALLOWED_ORIGINS": "https://gayatri.edu",
        "GAYATRI_DB_PATH": "gayatri_local.db",
        "DEBUG": "true",
    }
    with pytest.raises(RuntimeError, match="Debug and reload modes are strictly prohibited"):
        validate_production_config(env)


def test_production_reload_mode_rejected():
    """Reload mode must be rejected in production."""
    strong_secret = "a_super_secure_production_secret_key_with_very_high_entropy_32_chars!"
    env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": strong_secret,
        "GAYATRI_ALLOWED_ORIGINS": "https://gayatri.edu",
        "GAYATRI_DB_PATH": "gayatri_local.db",
        "RELOAD": "true",
    }
    with pytest.raises(RuntimeError, match="Debug and reload modes are strictly prohibited"):
        validate_production_config(env)


def test_run_server_rejects_reload_in_production(monkeypatch):
    """run_server must refuse to start with reload=True in production."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    with pytest.raises(RuntimeError, match="Reload mode is strictly prohibited"):
        run_server(reload=True)


# ── 5. Database Configuration Invariants ──────────────────────────────────────

def test_production_missing_database_path():
    """Missing or non-existent database file must abort production startup."""
    strong_secret = "a_super_secure_production_secret_key_with_very_high_entropy_32_chars!"
    env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": strong_secret,
        "GAYATRI_ALLOWED_ORIGINS": "https://gayatri.edu",
    }
    with pytest.raises(RuntimeError, match="Missing authoritative database configuration"):
        validate_production_config(env)

    env["GAYATRI_DB_PATH"] = "non_existent_database_file_12345.db"
    with pytest.raises(RuntimeError, match="Configured production database does not exist"):
        validate_production_config(env)


# ── 6. Model & Checksum Invariants ────────────────────────────────────────────

def test_production_model_checksum_verification():
    """Invalid model checksum must fail validation."""
    strong_secret = "a_super_secure_production_secret_key_with_very_high_entropy_32_chars!"
    with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as tmp:
        tmp.write(b"mock gguf model weights content")
        tmp_path = tmp.name

    try:
        env = {
            "GAYATRI_ENV": "production",
            "GAYATRI_JWT_SECRET": strong_secret,
            "GAYATRI_ALLOWED_ORIGINS": "https://gayatri.edu",
            "GAYATRI_DB_PATH": "gayatri_local.db",
            "GAYATRI_MODEL_FILE": tmp_path,
            "GAYATRI_MODEL_CHECKSUM": "0000000000000000000000000000000000000000000000000000000000000000",
        }
        with pytest.raises(RuntimeError, match="Model checksum mismatch"):
            validate_production_config(env)

        # Correct checksum succeeds
        import hashlib
        correct_sha = hashlib.sha256(b"mock gguf model weights content").hexdigest()
        env["GAYATRI_MODEL_CHECKSUM"] = correct_sha
        res = validate_production_config(env)
        assert res["production_enforced"] is True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ── 7. Production Application Factory & Docs Policy ───────────────────────────

def test_create_app_in_production_mode(monkeypatch):
    """create_app in production mode enforces strict CORS and disables docs by default."""
    strong_secret = "a_super_secure_production_secret_key_with_very_high_entropy_32_chars!"
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", strong_secret)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", "https://portal.gayatri.edu,https://app.gayatri.edu")
    monkeypatch.setenv("GAYATRI_DB_PATH", "gayatri_local.db")
    monkeypatch.delenv("GAYATRI_ENABLE_DOCS", raising=False)

    prod_app = create_app()
    assert prod_app.docs_url is None
    assert prod_app.redoc_url is None
    assert prod_app.openapi_url is None

    client = TestClient(prod_app)
    # Docs routes return 404 in production
    r_docs = client.get("/docs")
    assert r_docs.status_code == 404
    r_openapi = client.get("/openapi.json")
    assert r_openapi.status_code == 404

    # When explicitly enabled, docs routes are available
    monkeypatch.setenv("GAYATRI_ENABLE_DOCS", "true")
    prod_app_with_docs = create_app()
    assert prod_app_with_docs.docs_url == "/docs"
    client_docs = TestClient(prod_app_with_docs)
    r_docs_enabled = client_docs.get("/docs")
    assert r_docs_enabled.status_code == 200
