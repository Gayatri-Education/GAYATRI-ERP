# Phase 04 Plan — Financial Core: Billing, Double-Entry Accounting and Reconciliation

**Document:** `docs/erp_agent/plans/PHASE_04_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 04 — Financial Core: Billing, Double-Entry Accounting and Reconciliation  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 04 verifies and hardens the financial core of Gayatri-ERP:
1. **Fee Structures & Invoicing:** Fee categories, student fee accounts, monthly/term invoices, line items, and concession workflows.
2. **Double-Entry Financial Ledger:** Immutable, append-only entries in `financial_ledger_entries` tracking credits, debits, account balances, and running audit trails.
3. **Payment Webhook Processing & Deduplication:** HMAC signature verification across payment providers (Razorpay, UPI, Stripe, Mock), duplicate event rejection inside an atomic transaction boundary, invoice status progression (`unpaid` $\rightarrow$ `partially_paid` $\rightarrow$ `paid`), and official receipt issuance.
4. **Reconciliation & Auditing:** Automated reconciliation of invoice amounts, payment records, ledger balances, and bank statements with independent arithmetic checks.

---

## 2. Likely Files & Scope Boundary

- `central_platform/finance/service.py` (`FinanceService`)
- `central_platform/fees/service.py` (`FeeService`)
- `central_platform/models/finance.py`
- `central_platform/models/fees.py`
- `central_platform/api/routes/finance.py`
- `central_platform/api/routes/fees.py`
- `tests/test_qa_phase03_finance_integrity.py`
- `tests/test_phase30_fee_data_layer.py`
- `tests/test_phase31_fee_admin_ui.py`
- `tests/test_phase32_payment_provider_abstraction.py`

---

## 3. Targeted Test Scenarios

1. Unverified or unsigned webhook requests are rejected with `401 Unauthorized`.
2. Duplicate webhook payloads return cached idempotency results without re-crediting balances.
3. Amount or currency mismatches between order and webhook payload trigger rejection.
4. Payments applied to cancelled invoices trigger immediate rollback.
5. Ledger entries strictly balance (sum of credits equals sum of debits across the ledger).
6. Official receipt generation persists receipt number, amount, payment ID, and student linkage.

---

## 4. Exit Criteria (Binary Gate)

- [ ] All finance, fee data layer, fee admin UI, and payment abstraction suites pass with 100% success.
- [ ] Double-entry ledger append-only immutability verified.
- [ ] Webhook signature verification and deduplication verified under atomic transaction boundaries.
- [ ] Independent reconciliation calculations agree with invoice amounts and receipts.
- [ ] `docs/erp_agent/reports/PHASE_04_REPORT.md` and `docs/erp_agent/regressions/PHASE_04_REGRESSION.md` generated with passing evidence.
