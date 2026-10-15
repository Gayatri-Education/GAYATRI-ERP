"""Phase 03 QA Test Suite — Finance Integrity, Webhooks, Transactions, and Persisted Receipts.

Target Findings:
- ERP-001: Webhook signature verification, trust boundary, and provider enforcement
- ERP-002: Atomic financial state mutations and idempotent deduplication
- ERP-009: Persisted receipt retrieval, verification, and role/tenant authorization
"""

import hashlib
import hmac
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.fees.service import FeeService
from central_platform.finance.service import FinanceService
from central_platform.models.fees import InvoiceStatus
from central_platform.models.finance import OrderStatus
from central_platform.models.schema import Organization, User, UserRole


@pytest.fixture
def qa_finance_env(tmp_path):
    """Fixture providing isolated database, organizations, users, and fee accounts."""
    db_path = tmp_path / "test_qa_phase03.db"
    db = PlatformDatabase(db_path)

    # 1. Setup Organization A and B
    org_a_id = f"org-a-{uuid.uuid4().hex[:6]}"
    org_b_id = f"org-b-{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org_a_id, name="Org A Academy", slug=f"org-a-{org_a_id}"))
    db.create_organization(Organization(id=org_b_id, name="Org B School", slug=f"org-b-{org_b_id}"))

    # 2. Setup Users
    student_a = User(
        id=f"stu-a-{uuid.uuid4().hex[:6]}",
        organization_id=org_a_id,
        email="student.a@orga.edu",
        full_name="Student A",
        role=UserRole.STUDENT,
        is_active=True,
    )
    student_b = User(
        id=f"stu-b-{uuid.uuid4().hex[:6]}",
        organization_id=org_a_id,
        email="student.b@orga.edu",
        full_name="Student B",
        role=UserRole.STUDENT,
        is_active=True,
    )
    bursar_a = User(
        id=f"bursar-a-{uuid.uuid4().hex[:6]}",
        organization_id=org_a_id,
        email="bursar@orga.edu",
        full_name="Bursar A",
        role=UserRole.ORG_ADMIN,
        is_active=True,
    )
    admin_b = User(
        id=f"admin-b-{uuid.uuid4().hex[:6]}",
        organization_id=org_b_id,
        email="admin@orgb.edu",
        full_name="Admin B",
        role=UserRole.ORG_ADMIN,
        is_active=True,
    )
    db.create_user(student_a)
    db.create_user(student_b)
    db.create_user(bursar_a)
    db.create_user(admin_b)

    # 3. Setup Fee Account, Invoice, and Payment Order in Org A
    fee_svc = FeeService(db)
    fin_svc = FinanceService(db)

    account_a = fee_svc.create_fee_account(student_a.id, org_a_id)
    inv_a = fee_svc.generate_invoice(
        fee_account=account_a,
        amount_due=5000.0,
        due_date="2026-12-31",
    )
    order_a = fin_svc.create_payment_order(
        organization_id=org_a_id,
        invoice_id=inv_a.id,
        student_id=student_a.id,
        amount=5000.0,
        currency="INR",
        provider="razorpay",
        idempotency_key=f"idemp-{uuid.uuid4().hex[:8]}",
    )

    # Dependency override for FastAPI app
    app.dependency_overrides[get_db] = lambda: db

    yield {
        "db": db,
        "org_a_id": org_a_id,
        "org_b_id": org_b_id,
        "student_a": student_a,
        "student_b": student_b,
        "bursar_a": bursar_a,
        "admin_b": admin_b,
        "account_a": account_a,
        "invoice_a": inv_a,
        "order_a": order_a,
        "fin_svc": fin_svc,
    }

    app.dependency_overrides.pop(get_db, None)


def test_webhook_missing_signature_rejected_with_401(qa_finance_env):
    """ERP-001: Webhook without signature header must be rejected with HTTP 401."""
    client = TestClient(app)
    order = qa_finance_env["order_a"]

    payload = {
        "event": "payment.captured",
        "id": "evt_test_unsigned",
        "order_id": order.provider_order_id,
        "amount": 5000.0,
    }

    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401, f"Expected 401 Unauthorized for unsigned webhook, got {resp.status_code}: {resp.text}"

    # Invariant: No payment, receipt, or ledger mutation occurred
    with qa_finance_env["db"]._get_connection() as conn:
        payments = conn.execute("SELECT COUNT(*) FROM payments;").fetchone()[0]
        receipts = conn.execute("SELECT COUNT(*) FROM receipts;").fetchone()[0]
        ledger = conn.execute("SELECT COUNT(*) FROM financial_ledger_entries;").fetchone()[0]
        assert payments == 0
        assert receipts == 0
        assert ledger == 0


def test_webhook_invalid_signature_rejected_with_401(qa_finance_env):
    """ERP-001: Webhook with forged/tampered signature header must be rejected with HTTP 401."""
    client = TestClient(app)
    order = qa_finance_env["order_a"]

    payload = {
        "event": "payment.captured",
        "id": "evt_test_forged",
        "order_id": order.provider_order_id,
        "amount": 5000.0,
    }

    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_forged_signature_hex",
        },
    )
    assert resp.status_code == 401, f"Expected 401 Unauthorized for invalid signature, got {resp.status_code}: {resp.text}"


def test_webhook_tampered_payload_rejected_with_401(qa_finance_env):
    """ERP-001: Webhook whose body payload was altered after signing must be rejected with HTTP 401."""
    client = TestClient(app)
    order = qa_finance_env["order_a"]
    secret = "rzp_test_secret_qa"

    original_payload = {
        "event": "payment.captured",
        "id": "evt_test_tampered",
        "order_id": order.provider_order_id,
        "amount": 5000.0,
    }
    raw_original = json.dumps(original_payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_original, hashlib.sha256).hexdigest()

    # Tamper the amount
    tampered_payload = dict(original_payload)
    tampered_payload["amount"] = 50.0  # Tampered amount

    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=json.dumps(tampered_payload),
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Webhook-Secret": secret,
        },
    )
    assert resp.status_code == 401, f"Expected 401 for tampered payload, got {resp.status_code}: {resp.text}"


def test_webhook_unknown_provider_rejected_with_400(qa_finance_env):
    """ERP-001: Webhook route with unknown provider must return HTTP 400 Bad Request."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/finance/webhooks/unsupported_gateway",
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "some_sig",
        },
    )
    assert resp.status_code == 400, f"Expected 400 for unknown provider, got {resp.status_code}: {resp.text}"


def test_webhook_valid_signature_processes_and_records_truthful_verification(qa_finance_env):
    """ERP-001 & ERP-002: Validly signed webhook executes atomic commit with truthful signature_verified=1."""
    client = TestClient(app)
    order = qa_finance_env["order_a"]
    invoice = qa_finance_env["invoice_a"]
    secret = "rzp_test_secret_qa"

    payload_dict = {
        "event": "payment.captured",
        "id": f"evt_valid_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "payment_id": f"pay_rzp_{uuid.uuid4().hex[:8]}",
        "amount": 5000.0,
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    resp = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
            "X-Webhook-Secret": secret,
        },
    )
    assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "PROCESSED"
    assert data["is_duplicate"] is False
    assert "payment_id" in data
    assert "receipt_number" in data

    # Verify Database State
    with qa_finance_env["db"]._get_connection() as conn:
        # Check order updated to CAPTURED
        ord_row = conn.execute("SELECT status FROM payment_orders WHERE id = ?;", (order.id,)).fetchone()
        assert ord_row[0] == OrderStatus.CAPTURED.value

        # Check invoice marked paid
        inv_row = conn.execute("SELECT status, amount_paid FROM invoices WHERE id = ?;", (invoice.id,)).fetchone()
        assert inv_row[0] == InvoiceStatus.PAID.value
        assert inv_row[1] == 5000.0

        # Check ledger entry exists
        ledger_rows = conn.execute("SELECT amount, entry_type FROM financial_ledger_entries WHERE account_id = ?;", (qa_finance_env["account_a"].id,)).fetchall()
        assert len(ledger_rows) == 1
        assert ledger_rows[0][0] == 5000.0
        assert ledger_rows[0][1] == "CREDIT"

        # Check payment_webhook_events recorded signature_verified == 1 truthfully
        evt_row = conn.execute("SELECT signature_verified, status FROM payment_webhook_events WHERE event_id = ?;", (payload_dict["id"],)).fetchone()
        assert evt_row is not None
        assert evt_row[0] == 1
        assert evt_row[1] == "PROCESSED"


def test_webhook_idempotent_duplicate_delivery(qa_finance_env):
    """ERP-002: Repeated delivery of the exact same webhook must be idempotent with 0 duplicate ledger postings."""
    client = TestClient(app)
    order = qa_finance_env["order_a"]
    secret = "rzp_test_secret_qa"

    event_id = f"evt_dup_{uuid.uuid4().hex[:8]}"
    payload_dict = {
        "event": "payment.captured",
        "id": event_id,
        "order_id": order.provider_order_id,
        "payment_id": f"pay_rzp_{uuid.uuid4().hex[:8]}",
        "amount": 5000.0,
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
        "X-Webhook-Secret": secret,
    }

    # Delivery 1: Success
    resp1 = client.post("/api/v1/finance/webhooks/razorpay", content=raw_bytes, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["is_duplicate"] is False

    # Delivery 2: Idempotent duplicate
    resp2 = client.post("/api/v1/finance/webhooks/razorpay", content=raw_bytes, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["is_duplicate"] is True

    # Check ledger count is strictly 1
    with qa_finance_env["db"]._get_connection() as conn:
        ledger_count = conn.execute("SELECT COUNT(*) FROM financial_ledger_entries WHERE account_id = ?;", (qa_finance_env["account_a"].id,)).fetchone()[0]
        assert ledger_count == 1


def test_receipt_retrieval_persisted_and_authorized(qa_finance_env):
    """ERP-009: Persisted receipts can be retrieved with proper tenant and student authorization."""
    client = TestClient(app)
    order = qa_finance_env["order_a"]
    secret = "rzp_test_secret_qa"

    # 1. Process payment webhook to create a real persisted receipt
    payload_dict = {
        "event": "payment.captured",
        "id": f"evt_rct_{uuid.uuid4().hex[:8]}",
        "order_id": order.provider_order_id,
        "payment_id": f"pay_rzp_{uuid.uuid4().hex[:8]}",
        "amount": 5000.0,
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    resp_hook = client.post(
        "/api/v1/finance/webhooks/razorpay",
        content=raw_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Webhook-Secret": secret,
        },
    )
    assert resp_hook.status_code == 200
    receipt_number = resp_hook.json()["receipt_number"]

    # Lookup receipt_id from DB
    with qa_finance_env["db"]._get_connection() as conn:
        rct_row = conn.execute("SELECT id FROM receipts WHERE receipt_number = ?;", (receipt_number,)).fetchone()
        assert rct_row is not None
        receipt_id = rct_row[0]

    # 2. Bursar A (Org Admin of Org A) can retrieve the receipt
    token_bursar = create_access_token(
        user_id=qa_finance_env["bursar_a"].id,
        role="org_admin",
        organization_id=qa_finance_env["org_a_id"],
    )
    resp_bursar = client.get(
        f"/api/v1/finance/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {token_bursar}"},
    )
    assert resp_bursar.status_code == 200, f"Bursar failed to retrieve receipt: {resp_bursar.text}"
    rdata = resp_bursar.json()
    assert rdata["receipt_number"] == receipt_number
    assert rdata["amount"] == 5000.0
    assert rdata["student_id"] == qa_finance_env["student_a"].id

    # 3. Student A (owner of the invoice/receipt) can retrieve their own receipt
    token_student_a = create_access_token(
        user_id=qa_finance_env["student_a"].id,
        role="student",
        organization_id=qa_finance_env["org_a_id"],
    )
    resp_stu_a = client.get(
        f"/api/v1/finance/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {token_student_a}"},
    )
    assert resp_stu_a.status_code == 200
    assert resp_stu_a.json()["receipt_number"] == receipt_number

    # 4. Student B (different student in same Org A) cannot retrieve Student A's receipt (HTTP 403)
    token_student_b = create_access_token(
        user_id=qa_finance_env["student_b"].id,
        role="student",
        organization_id=qa_finance_env["org_a_id"],
    )
    resp_stu_b = client.get(
        f"/api/v1/finance/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {token_student_b}"},
    )
    assert resp_stu_b.status_code == 403, f"Expected 403 Forbidden for cross-student access, got {resp_stu_b.status_code}"

    # 5. Admin B (different Org B) cannot retrieve Org A's receipt (HTTP 404 or 403)
    token_admin_b = create_access_token(
        user_id=qa_finance_env["admin_b"].id,
        role="org_admin",
        organization_id=qa_finance_env["org_b_id"],
    )
    resp_admin_b = client.get(
        f"/api/v1/finance/receipts/{receipt_id}",
        headers={"Authorization": f"Bearer {token_admin_b}"},
    )
    assert resp_admin_b.status_code in (403, 404), f"Expected 403/404 for cross-tenant access, got {resp_admin_b.status_code}"


def test_service_unverified_webhook_rejected(qa_finance_env):
    """ERP-001: FinanceService rejects unverified webhooks without mutation."""
    svc = qa_finance_env["fin_svc"]
    order = qa_finance_env["order_a"]

    with pytest.raises(ValueError, match="Unverified webhook event cannot mutate financial state"):
        svc.process_payment_webhook(
            organization_id=qa_finance_env["org_a_id"],
            provider="razorpay",
            event_id="evt_reject_unverified",
            event_type="payment.captured",
            payload={"order_id": order.provider_order_id, "amount": 5000.0},
            signature_verified=False,
        )


def test_service_invalid_signature_rejected(qa_finance_env):
    """ERP-001: FinanceService rejects invalid signature and leaves DB intact."""
    svc = qa_finance_env["fin_svc"]
    order = qa_finance_env["order_a"]

    with pytest.raises(ValueError, match="Webhook signature verification failed"):
        svc.process_payment_webhook(
            organization_id=qa_finance_env["org_a_id"],
            provider="razorpay",
            event_id="evt_reject_invalidsig",
            event_type="payment.captured",
            payload={"order_id": order.provider_order_id, "amount": 5000.0},
            raw_payload=b'{"order_id": "order_123"}',
            signature="deadbeef_bad_sig",
            webhook_secret="test_secret",
        )


def test_service_amount_and_currency_mismatch_rejected(qa_finance_env):
    """ERP-002: FinanceService rejects amount or currency mismatch with payment order."""
    svc = qa_finance_env["fin_svc"]
    order = qa_finance_env["order_a"]

    # Amount mismatch
    with pytest.raises(ValueError, match="Webhook amount 100.0 does not match order amount 5000.0"):
        svc.process_payment_webhook(
            organization_id=qa_finance_env["org_a_id"],
            provider="razorpay",
            event_id="evt_reject_amount",
            event_type="payment.captured",
            payload={"order_id": order.provider_order_id, "amount": 100.0},
            signature_verified=True,
        )

    # Currency mismatch
    with pytest.raises(ValueError, match="Webhook currency USD does not match order currency INR"):
        svc.process_payment_webhook(
            organization_id=qa_finance_env["org_a_id"],
            provider="razorpay",
            event_id="evt_reject_currency",
            event_type="payment.captured",
            payload={"order_id": order.provider_order_id, "amount": 5000.0, "currency": "USD"},
            signature_verified=True,
        )


def test_service_cancelled_invoice_rejected(qa_finance_env):
    """ERP-002: Cannot apply payment webhook to a cancelled invoice."""
    svc = qa_finance_env["fin_svc"]
    db = qa_finance_env["db"]
    inv = qa_finance_env["invoice_a"]

    # Mark invoice cancelled
    with db._get_connection() as conn:
        conn.execute("UPDATE invoices SET status = 'cancelled' WHERE id = ?;", (inv.id,))

    with pytest.raises(ValueError, match="Cannot apply payment to cancelled invoice"):
        svc.process_payment_webhook(
            organization_id=qa_finance_env["org_a_id"],
            provider="razorpay",
            event_id="evt_reject_cancelled",
            event_type="payment.captured",
            payload={"invoice_id": inv.id, "amount": 5000.0},
            signature_verified=True,
        )

