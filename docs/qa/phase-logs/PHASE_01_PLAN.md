# PHASE-01 PLAN — Authentication, authorization, tenant isolation, and revocation (P0/P1)

## 1. Problem Statement & Audit Targets
This phase addresses findings `ERP-003`, `ERP-004`, `ERP-012`, `ERP-015`, and `ERP-019`:
1. `ERP-003`: `central_platform/auth/tokens.py`: `DatabaseRevocationStore.is_revoked()` swallows database exceptions and returns `False` (fail-open), and `revoke()` swallows database exceptions and returns `True` (reporting false success). `/auth/logout` reports success when no token is provided or when persistence fails.
2. `ERP-004`: Demo tokens and synthetic identity production guardrails must be verified to prevent unauthorized identity assumption in production environments.
3. `ERP-012`: `central_platform/api/routes/ai.py`: AI execution, provider control endpoints, provider toggles, and global kill switch lack server-side authentication and role-based access control.
4. `ERP-015`: Legacy endpoints in `central_platform/api/app.py` (`/api/teacher/*`, `/instruction/*`, `/alert/*`, `/api/student/snapshot`, `/api/sync/events`) lack authentication and tenant isolation, creating potential bypass vectors in production.
5. `ERP-019`: Edge cases in `central_platform/auth/dependencies.py` for optional or missing/malformed bearer tokens must fail safely.

---

## 2. In-Scope Files
- `central_platform/auth/tokens.py`
- `central_platform/auth/dependencies.py`
- `central_platform/api/routes/auth.py`
- `central_platform/api/routes/ai.py`
- `central_platform/api/app.py`
- `tests/test_qa_phase01_auth_remediation.py` (New targeted reproduction and regression suite)

---

## 3. Acceptance Criteria
- [ ] **A1 (ERP-003 - Fail Closed on DB Failure):** When `DatabaseRevocationStore` encounters a database failure during `is_revoked()`, it raises `PermissionError` (or a dedicated exception) so that `decode_and_verify_token()` fails closed and rejects the request.
- [ ] **A2 (ERP-003 - Truthful Revoke Persistence):** `DatabaseRevocationStore.revoke()` returns `False` if database persistence fails, and `/auth/logout` returns HTTP 500 when revocation persistence fails, and HTTP 400 when no token is supplied.
- [ ] **A3 (ERP-004 - Production Identity Isolation):** Synthetic users and demo tokens are strictly rejected in production environments.
- [ ] **A4 (ERP-012 - AI Control Authorization):** AI provider management, toggle, and kill switch endpoints require administrative roles (`SUPER_ADMIN` or `ORG_ADMIN`). Non-admin users (such as `STUDENT`) receive HTTP 403 Forbidden. Unauthenticated requests in production receive HTTP 401 Unauthorized.
- [ ] **A5 (ERP-015 - Legacy Endpoint Guardrails):** In production mode, unauthenticated access to legacy mutating endpoints (`/api/teacher/*`, `/instruction/*`, `/alert/*`, `/api/student/snapshot`) is strictly blocked with HTTP 401/403.
- [ ] **A6 (ERP-019 - Malformed Header Handling):** Malformed, truncated, or invalid `Authorization` headers on protected routes fail closed with HTTP 401/400.
- [ ] **A7 (Full Regression):** Complete automated test suite continues to pass without weakening any existing assertions.

---

## 4. Rollback Strategy
All changes are code-level guards and dependency wiring; no destructive database schema migrations are introduced in Phase 01. In the event of an unexpected regression, git revert cleanly restores previous behavior.
