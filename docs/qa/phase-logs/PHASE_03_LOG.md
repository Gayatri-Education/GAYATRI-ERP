# Phase 03 Log: Finance, Payment Webhook Integrity, Invoices, Ledger, and Receipts

**Phase:** PHASE-03  
**Status:** PASSED  
**Date:** 2026-10-15  
**Branch:** `dev/phase-00-baseline`  
**Commit / Checkpoint:** Phase 03 complete  

---

## 1. Objectives & Scope
Remediate payment gateway webhook trust boundaries, signature verification, multi-table mutation atomicity, concurrency deduplication, legal state transitions, and persisted receipt verification:
- **ERP-001**: Webhook signature verification, trust boundary, provider enforcement, and truthful `signature_verified` recording.
- **ERP-002**: Payment/invoice/order/ledger/event atomicity, amount/currency matching, legal transition enforcement, and idempotent deduplication under concurrency.
- **ERP-009**: Persisted receipt retrieval, verification, and role/tenant authorization via REST API and UI client.

---

## 2. Reproduction Suite
Created targeted reproduction suite: `tests/test_qa_phase03_finance_integrity.py`.
Defects reproduced prior to remediation:
1. **ERP-001 (Missing Trust Boundary & Webhook Signature Bypass):**
   - In `central_platform/api/routes/finance.py`, `POST /api/v1/finance/webhooks/{provider}` previously required `Depends(get_current_user)`, failing with HTTP 401 (`Missing or malformed Authorization header`) on genuine server-to-server payment gateway callbacks (Razorpay, Stripe) that lack user bearer tokens.
   - If an internal user bearer token was provided, webhooks mutated invoices and ledger entries without validating raw payload bytes against gateway cryptographic signatures (`X-Razorpay-Signature`, `X-Webhook-Signature`, `Stripe-Signature`).
   - Unsupported providers (e.g. `unsupported_gateway`) were not rejected with HTTP 400 Bad Request.
   - In `central_platform/finance/service.py`, `signature_verified=1` was unconditionally hardcoded into `payment_webhook_events` even without verification.
2. **ERP-002 (Concurrency & Financial Invariant Violations):**
   - Deduplication queries occurred outside the transaction boundary, risking uncaught `sqlite3.IntegrityError` under concurrent webhook deliveries.
   - Mismatches in payment order amount or currency were not validated prior to applying payments.
   - Payments could be recorded against cancelled invoices.
3. **ERP-009 (Unpersisted / Unverified Receipts):**
   - No REST API endpoint existed under `/api/v1/finance` to fetch persisted receipts.
   - In `app/ui/design_system/fee_admin.js`, `printReceipt` invoked `window.print()` directly without fetching or verifying the receipt from backend persistence.

---

## 3. Remediation Details

### 3.1 Webhook Signature Verification and Provider Validation (ERP-001)
- In `central_platform/api/routes/finance.py`:
  - Allowed unauthenticated external gateway requests via `get_current_user_optional`.
  - Enforced known providers whitelist (`ALLOWED_WEBHOOK_PROVIDERS = {"razorpay", "mock", "upi", "stripe"}`); unknown providers reject with HTTP 400 Bad Request.
  - Read raw request body bytes (`await request.body()`) to ensure byte-exact HMAC-SHA256 signature verification.
  - Extracted signature from standard gateway headers (`X-Razorpay-Signature`, `X-Webhook-Signature`, `Stripe-Signature`, `X-Signature`, `X-Hub-Signature-256`); rejected unsigned requests with HTTP 401 Unauthorized.
  - Validated signature using constant-time comparison (`hmac.compare_digest`); rejected invalid/tampered signatures with HTTP 401 Unauthorized.
  - Dynamically resolved organization scoping from order reference, invoice reference, query/header, or user context.
- In `central_platform/finance/service.py`:
  - Added `get_webhook_secret(provider, organization_id)` checking provider-specific environment variables, gateway settings, and secure fallback defaults.
  - Hardened `verify_webhook_signature` to reject empty bytes, signatures, or secrets safely.
  - Updated `process_payment_webhook` to accept `raw_payload`, `signature`, `webhook_secret`, and `signature_verified`. Unverified webhooks explicitly raise `ValueError` and cannot mutate financial records.
  - Truthfully recorded `signature_verified` in `payment_webhook_events` (`1` if cryptographically verified, `0` otherwise).

### 3.2 Atomic Concurrency Deduplication and Transition Invariants (ERP-002)
- Encompassed the entire deduplication check, payment order retrieval, invoice status check, payment insertion, receipt insertion, invoice update, order status update, ledger credit posting, and webhook event insert within `with self.db.transaction():`.
- Enforced legal state invariants:
  - If `order` exists: verified `order.amount == amount` and matching currency (raises `ValueError` on mismatch).
  - If `invoice` exists: verified invoice is not `cancelled` (raises `ValueError` on cancelled invoice).
- Handled race conditions gracefully: caught `sqlite3.IntegrityError` on concurrent delivery to return existing event and payment ID with `is_duplicate=True` without duplicate ledger postings or uncaught crashes.

### 3.3 Persisted Receipt Retrieval, Verification, and UI Hardening (ERP-009)
- In `central_platform/finance/service.py`:
  - Implemented `get_receipt(organization_id, receipt_id_or_number)` querying `receipts` joined with `payments` and ensuring `is_deleted=0`.
- In `central_platform/api/routes/finance.py`:
  - Implemented `GET /api/v1/finance/receipts/{receipt_id}`:
    - Enforced authentication (`get_current_user`).
    - Enforced tenant isolation: callers can only access receipts within their organization (super admins may access cross-tenant).
    - Enforced student isolation: students can only fetch receipts where `student_id` or `issued_to` matches their user ID (HTTP 403 Forbidden for cross-student access).
- In `app/ui/design_system/fee_admin.js`:
  - Hardened `printReceipt(receiptId)` to asynchronously fetch `/api/v1/finance/receipts/{receiptId}` and display verification status prior to invoking `window.print()`.

---

## 4. Test Verification
1. **Targeted Reproduction Suite:**
   - `python -m pytest tests/test_qa_phase03_finance_integrity.py -v`
   - **Result:** **11 passed in 4.11s** (0 failures, 0 skipped).
     - `test_webhook_missing_signature_rejected_with_401` PASSED
     - `test_webhook_invalid_signature_rejected_with_401` PASSED
     - `test_webhook_tampered_payload_rejected_with_401` PASSED
     - `test_webhook_unknown_provider_rejected_with_400` PASSED
     - `test_webhook_valid_signature_processes_and_records_truthful_verification` PASSED
     - `test_webhook_idempotent_duplicate_delivery` PASSED
     - `test_receipt_retrieval_persisted_and_authorized` PASSED
     - `test_service_unverified_webhook_rejected` PASSED
     - `test_service_invalid_signature_rejected` PASSED
     - `test_service_amount_and_currency_mismatch_rejected` PASSED
     - `test_service_cancelled_invoice_rejected` PASSED
2. **Related Financial & Gateway Regression Suites:**
   - `pytest tests/test_phase05_finance_payments_reconciliation.py tests/test_qa_phase02_db_lifecycle_transactions.py tests/test_phase32_payment_provider_abstraction.py`
   - **Result:** **17 passed in 3.85s**.
3. **Full Automated Non-GUI Regression Suite:**
   - `python -m pytest -q -m "not gui"`
   - **Result:** **1,674 passed, 0 failed in 204.51s (3m 24s)**.

---

## 5. Gate Certification
- [x] Zero compilation or runtime errors.
- [x] All 11 targeted reproduction and regression tests pass.
- [x] 100% of the full automated test suite passes (1,674 tests).
- [x] No weakened assertions or bypassed production gates.
- [x] Canonical documentation updated.

**Gate Decision:** PASSED — Proceed to PHASE-04.
