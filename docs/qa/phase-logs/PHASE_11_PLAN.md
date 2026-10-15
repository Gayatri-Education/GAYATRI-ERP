# Phase 11 Plan: API Contracts, Validation, Rate Limits, and Idempotency

**Phase:** PHASE-11  
**Status:** IN_PLANNING  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer  

---

## 1. Goal & Scope
Harden platform API contracts, input validation, bounded pagination, distributed rate limiting, and mutating operation idempotency. Enforce strict schema boundaries so malformed types, unknown enum values, unbounded queries, negative financial values, and oversized payloads are rejected at the API perimeter (HTTP 422/400). Guarantee idempotent retry semantics for financial orders, payment webhooks, and sync event batches. Ensure structured error envelopes carry tracing correlation (`X-Request-ID`) and preserve critical RFC headers (`WWW-Authenticate`, `Retry-After`).

---

## 2. Invariants & Target Behaviors
- **API Boundary Validation**:
  - `UserCreateRequest` (`central_platform/api/schemas.py`): Must validate `role` against `UserRole` enum values. Unrecognized roles like `"HACKER"` must be rejected at the boundary with HTTP 422, not accepted or silently stored in memory.
  - Bounded Pagination:
    - `list_users` (`central_platform/api/routes/users.py`): Enforce `limit: int = Query(default=50, ge=1, le=500)` and `offset: int = Query(default=0, ge=0)`.
    - `list_courses` (`central_platform/api/routes/courses.py`): Enforce `limit: int = Query(default=50, ge=1, le=500)` and `offset: int = Query(default=0, ge=0)`.
    - `ExportCreateRequest` (`central_platform/api/routes/institutional_analytics.py`): Enforce `limit: int = Field(default=1000, ge=1, le=10000)`. Negative or oversized limits must return HTTP 422.
  - Financial Contract Validation:
    - `OrderCreateRequest` (`central_platform/api/routes/finance.py`): Enforce `amount: float = Field(..., gt=0.0)`. Negative or zero amount orders must return HTTP 422.
    - `FinanceService.create_payment_order`: Validate `amount > 0` at domain level, raising `ValueError` on non-positive amounts.
  - Safe Ingest / Batch Limits:
    - `BatchSyncEventsRequest` (`central_platform/api/schemas.py`): Enforce bounded events array `events: List[Dict[str, Any]] = Field(..., min_length=1, max_length=1000)` and `student_id: str = Field(..., min_length=1, max_length=128)`.
- **Idempotency Guarantees**:
  - `FinanceService.create_payment_order`: When an `idempotency_key` is supplied, check for existing order in the same organization and return it if present, preventing duplicate orders or integrity violations.
  - Payment Webhook Ingestion: Webhook events deduplicate on `(organization_id, provider, event_id)` or `idempotency_key`.
  - Offline/Telemetry Sync: Batch sync endpoint `/api/v1/sync/events` acknowledges duplicate batches with `is_replay: True`.
- **Rate Limiting & Error Contracts**:
  - Atomic sliding window rate limiting via `PlatformDatabase.check_rate_limit_atomic` and `SecurityAuditor`.
  - HTTP exception handler in `central_platform/api/middleware.py`: Preserve `exc.headers` (e.g. `WWW-Authenticate`, `Retry-After`) while returning uniform `ApiResponse` error envelopes.

---

## 3. Implementation Plan
1. **Remediate `central_platform/api/schemas.py`**:
   - Add `@field_validator("role")` on `UserCreateRequest` to ensure role is valid in `UserRole`.
   - Add `events: List[Dict[str, Any]] = Field(..., min_length=1, max_length=1000)` and bounded `student_id` in `BatchSyncEventsRequest`.
2. **Remediate `central_platform/api/routes/users.py`**:
   - Add bounded pagination query parameters (`limit: int = Query(50, ge=1, le=500)`, `offset: int = Query(0, ge=0)`) to `list_users`.
   - Apply slice `results[offset : offset + limit]`.
3. **Remediate `central_platform/api/routes/courses.py`**:
   - Add bounded pagination query parameters (`limit: int = Query(50, ge=1, le=500)`, `offset: int = Query(0, ge=0)`) to `list_courses`.
   - Apply slice `result[offset : offset + limit]`.
4. **Remediate `central_platform/api/routes/institutional_analytics.py`**:
   - Add `Field(default=1000, ge=1, le=10000)` to `ExportCreateRequest.limit`.
5. **Remediate `central_platform/api/routes/finance.py` & `central_platform/finance/service.py`**:
   - In `OrderCreateRequest`: add `amount: float = Field(..., gt=0.0)`.
   - In `FinanceService.create_payment_order`: check existing order when `idempotency_key` is provided and return existing record; validate `amount > 0`.
6. **Remediate `central_platform/api/middleware.py`**:
   - In `http_exception_handler`: preserve `exc.headers` when returning JSON response.
7. **Author Reproduction Suite (`tests/test_qa_phase11_contracts_validation_idempotency.py`)**:
   - Verify negative/oversized pagination limit rejection (HTTP 422).
   - Verify invalid role rejection on user creation (HTTP 422).
   - Verify negative/zero financial order rejection (HTTP 422 & ValueError).
   - Verify oversized batch sync rejection (HTTP 422).
   - Verify payment order creation idempotency via idempotency_key.
   - Verify sync batch replay idempotency via operation_id.
   - Verify rate limiting sliding window atomic enforcement and retry-after.
   - Verify consistent error envelope and header preservation.
8. **Run targeted tests, debug, and execute full non-GUI regression suite (`python -m pytest -q -m "not gui"`)**.
9. **Update logs, trackers, issue register, and commit**.
