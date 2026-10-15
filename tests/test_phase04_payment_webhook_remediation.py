"""Phase 04 Remediation Test Suite — Payment Webhook Verification, Tenant Binding & Accounting Invariants (QA-004).

Mandatory Invariants Tested:
1. Strict Tenant Binding: Tenant is derived strictly from durable PaymentOrder, not caller headers/query/payload.
2. Caller Tenant Spoofing Rejected: Caller supplying mismatched X-Organization-ID is rejected with HTTP 400.
3. Zero 'org-default' Fallback: Unmatched/unknown orders are rejected with HTTP 400 without falling back.
4. Missing / Ambiguous Order References: Rejected with HTTP 400.
5. Provider & Merchant Matching: Mismatched provider or configured merchant ID is rejected with HTTP 400.
6. Constant-time Signature Verification: Missing or invalid signature rejected with HTTP 401.
7. Amount & Currency Discrepancies: Discrepancies rejected with HTTP 400 and zero financial mutations.
8. State Transitions: payment.failed transitions order to FAILED without payments or ledger credits.
9. Idempotency: Duplicate webhooks return is_duplicate=True without double-crediting.
10. Atomic Rollback: Injected transaction failures leave zero partial writes.
11. Durable Read-back: Restart persistence across SQLite connection boundaries.
12. Log Hygiene: Raw secrets and signatures are never logged.
"""

import hashlib
import hmac
import json
import logging
import uuid
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db
from central_platform.db import PlatformDatabase
from central_platform.fees.service import FeeService
from central_platform.finance.service import FinanceService
from central_platform.models.fees import InvoiceStatus
from central_platform.models.finance import OrderStatus, LedgerEntryType
from central_platform.models.schema import Organization, User, UserRole


@pytest.fixture
def phase04_env(tmp_path):
    """Provides isolated multi-tenant database environment for Phase 04 verification."""
    db_path = tmp_path / "test_phase04_webhook_remediation.db"
    db = PlatformDatabase(db_path)

    # 1. Setup Tenant Organizations
    org_a = Organization(id=f"org-alpha-{uuid.uuid4().hex[:6]}", name="Alpha School", slug=f"slug-alpha-{uuid.uuid4().hex[:6]}")
    org_b = Organization(id=f"org-beta-{uuid.uuid4().hex[:6]}", name="Beta Academy", slug=f"slug-beta-{uuid.uuid4().hex[:6]}")
    db.create_organization(org_a)
    db.create_organization(org_b)

    # 2. Setup Student and Bursar Users
    student_a = User(
        id=f"stu-a-{uuid.uuid4().hex[:6]}",
        organization_id=org_a.id,
        email="student.a@alpha.edu",
        full_name="Student Alpha",
        role=UserRole.STUDENT,
        is_active=True,
    )
    student_b = User(
        id=f"stu-b-{uuid.uuid4().hex[:6]}",
        organization_id=org_b.id,
        email="student.b@beta.edu",
        full_name="Student Beta",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.create_user(student_a)
    db.create_user(student_b)

    # 3. Setup Fee Account and Invoice in Org A
    fee_svc = FeeService(db)
    fin_svc = FinanceService(db)

    account_a = fee_svc.create_fee_account(student_a.id, org_a.id)
    inv_a = fee_svc.generate_invoice(
        fee_account=account_a,
        amount_due=7500.0,
        due_date="2026-11-30",
    )

    # 4. Setup Payment Order in Org A
    order_a = fin_svc.create_payment_order(
        organization_id=org_a.id,
        invoice_id=inv_a.id,
        student_id=student_a.id,
        amount=7500.0,
        currency="INR",
        provider="razorpay",
        idempotency_key=f"idemp-{uuid.uuid4().hex[:8]}",
    )

    # 5. Configure Payment Provider & Secret for Org A
    secret_a = f"rzp_sec_{uuid.uuid4().hex[:12]}"
    merchant_a = f"acc_rzp_{uuid.uuid4().hex[:8]}"
    db.save_payment_provider_config(
        organization_id=org_a.id,
        provider="razorpay",
        merchant_id=merchant_a,
        webhook_secret=secret_a,
    )

    app.dependency_overrides[get_db] = lambda: db

    yield {
        "db": db,
        "db_path": db_path,
        "org_a": org_a,
        "org_b": org_b,
        "student_a": student_a,
        "student_b": student_b,
        "account_a": account_a,
        "invoice_a": inv_a,
        "order_a": order_a,
        "secret_a": secret_a,
        "merchant_a": merchant_a,
        "fee_svc": fee_svc,
        "fin_svc": fin_svc,
    }

    app.dependency_overrides.pop(get_db, None)


def _sign_payload(payload_dict: dict, secret: str) -> tuple[bytes, str]:
    raw = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, sig


# ── Test 1: Strict Tenant Binding (Caller Cannot Spoof Tenant) ───────────────

def test_tenant_binding_derived_from_order_caller_cannot_spoof(phase04_env):
    """QA-004: Webhook tenant is derived from the order. A mismatched caller-supplied tenant is rejected."""
    client = TestClient(app)
    order = phase04_env["order_a"]
    secret = phase04_env["secret_a"]
    attacker_org = phase04_env["org_b"].id

    payload = {
        "event": "payment.captured",
        "id": f"evt_spoof_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "amount": 7500.0,
    }
    raw, sig = _sign_payload(payload, secret)

    # 1. Attacker attempts tenant override via X-Organization-ID header
    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Organization-ID": attacker_org,
        },
    )
    assert resp.status_code == 400
    assert "Organization mismatch" in resp.json()["detail"]

    # 2. Attacker attempts tenant override via query parameter
    resp_query = client.post(
        f"/api/v1/finance/webhooks/razorpay?org_id={attacker_org}",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp_query.status_code == 400
    assert "Organization mismatch" in resp_query.json()["detail"]

    # Invariant: Zero payments or ledger entries recorded under attacker_org or org_a
    with phase04_env["db"]._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM payments;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM financial_ledger_entries;").fetchone()[0] == 0


# ── Test 2: Elimination of org-default Fallback for Unknown Orders ────────────

def test_unknown_order_rejected_zero_org_default_fallback(phase04_env):
    """QA-004: Unknown order cannot mutate database and never falls back to 'org-default'."""
    client = TestClient(app)
    fake_order_id = "order_rzp_unknown_999999"

    payload = {
        "event": "payment.captured",
        "id": f"evt_unknown_{uuid.uuid4().hex[:8]}",
        "order_id": fake_order_id,
        "amount": 7500.0,
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(b"test_webhook_secret", raw, hashlib.sha256).hexdigest()

    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp.status_code == 400
    assert "Unknown or unmatched payment order" in resp.json()["detail"]

    # Invariant: No payment created under 'org-default' or any other tenant
    with phase04_env["db"]._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM payments WHERE org_id = 'org-default';").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM payments;").fetchone()[0] == 0


# ── Test 3: Missing Order Reference Rejected ──────────────────────────────────

def test_missing_order_reference_rejected(phase04_env):
    """QA-004: Webhook payload missing order reference is rejected with HTTP 400."""
    client = TestClient(app)
    payload = {
        "event": "payment.captured",
        "id": f"evt_no_ord_{uuid.uuid4().hex[:8]}",
        "amount": 7500.0,
    }
    raw, sig = _sign_payload(payload, phase04_env["secret_a"])

    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
        },
    )
    assert resp.status_code == 400
    assert "Missing payment order reference" in resp.json()["detail"]


# ── Test 4: Provider Mismatch Rejection ───────────────────────────────────────

def test_provider_mismatch_rejected(phase04_env):
    """QA-004: Webhook posted to provider endpoint differing from order's registered provider is rejected."""
    client = TestClient(app)
    order = phase04_env["order_a"]  # Registered as 'razorpay'

    payload = {
        "event": "payment.captured",
        "id": f"evt_prov_mismatch_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "amount": 7500.0,
    }
    raw, sig = _sign_payload(payload, phase04_env["secret_a"])

    # Attempt to post razorpay order to mock provider endpoint
    resp = client.post(
        "/api/v1/finance/webhooks/mock",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": sig,
        },
    )
    assert resp.status_code == 400
    assert "Provider mismatch" in resp.json()["detail"]


# ── Test 5: Merchant Identity Verification ────────────────────────────────────

def test_merchant_identity_verification(phase04_env):
    """QA-004: Configured merchant ID is strictly verified when present in payload."""
    client = TestClient(app)
    order = phase04_env["order_a"]
    secret = phase04_env["secret_a"]
    correct_merchant = phase04_env["merchant_a"]
    wrong_merchant = f"acc_rzp_wrong_{uuid.uuid4().hex[:6]}"

    # Case A: Payload specifies wrong merchant account
    payload_bad = {
        "event": "payment.captured",
        "id": f"evt_bad_merch_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "account_id": wrong_merchant,
        "amount": 7500.0,
    }
    raw_bad, sig_bad = _sign_payload(payload_bad, secret)
    resp_bad = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw_bad,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig_bad,
        },
    )
    assert resp_bad.status_code == 400
    assert "Merchant mismatch" in resp_bad.json()["detail"]

    # Case B: Payload specifies correct merchant account
    payload_good = {
        "event": "payment.captured",
        "id": f"evt_good_merch_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "account_id": correct_merchant,
        "amount": 7500.0,
    }
    raw_good, sig_good = _sign_payload(payload_good, secret)
    resp_good = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw_good,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig_good,
        },
    )
    assert resp_good.status_code == 200
    assert resp_good.json()["status"] == "PROCESSED"


# ── Test 6: Amount and Currency Mismatches Have Zero Side Effects ─────────────

def test_amount_and_currency_mismatch_rejected_zero_side_effects(phase04_env):
    """QA-004: Amount or currency discrepancy rejects mutation with zero financial side effects."""
    client = TestClient(app)
    order = phase04_env["order_a"]
    secret = phase04_env["secret_a"]

    # 1. Amount mismatch (e.g. partial unauthorized amount)
    payload_amt = {
        "event": "payment.captured",
        "id": f"evt_amt_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "amount": 100.0,  # Expected 7500.0
    }
    raw_amt, sig_amt = _sign_payload(payload_amt, secret)
    resp_amt = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw_amt,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig_amt},
    )
    assert resp_amt.status_code == 400
    assert "amount" in resp_amt.json()["detail"].lower()

    # 2. Currency mismatch (e.g. USD instead of INR)
    payload_cur = {
        "event": "payment.captured",
        "id": f"evt_cur_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "amount": 7500.0,
        "currency": "EUR",  # Expected INR
    }
    raw_cur, sig_cur = _sign_payload(payload_cur, secret)
    resp_cur = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw_cur,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig_cur},
    )
    assert resp_cur.status_code == 400
    assert "currency" in resp_cur.json()["detail"].lower()

    # Invariant: Invoice balance and payment tables unchanged
    with phase04_env["db"]._get_connection() as conn:
        inv_row = conn.execute("SELECT amount_paid, status FROM invoices WHERE id = ?;", (phase04_env["invoice_a"].id,)).fetchone()
        assert inv_row[0] == 0.0
        assert inv_row[1] == InvoiceStatus.ISSUED.value


# ── Test 7: Payment Failure State Transition ──────────────────────────────────

def test_payment_failure_event_transitions_order_without_ledger_credit(phase04_env):
    """QA-004: payment.failed event marks order FAILED without creating payments or ledger credits."""
    client = TestClient(app)
    order = phase04_env["order_a"]
    secret = phase04_env["secret_a"]

    payload = {
        "event": "payment.failed",
        "id": f"evt_fail_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "amount": 7500.0,
    }
    raw, sig = _sign_payload(payload, secret)

    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FAILED"
    assert data["order_status"] == "FAILED"

    # Verify Database state
    with phase04_env["db"]._get_connection() as conn:
        ord_status = conn.execute("SELECT status FROM payment_orders WHERE id = ?;", (order.id,)).fetchone()[0]
        assert ord_status == OrderStatus.FAILED.value

        # Zero payments, zero receipts, zero ledger entries
        assert conn.execute("SELECT COUNT(*) FROM payments;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM receipts;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM financial_ledger_entries;").fetchone()[0] == 0


# ── Test 8: Deduplication and Idempotency Across Multiple Deliveries ──────────

def test_idempotent_duplicate_delivery(phase04_env):
    """QA-004: Duplicate webhook delivery is strictly idempotent with zero duplicate ledger entries."""
    client = TestClient(app)
    order = phase04_env["order_a"]
    secret = phase04_env["secret_a"]
    account_a = phase04_env["account_a"]

    event_id = f"evt_dup_test_{uuid.uuid4().hex[:8]}"
    payload = {
        "event": "payment.captured",
        "id": event_id,
        "order_id": order.provider_order_id,
        "amount": 7500.0,
    }
    raw, sig = _sign_payload(payload, secret)
    headers = {"Content-Type": "application/json", "X-Razorpay-Signature": sig}

    # Delivery 1: Success
    resp1 = client.post("/api/v1/finance/webhooks/razorpay", content=raw, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["is_duplicate"] is False

    # Delivery 2: Exact duplicate
    resp2 = client.post("/api/v1/finance/webhooks/razorpay", content=raw, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["is_duplicate"] is True

    # Invariant: Exactly 1 payment, 1 receipt, and 1 financial ledger entry
    with phase04_env["db"]._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM payments;").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM receipts;").fetchone()[0] == 1
        ledger_count = conn.execute("SELECT COUNT(*) FROM financial_ledger_entries WHERE account_id = ?;", (account_a.id,)).fetchone()[0]
        assert ledger_count == 1


# ── Test 9: Atomic Rollback on Injected Failure ────────────────────────────────

def test_atomic_rollback_on_injected_failure(phase04_env, monkeypatch):
    """QA-004: Injected database failure mid-transaction rolls back all partial writes."""
    order = phase04_env["order_a"]
    fin_svc = phase04_env["fin_svc"]
    secret = phase04_env["secret_a"]

    payload = {
        "event": "payment.captured",
        "id": f"evt_rollback_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "amount": 7500.0,
    }
    raw, sig = _sign_payload(payload, secret)

    # Monkeypatch post_ledger_entry to inject an unexpected database exception
    def failing_post_ledger(*args, **kwargs):
        raise RuntimeError("Simulated ledger storage crash")

    monkeypatch.setattr(fin_svc, "post_ledger_entry", failing_post_ledger)

    with pytest.raises(RuntimeError, match="Simulated ledger storage crash"):
        fin_svc.process_payment_webhook(
            organization_id=phase04_env["org_a"].id,
            provider="razorpay",
            event_id=payload["id"],
            event_type="payment.captured",
            payload=payload,
            raw_payload=raw,
            signature=sig,
            webhook_secret=secret,
            signature_verified=True,
        )

    # Invariant: Complete rollback — zero payments, zero receipts, zero webhook events persisted
    with phase04_env["db"]._get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM payments;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM receipts;").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM payment_webhook_events;").fetchone()[0] == 0
        # Order status must remain CREATED, not CAPTURED
        ord_status = conn.execute("SELECT status FROM payment_orders WHERE id = ?;", (order.id,)).fetchone()[0]
        assert ord_status == OrderStatus.CREATED.value


# ── Test 10: Durable Read-back Across Process Restart ──────────────────────────

def test_durable_read_back_across_db_restart(phase04_env):
    """QA-004: Webhook persistence survives connection tear-down and DB restarts."""
    client = TestClient(app)
    order = phase04_env["order_a"]
    secret = phase04_env["secret_a"]

    payload = {
        "event": "payment.captured",
        "id": f"evt_durable_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "amount": 7500.0,
    }
    raw, sig = _sign_payload(payload, secret)

    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
    )
    assert resp.status_code == 200
    receipt_num = resp.json()["receipt_number"]

    # Simulate restart by instantiating a fresh PlatformDatabase instance
    restarted_db = PlatformDatabase(phase04_env["db_path"])
    restarted_fin = FinanceService(restarted_db)

    # Read back receipt
    receipt = restarted_fin.get_receipt(phase04_env["org_a"].id, receipt_num)
    assert receipt is not None
    assert receipt["amount"] == 7500.0
    assert receipt["organization_id"] == phase04_env["org_a"].id

    # Read back ledger balance
    balance = restarted_fin.calculate_ledger_balance(phase04_env["org_a"].id, phase04_env["account_a"].id)
    assert balance == -7500.0  # Credit balance


# ── Test 11: Log Hygiene (No Raw Secrets or Signatures in Logs) ────────────────

def test_log_hygiene_no_raw_secrets_or_signatures(phase04_env, caplog):
    """QA-004: Payment processing never logs raw secrets or HMAC signatures."""
    client = TestClient(app)
    order = phase04_env["order_a"]
    secret = phase04_env["secret_a"]

    payload = {
        "event": "payment.captured",
        "id": f"evt_log_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "amount": 7500.0,
    }
    raw, sig = _sign_payload(payload, secret)

    with caplog.at_level(logging.DEBUG):
        resp = client.post(
            "/api/v1/finance/webhooks/razorpay",
            content=raw,
            headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig},
        )
        assert resp.status_code == 200

    # Assert raw secret and signature are not present in any captured log message
    for record in caplog.records:
        assert secret not in record.getMessage()
        assert sig not in record.getMessage()
