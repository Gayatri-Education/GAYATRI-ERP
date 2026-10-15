"""QA Phase 11 Test Suite: API Contracts, Validation, Rate Limits, and Idempotency.

Verifies:
- Strict schema validation at the API perimeter (rejecting invalid roles, negative amounts, oversized arrays with 422).
- Bounded pagination enforcement (rejecting negative or out-of-range limit queries with 422).
- Mutating operation idempotency across finance and synchronization.
- Atomic sliding window rate limiting.
- Structured error response envelope consistency and header preservation.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.finance.service import FinanceService
from central_platform.models.schema import Organization, User, UserRole
from central_platform.sync.service import SyncService


@pytest.fixture
def isolated_db(tmp_path: Path):
    """Provide a fresh isolated database with schema and migrations applied."""
    db_file = str(tmp_path / "phase11_contracts_test.db")
    db = PlatformDatabase(db_file)
    old_env = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = db_file
    yield db
    if old_env:
        os.environ["GAYATRI_DB_PATH"] = old_env
    else:
        os.environ.pop("GAYATRI_DB_PATH", None)
    db.close()


@pytest.fixture
def client(isolated_db: PlatformDatabase):
    """Provide FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_headers(isolated_db: PlatformDatabase):
    """Provide authorization headers for a super admin."""
    org = Organization(id="org-test-11", name="Phase 11 Org", slug="phase11-org")
    isolated_db.create_organization(org)
    admin = User(
        id="usr-admin-11",
        email="admin11@gayatri.ai",
        full_name="Admin 11",
        role=UserRole.SUPER_ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    isolated_db.create_user(admin)
    token = create_access_token(user_id=admin.id, role="super_admin", organization_id=org.id)
    return {"Authorization": f"Bearer {token}"}


# ── 1. API Boundary Validation ───────────────────────────────────────────────

def test_user_create_invalid_role_rejected_with_422(client: TestClient, admin_headers: dict):
    """Invalid role like 'HACKER' must be rejected at the boundary with HTTP 422."""
    payload = {
        "username": "new_bad_actor",
        "email": "badactor@gayatri.ai",
        "password": "Password123#",
        "role": "HACKER",
        "organization_id": "org-test-11",
    }
    resp = client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_user_create_valid_role_accepted(client: TestClient, admin_headers: dict):
    """Valid role like 'TEACHER' or 'STUDENT' is accepted and created with HTTP 201."""
    payload = {
        "username": "valid_teacher_11",
        "email": "teacher11@gayatri.ai",
        "password": "Password123#",
        "role": "TEACHER",
        "organization_id": "org-test-11",
    }
    resp = client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["role"] == "TEACHER"


def test_users_pagination_bounds(client: TestClient, admin_headers: dict):
    """Users list must enforce bounded limit/offset queries."""
    # Negative limit -> 422
    resp_neg = client.get("/api/v1/users?limit=-1", headers=admin_headers)
    assert resp_neg.status_code == 422

    # Oversized limit -> 422
    resp_huge = client.get("/api/v1/users?limit=1000", headers=admin_headers)
    assert resp_huge.status_code == 422

    # Valid bounded pagination
    resp_valid = client.get("/api/v1/users?limit=2&offset=0", headers=admin_headers)
    assert resp_valid.status_code == 200
    data = resp_valid.json()["data"]
    assert len(data) <= 2


def test_courses_pagination_bounds(client: TestClient):
    """Courses catalog must enforce bounded limit/offset queries."""
    # Negative limit -> 422
    resp_neg = client.get("/api/v1/courses?limit=-5")
    assert resp_neg.status_code == 422

    # Oversized limit -> 422
    resp_huge = client.get("/api/v1/courses?limit=10000")
    assert resp_huge.status_code == 422

    # Valid bounded query
    resp_valid = client.get("/api/v1/courses?limit=1&offset=0")
    assert resp_valid.status_code == 200
    data = resp_valid.json()["data"]
    assert len(data) <= 1


def test_export_limit_bounds(client: TestClient, admin_headers: dict):
    """Export request must reject negative or oversized limits."""
    # Negative limit -> 422
    resp_neg = client.post(
        "/api/v1/analytics/institutional/export",
        json={"export_type": "STUDENTS", "limit": -10},
        headers=admin_headers,
    )
    assert resp_neg.status_code == 422

    # Oversized limit > 10000 -> 422
    resp_huge = client.post(
        "/api/v1/analytics/institutional/export",
        json={"export_type": "STUDENTS", "limit": 50000},
        headers=admin_headers,
    )
    assert resp_huge.status_code == 422


def test_order_create_positive_amount_required(client: TestClient, admin_headers: dict, isolated_db: PlatformDatabase):
    """Finance orders must require positive amounts both at API and service layers."""
    # API layer: negative amount -> 422
    resp_neg = client.post(
        "/api/v1/finance/orders",
        json={
            "invoice_id": "inv-001",
            "student_id": "stu-001",
            "amount": -50.0,
        },
        headers=admin_headers,
    )
    assert resp_neg.status_code == 422

    # API layer: zero amount -> 422
    resp_zero = client.post(
        "/api/v1/finance/orders",
        json={
            "invoice_id": "inv-001",
            "student_id": "stu-001",
            "amount": 0.0,
        },
        headers=admin_headers,
    )
    assert resp_zero.status_code == 422

    # Service layer: non-positive amount raises ValueError
    fin_svc = FinanceService(isolated_db)
    with pytest.raises(ValueError, match="positive"):
        fin_svc.create_payment_order(
            organization_id="org-test-11",
            invoice_id="inv-001",
            student_id="stu-001",
            amount=-100.0,
        )


def test_sync_events_bounded_payload(client: TestClient, admin_headers: dict):
    """Sync batch must enforce bounded upper limit on events array."""
    # Oversized events array (>1000 items) -> 422
    huge_events = [{"event_id": f"ev-{i}", "event_type": "step"} for i in range(1001)]
    resp_huge = client.post(
        "/api/v1/sync/events",
        json={"student_id": "stu-001", "events": huge_events},
        headers=admin_headers,
    )
    assert resp_huge.status_code == 422

    # Valid array within bounds -> 200
    valid_events = [{"event_id": "ev-001", "event_type": "step"}]
    resp_valid = client.post(
        "/api/v1/sync/events",
        json={"student_id": "stu-001", "events": valid_events},
        headers=admin_headers,
    )
    assert resp_valid.status_code == 200


# ── 2. Mutating Operation Idempotency ────────────────────────────────────────

def test_payment_order_creation_idempotency(isolated_db: PlatformDatabase):
    """Calling create_payment_order twice with same idempotency_key returns identical order without duplication."""
    from central_platform.fees.service import FeeService

    org_id = "org-test-11"
    if not isolated_db.get_organization(org_id):
        isolated_db.create_organization(Organization(id=org_id, name="Phase 11 Org", slug="phase11-org"))

    student = User(
        id="stu-idem-01",
        organization_id=org_id,
        email="stu.idem@phase11.org",
        full_name="Student Idem",
        role=UserRole.STUDENT,
        is_active=True,
    )
    isolated_db.create_user(student)

    fee_svc = FeeService(isolated_db)
    fee_account = fee_svc.create_fee_account(student.id, org_id)
    inv = fee_svc.generate_invoice(fee_account, amount_due=1500.0, due_date="2026-12-31")

    fin_svc = FinanceService(isolated_db)
    key = "idemp-order-key-12345"

    order1 = fin_svc.create_payment_order(
        organization_id=org_id,
        invoice_id=inv.id,
        student_id=student.id,
        amount=1500.0,
        idempotency_key=key,
    )

    order2 = fin_svc.create_payment_order(
        organization_id=org_id,
        invoice_id=inv.id,
        student_id=student.id,
        amount=1500.0,
        idempotency_key=key,
    )

    # Identical order returned
    assert order1.id == order2.id
    assert order1.provider_order_id == order2.provider_order_id

    # Verify database has exactly 1 row
    with isolated_db._get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM payment_orders WHERE organization_id = ? AND idempotency_key = ?;",
            (org_id, key),
        ).fetchone()[0]
        assert count == 1


def test_sync_batch_replay_idempotency(isolated_db: PlatformDatabase):
    """Sync batch replay with same operation_id returns is_replay=True and idempotent result."""
    sync_svc = SyncService(db=isolated_db)
    op_id = "op-sync-replay-001"
    student_id = "stu-sync-01"
    events = [
        {"event_id": "ev-p11-1", "event_type": "turn_completed", "score": 1.0, "timestamp": "2026-10-15T12:00:00Z"},
        {"event_id": "ev-p11-2", "event_type": "turn_completed", "score": 0.8, "timestamp": "2026-10-15T12:01:00Z"},
    ]

    res1 = sync_svc.process_sync_batch(
        student_id=student_id,
        events=events,
        operation_id=op_id,
    )
    assert res1["ok"] is True
    assert res1["synced_count"] == 2
    assert res1.get("is_replay", False) is False

    # Second invocation with same operation_id must detect replay
    res2 = sync_svc.process_sync_batch(
        student_id=student_id,
        events=events,
        operation_id=op_id,
    )
    assert res2["ok"] is True
    assert res2["is_replay"] is True
    assert set(res2["acknowledged_ids"]) == {"ev-p11-1", "ev-p11-2"}


# ── 3. Distributed Sliding-Window Rate Limiting ──────────────────────────────

def test_atomic_sliding_window_rate_limiting(isolated_db: PlatformDatabase):
    """Atomic sliding window rate limiter correctly limits, tracks remaining, and records reset."""
    key = "ratelimit_key_phase11"
    limit = 3

    r1 = isolated_db.check_rate_limit_atomic(key, limit=limit, window_seconds=10.0, record=True)
    assert r1["allowed"] is True
    assert r1["current_count"] == 1
    assert r1["remaining"] == 2

    r2 = isolated_db.check_rate_limit_atomic(key, limit=limit, window_seconds=10.0, record=True)
    assert r2["allowed"] is True
    assert r2["current_count"] == 2
    assert r2["remaining"] == 1

    r3 = isolated_db.check_rate_limit_atomic(key, limit=limit, window_seconds=10.0, record=True)
    assert r3["allowed"] is True
    assert r3["current_count"] == 3
    assert r3["remaining"] == 0

    # 4th request must be rejected
    r4 = isolated_db.check_rate_limit_atomic(key, limit=limit, window_seconds=10.0, record=True)
    assert r4["allowed"] is False
    assert r4["remaining"] == 0
    assert r4["reset_seconds"] > 0.0


# ── 4. Error Envelopes and Header Preservation ───────────────────────────────

def test_error_envelope_and_header_preservation(client: TestClient):
    """HTTPException should preserve custom headers like WWW-Authenticate while returning structured envelope."""
    # Access protected route without credentials: expect 401 with WWW-Authenticate header
    resp = client.get("/api/v1/analytics/institutional/kpis")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers or "www-authenticate" in resp.headers

    body = resp.json()
    assert body["ok"] is False
    assert "error" in body
    assert body["error"]["code"] == "HTTP_401"
    assert "meta" in body
    assert "request_id" in body["meta"]
    assert "X-Request-ID" in resp.headers
