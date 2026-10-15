"""Phase 10: Health, Readiness, Observability, and Failure Reporting Suite.

Verifies:
- ERP-006: /api/health truthful reporting (no hardcoded 5 students count, no masking of DEGRADED to HEALTHY, 503 on DB down).
- ERP-020: Probes truthfully test failure without masking; deep health and storage writability validation.
- Readiness vs Liveness vs Health lifecycle contracts.
- Recovery from transient dependency failure.
- Request ID tracing and secret leakage prevention in error responses.
"""
from __future__ import annotations

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import create_app
from central_platform.auth.dependencies import get_db
from central_platform.db import PlatformDatabase
from central_platform.health.service import PlatformHealthService


@pytest.fixture
def health_env(tmp_path):
    """Provides isolated DB and app with access to health_service."""
    db_file = tmp_path / "health_test.db"
    db = PlatformDatabase(str(db_file))

    app = create_app()
    import central_platform.auth.dependencies as auth_deps
    old_instance = auth_deps._DB_INSTANCE
    old_env = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = str(db_file)
    auth_deps._DB_INSTANCE = db
    app.dependency_overrides[get_db] = lambda: db

    # Ensure app health_service is linked to the test DB
    health_svc: PlatformHealthService = app.state.health_service
    health_svc.db = db

    client = TestClient(app)

    yield {
        "db": db,
        "app": app,
        "client": client,
        "health_svc": health_svc,
    }

    health_svc.reset_simulated_failures()
    auth_deps._DB_INSTANCE = old_instance
    if old_env is not None:
        os.environ["GAYATRI_DB_PATH"] = old_env
    else:
        os.environ.pop("GAYATRI_DB_PATH", None)


# ── 1. ERP-006: /api/health Truthful Reporting ────────────────────────────────

def test_erp006_legacy_health_no_fabricated_student_count_when_empty(health_env):
    """When no students are enrolled in the target course, students_monitored must be 0, never hardcoded 5."""
    client = health_env["client"]

    # In an empty course with no students enrolled:
    import central_platform.api.app as app_mod
    real_portal = app_mod._portal_service
    try:
        # Mock overview returning total_students = 0
        class MockOverview:
            total_students = 0
        class MockPortal:
            def get_dashboard_overview(self, course_id):
                return MockOverview()
        app_mod._portal_service = MockPortal()

        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["students_monitored"] == 0, f"Expected 0 students monitored, got {data['students_monitored']} (fabricated 5?)"
    finally:
        app_mod._portal_service = real_portal


def test_erp006_legacy_health_query_failure_returns_zero_not_fallback_five(health_env):
    """When portal dashboard overview query fails, students_monitored must be 0, never fallback to 5."""
    client = health_env["client"]

    import central_platform.api.app as app_mod
    real_portal = app_mod._portal_service
    try:
        class FailingPortal:
            def get_dashboard_overview(self, course_id):
                raise RuntimeError("Database connection timed out during dashboard aggregation")
        app_mod._portal_service = FailingPortal()

        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["students_monitored"] == 0, f"Expected 0 on query failure, got {data['students_monitored']} (fabricated fallback 5?)"
    finally:
        app_mod._portal_service = real_portal


def test_erp006_legacy_health_reports_degraded_when_subsystem_degraded(health_env):
    """When a non-critical subsystem is DEGRADED, /api/health must report DEGRADED, not mask it as HEALTHY."""
    client = health_env["client"]
    health_svc = health_env["health_svc"]

    # Point manifest_path to non-existent file to simulate DEGRADED model_registry
    old_manifest = health_svc.manifest_path
    health_svc.manifest_path = "C:\\non_existent_model_manifest_12345.json"
    try:
        h = health_svc.check_health()
        assert h["health_level"] == "DEGRADED"

        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DEGRADED" or data.get("health_level") == "DEGRADED", (
            f"Degraded subsystem was masked as: {data}"
        )
    finally:
        health_svc.manifest_path = old_manifest


def test_erp006_legacy_health_returns_503_when_database_unhealthy(health_env):
    """When the critical database subsystem fails, /api/health must return HTTP 503, not HTTP 200."""
    client = health_env["client"]
    health_svc = health_env["health_svc"]

    health_svc.simulate_subsystem_failure("database", True)
    resp = client.get("/api/health")
    assert resp.status_code == 503, f"Expected HTTP 503 when DB fails, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "UNHEALTHY"


# ── 2. Readiness & Liveness Lifecycle Probes ─────────────────────────────────

def test_readyz_reports_503_and_not_ready_when_database_fails(health_env):
    """Readiness probe /readyz must return HTTP 503 and ready=False when DB fails."""
    client = health_env["client"]
    health_svc = health_env["health_svc"]

    health_svc.simulate_subsystem_failure("database", True)
    resp = client.get("/readyz")
    assert resp.status_code == 503
    data = resp.json()
    assert data["ready"] is False
    assert data["status"] == "UNHEALTHY"


def test_readyz_recovers_to_200_when_database_failure_cleared(health_env):
    """Readiness probe /readyz must dynamically recover to HTTP 200 and ready=True when restored."""
    client = health_env["client"]
    health_svc = health_env["health_svc"]

    # 1. Break
    health_svc.simulate_subsystem_failure("database", True)
    assert client.get("/readyz").status_code == 503

    # 2. Heal
    health_svc.simulate_subsystem_failure("database", False)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True
    assert data["status"] != "UNHEALTHY"


def test_livez_always_reports_alive(health_env):
    """Liveness probe /livez reports process execution regardless of dependency failures."""
    client = health_env["client"]
    health_svc = health_env["health_svc"]

    health_svc.simulate_subsystem_failure("database", True)
    resp = client.get("/livez")
    assert resp.status_code == 200
    assert resp.json()["alive"] is True


def test_healthz_returns_503_on_critical_subsystem_failure(health_env):
    """Probe /healthz returns HTTP 503 when database is down."""
    client = health_env["client"]
    health_svc = health_env["health_svc"]

    health_svc.simulate_subsystem_failure("database", True)
    resp = client.get("/healthz")
    assert resp.status_code == 503
    assert resp.json()["status"] == "UNHEALTHY"


# ── 3. ERP-020: Deep Health & Storage Writability Validation ─────────────────

def test_erp020_deep_health_integrity_check(health_env):
    """Deep health probe must verify SQLite integrity check and table counts."""
    health_svc = health_env["health_svc"]
    deep = health_svc.check_deep_health()
    assert "database" in deep["subsystems"]
    db_info = deep["subsystems"]["database"]
    assert db_info["status"] == "HEALTHY"
    assert db_info["integrity"] == "ok"
    assert db_info["table_count"] > 0


def test_erp020_storage_probe_detects_unwritable_path(health_env):
    """Storage probe must check real directory existence and report UNHEALTHY if missing or unwritable."""
    health_svc = health_env["health_svc"]

    old_env = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = "Z:\\nonexistent_volume_9999\\bad.db"
    try:
        res = health_svc.probe_storage()
        assert res["status"] == "UNHEALTHY"
        assert "error" in res
    finally:
        if old_env is not None:
            os.environ["GAYATRI_DB_PATH"] = old_env
        else:
            os.environ.pop("GAYATRI_DB_PATH", None)


# ── 4. Observability: Tracing and Secret Scrubbing ───────────────────────────

def test_observability_x_request_id_and_no_secret_leakage(health_env):
    """Responses must return X-Request-ID and structured error envelopes without secret leakage."""
    client = health_env["client"]

    # 1. Custom request ID propagated
    custom_id = "req-obs-trace-999"
    resp = client.get("/healthz", headers={"X-Request-ID": custom_id})
    assert resp.headers.get("X-Request-ID") == custom_id

    # 2. Trigger error and check secrets are not in error body
    resp_err = client.get("/api/v1/users/non-existent-user-1234")
    assert resp_err.status_code in (401, 403, 404)
    content = resp_err.text
    # Ensure standard sensitive strings are absent
    for sensitive in ("jwt_secret", "password_hash", "service_role", "sk-", "bearer "):
        assert sensitive not in content.lower(), f"Sensitive token pattern '{sensitive}' leaked in response: {content}"
