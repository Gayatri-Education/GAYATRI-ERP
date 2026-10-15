"""Reproduction and regression test suite for Phase 02: Database Lifecycle,
Dependency Injection, Transactions, and Durable State (ERP-002, ERP-005, ERP-021).
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db as canonical_get_db
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.finance.service import FinanceService
from central_platform.models.finance import LedgerEntryType


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_dependency_override_unification(client, tmp_path: Path):
    """ERP-005: Overriding canonical get_db must be honored across all route modules."""
    custom_db_path = str(tmp_path / "custom_override.db")
    custom_db = PlatformDatabase(db_path=custom_db_path)

    # Seed an organization and entitlement in custom_db
    with custom_db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-override-123', 'Override Org', 'override-org', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);"
        )
        conn.execute(
            "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
            "VALUES ('ent-ovr-1', 'org-override-123', 'custom_override_module', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);"
        )

    # Override the canonical get_db dependency in FastAPI
    app.dependency_overrides[canonical_get_db] = lambda: custom_db

    try:
        # Check that identity route reflects data from custom_db
        token = create_access_token("usr_admin", "super_admin", "org-override-123")
        resp = client.get(
            "/api/v1/identity/entitlements",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200 with overridden DB, got {resp.status_code}: {resp.text}"
        data = resp.json()
        entitlements = data.get("entitlements", [])
        assert any(e.get("module_key") == "custom_override_module" for e in entitlements), (
            f"Overridden canonical get_db was not used by route module; got: {data}"
        )
    finally:
        app.dependency_overrides.pop(canonical_get_db, None)
        custom_db.close()


def test_finance_webhook_transaction_rollback_on_failure(tmp_path: Path):
    """ERP-002: In finance webhook capture, failure during ledger or secondary write must roll back payment and receipt."""
    db_file = str(tmp_path / "tx_test.db")
    db = PlatformDatabase(db_path=db_file)
    svc = FinanceService(db)

    org_id = "org-test"
    inv_id = "inv-test-999"
    student_id = "std-test-1"
    account_id = "facc-test-1"

    # Seed prerequisites
    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES (?, 'Test Org', 'test-org', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);",
            (org_id,),
        )
        conn.execute(
            "INSERT INTO users (id, email, full_name, role, organization_id, created_at, updated_at) "
            "VALUES (?, 'std@test.com', 'Student Test', 'student', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);",
            (student_id, org_id),
        )
        conn.execute(
            "INSERT INTO fee_accounts (id, student_id, org_id, total_due, total_paid, balance_due, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 5000.0, 0.0, 5000.0, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);",
            (account_id, student_id, org_id),
        )
        conn.execute(
            "INSERT INTO invoices (id, fee_account_id, student_id, org_id, invoice_number, amount_due, amount_paid, status, due_date, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'INV-001', 5000.0, 0.0, 'pending', '2026-12-31', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);",
            (inv_id, account_id, student_id, org_id),
        )

    # Simulate failure in post_ledger_entry
    with patch.object(svc, "post_ledger_entry", side_effect=RuntimeError("Simulated ledger failure")):
        with pytest.raises(RuntimeError, match="Simulated ledger failure"):
            svc.process_payment_webhook(
                organization_id=org_id,
                provider="razorpay",
                event_id="evt_fail_1",
                event_type="payment.captured",
                payload={"invoice_id": inv_id, "amount": 2500.0, "payment_id": "pay_fail_1"},
            )

    # Verify atomic rollback: no payment inserted, no receipt inserted, invoice untouched
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM payments WHERE invoice_id = ?;", (inv_id,))
        assert cur.fetchone()[0] == 0, "Payment record must be rolled back on error"

        cur.execute("SELECT COUNT(*) FROM receipts;")
        assert cur.fetchone()[0] == 0, "Receipt record must be rolled back on error"

        cur.execute("SELECT amount_paid, status FROM invoices WHERE id = ?;", (inv_id,))
        row = cur.fetchone()
        assert row[0] == 0.0, "Invoice amount_paid must not be mutated on rollback"
        assert row[1] == "pending", "Invoice status must remain pending on rollback"

    db.close()


def test_finance_webhook_idempotency(tmp_path: Path):
    """ERP-002: Re-delivering identical webhook event must return duplicate indicator without duplicate records."""
    db_file = str(tmp_path / "idempotent_test.db")
    db = PlatformDatabase(db_path=db_file)
    svc = FinanceService(db)

    org_id = "org-test"
    inv_id = "inv-test-idemp"
    student_id = "std-test-idemp"
    account_id = "facc-test-idemp"

    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) VALUES (?, 'Test Org', 'test-org', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);",
            (org_id,),
        )
        conn.execute(
            "INSERT INTO users (id, email, full_name, role, organization_id, created_at, updated_at) VALUES (?, 'std2@test.com', 'Student Test 2', 'student', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);",
            (student_id, org_id),
        )
        conn.execute(
            "INSERT INTO fee_accounts (id, student_id, org_id, total_due, total_paid, balance_due, status, created_at, updated_at) VALUES (?, ?, ?, 5000.0, 0.0, 5000.0, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);",
            (account_id, student_id, org_id),
        )
        conn.execute(
            "INSERT INTO invoices (id, fee_account_id, student_id, org_id, invoice_number, amount_due, amount_paid, status, due_date, created_at, updated_at) VALUES (?, ?, ?, ?, 'INV-002', 5000.0, 0.0, 'pending', '2026-12-31', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);",
            (inv_id, account_id, student_id, org_id),
        )

    payload = {"invoice_id": inv_id, "amount": 1000.0, "payment_id": "pay_idemp_1"}

    # First delivery
    res1 = svc.process_payment_webhook(
        organization_id=org_id,
        provider="razorpay",
        event_id="evt_idemp_1",
        event_type="payment.captured",
        payload=payload,
    )
    assert res1.get("is_duplicate") is not True

    # Second delivery with identical event_id
    res2 = svc.process_payment_webhook(
        organization_id=org_id,
        provider="razorpay",
        event_id="evt_idemp_1",
        event_type="payment.captured",
        payload=payload,
    )
    assert res2.get("is_duplicate") is True

    # Verify no duplicate payments
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM payments WHERE invoice_id = ?;", (inv_id,))
        assert cur.fetchone()[0] == 1, "Exactly one payment must exist"

        cur.execute("SELECT COUNT(*) FROM receipts;")
        assert cur.fetchone()[0] == 1, "Exactly one receipt must exist"

    db.close()


def test_database_isolation_between_instances(tmp_path: Path):
    """ERP-021: Independent database paths must guarantee 100% data isolation."""
    db1_path = str(tmp_path / "isolated_1.db")
    db2_path = str(tmp_path / "isolated_2.db")

    db1 = PlatformDatabase(db_path=db1_path)
    db2 = PlatformDatabase(db_path=db2_path)

    with db1._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) VALUES ('org-db1-only', 'Org 1', 'org-1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);"
        )

    with db2._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM organizations WHERE id = 'org-db1-only';")
        assert cur.fetchone()[0] == 0, "db2 must not see organizations inserted into db1"

    db1.close()
    db2.close()
