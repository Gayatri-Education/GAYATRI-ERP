"""Reproduction and regression test suite for Phase 01: Authentication, Authorization,
Tenant Isolation, and Token Revocation (ERP-003, ERP-004, ERP-012, ERP-014, ERP-015, ERP-019).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.tokens import (
    DatabaseRevocationStore,
    create_access_token,
    decode_and_verify_token,
    set_revocation_store,
)
from central_platform.models.schema import User, UserRole


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_revocation_store_fails_closed_on_db_error():
    """ERP-003: When DB check fails, is_revoked must fail closed (raise PermissionError) rather than returning False."""
    store = DatabaseRevocationStore(db_path="invalid_path_dummy.db")
    with patch.object(store, "_get_db", side_effect=RuntimeError("Database connection dropped")):
        with pytest.raises(PermissionError, match="revocation.*database unavailable|Revocation store"):
            store.is_revoked("jwt-test-jti-12345")


def test_revocation_store_revoke_truthful_failure_on_db_error():
    """ERP-003: When DB write fails during revocation, revoke() must return False rather than reporting false success."""
    store = DatabaseRevocationStore(db_path="invalid_path_dummy.db")
    with patch.object(store, "_get_db", side_effect=RuntimeError("Database disk full")):
        result = store.revoke("jwt-test-jti-12345")
        assert result is False, "revoke() must return False on database write error"


def test_logout_fails_when_no_token_provided(client):
    """ERP-003: /auth/logout called without any bearer token or refresh token must reject with 400 Bad Request."""
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 400
    assert "no token provided" in resp.json()["detail"].lower()


def test_logout_fails_when_revocation_persistence_fails(client):
    """ERP-003: /auth/logout must return HTTP 500 when revocation persistence fails."""
    store = DatabaseRevocationStore(db_path="invalid_path_dummy.db")
    with patch.object(store, "_get_db", side_effect=RuntimeError("DB write failure")):
        set_revocation_store(store)
        try:
            token = create_access_token("usr_test_logout", "student", expires_minutes=15)
            resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 500
            assert "failed to persist token revocation" in resp.json()["detail"].lower()
        finally:
            set_revocation_store(None)


def test_ai_killswitch_requires_admin_authorization(client):
    """ERP-012: In production, /api/v1/ai/killswitch must reject unauthenticated requests (401) and student callers (403)."""
    mock_student = User(
        id="usr_student_1",
        email="s@test.com",
        full_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
        is_deleted=False,
        organization_id="org_default",
    )
    mock_admin = User(
        id="usr_admin_1",
        email="a@test.com",
        full_name="Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_deleted=False,
        organization_id="org_default",
    )

    with patch("central_platform.auth.dependencies.is_production_mode", return_value=True), \
         patch("central_platform.api.routes.ai.is_production_mode", return_value=True), \
         patch("central_platform.auth.dependencies.get_db") as mock_db_getter:
        
        mock_db = MagicMock()
        mock_db.get_user_credentials.return_value = {"is_suspended": False}
        mock_db_getter.return_value = mock_db

        # 1. Unauthenticated request in production -> 401
        unauth_resp = client.post("/api/v1/ai/killswitch", json={"enabled": True, "reason": "test"})
        assert unauth_resp.status_code == 401

        # 2. Student token in production -> 403 Forbidden
        mock_db.get_user.return_value = mock_student
        student_token = create_access_token("usr_student_1", "student", "org_default")
        student_resp = client.post(
            "/api/v1/ai/killswitch",
            json={"enabled": True, "reason": "test"},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert student_resp.status_code == 403

        # 3. Super Admin token in production -> 200 OK
        mock_db.get_user.return_value = mock_admin
        admin_token = create_access_token("usr_admin_1", "super_admin", "org_default")
        admin_resp = client.post(
            "/api/v1/ai/killswitch",
            json={"enabled": False, "reason": "resume normal operation"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_resp.status_code == 200
        assert admin_resp.json()["ok"] is True


def test_ai_providers_require_admin_authorization(client):
    """ERP-012: In production, /api/v1/ai/providers must reject unauthenticated (401) and student callers (403)."""
    mock_student = User(
        id="usr_student_1",
        email="s@test.com",
        full_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
        is_deleted=False,
        organization_id="org_default",
    )
    mock_teacher = User(
        id="usr_teacher_1",
        email="t@test.com",
        full_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
        is_deleted=False,
        organization_id="org_default",
    )

    with patch("central_platform.auth.dependencies.is_production_mode", return_value=True), \
         patch("central_platform.api.routes.ai.is_production_mode", return_value=True), \
         patch("central_platform.auth.dependencies.get_db") as mock_db_getter:
        
        mock_db = MagicMock()
        mock_db.get_user_credentials.return_value = {"is_suspended": False}
        mock_db_getter.return_value = mock_db

        # Unauthenticated listing in production -> 401
        unauth_resp = client.get("/api/v1/ai/providers")
        assert unauth_resp.status_code == 401

        # Student token in production -> 403
        mock_db.get_user.return_value = mock_student
        student_token = create_access_token("usr_student_1", "student", "org_default")
        student_resp = client.get(
            "/api/v1/ai/providers",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert student_resp.status_code == 403

        # Teacher token in production -> 200 OK (inspection allowed for teachers)
        mock_db.get_user.return_value = mock_teacher
        teacher_token = create_access_token("usr_teacher_1", "teacher", "org_default")
        teacher_resp = client.get(
            "/api/v1/ai/providers",
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        assert teacher_resp.status_code == 200
        assert teacher_resp.json()["ok"] is True


def test_ai_create_provider_rejects_invalid_type_with_422(client):
    """ERP-014: Submitting an invalid provider_type must raise HTTP 422 Unprocessable Entity instead of silent fallback."""
    mock_admin = User(
        id="usr_admin_1",
        email="a@test.com",
        full_name="Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_deleted=False,
        organization_id="org_default",
    )
    with patch("central_platform.auth.dependencies.get_db") as mock_db_getter:
        mock_db = MagicMock()
        mock_db.get_user.return_value = mock_admin
        mock_db.get_user_credentials.return_value = {"is_suspended": False}
        mock_db_getter.return_value = mock_db
        admin_token = create_access_token("usr_admin_1", "super_admin", "org_default")

        resp = client.post(
            "/api/v1/ai/providers",
            json={"provider_name": "invalid_test_provider", "provider_type": "completely_bogus_type"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "invalid provider_type" in resp.json()["detail"].lower()


def test_legacy_endpoints_reject_unauthenticated_in_production(client):
    """ERP-015: In production mode, legacy mutating routes reject unauthenticated access and verify caller identity."""
    mock_student = User(
        id="student_001",
        email="s@test.com",
        full_name="Student",
        role=UserRole.STUDENT,
        is_active=True,
        is_deleted=False,
        organization_id="org_default",
    )
    mock_teacher = User(
        id="teacher_001",
        email="t@test.com",
        full_name="Teacher",
        role=UserRole.TEACHER,
        is_active=True,
        is_deleted=False,
        organization_id="org_default",
    )

    with patch("central_platform.auth.dependencies.is_production_mode", return_value=True), \
         patch("central_platform.api.app.is_production_mode", return_value=True), \
         patch("central_platform.auth.dependencies.get_db") as mock_db_getter:
        
        mock_db = MagicMock()
        mock_db.get_user_credentials.return_value = {"is_suspended": False}
        mock_db_getter.return_value = mock_db

        # 1. Unauthenticated mutation -> 401
        unauth_resp = client.post(
            "/api/teacher/instruction",
            json={"instruction": "Test instruction", "course_id": "crs-chem-101"},
        )
        assert unauth_resp.status_code == 401

        # 2. Student trying to create teacher instruction -> 403 Forbidden
        mock_db.get_user.return_value = mock_student
        student_token = create_access_token("student_001", "student", "org_default")
        student_resp = client.post(
            "/api/teacher/instruction",
            json={"instruction": "Test instruction", "course_id": "crs-chem-101"},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert student_resp.status_code == 403

        # 3. Teacher creating teacher instruction -> 200 OK
        mock_db.get_user.return_value = mock_teacher
        teacher_token = create_access_token("teacher_001", "teacher", "org_default")
        teacher_resp = client.post(
            "/api/teacher/instruction",
            json={"instruction": "Read Chapter 4 carefully", "course_id": "crs-chem-101"},
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        assert teacher_resp.status_code == 200
        assert teacher_resp.json()["ok"] is True

        # 4. Student submitting snapshot for another student -> 403 Forbidden
        mock_db.get_user.return_value = mock_student
        spoof_snapshot_resp = client.post(
            "/api/student/snapshot",
            json={"student_id": "student_999", "mastery": 0.99},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert spoof_snapshot_resp.status_code == 403

        # 5. Student submitting own snapshot -> 200 OK
        own_snapshot_resp = client.post(
            "/api/student/snapshot",
            json={"student_id": "student_001", "mastery": 0.85},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert own_snapshot_resp.status_code == 200
        assert own_snapshot_resp.json()["ok"] is True
