"""Tests for QA Phase 05: Authentication, Revocation, Authorization & Distributed Rate Limiting.

Verifies:
- GQA-005: Durable multi-worker JWT revocation registry surviving restarts and cross-worker bypass.
- GQA-006: Distributed atomic sliding-window rate limiting, fail-closed cluster readiness, and differentiated policies.
- GQA-013: Security proofs, refresh token rotation, replay prevention, and multi-tenant/role authorization matrix.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import extract_bearer_token, get_current_user
from central_platform.auth.tokens import (
    DatabaseRevocationStore,
    InMemoryRevocationStore,
    create_access_token,
    create_refresh_token,
    decode_and_verify_token,
    get_revocation_store,
    is_token_revoked,
    revoke_token,
    set_revocation_store,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Course,
    Organization,
    RAGSource,
    Session as DbSession,
    SessionStatus,
    User,
    UserRole,
)
from central_platform.security.auditor import (
    DatabaseRateLimiterStore,
    InMemoryRateLimiterBackend,
    SecurityAuditor,
    SharedRateLimiterBackend,
)


@pytest.fixture
def isolated_db(tmp_path: Path):
    """Provide a fresh isolated database with schema and migrations applied."""
    db_file = str(tmp_path / "phase05_auth_test.db")
    db = PlatformDatabase(db_file)
    old_env = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = db_file
    set_revocation_store(DatabaseRevocationStore(db_file))
    yield db
    if old_env:
        os.environ["GAYATRI_DB_PATH"] = old_env
    else:
        os.environ.pop("GAYATRI_DB_PATH", None)
    set_revocation_store(None)
    db.close()


@pytest.fixture
def client(isolated_db):
    """Provide FastAPI test client."""
    with TestClient(app) as c:
        yield c


# ── 1. Token Validation Lifecycle & Negative Tests ─────────────────────────

def test_token_validation_lifecycle_invalid_expired_wrong_type():
    """Verify signature, expiry, type, and tampering checks in decode_and_verify_token."""
    access_token = create_access_token(user_id="user_valid", role="student", expires_minutes=15)
    payload = decode_and_verify_token(access_token, expected_type="access")
    assert payload["sub"] == "user_valid"
    assert payload["role"] == "student"

    # Expired token
    expired_token = create_access_token(user_id="user_exp", role="student", expires_minutes=-10)
    with pytest.raises(PermissionError, match="Token has expired"):
        decode_and_verify_token(expired_token, expected_type="access")

    # Wrong token type (refresh token passed as access token)
    refresh_token = create_refresh_token(user_id="user_ref")
    with pytest.raises(PermissionError, match="Expected token type 'access', got 'refresh'"):
        decode_and_verify_token(refresh_token, expected_type="access")

    # Tampered signature
    tampered = access_token[:-4] + "fake"
    with pytest.raises(PermissionError, match="Invalid token signature"):
        decode_and_verify_token(tampered, expected_type="access")


def test_user_account_status_suspended_deleted_inactive(isolated_db: PlatformDatabase):
    """Verify that inactive, deleted, or suspended users are rejected with 403 Forbidden."""
    org = Organization(id="org-status-1", name="Status Org", slug="status-org")
    isolated_db.create_organization(org)

    # 1. Inactive user
    u_inactive = User(
        id="usr-inactive",
        email="inactive@test.org",
        full_name="Inactive",
        role=UserRole.STUDENT,
        organization_id=org.id,
        is_active=False,
    )
    isolated_db.create_user(u_inactive)
    token_inactive = create_access_token(user_id=u_inactive.id, role="student")

    with pytest.raises(Exception) as exc_info:
        import asyncio
        asyncio.run(get_current_user(authorization=f"Bearer {token_inactive}"))
    assert exc_info.value.status_code == 403
    assert "inactive or deleted" in exc_info.value.detail.lower()

    # 2. Suspended user
    u_suspended = User(
        id="usr-suspended",
        email="suspended@test.org",
        full_name="Suspended",
        role=UserRole.STUDENT,
        organization_id=org.id,
        is_active=True,
    )
    isolated_db.create_user(u_suspended)
    isolated_db.set_user_password(u_suspended.id, "Pass1234#")
    isolated_db.suspend_user(u_suspended.id, reason="disciplinary")

    token_suspended = create_access_token(user_id=u_suspended.id, role="student")
    with pytest.raises(Exception) as exc_info:
        import asyncio
        asyncio.run(get_current_user(authorization=f"Bearer {token_suspended}"))
    assert exc_info.value.status_code == 403
    assert "suspended" in exc_info.value.detail.lower()


# ── 2. GQA-005: Multi-Worker Revocation & Persistence Proof ────────────────

def test_multi_worker_revocation_and_persistence(tmp_path: Path):
    """GQA-005: Revoke token on worker A and verify rejection on worker B and post-restart."""
    shared_db_path = str(tmp_path / "multi_worker_revocation.db")
    db = PlatformDatabase(shared_db_path)

    # Simulate Worker A and Worker B with separate revocation store instances connected to same DB
    worker_a_store = DatabaseRevocationStore(db_path=shared_db_path)
    worker_b_store = DatabaseRevocationStore(db_path=shared_db_path)

    token = create_access_token(user_id="user_worker_test", role="teacher", expires_minutes=30)
    payload = decode_and_verify_token(token)
    jti = payload["jti"]

    # Initial state: both workers see token as active
    assert worker_a_store.is_revoked(jti) is False
    assert worker_b_store.is_revoked(jti) is False

    # Worker A revokes the token
    worker_a_store.revoke(jti, user_id="user_worker_test", reason="security_incident")
    assert worker_a_store.is_revoked(jti) is True

    # Worker B must immediately detect the revocation via shared database backing
    assert worker_b_store.is_revoked(jti) is True

    # Process restart simulation: new independent store instance
    worker_c_store = DatabaseRevocationStore(db_path=shared_db_path)
    assert worker_c_store.is_revoked(jti) is True

    # decode_and_verify_token with store active must raise PermissionError
    set_revocation_store(worker_c_store)
    try:
        with pytest.raises(PermissionError, match="Token has been revoked"):
            decode_and_verify_token(token)
    finally:
        set_revocation_store(None)
    db.close()


# ── 3. Refresh Token Rotation & Replay Prevention ─────────────────────────

def test_refresh_token_rotation_and_replay_prevention(client: TestClient, isolated_db: PlatformDatabase):
    """Verify refresh token rotation: old refresh token is revoked and cannot be reused."""
    org = Organization(id="org-rot-1", name="Rotation Org", slug="rot-org")
    isolated_db.create_organization(org)
    user = User(
        id="usr-rot-student",
        email="rot_student@test.org",
        full_name="Rotation Student",
        role=UserRole.STUDENT,
        organization_id=org.id,
        is_active=True,
    )
    isolated_db.create_user(user)
    isolated_db.set_user_password(user.id, "ValidPass#2026")

    # 1. Login to obtain access token and initial refresh token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "rot_student@test.org", "password": "ValidPass#2026"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()["data"]
    ref_tok_1 = login_data["refresh_token"]

    # 2. Refresh token rotation: exchange ref_tok_1 for new tokens
    refresh_resp_1 = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ref_tok_1},
    )
    assert refresh_resp_1.status_code == 200
    ref_data_1 = refresh_resp_1.json()["data"]
    acc_tok_2 = ref_data_1["access_token"]
    ref_tok_2 = ref_data_1["refresh_token"]
    assert ref_tok_2 != ref_tok_1

    # 3. Replay attack: try to reuse ref_tok_1
    replay_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ref_tok_1},
    )
    assert replay_resp.status_code == 401
    assert "revoked" in replay_resp.json()["detail"].lower()

    # 4. Valid use of rotated ref_tok_2 succeeds
    refresh_resp_2 = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ref_tok_2},
    )
    assert refresh_resp_2.status_code == 200


def test_logout_invalidates_tokens(client: TestClient, isolated_db: PlatformDatabase):
    """Verify logout revokes both access and refresh tokens."""
    org = Organization(id="org-logout", name="Logout Org", slug="logout-org")
    isolated_db.create_organization(org)
    user = User(
        id="usr-logout",
        email="logout@test.org",
        full_name="Logout User",
        role=UserRole.STUDENT,
        organization_id=org.id,
        is_active=True,
    )
    isolated_db.create_user(user)
    isolated_db.set_user_password(user.id, "Pass1234#")

    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "logout@test.org", "password": "Pass1234#"},
    )
    assert login_res.status_code == 200
    acc_tok = login_res.json()["data"]["access_token"]
    ref_tok = login_res.json()["data"]["refresh_token"]

    # Call /logout with access token and refresh token in body
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {acc_tok}"},
        json={"refresh_token": ref_tok},
    )
    assert logout_res.status_code == 200

    # /me with revoked access token must fail
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {acc_tok}"})
    assert me_res.status_code == 401

    # /refresh with revoked refresh token must fail
    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": ref_tok})
    assert ref_res.status_code == 401


# ── 4. GQA-006: Distributed Rate Limiting & Fail-Closed Readiness ──────────

def test_cluster_rate_limiter_readiness_failure():
    """GQA-006: In cluster-required mode, missing shared store fails readiness and raises RuntimeError."""
    limiter = SharedRateLimiterBackend(rate_limit_per_minute=10, shared_store=None, cluster_required=True)
    ready, reason = limiter.check_readiness()
    assert ready is False
    assert "Shared rate limiter backend required in cluster mode" in reason

    with pytest.raises(RuntimeError, match="Shared rate limiter backend required in cluster mode"):
        limiter.is_allowed("test_key")

    with pytest.raises(RuntimeError, match="Shared rate limiter backend required in cluster mode"):
        limiter.get_status("test_key")


def test_atomic_distributed_rate_limiter_across_workers(tmp_path: Path):
    """GQA-006: Two simulated workers sharing database enforce one single global limit."""
    shared_db_path = str(tmp_path / "shared_ratelimit.db")
    db = PlatformDatabase(shared_db_path)

    worker_1_store = DatabaseRateLimiterStore(db_path=shared_db_path)
    worker_2_store = DatabaseRateLimiterStore(db_path=shared_db_path)

    limiter_1 = SharedRateLimiterBackend(rate_limit_per_minute=4, shared_store=worker_1_store, cluster_required=True)
    limiter_2 = SharedRateLimiterBackend(rate_limit_per_minute=4, shared_store=worker_2_store, cluster_required=True)

    identity = "student_cluster_shared_id"

    # Worker 1 issues 2 requests
    assert limiter_1.is_allowed(identity, limit=4) is True
    assert limiter_1.is_allowed(identity, limit=4) is True

    # Worker 2 issues 2 requests
    assert limiter_2.is_allowed(identity, limit=4) is True
    assert limiter_2.is_allowed(identity, limit=4) is True

    # Limit of 4 is now reached across the cluster!
    # 5th request from Worker 1 must be rejected
    assert limiter_1.is_allowed(identity, limit=4) is False

    # 6th request from Worker 2 must also be rejected
    status = limiter_2.get_status(identity, limit=4, record=False)
    assert status["allowed"] is False
    assert status["current_count"] == 4
    assert status["remaining"] == 0
    assert status["backend"] == "shared_distributed"
    assert status["guarantee"] == "cluster_wide"

    db.close()


def test_differentiated_rate_limit_policies():
    """Verify distinct rate limit policies across actor categories."""
    auditor = SecurityAuditor(rate_limit_backend=InMemoryRateLimiterBackend(rate_limit_per_minute=100))

    # Anonymous policy (limit 20)
    for i in range(20):
        assert auditor.check_rate_limit_for_identity("anon_client_1", category="anonymous") is True
    assert auditor.check_rate_limit_for_identity("anon_client_1", category="anonymous") is False

    # Auth sensitive policy (limit 10)
    for i in range(10):
        assert auditor.check_rate_limit_for_identity("auth_actor_1", category="auth_sensitive") is True
    assert auditor.check_rate_limit_for_identity("auth_actor_1", category="auth_sensitive") is False


# ── 5. Authorization Matrix & Boundary Checks ─────────────────────────────

def test_student_cannot_access_other_student_session(client: TestClient, isolated_db: PlatformDatabase):
    """Verify student A cannot view or manipulate student B's tutoring session (IDOR mitigation)."""
    org = Organization(id="org-auth-matrix", name="Matrix Org", slug="matrix-org")
    isolated_db.create_organization(org)

    student_a = User(id="student_a", email="sa@test.org", full_name="A", role=UserRole.STUDENT, organization_id=org.id)
    student_b = User(id="student_b", email="sb@test.org", full_name="B", role=UserRole.STUDENT, organization_id=org.id)
    isolated_db.create_user(student_a)
    isolated_db.create_user(student_b)

    # Course & Session belonging to Student B
    course_chem = Course(id="chem_101", organization_id=org.id, code="CHEM101", title="Chemistry 101")
    isolated_db.create_course(course_chem)
    sess_b = DbSession(id="sess-b-123", student_id="student_b", course_id="chem_101", concept_id="stoichiometry", status=SessionStatus.ACTIVE)
    isolated_db.create_session(sess_b)

    token_a = create_access_token(user_id="student_a", role="student", organization_id=org.id)

    # Student A tries to read Student B's session
    resp = client.get(f"/api/v1/sessions/{sess_b.id}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 403
    assert "another student's session" in resp.json()["detail"].lower()


def test_student_cannot_query_rag_for_other_student(client: TestClient, isolated_db: PlatformDatabase):
    """Verify student A cannot query RAG on behalf of student B."""
    org = Organization(id="org-rag-test", name="RAG Org", slug="rag-org")
    isolated_db.create_organization(org)

    student_a = User(id="student_rag_a", email="ra@test.org", full_name="RA", role=UserRole.STUDENT, organization_id=org.id)
    isolated_db.create_user(student_a)

    token_a = create_access_token(user_id="student_rag_a", role="student", organization_id=org.id)

    # Student A attempts RAG query with student_id set to student_b
    rag_payload = {
        "query": "What is the first law of thermodynamics?",
        "student_id": "student_rag_b",
    }
    resp = client.post("/api/v1/rag/query", headers={"Authorization": f"Bearer {token_a}"}, json=rag_payload)
    assert resp.status_code == 403
    assert "on behalf of another student" in resp.json()["detail"].lower()


def test_cross_tenant_isolation_org_admin(client: TestClient, isolated_db: PlatformDatabase):
    """Verify org admin from Org 1 cannot delete a knowledge source belonging to Org 2."""
    org1 = Organization(id="org-alpha-01", name="Alpha", slug="alpha")
    org2 = Organization(id="org-beta-02", name="Beta", slug="beta")
    isolated_db.create_organization(org1)
    isolated_db.create_organization(org2)

    admin_1 = User(id="admin_org1", email="admin1@alpha.edu", full_name="Admin 1", role=UserRole.ORG_ADMIN, organization_id=org1.id)
    isolated_db.create_user(admin_1)

    # Course & Knowledge source owned by Org 2
    course_phys = Course(id="physics_101", organization_id=org2.id, code="PHYS101", title="Physics 101")
    isolated_db.create_course(course_phys)
    src_org2 = RAGSource(
        id="src-beta-01",
        organization_id=org2.id,
        course_id="physics_101",
        title="Beta Physics",
        subject="physics",
        source_type="textbook",
    )
    isolated_db.create_rag_source(src_org2)

    token_admin1 = create_access_token(user_id="admin_org1", role="org_admin", organization_id=org1.id)

    # Admin 1 attempts to delete Org 2's source
    del_resp = client.delete(f"/api/v1/rag/sources/{src_org2.id}", headers={"Authorization": f"Bearer {token_admin1}"})
    assert del_resp.status_code == 403
    assert "another organization" in del_resp.json()["detail"].lower()



# ── 6. Malformed, Missing, and Oversized Auth Headers ───────────────────────

def test_auth_headers_malformed_missing_oversized(client: TestClient):
    """Verify missing, malformed, duplicate, and oversized Authorization headers."""
    # 1. Missing header
    res_missing = client.get("/api/v1/auth/me")
    assert res_missing.status_code == 401
    assert "missing or malformed" in res_missing.json()["detail"].lower()

    # 2. Malformed duplicate / comma-separated header
    res_dup = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer tok1, Bearer tok2"})
    assert res_dup.status_code == 401

    # 3. Oversized header (> 8192 chars)
    oversized = "Bearer " + ("A" * 9000)
    res_oversized = client.get("/api/v1/auth/me", headers={"Authorization": oversized})
    assert res_oversized.status_code == 400
    assert "exceeds maximum allowed length" in res_oversized.json()["detail"].lower()
