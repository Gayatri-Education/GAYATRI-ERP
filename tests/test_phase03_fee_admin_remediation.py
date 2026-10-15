"""Phase 03 — Fee Administration & Receipt Handling Remediation Test Suite (QA-003).

Verifies:
1. Genuine summary derived from real database invoices, payments, and discounts.
2. Genuine outstanding reports derived from real unpaid invoices.
3. Empty organization returns honest zeros (0.0 totals, empty reports).
4. Empty student roster returns NO_ELIGIBLE_STUDENTS with 0 invoices created.
5. Monthly billing creates durable invoices and updates fee_accounts in DB.
6. Deduplication & idempotency: running billing twice for same month returns identical batch without duplicate invoices.
7. Atomic rollback: injected failure during billing run rolls back all partial writes.
8. Read-back across DB restart verifies persisted billing and invoice rows.
9. Production mode strictly forbids sample names, fixed totals, and demo billing.
10. Fee admin JS receipt verification contract ensures failures never trigger printing.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
import pytest

from central_platform.db import PlatformDatabase
from central_platform.models.fees import (
    Discount,
    DiscountType,
    FeeAccount,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
)
from central_platform.models.schema import Organization, User, UserRole
from central_platform.portals.fee_admin import (
    FeeAdminController,
    FeeAdminSummary,
    OutstandingReportItem,
)


@pytest.fixture
def clean_fee_db(tmp_path: Path):
    """Isolated temporary database for fee administration tests."""
    db_file = tmp_path / "test_fee_admin.db"
    return PlatformDatabase(db_path=str(db_file))


def _setup_org_and_students(db: PlatformDatabase, org_id: str, student_count: int = 3) -> List[User]:
    db.create_organization(Organization(id=org_id, name=f"Org {org_id}", slug=f"org-{org_id}"))
    students = []
    for i in range(student_count):
        sid = f"stu_{org_id}_{i+1}"
        u = User(
            id=sid,
            organization_id=org_id,
            email=f"{sid}@school.edu",
            full_name=f"Student {i+1}",
            role=UserRole.STUDENT,
        )
        db.create_user(u)
        students.append(u)
    return students


def test_real_fee_summary_from_database(clean_fee_db: PlatformDatabase):
    """Genuine summary calculations reflect real database payments, invoices, and discounts."""
    db = clean_fee_db
    org_id = "org_sum_real"
    students = _setup_org_and_students(db, org_id, student_count=2)
    s1, s2 = students[0], students[1]

    # Create fee accounts
    fa1 = FeeAccount(id="fa_s1", student_id=s1.id, org_id=org_id, total_due=20000.0, total_paid=15000.0, balance_due=5000.0)
    fa2 = FeeAccount(id="fa_s2", student_id=s2.id, org_id=org_id, total_due=15000.0, total_paid=0.0, balance_due=15000.0)
    db.create_fee_account(fa1)
    db.create_fee_account(fa2)

    now_iso = datetime.now(timezone.utc).isoformat()

    # Invoice 1: Partially paid
    db.create_invoice(
        Invoice(
            id="inv_1",
            fee_account_id=fa1.id,
            student_id=s1.id,
            org_id=org_id,
            invoice_number="INV-001",
            amount_due=20000.0,
            amount_paid=15000.0,
            due_date="2026-10-15",
            status=InvoiceStatus.PARTIALLY_PAID,
        )
    )

    # Invoice 2: Issued and overdue
    db.create_invoice(
        Invoice(
            id="inv_2",
            fee_account_id=fa2.id,
            student_id=s2.id,
            org_id=org_id,
            invoice_number="INV-002",
            amount_due=15000.0,
            amount_paid=0.0,
            due_date="2026-09-01",  # Past due date
            status=InvoiceStatus.ISSUED,
        )
    )

    # Payment for Invoice 1
    db.create_payment(
        Payment(
            id="pmt_1",
            invoice_id="inv_1",
            fee_account_id=fa1.id,
            student_id=s1.id,
            org_id=org_id,
            amount=15000.0,
            payment_method=PaymentMethod.UPI,
            status=PaymentStatus.COMPLETED,
            payment_date=now_iso,
        )
    )

    # Discount applied to account 1
    db.create_discount(
        Discount(
            id="dsc_1",
            fee_account_id=fa1.id,
            invoice_id="inv_1",
            code="MERIT10",
            discount_type=DiscountType.FIXED_AMOUNT,
            value=2000.0,
            applied_amount=2000.0,
        )
    )

    summary = FeeAdminController.get_fee_admin_summary(org_id=org_id, db=db)
    assert isinstance(summary, FeeAdminSummary)
    assert summary.org_id == org_id
    assert summary.total_collected == 15000.0
    assert summary.total_pending == 20000.0  # (20K - 15K) + (15K - 0) = 20,000
    assert summary.total_overdue == 15000.0  # inv_2 is past due
    assert summary.total_discounts == 2000.0
    assert summary.accounts_count == 2


def test_real_outstanding_reports_from_database(clean_fee_db: PlatformDatabase):
    """Outstanding reports and CSV export reflect real database unpaid invoices."""
    db = clean_fee_db
    org_id = "org_rep_real"
    students = _setup_org_and_students(db, org_id, student_count=1)
    s1 = students[0]

    fa = FeeAccount(id="fa_rep_1", student_id=s1.id, org_id=org_id, total_due=12000.0, balance_due=12000.0)
    db.create_fee_account(fa)

    db.create_invoice(
        Invoice(
            id="inv_rep_1",
            fee_account_id=fa.id,
            student_id=s1.id,
            org_id=org_id,
            invoice_number="INV-REP-01",
            amount_due=12000.0,
            amount_paid=0.0,
            due_date="2026-08-15",
            status=InvoiceStatus.ISSUED,
        )
    )

    items = FeeAdminController.get_outstanding_reports(org_id=org_id, db=db)
    assert len(items) == 1
    item = items[0]
    assert isinstance(item, OutstandingReportItem)
    assert item.student_id == s1.id
    assert item.student_name == "Student 1"
    assert item.amount_due == 12000.0
    assert item.overdue_days > 30
    assert item.status == "overdue"

    csv_data = FeeAdminController.export_outstanding_report_csv(org_id=org_id, db=db)
    assert "Student ID,Student Name,Grade,Amount Due (INR),Overdue Days,Status" in csv_data
    assert s1.id in csv_data
    assert "Student 1" in csv_data
    assert "12000.00" in csv_data


def test_empty_organization_returns_honest_zeros(clean_fee_db: PlatformDatabase):
    """Empty organization returns honest zero metrics without fabricated summary figures."""
    org_id = "org_empty_fee"
    clean_fee_db.create_organization(Organization(id=org_id, name="Empty Org", slug="empty-org"))

    summary = FeeAdminController.get_fee_admin_summary(org_id=org_id, db=clean_fee_db)
    assert summary.total_collected == 0.0
    assert summary.total_pending == 0.0
    assert summary.total_overdue == 0.0
    assert summary.total_discounts == 0.0
    assert summary.accounts_count == 0

    reports = FeeAdminController.get_outstanding_reports(org_id=org_id, db=clean_fee_db)
    assert reports == []


def test_empty_eligible_students_returns_no_eligible_students_status(clean_fee_db: PlatformDatabase):
    """Running monthly billing with no eligible students returns NO_ELIGIBLE_STUDENTS and 0 invoices."""
    org_id = "org_no_stu"
    clean_fee_db.create_organization(Organization(id=org_id, name="No Stu Org", slug="no-stu-org"))

    res = FeeAdminController.generate_monthly_billing(org_id=org_id, month_year="2026-11", db=clean_fee_db)
    assert res["status"] == "NO_ELIGIBLE_STUDENTS"
    assert res["invoices_generated"] == 0
    assert res["total_amount"] == 0.0
    assert res["organization_id"] == org_id
    assert res["month_year"] == "2026-11"


def test_monthly_billing_creates_durable_invoices_and_updates_fee_accounts(clean_fee_db: PlatformDatabase):
    """Monthly billing generates durable invoice rows and updates fee account balances atomically."""
    db = clean_fee_db
    org_id = "org_bill_run"
    students = _setup_org_and_students(db, org_id, student_count=3)

    res = FeeAdminController.generate_monthly_billing(org_id=org_id, month_year="2026-11", db=db)
    assert res["status"] == "COMPLETED"
    assert res["invoices_generated"] == 3
    assert res["total_amount"] == 45000.0
    assert "batch_id" in res

    # Verify durable invoices exist in DB
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*), sum(amount_due) FROM invoices WHERE org_id = ? AND is_deleted = 0;", (org_id,))
        count, total = cursor.fetchone()
        assert count == 3
        assert total == 45000.0

        # Verify fee accounts updated
        cursor.execute("SELECT count(*), sum(balance_due) FROM fee_accounts WHERE org_id = ?;", (org_id,))
        acc_count, balance = cursor.fetchone()
        assert acc_count == 3
        assert balance == 45000.0


def test_monthly_billing_idempotency_and_deduplication(clean_fee_db: PlatformDatabase):
    """Executing monthly billing multiple times for the same month creates no duplicates and returns identical batch."""
    db = clean_fee_db
    org_id = "org_idempotent_bill"
    _setup_org_and_students(db, org_id, student_count=2)

    # First run
    run1 = FeeAdminController.generate_monthly_billing(org_id=org_id, month_year="2026-11", db=db)
    assert run1["status"] == "COMPLETED"
    assert run1["invoices_generated"] == 2
    assert run1["total_amount"] == 30000.0
    batch_id_1 = run1["batch_id"]

    # Second run (identical period)
    run2 = FeeAdminController.generate_monthly_billing(org_id=org_id, month_year="2026-11", db=db)
    assert run2["status"] == "COMPLETED"
    assert run2["invoices_generated"] == 2
    assert run2["total_amount"] == 30000.0
    assert run2["batch_id"] == batch_id_1

    # Verify no duplicate invoices were inserted into the database
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM invoices WHERE org_id = ?;", (org_id,))
        assert cursor.fetchone()[0] == 2


def test_atomic_rollback_on_injected_invoice_creation_failure(clean_fee_db: PlatformDatabase, monkeypatch):
    """Injected failure during billing batch rolls back completely, leaving zero orphaned rows."""
    db = clean_fee_db
    org_id = "org_rollback_test"
    _setup_org_and_students(db, org_id, student_count=2)

    # Invalidate billing batch insertion to simulate mid-batch failure
    original_execute = db._get_connection

    class FailingConnection:
        def __init__(self, conn):
            self.conn = conn

        def __enter__(self):
            return self.conn.__enter__()

        def __exit__(self, exc_type, exc_val, exc_tb):
            return self.conn.__exit__(exc_type, exc_val, exc_tb)

    # Force error during billing batch
    def broken_connection():
        conn = original_execute()
        # Create a trigger that raises error on second invoice
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS fail_on_second_invoice
            BEFORE INSERT ON invoices
            WHEN (SELECT count(*) FROM invoices WHERE org_id = 'org_rollback_test') >= 1
            BEGIN
                SELECT RAISE(FAIL, 'Injected mid-batch disk corruption');
            END;
        """)
        return conn

    monkeypatch.setattr(db, "_get_connection", broken_connection)

    with pytest.raises(Exception) as exc_info:
        FeeAdminController.generate_monthly_billing(org_id=org_id, month_year="2026-11", db=db)
    assert "injected mid-batch" in str(exc_info.value).lower()

    # Reconnect and verify complete rollback: exactly 0 invoices persisted
    with original_execute() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM invoices WHERE org_id = ?;", (org_id,))
        assert cursor.fetchone()[0] == 0


def test_production_mode_forbids_sample_content_and_demo_billing(monkeypatch, clean_fee_db: PlatformDatabase):
    """When GAYATRI_ENV=production, demo mode raises ValueError, and empty queries return zeros."""
    monkeypatch.setenv("GAYATRI_ENV", "production")

    # 1. Requesting demo mode in production raises ValueError
    with pytest.raises(ValueError) as exc:
        FeeAdminController.get_fee_admin_summary(org_id="org_test_01", db=clean_fee_db, demo_mode=True)
    assert "prohibited in production" in str(exc.value).lower()

    with pytest.raises(ValueError) as exc:
        FeeAdminController.get_outstanding_reports(org_id="org_test_01", db=clean_fee_db, demo_mode=True)
    assert "prohibited in production" in str(exc.value).lower()

    with pytest.raises(ValueError) as exc:
        FeeAdminController.generate_monthly_billing(org_id="org_test_01", month_year="2026-11", db=clean_fee_db, demo_mode=True)
    assert "prohibited in production" in str(exc.value).lower()

    # 2. In production, unseeded org returns honest empty results (no sample Aarav Sharma)
    summary = FeeAdminController.get_fee_admin_summary(org_id="org_empty_prod", db=clean_fee_db)
    assert summary.total_collected == 0.0
    assert summary.accounts_count == 0

    reports = FeeAdminController.get_outstanding_reports(org_id="org_empty_prod", db=clean_fee_db)
    assert reports == []


def test_durable_read_back_across_db_restart(tmp_path: Path):
    """Persisted invoices, fee accounts, and billing batches read back identically across connection restart."""
    db_file = tmp_path / "durable_fee_test.db"

    # Instance 1: Generate billing batch
    db1 = PlatformDatabase(db_path=str(db_file))
    org_id = "org_durable_fee"
    _setup_org_and_students(db1, org_id, student_count=2)

    run1 = FeeAdminController.generate_monthly_billing(org_id=org_id, month_year="2026-11", db=db1)
    assert run1["status"] == "COMPLETED"
    assert run1["invoices_generated"] == 2
    del db1

    # Instance 2: Read back from separate connection
    db2 = PlatformDatabase(db_path=str(db_file))
    summary = FeeAdminController.get_fee_admin_summary(org_id=org_id, db=db2)
    assert summary.total_pending == 30000.0
    assert summary.accounts_count == 2

    reports = FeeAdminController.get_outstanding_reports(org_id=org_id, db=db2)
    assert len(reports) == 2
    assert sum(r.amount_due for r in reports) == 30000.0


def test_fee_admin_js_receipt_verification_contract():
    """Verify that fee_admin.js stops printing on receipt verification failure and has separate page print."""
    js_path = Path("app/ui/design_system/fee_admin.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    # 1. Verified-only receipt printing
    assert "printReceipt" in content
    assert "printCurrentPage" in content

    # 2. Must not fall back to window.print() inside catch or on invalid ID
    lines = content.splitlines()
    in_print_receipt = False
    in_catch = False

    for line in lines:
        if "function printReceipt(" in line:
            in_print_receipt = True
        elif in_print_receipt and line.strip().startswith("function "):
            in_print_receipt = False

        if in_print_receipt:
            if "catch" in line:
                in_catch = True
            elif in_catch and "}" in line:
                in_catch = False

            if in_catch:
                assert "window.print()" not in line, "catch block in printReceipt must not fall back to window.print()"

    # 3. Validation toast on missing receiptId
    assert "Receipt ID is required" in content
    # 4. Check for status check failure abort
    assert "Unable to verify persisted receipt" in content
