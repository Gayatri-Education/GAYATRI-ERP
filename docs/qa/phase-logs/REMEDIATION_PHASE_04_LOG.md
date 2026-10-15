# Remediation Phase 04 Execution Log — Payment Webhook Verification, Tenant Binding & Accounting Invariants (QA-004)

**Phase ID:** 04  
**Target Vulnerability / Finding:** QA-004 (Payment Webhook Tenant Spoofing, Org-Default Fallback & Accounting Invariants)  
**Branch:** `qa/production-readiness-remediation`  
**Execution Timestamp:** 2026-10-15T22:07:30+05:30  
**Status:** PASSED  

---

## 1. Objectives & Inspection Findings
- **Audit Issue QA-004:** `central_platform/api/routes/finance.py:ingest_webhook()` accepted caller-supplied tenant hints (`X-Organization-ID`, `?org_id=`, or `payload["organization_id"]`) to establish the tenant scope before verifying the order, and defaulted to `"org-default"` if no organization or order was found.
- **Service Mutation Flaw:** In `central_platform/finance/service.py:process_payment_webhook()`, unmatched orders (`order is None`) still created payment records and receipts under the resolved or default organization without raising an error.
- **Provider & Merchant Gaps:** No organization-level merchant/provider configuration table existed, preventing per-organization webhook secret and merchant identity validation. Failed payment events did not explicitly transition orders without financial side effects.

---

## 2. Remediation Details

### A. Merchant & Provider Configuration (`models/finance.py` & `db.py`)
- Added `OrganizationPaymentProvider` dataclass to `central_platform/models/finance.py`.
- Added `organization_payment_providers` table with `UNIQUE(organization_id, provider)` constraint in `PlatformDatabase._init_db()` in `central_platform/db.py`.
- Added `save_payment_provider_config()` and `get_payment_provider_config()` helper methods to `PlatformDatabase` and `FinanceService`.

### B. Route-Level Hardening (`central_platform/api/routes/finance.py`)
- **Strict Order Resolution:** Extracted `order_ref` from payload; missing order references immediately reject with HTTP 400 (`Missing payment order reference in webhook payload`).
- **Database-Derived Tenant Binding:** Looked up `PaymentOrder` in `payment_orders` by `provider_order_id` or `id`. Unmatched orders reject with HTTP 400 (`Unknown or unmatched payment order`). Ambiguous orders (>1 matches) reject with HTTP 400. Authoritative tenant `org_id` is derived strictly from `order.organization_id`.
- **Tenant Mismatch Rejection:** If caller supplies `X-Organization-ID`, query param, or payload `organization_id` that contradicts `order.organization_id`, the request is rejected with HTTP 400 (`Organization mismatch for payment order`).
- **Elimination of `org-default`:** Completely eliminated the `"org-default"` fallback.
- **Provider & Merchant Identity Verification:**
  - Order provider must match route provider (`order.provider == provider_clean`), else HTTP 400 (`Provider mismatch`).
  - If organization has configured `merchant_id` for the provider, payload merchant (`account_id`, `merchant_vpa`) is compared and must match, else HTTP 400 (`Merchant mismatch`).
- **Constant-Time HMAC Signature Check:** Resolved organization-scoped webhook secret and verified signature over exact raw payload bytes using `hmac.compare_digest`. Missing or invalid signature rejects with HTTP 401.

### C. Domain Service Hardening (`central_platform/finance/service.py`)
- Updated `get_webhook_secret()` to prioritize organization-level configuration from `organization_payment_providers`, followed by tenant-specific environment variables.
- Refactored `process_payment_webhook()`:
  - Required an existing persisted `PaymentOrder` belonging to `organization_id`.
  - Validated amount tolerance (`abs(order.amount - amount) <= 0.01`) and currency matching.
  - Validated that the referenced invoice exists, belongs to the exact same tenant, and is not cancelled.
  - Implemented explicit state transition for `payment.failed`: transitions order status to `FAILED` with zero payment rows, zero receipts, and zero ledger entries.
  - Implemented idempotency guard: orders already `CAPTURED` return `is_duplicate=True` without double-crediting ledger accounts or overpaying invoices.
  - Enforced atomic transaction boundary (`with self.db.transaction():`) wrapping deduplication check, payment creation, receipt creation, invoice update, order status transition, ledger credit, and webhook event audit log.

---

## 3. Verification & Test Execution
- **Dedicated Test Suite:** Authored `tests/test_phase04_payment_webhook_remediation.py` containing 11 comprehensive tests:
  1. `test_tenant_binding_derived_from_order_caller_cannot_spoof`: PASSED
  2. `test_unknown_order_rejected_zero_org_default_fallback`: PASSED
  3. `test_missing_order_reference_rejected`: PASSED
  4. `test_provider_mismatch_rejected`: PASSED
  5. `test_merchant_identity_verification`: PASSED
  6. `test_amount_and_currency_mismatch_rejected_zero_side_effects`: PASSED
  7. `test_payment_failure_event_transitions_order_without_ledger_credit`: PASSED
  8. `test_idempotent_duplicate_delivery`: PASSED
  9. `test_atomic_rollback_on_injected_failure`: PASSED
  10. `test_durable_read_back_across_db_restart`: PASSED
  11. `test_log_hygiene_no_raw_secrets_or_signatures`: PASSED
- **Connected Finance Suite:** Executed 35 tests across Phase 04, Phase 03 QA, Phase 05 Finance Reconciliation, and Phase 32 Provider Abstraction:
  - **Passed:** 35/35 (100%) in 9.26s.
- **Multi-Phase Regression Suite:** Executed 87 tests across Phase 01, Phase 02, Phase 03, Phase 04, UI Bridges, Parent Portal, and Privacy Rules:
  - **Passed:** 87/87 (100%) in 16.63s.
- **Architecture Invariants:** Executed `pytest -v tests/architecture`:
  - **Passed:** 13/13 (100%) in 1.53s.

---

## 4. Exit Criteria Verification
- [x] No caller-supplied tenant field can establish the tenant for a payment mutation.
- [x] Unknown provider/order/tenant and amount/currency mismatch have zero side effects.
- [x] Duplicate and concurrent deliveries are strictly idempotent.
- [x] Invoice, payment, ledger, receipt, and webhook event remain consistent after failures and restart.
- [x] Zero test assertions weakened, zero skipped or xfailed tests.
