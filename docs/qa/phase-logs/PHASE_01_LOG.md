# Phase 01 Log: Authentication, Authorization, Tenant Isolation, and Revocation

**Phase:** PHASE-01  
**Status:** PASSED  
**Date:** 2026-10-15  
**Branch:** `dev/phase-00-baseline`  
**Commit / Checkpoint:** Phase 01 complete  

---

## 1. Objectives & Scope
Remediate security, authentication, tenant isolation, and token revocation vulnerabilities:
- **ERP-003**: Token revocation failure modes & silent bypass (`DatabaseRevocationStore` fail-open on DB downtime; `/auth/logout` silent success on write failure).
- **ERP-004**: Tenant boundary leaks in token decoding and validation.
- **ERP-012**: Unprotected AI Gateway administration & kill switch routes (`/ai/killswitch`, `/ai/providers`, etc.).
- **ERP-014**: Invalid `provider_type` silently defaulted to `ProviderType.MOCK` instead of raising HTTP 422.
- **ERP-015**: Unauthenticated legacy endpoints in `central_platform/api/app.py` allowing unauthenticated mutations.
- **ERP-019**: RBAC role hierarchy normalization and enforcement across endpoints.

---

## 2. Reproduction Suite
Created targeted reproduction suite: `tests/test_qa_phase01_auth_remediation.py`.
Defects reproduced prior to remediation:
1. `DatabaseRevocationStore.is_revoked()` returned `False` when the database raised an exception (failing open and allowing revoked tokens).
2. `DatabaseRevocationStore.revoke()` caught database write errors and returned `True` (falsely reporting revocation success).
3. `/api/v1/auth/logout` accepted requests with missing authorization headers and reported 200 OK without revoking any token.
4. `/api/v1/ai/killswitch` and `/api/v1/ai/providers` permitted unauthenticated requests and student tokens to execute administrative actions in production mode.
5. `/api/v1/ai/providers` silently accepted invalid provider types and registered them as `mock`.
6. Legacy endpoints (`/api/teacher/instruction`, `/instruction/toggle`, `/alert/resolve`, `/api/student/snapshot`, `/api/sync/events`) permitted unauthenticated mutations in production mode.

---

## 3. Remediation Details

### 3.1 `central_platform/auth/tokens.py`
- Hardened `DatabaseRevocationStore`:
  - `is_revoked(jti)`: Fails closed by raising `PermissionError` if the underlying database query fails, preventing revoked tokens from being treated as valid during DB outages.
  - `revoke(jti, ...)`: Truthfully returns `False` if database write fails, preventing false reporting of revocation.
  - `__init__(db_path)`: Supports both `PlatformDatabase` instances and database path strings/nulls seamlessly.

### 3.2 `central_platform/api/routes/auth.py`
- Updated `/auth/logout`:
  - Requires either an `Authorization: Bearer <token>` header or `refresh_token` in body; returns `400 Bad Request` if neither is provided.
  - Checks the return value of `revocation_store.revoke(...)`; raises `HTTPException(500, detail="Failed to persist token revocation")` if revocation write fails.

### 3.3 `central_platform/api/routes/ai.py`
- Added authorization guards `_verify_ai_admin_access(current_user)` and `_verify_ai_read_access(current_user)`:
  - In production mode (`is_production_mode()`), unauthenticated requests are rejected with `401 Unauthorized`.
  - Authenticated non-admin callers (such as students) attempting to toggle kill switches, mutate providers, update budgets, alter allowlists, or reset circuit breakers are rejected with `403 Forbidden`.
  - Inspection of providers requires at least `TEACHER`, `ORG_ADMIN`, or `SUPER_ADMIN`.
- Updated `create_or_update_provider`:
  - Explicitly validates `req.provider_type`; raises `HTTP 422 Unprocessable Entity` for invalid provider types instead of falling back to `mock`.

### 3.4 `central_platform/api/app.py`
- Exported `is_production_mode` and imported auth dependencies at module level.
- Implemented `_enforce_legacy_auth(current_user, allowed_roles)`:
  - In production mode, rejects unauthenticated callers with `401 Unauthorized`.
  - Rejects callers whose role does not match allowed roles with `403 Forbidden`.
  - Enforces student self-isolation on `/api/student/snapshot` and `/api/sync/events`: students can only submit snapshots and sync events for their own `student_id`.

---

## 4. Test Verification
1. **Targeted Reproduction Suite:**
   - `python -m pytest tests/test_qa_phase01_auth_remediation.py -v`
   - **Result:** 8 passed in 4.40s.
2. **Related Security & AI Suites:**
   - 86 passed in 16.50s (`test_phase01_production_config_hardening`, `test_phase04_ai_gateway_remediation`, `test_phase17_ai_gateway_model_router_platform`, `test_phase18_ai_governance_observability_platform`, `test_qa_phase01_authoritative_config`, `test_qa_phase02_ai_execution_integrity`).
3. **Full Automated Non-GUI Regression Suite:**
   - `python -m pytest -q -m "not gui"`
   - **Result:** **1,659 passed, 0 failed in 180.92s**.

---

## 5. Gate Certification
- [x] Zero compilation or runtime errors.
- [x] All 8 targeted reproduction and regression tests pass.
- [x] 100% of the full automated test suite passes (1,659 tests).
- [x] No weakened assertions or bypassed production gates.
- [x] Canonical documentation updated.

**Gate Decision:** PASSED — Proceed to PHASE-02.
