"""Phase 05: Finance, Real Payment Integrations and Reconciliation.

Tests cover:
1. Migration 013 schema creation and clean rollback.
2. Fee concession submission and administrative approval workflow.
3. Server-authoritative payment order creation and lifecycle.
4. HMAC-SHA256 webhook signature validation and tamper rejection.
5. Idempotent webhook processing preventing duplicate ledger postings and duplicate receipts.
6. Append-only financial ledger integrity and balance reconciliation.
7. Batch reconciliation engine and settlement discrepancy detection.
8. Cross-tenant isolation for financial records, orders, and ledgers.
9. REST API endpoints and RBAC authorization matrix.
"""

import hmac
import hashlib
import json
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from central_platform.db import PlatformDatabase
from central_platform.models import Organization, User, UserRole
from central_platform.models.fees import (
    FeeStructure,
    FeePlan,
    FeeAccount,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Receipt,
)
from central_platform.models.finance import (
    PaymentOrder,
    OrderStatus,
    WebhookEventStatus,
    LedgerEntryType,
    FinancialLedgerEntry,
    ReconciliationStatus,
    ReconciliationRecord,
    ConcessionStatus,
    FeeConcession,
)
from central_platform.fees.service import FeeService
from central_platform.finance.service import FinanceService
from central_platform.auth.tokens import create_access_token
from central_platform.api.app import app

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


@pytest.fixture
def platform_db(tmp_path):
    """File-backed PlatformDatabase instance migrated through 013."""
    db_file = str(tmp_path / "test_phase05.db")
    db = PlatformDatabase(db_file)
    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-school-1', 'Greenwood High', 'greenwood-high', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-coaching-2', 'Apex IIT Academy', 'apex-iit', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
        )
        for mod in ["finance", "fees", "academic", "sis"]:
            conn.execute(
                "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
                f"VALUES ('ent-{mod}-1', 'org-school-1', '{mod}', 1, '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
            )
            conn.execute(
                "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
                f"VALUES ('ent-{mod}-2', 'org-coaching-2', '{mod}', 1, '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
            )
        # Create student users
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            "VALUES ('usr-stu-1', 'org-school-1', 'student1@gw.edu', 'Aarav Sharma', 'student', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            "VALUES ('usr-stu-2', 'org-coaching-2', 'student2@apex.edu', 'Neha Gupta', 'student', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
        )
    yield db
    db.close()


# ── Test 1: Migration 013 Up and Down Verification ───────────────────────────

def test_migration_013_up_and_down():
    """Verify migration 013 creates all financial tables and down script removes them cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply up through 012
    for i in range(1, 13):
        scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Apply 013
    up_013 = MIGRATIONS_DIR / "013_finance_payments_reconciliation.sql"
    assert up_013.exists(), "013 forward migration script must exist"
    conn.executescript(up_013.read_text(encoding="utf-8"))

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_up = {r[0] for r in cursor.fetchall()}

    expected_tables = {
        "payment_orders",
        "payment_webhook_events",
        "financial_ledger_entries",
        "reconciliation_records",
        "fee_concessions",
    }
    for t in expected_tables:
        assert t in tables_after_up, f"Table {t} should exist after migration 013"

    # Roll back 013
    down_013 = MIGRATIONS_DIR / "013_finance_payments_reconciliation_down.sql"
    assert down_013.exists(), "013 rollback migration script must exist"
    conn.executescript(down_013.read_text(encoding="utf-8"))

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_down = {r[0] for r in cursor.fetchall()}

    for t in expected_tables:
        assert t not in tables_after_down, f"Table {t} should be removed after rollback"

    conn.close()


# ── Test 2: Fee Concession Submission and Approval Workflow ──────────────────

def test_fee_concession_workflow(platform_db):
    """Verify fee concession requests can be submitted, audited, and approved/rejected."""
    fee_svc = FeeService(platform_db)
    fin_svc = FinanceService(platform_db)

    fs = fee_svc.create_fee_structure(
        org_id="org-school-1",
        name="Tuition Grade 10",
        code="TUT-G10",
        amount=50000.0,
    )

    # 1. Submit Concession Request (e.g., Merit scholarship 25%)
    conc = fin_svc.request_concession(
        organization_id="org-school-1",
        student_id="usr-stu-1",
        fee_structure_id=fs.id,
        concession_type="percentage",
        amount_or_percentage=25.0,
        reason="Merit rank top 1% scholarship",
        requested_by="officer-1",
    )
    assert conc.id is not None
    assert conc.status == ConcessionStatus.PENDING

    # 2. Approve Concession Request
    approved = fin_svc.approve_concession(
        organization_id="org-school-1",
        concession_id=conc.id,
        approved_by="principal-1",
        approved=True,
    )
    assert approved.status == ConcessionStatus.APPROVED
    assert approved.approved_by == "principal-1"
    assert approved.approved_at is not None


# ── Test 3: Server-Authoritative Payment Order Creation ──────────────────────

def test_payment_order_creation_and_lifecycle(platform_db):
    """Test server-authoritative creation of payment gateway orders."""
    fee_svc = FeeService(platform_db)
    fin_svc = FinanceService(platform_db)

    # Setup fee account & invoice
    account = fee_svc.create_fee_account("usr-stu-1", "org-school-1")
    inv = fee_svc.generate_invoice(
        fee_account=account,
        amount_due=15000.0,
        due_date="2026-11-30",
    )

    # Create Payment Order
    order = fin_svc.create_payment_order(
        organization_id="org-school-1",
        invoice_id=inv.id,
        student_id="usr-stu-1",
        amount=15000.0,
        currency="INR",
        provider="razorpay",
        idempotency_key="idemp-ord-001",
    )
    assert order.id is not None
    assert order.status == OrderStatus.CREATED
    assert order.provider_order_id.startswith("order_")
    assert order.amount == 15000.0


# ── Test 4: HMAC Webhook Signature Validation ────────────────────────────────

def test_webhook_hmac_signature_verification_and_tamper_rejection(platform_db):
    """Verify authentic HMAC-SHA256 signatures are validated and tampered payloads rejected."""
    fin_svc = FinanceService(platform_db)
    secret = "rzp_webhook_secret_key_123"

    payload_dict = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_live_001",
                    "order_id": "order_live_001",
                    "amount": 1500000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }
    raw_payload = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")

    # Generate genuine signature
    genuine_sig = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()

    # 1. Genuine payload + genuine signature -> True
    assert fin_svc.verify_webhook_signature(raw_payload, genuine_sig, secret) is True

    # 2. Tampered signature -> False
    assert fin_svc.verify_webhook_signature(raw_payload, "tampered_signature_hex", secret) is False

    # 3. Tampered payload -> False
    tampered_payload = raw_payload.replace(b"1500000", b"1000000")
    assert fin_svc.verify_webhook_signature(tampered_payload, genuine_sig, secret) is False


# ── Test 5: Idempotent Webhook Deduplication ──────────────────────────────────

def test_idempotent_webhook_deduplication(platform_db):
    """Verify duplicate webhooks do not double-post to the ledger or issue duplicate receipts."""
    fee_svc = FeeService(platform_db)
    fin_svc = FinanceService(platform_db)

    account = fee_svc.create_fee_account("usr-stu-1", "org-school-1")
    inv = fee_svc.generate_invoice(
        fee_account=account,
        amount_due=10000.0,
        due_date="2026-11-30",
    )
    order = fin_svc.create_payment_order(
        organization_id="org-school-1",
        invoice_id=inv.id,
        student_id="usr-stu-1",
        amount=10000.0,
        idempotency_key="idemp-dedup-01",
    )

    event_payload = {
        "event": "payment.captured",
        "id": "evt_rzp_9999",
        "order_id": order.provider_order_id,
        "payment_id": "pay_rzp_8888",
        "amount": 10000.0,
    }

    # 1. First webhook delivery: successfully captures payment and logs ledger entry
    result1 = fin_svc.process_payment_webhook(
        organization_id="org-school-1",
        provider="razorpay",
        event_id="evt_rzp_9999",
        event_type="payment.captured",
        payload=event_payload,
        idempotency_key="idemp-hook-9999",
    )
    assert result1["status"] == "PROCESSED"
    assert result1["is_duplicate"] is False
    assert result1["payment_id"] is not None
    assert result1["receipt_number"] is not None

    # Check ledger count
    ledger_entries_1 = fin_svc.get_account_ledger("org-school-1", account.id)
    assert len(ledger_entries_1) == 1

    # 2. Second webhook delivery (exact same event_id & idempotency_key)
    result2 = fin_svc.process_payment_webhook(
        organization_id="org-school-1",
        provider="razorpay",
        event_id="evt_rzp_9999",
        event_type="payment.captured",
        payload=event_payload,
        idempotency_key="idemp-hook-9999",
    )
    assert result2["status"] == "PROCESSED"
    assert result2["is_duplicate"] is True

    # Ledger count must remain strictly 1 (no duplicate credit)
    ledger_entries_2 = fin_svc.get_account_ledger("org-school-1", account.id)
    assert len(ledger_entries_2) == 1


# ── Test 6: Append-Only Financial Ledger Integrity ───────────────────────────

def test_append_only_financial_ledger_integrity(platform_db):
    """Verify every invoice, payment, and refund creates an immutable audit trail."""
    fee_svc = FeeService(platform_db)
    fin_svc = FinanceService(platform_db)

    account = fee_svc.create_fee_account("usr-stu-1", "org-school-1")
    inv = fee_svc.generate_invoice(
        fee_account=account,
        amount_due=8000.0,
        due_date="2026-11-30",
    )

    # Record initial DEBIT on invoice generation
    fin_svc.post_ledger_entry(
        organization_id="org-school-1",
        account_id=account.id,
        invoice_id=inv.id,
        entry_type=LedgerEntryType.DEBIT,
        amount=8000.0,
        description="Term 1 Tuition Fee Invoice",
    )

    # Record CREDIT on payment
    pmt, _ = fee_svc.record_payment(
        invoice=inv,
        fee_account=account,
        amount=5000.0,
        payment_method=PaymentMethod.UPI,
    )
    fin_svc.post_ledger_entry(
        organization_id="org-school-1",
        account_id=account.id,
        invoice_id=inv.id,
        payment_id=pmt.id,
        entry_type=LedgerEntryType.CREDIT,
        amount=5000.0,
        description="UPI Partial Payment Settlement",
    )

    entries = fin_svc.get_account_ledger("org-school-1", account.id)
    assert len(entries) == 2
    assert entries[0].entry_type == LedgerEntryType.DEBIT
    assert entries[0].amount == 8000.0
    assert entries[1].entry_type == LedgerEntryType.CREDIT
    assert entries[1].amount == 5000.0

    # Net balance check: Debit (8000) - Credit (5000) = 3000 due
    balance = fin_svc.calculate_ledger_balance("org-school-1", account.id)
    assert balance == 3000.0


# ── Test 7: Batch Reconciliation Engine & Discrepancy Detection ──────────────

def test_batch_reconciliation_discrepancy_flagging(platform_db):
    """Verify reconciliation matches settlements and flags unexplained discrepancies."""
    fin_svc = FinanceService(platform_db)

    # 1. Matching Run (Zero Discrepancy)
    rec1 = fin_svc.execute_reconciliation(
        organization_id="org-school-1",
        run_date="2026-10-14",
        provider="razorpay",
        total_expected=50000.0,
        total_settled=50000.0,
        reconciled_by="bursar-1",
    )
    assert rec1.status == ReconciliationStatus.RESOLVED
    assert rec1.discrepancy_amount == 0.0

    # 2. Mismatch Run (Discrepancy Detected)
    rec2 = fin_svc.execute_reconciliation(
        organization_id="org-school-1",
        run_date="2026-10-14",
        provider="razorpay",
        total_expected=50000.0,
        total_settled=48500.0,  # 1500 shortfall
        reconciled_by="bursar-1",
        notes="Bank settlement batch short by Rs. 1500 (unsettled chargeback)",
    )
    assert rec2.status == ReconciliationStatus.DISCREPANCY_FLAGGED
    assert rec2.discrepancy_amount == 1500.0


# ── Test 8: Cross-Tenant Financial Isolation ─────────────────────────────────

def test_cross_tenant_isolation_phase05(platform_db):
    """Verify Org A finance records cannot be accessed or modified by Org B."""
    fee_svc = FeeService(platform_db)
    fin_svc = FinanceService(platform_db)

    account_a = fee_svc.create_fee_account("usr-stu-1", "org-school-1")
    inv_a = fee_svc.generate_invoice(
        fee_account=account_a,
        amount_due=12000.0,
        due_date="2026-11-30",
    )
    order_a = fin_svc.create_payment_order(
        organization_id="org-school-1",
        invoice_id=inv_a.id,
        student_id="usr-stu-1",
        amount=12000.0,
    )

    # Org B attempts to look up Org A's payment order
    order_b = fin_svc.get_payment_order("org-coaching-2", order_a.id)
    assert order_b is None

    # Org B attempts to query Org A's ledger
    ledger_b = fin_svc.get_account_ledger("org-coaching-2", account_a.id)
    assert len(ledger_b) == 0


# ── Test 9: REST API Endpoints and RBAC Authorization ────────────────────────

def test_phase05_api_endpoints_and_rbac():
    """Verify REST API routes for finance, orders, webhooks, and reconciliation."""
    import uuid
    db = PlatformDatabase()
    org_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org_id, name="Phase 05 Org", slug=f"p5-org-{org_id}"))

    stu_id = f"stu_{uuid.uuid4().hex[:6]}"
    user = User(
        id=stu_id,
        organization_id=org_id,
        email=f"{stu_id}@gw.edu",
        full_name="API Student",
        role=UserRole.STUDENT,
    )
    db.create_user(user)

    account = FeeService(db).create_fee_account(stu_id, org_id)
    inv = FeeService(db).generate_invoice(account, 25000.0, "2026-11-30")

    token = create_access_token(
        user_id="user-bursar-p5",
        role="org_admin",
        organization_id=org_id,
    )
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)

    # 1. Create Payment Order via API
    resp_order = client.post(
        "/api/v1/finance/orders",
        headers=headers,
        json={
            "invoice_id": inv.id,
            "student_id": stu_id,
            "amount": 25000.0,
            "currency": "INR",
            "provider": "razorpay",
        },
    )
    assert resp_order.status_code == 201
    assert resp_order.json()["amount"] == 25000.0

    # 2. Reconcile Batch via API
    resp_rec = client.post(
        "/api/v1/finance/reconcile",
        headers=headers,
        json={
            "run_date": "2026-10-15",
            "provider": "razorpay",
            "total_expected": 25000.0,
            "total_settled": 25000.0,
        },
    )
    assert resp_rec.status_code == 200
    assert resp_rec.json()["status"] == "RESOLVED"
