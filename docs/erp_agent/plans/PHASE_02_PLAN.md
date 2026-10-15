# Phase 02 Plan — Shared Identity, Tenancy, Permissions and Audit Foundation

**Document:** `docs/erp_agent/plans/PHASE_02_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 02 — Shared Identity, Tenancy, Permissions and Audit Foundation  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 02 verifies and hardens the foundational identity, multi-tenant isolation, authorization scoping, migration ledger, and security auditing layers across the platform:
1. Validate organizations, branches, academic sessions, and user identities.
2. Verify that tenant scoping is derived strictly server-side from authenticated principal credentials and database grants.
3. Verify that client-supplied `X-Branch-ID` or `organization_id` queries cannot bypass authorization or escalate privileges.
4. Verify multi-worker token revocation using the persistent `revoked_tokens` database ledger.
5. Verify parent-to-child relationship boundaries (unrelated child records cannot be read or modified).
6. Verify security audit logging convention (`SecurityAuditor.sanitize_pii_logs`) ensuring zero secret, password, or PII leaks in audit tables.
7. Verify migration ledger stability and isolated database restore drills.

---

## 2. Likely Files & Scope Boundary

- `central_platform/auth/dependencies.py` (server-side caller resolution & tenant scoping)
- `central_platform/auth/tokens.py` (JWT issuance, bcrypt hashing, revocation checks)
- `central_platform/rbac/engine.py` (normalized roles & permission matrix)
- `central_platform/security/audit.py` & `auditor.py` (scrubbed audit trails)
- `central_platform/db.py` (connection management, WAL configuration, transactions)
- `migrations/` (migrations 001–009)
- `tests/test_qa_phase01_auth_remediation.py`
- `tests/test_qa_phase02_db_lifecycle_transactions.py`
- `tests/test_qa_phase05_auth_revocation_ratelimit.py`
- `tests/test_qa_phase08_security_adversarial.py`
- `tests/test_phase07_tenant_isolation.py`
- `tests/test_phase3_auth_rbac.py`

---

## 3. Targeted Test Scenarios

1. Missing, malformed, or expired JWT tokens return `401 Unauthorized`.
2. Spoofed `X-Branch-ID` or cross-tenant org queries return `403 Forbidden`.
3. Revoked tokens are rejected across processes and threads.
4. Role escalation attempts (e.g., student calling admin endpoints) return `403 Forbidden`.
5. Parent accessing an unrelated child's session, marks, or fees returns `403 Forbidden` / `404 Not Found`.
6. Sensitive credentials (passwords, tokens, full emails) are redacted in audit logs.
7. Database migrations apply cleanly forward and backward without data corruption.

---

## 4. Exit Criteria (Binary Gate)

- [ ] All targeted identity, tenancy, RBAC, and audit test suites pass with 100% success.
- [ ] Server-derived scope enforcement confirmed across all tested API endpoints.
- [ ] Multi-worker token revocation verified in persistent database table.
- [ ] Audit logs verified clean of secret or unmasked PII leakage.
- [ ] Database backup and restore drill verified in an isolated test environment.
- [ ] `docs/erp_agent/reports/PHASE_02_REPORT.md` and `docs/erp_agent/regressions/PHASE_02_REGRESSION.md` generated with passing evidence.
