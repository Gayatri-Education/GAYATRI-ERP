# Phase 04 Plan — Payment Webhook Verification, Tenant Binding & Accounting Invariants (QA-004)

## 1. Context & Objectives
In Phase 03, we remediated fee administration, billing batches, and receipt handling (QA-003).
In Phase 04, we remediate QA-004: eliminating payment webhook tenant spoofing, removing the `org-default` fallback, strictly binding payment events to persisted payment orders and invoices, verifying signatures with constant-time comparison using organization-scoped secrets, and enforcing atomic accounting invariants.

### Target Locations
- `central_platform/api/routes/finance.py`: `ingest_webhook()` route scoping, signature checking, and merchant validation.
- `central_platform/finance/service.py`: `process_payment_webhook()`, `get_webhook_secret()`, signature verification, and atomic state mutations.
- `central_platform/models/finance.py`: Add `OrganizationPaymentProvider` model for merchant/gateway configuration.
- `central_platform/db.py`: Add `organization_payment_providers` table and helper methods for organization payment configurations.

---

## 2. Gap Analysis & Root Causes
1. **Tenant Spoofing Vulnerability:** In `ingest_webhook()`, `org_id` was resolved from `request.headers.get("x-organization-id")` or `request.query_params.get("org_id")` or `payload_dict.get("organization_id")` before inspecting any payment order. A malicious caller could target a victim organization simply by setting an arbitrary header.
2. **`org-default` Fallback:** If no organization was provided and no order was found, the route defaulted to `"org-default"`, allowing unlinked or unmatched events to mutate database tables and create orphaned payment records.
3. **Unmatched / Unknown Order Mutation:** In `FinanceService.process_payment_webhook()`, if `order` was `None`, the function did not raise an error. Instead, it proceeded to create a payment record and receipt with empty invoice and student fields, and returned HTTP 200 `PROCESSED`.
4. **Unscoped Webhook Secrets:** `get_webhook_secret()` took an optional `organization_id` parameter but ignored it, using global environment variables or static defaults. Each organization must be able to have its own merchant account and webhook secret.
5. **Missing State Transition Handling:** Events such as `payment.failed` were not explicitly handled to transition order states without financial mutation. Re-captured orders were vulnerable to duplicate payment creation.
6. **Invoice Tenant Verification:** If an order referenced an invoice, there was no check confirming that the invoice actually belonged to the same organization as the order.

---

## 3. Remediation Architecture

### A. Merchant / Provider Configuration (`models/finance.py` & `db.py`)
- Define `OrganizationPaymentProvider` dataclass:
  - `id`, `organization_id`, `provider`, `merchant_id`, `webhook_secret`, `api_key`, `is_active`, `created_at`, `updated_at`.
- Add `organization_payment_providers` table to database initialization in `central_platform/db.py`:
  - `UNIQUE(organization_id, provider)` constraint.
- Add `save_payment_provider_config()` and `get_payment_provider_config()` to `PlatformDatabase` and `FinanceService`.

### B. Route-Level Hardening (`central_platform/api/routes/finance.py`)
- **Mandatory Order Reference:** Extract `order_ref` from gateway payload. If missing, return HTTP 400 (`Missing payment order reference in webhook payload`).
- **Unambiguous Order Resolution:** Query `payment_orders` for `provider_order_id = ? OR id = ?`.
  - 0 matches: Return HTTP 400 (`Unknown or unmatched payment order`).
  - >1 matches: Return HTTP 400 (`Ambiguous payment order reference`).
  - 1 match: Authoritative `org_id = order.organization_id`.
- **Tenant Mismatch Rejection:** If the caller provides `X-Organization-ID`, `org_id` query param, or payload `organization_id`, assert that it strictly equals `order.organization_id`. Otherwise reject with HTTP 400 (`Organization mismatch for payment order`).
- **Provider Mismatch Rejection:** Assert that `order.provider == provider_clean`. Otherwise reject with HTTP 400 (`Provider mismatch`).
- **Merchant Identity Verification:** If the organization has a configured `merchant_id` for this provider, verify that any merchant identifier in the payload (`account_id`, `merchant_id`, `merchant_vpa`) matches the configured merchant. Reject with HTTP 400 if mismatched.
- **Organization-Scoped Secret & HMAC Verification:** Look up the webhook secret for `(provider, order.organization_id)`. Verify signature over raw payload bytes using constant-time comparison (`hmac.compare_digest`). Reject with HTTP 401 if missing or invalid.
- **Zero `org-default` Fallback:** Completely delete the `org-default` fallback.

### C. Domain Service Hardening (`central_platform/finance/service.py`)
- **Strict Order Validation:** `process_payment_webhook()` requires an existing persisted `PaymentOrder`. If not found in the organization, raise `ValueError`.
- **Amount & Currency Validation:** Validate `abs(order.amount - payload_amount) <= 0.01` and currency match. Raise `ValueError` on discrepancy.
- **Invoice Tenant Integrity:** Verify invoice belongs to the exact same `organization_id`. Reject cancelled invoices.
- **Explicit Event State Transitions:**
  - `payment.captured` / `payment.authorized` / `payment.paid`: Transition order to `CAPTURED`, create payment, receipt, update invoice, and post `CREDIT` ledger entry.
  - `payment.failed`: Transition order to `FAILED`. Do not create payment, receipt, or ledger entry.
  - Idempotent duplicate: If already `CAPTURED` or duplicate event ID / idempotency key, return `status="PROCESSED", is_duplicate=True` without duplicate writes.
- **Atomic Transaction Guarantee:** Wrap deduplication check, payment, receipt, invoice update, order status update, ledger credit, and webhook event logging inside `with self.db.transaction():`.
- **Sanitized Logging:** Never log raw secrets, signatures, bank credentials, or PII.

---

## 4. Verification & Testing Strategy
Author `tests/test_phase04_payment_webhook_remediation.py` covering:
1. Derivation of tenant strictly from existing `PaymentOrder` (caller cannot spoof via header, query, or payload).
2. Rejection of caller-supplied mismatched `X-Organization-ID` with HTTP 400.
3. Complete elimination of `org-default` fallback (unmatched order rejected with HTTP 400).
4. Missing order reference rejected with HTTP 400.
5. Ambiguous order reference matching multiple orders rejected with HTTP 400.
6. Missing signature header rejected with HTTP 401.
7. Forged/invalid signature rejected with HTTP 401.
8. Provider mismatch rejected with HTTP 400.
9. Configured merchant identity mismatch rejected with HTTP 400.
10. Amount mismatch rejected with HTTP 400 without financial mutations.
11. Currency mismatch rejected with HTTP 400 without financial mutations.
12. Cancelled invoice rejected with HTTP 400.
13. Cross-tenant invoice mismatch rejected with HTTP 400.
14. Payment failure event transitions order to `FAILED` without creating payments or ledger credits.
15. Idempotent duplicate delivery returns `is_duplicate=True` with zero duplicate ledger entries.
16. Atomic rollback on injected failure (no partial payments, receipts, or ledger entries).
17. Durable read-back across DB restart.
18. Log hygiene: verification that secrets and signatures are never logged.

Regression Verification:
- `pytest tests/test_qa_phase03_finance_integrity.py tests/test_phase05_finance_payments_reconciliation.py tests/test_phase32_payment_provider_abstraction.py -v`
- Full regression suite including architecture invariants.

---

## 5. Exit Criteria
- [ ] No caller-supplied tenant field can establish the tenant for a payment mutation.
- [ ] Unknown provider/order/tenant and amount/currency mismatch have zero side effects.
- [ ] Duplicate and concurrent deliveries are strictly idempotent.
- [ ] Invoice, payment, ledger, receipt, and webhook event remain consistent after failures and restart.
- [ ] Zero test assertions weakened, zero skipped or xfailed tests.
