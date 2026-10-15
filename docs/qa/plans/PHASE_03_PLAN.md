# Phase 03 Plan — Financially Trustworthy Fee Administration & Receipts (QA-003)

## 1. Context & Objectives
In Phase 02, we eliminated synthetic parent metrics and enforced boundary authorization.
In Phase 03, we remediate QA-003: making fee administration, monthly billing generation, outstanding aging reports, and receipt handling financially trustworthy and verifiable.

### Target Locations
- `central_platform/portals/fee_admin.py`: Hardcoded `FeeAdminSummary` (1.25M, 340K, 85K, 45K, 420), static `get_outstanding_reports()` rows, and `generate_monthly_billing()` fabricating 3 invoices / 45,000 INR without creating rows.
- `app/ui/design_system/fee_admin.js`: `printReceipt()` blindly falls back to `window.print()` if verification throws or fails.
- `central_platform/fees/service.py`: Financial calculation invariants, atomic invoice generation, and double-entry consistency.
- `central_platform/api/routes/finance.py`: Monthly billing, receipt fetching, and outstanding reports endpoints.
- `central_platform/db.py`: Missing `get_students_by_organization()` and `billing_batches` persistence.

---

## 2. Gap Analysis & Root Causes
1. **Fabricated Monthly Billing:** `FeeAdminController.generate_monthly_billing()` reports 3 invoices and 45,000 INR when no students exist, and increments in-memory counters without persisting any `Invoice` records in the database.
2. **Hardcoded Summary & Reports:** `FeeAdminSummary` defaults to static figures (1.25M collected, 340K pending), and `get_outstanding_reports()` returns hardcoded sample students (`Aarav Sharma`, `Priya Patel`, `Vikram Singh`).
3. **Receipt Printing Bypass:** `printReceipt(receiptId)` in `fee_admin.js` invokes `window.print()` inside `catch (e)` and when `!receiptId`, allowing unverified or failed receipt requests to trigger printing.
4. **Missing Database Persistence:** No `billing_batches` table exists to record batch runs, preventing database-level idempotency and deduplication.

---

## 3. Remediation Architecture

### A. Database Enhancements (`central_platform/db.py`)
- Add `billing_batches` table with `UNIQUE(organization_id, month_year)` constraint to enforce batch idempotency.
- Add `get_students_by_organization(organization_id)` to query active students from `student_profiles` and `users`.
- Add `create_billing_batch()` and `get_billing_batch()` helper methods.

### B. Core Portal Controller (`central_platform/portals/fee_admin.py`)
- **Real Summary Queries:** Compute `total_collected`, `total_pending`, `total_overdue`, `total_discounts`, and `accounts_count` from database `fee_accounts`, `invoices`, `payments`, and `discounts`.
- **Real Outstanding Reports:** Query active unpaid/overdue invoices, computing accurate `amount_due` and `overdue_days`.
- **Production Guard:** Remove static defaults and sample rows from production mode. Return honest empty/zero states when no records exist.
- **Atomic & Idempotent Monthly Billing:**
  - Check `billing_batches` for existing run; return existing confirmed batch if already processed (deduplication).
  - Query eligible active students. If none, return `NO_ELIGIBLE_STUDENTS` with 0 invoices and 0.0 amount.
  - In an atomic transaction, generate `Invoice` rows, update `fee_accounts` balances, and record ledger entries.
  - Roll back entirely if any row creation fails.
  - Persist `billing_batches` record with status `COMPLETED`.

### C. UI Controller (`app/ui/design_system/fee_admin.js`)
- Refactor `printReceipt(receiptId)`:
  - Require valid `receiptId`; abort with toast if missing.
  - Validate API response fields (`receipt_number`, `amount`, `issued_to`).
  - Abort immediately on 401, 403, 404, network error, or malformed JSON without printing.
  - Separate `printCurrentPage()` into an explicit distinct action.

---

## 4. Verification & Testing Strategy
Author `tests/test_phase03_fee_admin_remediation.py` covering:
1. Genuine summary derived from real database invoices and payments.
2. Genuine outstanding reports derived from real unpaid invoices.
3. Empty organization returns honest zeros (`0.0` totals, empty reports).
4. Empty student roster returns `NO_ELIGIBLE_STUDENTS` with 0 invoices created.
5. Monthly billing creates durable `Invoice` rows and updates `fee_accounts` in DB.
6. Deduplication & idempotency: running billing twice for same month returns identical batch without duplicate invoices.
7. Atomic rollback: injected failure during billing run rolls back all partial writes.
8. Read-back across DB restart verifies persisted billing and invoice rows.
9. Production mode strictly forbids sample names and fabricated numbers.
10. UI receipt verification contract: failure stops printing.

Regression Verification:
- `pytest tests/test_phase31_fee_admin_ui.py tests/test_qa_phase05_ui_bridges_contracts.py tests/test_submodule_6d_finance_ledger_reconciliation.py -v`
- Full regression suite including architecture tests.

---

## 5. Exit Criteria
- [ ] No production fee summary or export contains seeded sample data.
- [ ] Monthly billing creates durable invoices or reports `NO_ELIGIBLE_STUDENTS`; counts match read-back rows.
- [ ] Repeated requests do not create duplicate invoices.
- [ ] All invoice, payment, ledger, and fee-account balances reconcile.
- [ ] Receipt verification failure never triggers receipt printing.
- [ ] All tests pass without weakening any assertion.
