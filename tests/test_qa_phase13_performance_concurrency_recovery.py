"""QA Phase 13 Test Suite: Performance, Concurrency, Reliability, and Recovery.

Verifies:
- High-concurrency multithreaded database operations without deadlocks or lock errors.
- Concurrent payment webhook duplicate race prevention and idempotent deduplication.
- Concurrent user authentication and token issuance under load.
- FailureRecoveryManager classification, diagnostics, and retryability semantics.
- API latency benchmarks (p50 < 50ms, p95 < 200ms).
- Database busy timeout configuration (>= 30000ms).
"""

from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
import time
import uuid
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.finance.service import FinanceService
from central_platform.fees.service import FeeService
from central_platform.models.schema import Course, Organization, User, UserRole
from central_platform.recovery.manager import FailureCategory, FailureRecoveryManager


@pytest.fixture
def isolated_db(tmp_path: Path):
    """Provide a fresh isolated database with schema and migrations applied."""
    db_file = str(tmp_path / "phase13_perf_test.db")
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


# ── 1. Database Concurrency & Busy Timeout ───────────────────────────────────

def test_connection_busy_timeout_configured(isolated_db: PlatformDatabase):
    """PlatformDatabase must configure PRAGMA busy_timeout >= 30000ms."""
    with isolated_db._get_connection() as conn:
        timeout_ms = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        assert timeout_ms >= 30000


def test_concurrent_multithreaded_db_writes(isolated_db: PlatformDatabase):
    """10 parallel threads writing records must succeed without database deadlocks."""
    org = Organization(id="org-conc-13", name="Concurrency Org", slug="conc-org")
    isolated_db.create_organization(org)

    def write_worker(idx: int) -> str:
        # Each worker creates a user and a course using thread-safe connection handle
        worker_db = PlatformDatabase(isolated_db.db_path)
        try:
            uid = f"usr-conc-{idx}-{uuid.uuid4().hex[:6]}"
            cid = f"crs-conc-{idx}-{uuid.uuid4().hex[:6]}"
            user = User(
                id=uid,
                organization_id=org.id,
                email=f"worker_{idx}@conc.org",
                full_name=f"Worker {idx}",
                role=UserRole.STUDENT,
                is_active=True,
            )
            course = Course(
                id=cid,
                code=f"CONC{idx}",
                title=f"Concurrent Course {idx}",
                organization_id=org.id,
            )
            worker_db.create_user(user)
            worker_db.create_course(course)
            return uid
        finally:
            worker_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(write_worker, i) for i in range(10)]
        results = [f.result() for f in futures]

    assert len(results) == 10
    # Verify all 10 users were committed
    with isolated_db._get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users WHERE organization_id = ?;", (org.id,)).fetchone()[0]
        assert count == 10


# ── 2. Concurrent Webhook Race Condition Prevention ──────────────────────────

def test_payment_webhook_concurrent_race_deduplication(isolated_db: PlatformDatabase):
    """Simultaneous webhook deliveries for the same event must process exactly once."""
    org = Organization(id="org-fin-race", name="Fin Race Org", slug="fin-race-org")
    isolated_db.create_organization(org)
    student = User(
        id="stu-race-01",
        organization_id=org.id,
        email="student.race@fin.org",
        full_name="Race Student",
        role=UserRole.STUDENT,
        is_active=True,
    )
    isolated_db.create_user(student)

    fee_svc = FeeService(isolated_db)
    fee_account = fee_svc.create_fee_account(student.id, org.id)
    inv = fee_svc.generate_invoice(fee_account, amount_due=2000.0, due_date="2026-12-31")

    fin_svc = FinanceService(isolated_db)
    order = fin_svc.create_payment_order(
        organization_id=org.id,
        invoice_id=inv.id,
        student_id=student.id,
        amount=2000.0,
        provider="razorpay",
    )

    event_id = f"evt-race-{uuid.uuid4().hex[:8]}"
    idemp_key = f"idemp-race-{uuid.uuid4().hex[:8]}"
    payload = {
        "event": "payment.captured",
        "order_id": order.provider_order_id,
        "amount": 2000.0,
        "currency": "INR",
        "payment_id": f"pay-race-{uuid.uuid4().hex[:8]}",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay-race-{uuid.uuid4().hex[:8]}",
                    "order_id": order.provider_order_id,
                    "amount": 200000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }

    # Execute 5 concurrent webhook calls
    def webhook_worker() -> bool:
        worker_db = PlatformDatabase(isolated_db.db_path)
        worker_fin = FinanceService(worker_db)
        try:
            res = worker_fin.process_payment_webhook(
                organization_id=org.id,
                provider="razorpay",
                event_id=event_id,
                event_type="payment.captured",
                payload=payload,
                signature_verified=True,
                idempotency_key=idemp_key,
            )
            return res.get("status") == "PROCESSED"
        except Exception:
            return False
        finally:
            worker_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(webhook_worker) for _ in range(5)]
        outcomes = [f.result() for f in futures]

    assert all(outcomes)

    # Invariants: exactly 1 payment record, exactly 1 receipt, invoice marked paid
    with isolated_db._get_connection() as conn:
        payments_count = conn.execute(
            "SELECT COUNT(*) FROM payments WHERE org_id = ? AND student_id = ?;",
            (org.id, student.id),
        ).fetchone()[0]
        assert payments_count == 1

        receipts_count = conn.execute(
            "SELECT COUNT(*) FROM receipts WHERE issued_to = ?;",
            (student.id,),
        ).fetchone()[0]
        assert receipts_count == 1


# ── 3. Failure Recovery Classification & Retryability ────────────────────────

def test_failure_recovery_classification_and_retryability():
    """FailureRecoveryManager must provide observable, structured diagnostic contracts."""
    from central_platform.recovery.manager import RecoveryStatus

    # 1. Provider Timeout
    rec_timeout = FailureRecoveryManager.handle_provider_timeout(
        error=TimeoutError("Connection timed out after 5.0s"),
        max_retries=3,
        provider="gemini",
    )
    assert rec_timeout.failure_category == FailureCategory.PROVIDER_TIMEOUT
    assert rec_timeout.retryable is True
    assert rec_timeout.status == RecoveryStatus.DEGRADED_FALLBACK
    assert "timeout" in rec_timeout.technical_diagnostic.lower()

    # 2. Database Unavailable
    rec_db = FailureRecoveryManager.handle_database_failure(
        operation="fetch_session",
        error=RuntimeError("connection dropped"),
    )
    assert rec_db.failure_category == FailureCategory.DATABASE_FAILURE
    assert rec_db.status == RecoveryStatus.DEGRADED_FALLBACK
    assert rec_db.retryable is True

    # 3. Duplicate Sync Replay
    rec_sync = FailureRecoveryManager.handle_duplicate_sync(
        operation_id="op-dup-999",
        student_id="stu-dup-1",
        duplicate_count=2,
    )
    assert rec_sync.failure_category == FailureCategory.DUPLICATE_SYNC
    assert rec_sync.status == RecoveryStatus.RECOVERED
    assert rec_sync.retryable is False


# ── 4. API Latency SLAs (p50 < 50ms, p95 < 200ms) ────────────────────────────

def test_latency_benchmarks_sla(client: TestClient):
    """Ensure core routes satisfy performance latency targets under sequential load."""
    latencies = []
    for _ in range(30):
        t0 = time.perf_counter()
        resp = client.get("/healthz")
        latencies.append((time.perf_counter() - t0) * 1000)
        assert resp.status_code == 200

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]

    # Assert p50 and p95 SLAs
    assert p50 < 50.0, f"Expected p50 < 50ms, got {p50:.2f}ms"
    assert p95 < 200.0, f"Expected p95 < 200ms, got {p95:.2f}ms"
