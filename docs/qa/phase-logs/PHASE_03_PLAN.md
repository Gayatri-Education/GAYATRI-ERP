# Phase 03 Plan: Finance, Payment Webhook Integrity, Invoices, Ledger, and Receipts

**Phase:** PHASE-03  
**Status:** IN_PROGRESS  
**Date:** 2026-10-15  
**Target Findings:** ERP-001, ERP-002, ERP-009  

---

## 1. Problem Analysis & Objectives

### 1.1 ERP-001: Webhook Signature Verification, Trust Boundary & Provider Enforcement
- **Findings & Root Causes:**
  1. `POST /api/v1/finance/webhooks/{provider}` in `central_platform/api/routes/finance.py` previously depended on `get_current_user`, which blocks genuine external gateway webhooks (e.g., Razorpay, Stripe) that lack user bearer tokens. If a bearer token was passed, it allowed arbitrary callers to mutate financial records without signature verification.
  2. The endpoint did not read or preserve raw request payload bytes (`request.body()`), which is required for deterministic HMAC-SHA256 signature verification.
  3. No gateway signature headers (`X-Razorpay-Signature`, `X-Webhook-Signature`, `Stripe-Signature`) were validated.
  4. Unsupported or unknown payment providers were not rejected with appropriate HTTP error codes.
  5. In `central_platform/finance/service.py`, `signature_verified=1` was hardcoded into the `payment_webhook_events` insert statement even when no cryptographic signature verification was performed.
- **Invariants & Requirements:**
  - Unverified webhooks must NOT mutate financial state (no payments, no receipts, no ledger credits, no invoice/order status transitions).
  - Webhooks with missing, invalid, or tampered signatures must be rejected with HTTP 401 Unauthorized.
  - Unknown/unsupported payment providers must be rejected with HTTP 400 Bad Request.
  - Raw payload bytes must be verified against HMAC-SHA256 signatures before processing.
  - `signature_verified` must truthfully reflect the cryptographic verification outcome in `payment_webhook_events`.

### 1.2 ERP-002: Atomic Multi-Table Mutations & Concurrent Deduplication
- **Findings & Root Causes:**
  1. Although `FinanceService.process_payment_webhook`'s main mutation block was wrapped in a transaction in Phase 02, deduplication queries occurred outside the transaction, and concurrent webhook deliveries could race.
  2. Concurrent duplicate webhook deliveries could throw uncaught `sqlite3.IntegrityError` due to unique constraints (`organization_id, provider, event_id`).
  3. Legal state transitions (checking if invoice is already paid or cancelled, or if order amount/currency mismatches the webhook payload) were not fully enforced before mutating state.
- **Invariants & Requirements:**
  - Idempotent processing must safely return existing payment and receipt records without double-posting ledger credits or raising uncaught exceptions under concurrency.
  - Multi-table mutations (`payments`, `receipts`, `invoices`, `payment_orders`, `financial_ledger_entries`, `payment_webhook_events`) must commit atomically or rollback completely on any secondary write failure.
  - Order/invoice amount or currency mismatch must be caught and rejected without financial state corruption.

### 1.3 ERP-009: Persisted Receipt Retrieval, Verification, and Authorization
- **Findings & Root Causes:**
  1. No REST API endpoint existed under `/api/v1/finance` for retrieving persisted receipts.
  2. `FinanceService` lacked a dedicated method to fetch receipts joined with payment, student, and tenant isolation context.
  3. The UI helper in `app/ui/design_system/fee_admin.js` (`printReceipt`) invoked `window.print()` directly without fetching or verifying persisted receipt data from the backend.
- **Invariants & Requirements:**
  - Implement `GET /api/v1/finance/receipts/{receipt_id}` enforcing:
    - User authentication (`get_current_user`).
    - Tenant isolation: receipts from Org A cannot be read by users in Org B (HTTP 404/403).
    - Student isolation: students can only fetch their own receipts (HTTP 403 Forbidden for cross-student access).
    - Administrative access: bursars, org admins, and super admins can view any receipt in their organization.
  - Return comprehensive persisted receipt data including receipt number, payment details, amount, timestamp, student ID, and invoice reference.

---

## 2. Implementation Steps
1. **Targeted Reproduction Suite:**
   - Create `tests/test_qa_phase03_finance_integrity.py` asserting:
     - Unsigned or missing signature webhooks are rejected (HTTP 401).
     - Tampered signature or tampered payload webhooks are rejected (HTTP 401).
     - Unknown provider webhooks are rejected (HTTP 400).
     - Validly signed webhooks succeed, update invoice/order, post to ledger, and record `signature_verified=1`.
     - Concurrent/duplicate webhooks return idempotent success without duplicate ledger postings.
     - Amount/currency mismatch is rejected.
     - Persisted receipt retrieval (`GET /api/v1/finance/receipts/{receipt_id}`) returns correct data for authorized users.
     - Student access control prevents cross-student receipt access (HTTP 403).
     - Tenant isolation prevents cross-organization receipt access (HTTP 404/403).
2. **Harden `central_platform/finance/service.py`:**
   - Add `get_webhook_secret(provider, organization_id)`.
   - Update `process_payment_webhook` to:
     - Accept `raw_payload`, `signature`, `signature_verified`, `webhook_secret`.
     - Enforce that unverified webhooks cannot mutate financial state.
     - Verify signature using HMAC-SHA256 if `signature` is provided.
     - Check amount and currency matching against existing `payment_order`.
     - Handle concurrent duplicate delivery gracefully within transaction boundaries.
     - Persist truthful `signature_verified` (`1` if verified, `0` if rejected).
   - Add `get_receipt(organization_id, receipt_id_or_number)` querying persisted receipt, payment, student, and invoice information.
3. **Harden `central_platform/api/routes/finance.py`:**
   - Update `POST /webhooks/{provider}`:
     - Accept `Request` to read exact raw payload bytes.
     - Allow webhook authentication without requiring a user Bearer token (`get_current_user_optional`).
     - Validate provider against known providers (`razorpay`, `mock`, `upi`, `stripe`).
     - Extract signature from `X-Razorpay-Signature`, `X-Webhook-Signature`, `Stripe-Signature`, `X-Signature`.
     - Enforce signature validation with 401 on missing or invalid signature.
     - Dynamically resolve `organization_id` from order, invoice, header, or claims.
   - Add `GET /receipts/{receipt_id}`:
     - Authenticate with `get_current_user`.
     - Verify tenant and student isolation.
     - Return persisted receipt details or 404/403.
4. **Harden `app/ui/design_system/fee_admin.js`:**
   - Update `printReceipt` to asynchronously fetch receipt details from `/api/v1/finance/receipts/{receiptId}` before triggering printing.
5. **Run Tests & Verify:**
   - Run `tests/test_qa_phase03_finance_integrity.py`.
   - Run `tests/test_phase05_finance_payments_reconciliation.py`.
   - Run full regression suite (`pytest -q -m "not gui"`).
6. **Update Records:**
   - Create `docs/qa/phase-logs/PHASE_03_LOG.md`.
   - Update `docs/qa/PROGRESS_TRACKER.yaml` and `GAYATRI_ERP_PROGRESS_TRACKER.yaml`.
   - Update `docs/qa/ISSUE_REGISTER.md`.
