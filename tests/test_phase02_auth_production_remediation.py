"""Phase 2 Test Suite — Authentication and Identity Production Remediation.

Fulfills Phase 2 Acceptance Criteria (P0-01, P0-06):
1. Unknown username returns 401 Unauthorized in production mode.
2. Wrong password returns 401 Unauthorized.
3. Suspended account returns 403 Forbidden.
4. Inactive or deleted account returns 403 Forbidden.
5. Mock and synthetic identity fallbacks are strictly prohibited in production mode.
6. Authoritative DB user authenticates and receives verified JWT bound to DB role and organization.
7. Unverified email-only password reset is rejected with 400 Bad Request in production mode.
8. Single-use password reset tokens: resetting with a valid token succeeds once and invalidates the token.
9. Reusing an invalidated password reset token fails with 400 Bad Request.
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db
from central_platform.db import PlatformDatabase
from central_platform.models.schema import Organization, User, UserRole


PROD_JWT_SECRET = "super_secure_production_jwt_secret_with_32_characters_minimum!"
PROD_ORIGINS = "https://app.gayatri.edu"


@pytest.fixture
def auth_prod_db(tmp_path, monkeypatch):
    """Isolated database fixture populated with verified test users."""
    db_path = str(tmp_path / "auth_prod_test.db")
    db = PlatformDatabase(db_path)

    # 1. Organization
    org = Organization(id="org-prod-01", name="Prod Test Academy", slug="prod-test")
    db.create_organization(org)

    # 2. Active Student User
    student = User(
        id="usr-student-active",
        email="student.active@gayatri.edu",
        full_name="Active Student",
        role=UserRole.STUDENT,
        organization_id=org.id,
        is_active=True,
    )
    db.create_user(student)
    db.set_user_password(student.id, "StudentSecret#123")

    # 3. Suspended Teacher User
    suspended = User(
        id="usr-teacher-suspended",
        email="teacher.suspended@gayatri.edu",
        full_name="Suspended Teacher",
        role=UserRole.TEACHER,
        organization_id=org.id,
        is_active=True,
    )
    db.create_user(suspended)
    db.set_user_password(suspended.id, "TeacherSecret#123")
    db.suspend_user(suspended.id)

    # 4. Inactive User
    inactive = User(
        id="usr-inactive-user",
        email="user.inactive@gayatri.edu",
        full_name="Inactive User",
        role=UserRole.STUDENT,
        organization_id=org.id,
        is_active=False,
    )
    db.create_user(inactive)
    db.set_user_password(inactive.id, "InactiveSecret#123")

    # 5. User for password reset tests
    reset_user = User(
        id="usr-reset-target",
        email="reset.target@gayatri.edu",
        full_name="Reset Target",
        role=UserRole.STUDENT,
        organization_id=org.id,
        is_active=True,
    )
    db.create_user(reset_user)
    db.set_user_password(reset_user.id, "OldPassword#123")

    # Set dependency override and env var
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    yield {
        "db": db,
        "client": client,
        "student": student,
        "suspended": suspended,
        "inactive": inactive,
        "reset_user": reset_user,
    }

    app.dependency_overrides.pop(get_db, None)


# ── 1. Production Mode Login Invariants (P0-01) ────────────────────────────────

def test_production_login_unknown_user_returns_401(auth_prod_db, monkeypatch):
    """Unknown username in production must return 401 without constructing a mock user."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", PROD_JWT_SECRET)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", PROD_ORIGINS)

    client = auth_prod_db["client"]
    resp = client.post("/api/v1/auth/login", json={"username": "non_existent_user_999", "password": "password"})
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


def test_production_login_mock_users_prohibited(auth_prod_db, monkeypatch):
    """Built-in mock usernames must return 401 in production if not in DB."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", PROD_JWT_SECRET)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", PROD_ORIGINS)

    client = auth_prod_db["client"]
    for mock_name in ["admin", "teacher_1", "student_001"]:
        resp = client.post("/api/v1/auth/login", json={"username": mock_name, "password": "password"})
        assert resp.status_code == 401, f"Mock user {mock_name} should not authenticate in production"


def test_production_login_wrong_password_returns_401(auth_prod_db, monkeypatch):
    """Existing DB user with wrong password must return 401."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", PROD_JWT_SECRET)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", PROD_ORIGINS)

    client = auth_prod_db["client"]
    resp = client.post("/api/v1/auth/login", json={"username": "student.active@gayatri.edu", "password": "WrongPassword#999"})
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


def test_production_login_suspended_account_returns_403(auth_prod_db, monkeypatch):
    """Suspended DB user must return 403 Forbidden even with correct credentials."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", PROD_JWT_SECRET)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", PROD_ORIGINS)

    client = auth_prod_db["client"]
    resp = client.post("/api/v1/auth/login", json={"username": "teacher.suspended@gayatri.edu", "password": "TeacherSecret#123"})
    assert resp.status_code == 403
    assert "suspended" in resp.json()["detail"].lower()


def test_production_login_inactive_account_returns_403(auth_prod_db, monkeypatch):
    """Inactive DB user must return 403 Forbidden."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", PROD_JWT_SECRET)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", PROD_ORIGINS)

    client = auth_prod_db["client"]
    resp = client.post("/api/v1/auth/login", json={"username": "user.inactive@gayatri.edu", "password": "InactiveSecret#123"})
    assert resp.status_code == 403
    assert "inactive" in resp.json()["detail"].lower()


def test_production_login_valid_db_user_succeeds(auth_prod_db, monkeypatch):
    """Valid DB user logs in and receives verified tokens bound to authoritative DB identity."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", PROD_JWT_SECRET)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", PROD_ORIGINS)

    client = auth_prod_db["client"]
    resp = client.post("/api/v1/auth/login", json={"username": "student.active@gayatri.edu", "password": "StudentSecret#123"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user_id"] == "usr-student-active"
    assert data["role"] == "STUDENT"
    assert data["organization_id"] == "org-prod-01"
    assert "access_token" in data
    assert "refresh_token" in data

    # Verify token on /me
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()["data"]
    assert me_data["user_id"] == "usr-student-active"
    assert me_data["email"] == "student.active@gayatri.edu"


# ── 2. Production Password Reset Invariants (P0-06) ───────────────────────────

def test_production_password_reset_without_token_rejected(auth_prod_db, monkeypatch):
    """In production mode, password reset without token must return 400 Bad Request."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", PROD_JWT_SECRET)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", PROD_ORIGINS)

    client = auth_prod_db["client"]
    resp = client.post(
        "/api/v1/auth/password-reset",
        json={"email": "reset.target@gayatri.edu", "new_password": "NewAttemptedPassword#999"},
    )
    assert resp.status_code == 400
    assert "token is required" in resp.json()["detail"].lower()


def test_production_password_reset_token_single_use(auth_prod_db, monkeypatch):
    """Password reset token succeeds once and cannot be reused."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", PROD_JWT_SECRET)
    monkeypatch.setenv("GAYATRI_ALLOWED_ORIGINS", PROD_ORIGINS)

    db = auth_prod_db["db"]
    client = auth_prod_db["client"]

    token = "one-time-secure-reset-token-xyz-12345"
    db.set_password_reset_token("reset.target@gayatri.edu", token)

    # 1. First reset succeeds
    resp1 = client.post(
        "/api/v1/auth/password-reset",
        json={"email": "reset.target@gayatri.edu", "token": token, "new_password": "FreshNewPassword#789"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["data"]["reset"] is True

    # Verify user can log in with new password
    auth_user = db.authenticate_user("reset.target@gayatri.edu", "FreshNewPassword#789")
    assert auth_user is not None

    # 2. Reusing same token must fail
    resp2 = client.post(
        "/api/v1/auth/password-reset",
        json={"email": "reset.target@gayatri.edu", "token": token, "new_password": "AnotherNewPassword#000"},
    )
    assert resp2.status_code == 400
    assert "invalid or expired" in resp2.json()["detail"].lower()


# ── 3. Development Mode Compatibility ─────────────────────────────────────────

def test_development_login_mock_fallback_preserved(auth_prod_db, monkeypatch):
    """In development mode (non-production), mock user fallback remains functional for dev."""
    monkeypatch.delenv("GAYATRI_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    client = auth_prod_db["client"]
    resp = client.post("/api/v1/auth/login", json={"username": "teacher_1", "password": "password"})
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "TEACHER"
