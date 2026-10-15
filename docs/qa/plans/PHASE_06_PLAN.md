# Phase 06 Implementation Plan — Central Authorization & Tenant-Isolation Audit (QA-006)

**Contract Reference:** [`../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md) § 9  
**Parent Issue:** QA-006 (Central authorization and tenant-isolation audit across every route)  
**Branch:** `qa/production-readiness-remediation`  
**Execution Date:** 2026-10-15  

---

## 1. Problem Statement & Audit Findings

During the Phase 06 automated route inventory and code audit across all 38 router modules and the central `app.py`, multiple authorization and tenant-isolation vulnerabilities were identified:

1. **Ad-Hoc and Broken Role Checks:**
   - In `central_platform/api/routes/ops_gate.py`:
     - `/release-gate` compares `current_user.role` directly to raw string tuples `("admin", "org_admin", "super_admin")`.
     - `/release-manifest` contains **no role check whatsoever**, allowing any authenticated user (e.g. students or parents) to query release manifests and server paths.
   - In `central_platform/api/routes/organizations.py`:
     - `create_organization`: checks `role_str = current_user.role.value if isinstance(...) else ...` and then evaluates `if role_str != "SUPER_ADMIN":`. Because `UserRole.SUPER_ADMIN.value` is `"super_admin"` (lowercase), this comparison **fails even for valid Super Admins** (`"super_admin" != "SUPER_ADMIN"`).
   - In `central_platform/api/routes/curricula.py`:
     - `_enforce_authoring_auth` only blocks `STUDENT`, allowing `PARENT` to author or import curricula (fail-open).
   - In `central_platform/api/routes/admin.py`:
     - `_enforce_admin_auth` only checks `if current_user.role in (UserRole.STUDENT, UserRole.TEACHER)`, allowing `PARENT` or other non-admin roles to access admin dashboards (fail-open).
   - In `central_platform/api/routes/users.py`:
     - `list_users` only checks `STUDENT`, allowing `PARENT` to list platform users. Furthermore, if an `ORG_ADMIN` omits `organization_id`, the query returns users across **all organizations**.
   - In `central_platform/api/routes/classes.py`:
     - `create_class_group` and `create_cohort_for_class` use inconsistent string upper-casing comparisons against `UserRole.STUDENT.value` and `"SUPER_ADMIN"`.

2. **Unauthenticated Sensitive Endpoints:**
   - In `central_platform/api/routes/ai.py`:
     - `GET /ai/observability/metrics`, `GET /ai/observability/logs`, `GET /ai/governance/budgets`, `GET /ai/governance/circuit-breakers`, `GET /ai/governance/allowlist`, and `GET /ai/governance/cost-breakdown` require no authentication at all, exposing platform telemetry, student IDs, and financial budget data.
   - In `central_platform/api/routes/classes.py`:
     - `GET /classes`, `GET /classes/{class_id}`, and `GET /classes/{class_id}/cohorts` lack authentication and tenant isolation.
   - In `central_platform/api/routes/instructions.py`:
     - `GET /instructions` and `GET /instructions/{instruction_id}` lack authentication and tenant isolation.
     - `DELETE /instructions/{instruction_id}` lacks tenant validation.
   - In `central_platform/api/routes/organizations.py`:
     - `GET /organizations` and `GET /organizations/{org_id}` lack authentication and tenant isolation.

3. **Cross-Tenant IDOR and Missing Scoping in SQL Queries:**
   - In `central_platform/api/routes/enrollments.py`:
     - `GET /enrollments` queries all enrollments without an organization filter when `student_id` is omitted.
     - `GET /enrollments/{enrollment_id}` returns any enrollment across any organization to any non-student caller without verifying tenant match.
   - In `central_platform/auth/dependencies.py`:
     - `enforce_resource_boundaries` only validates `target_org_id` if explicitly supplied by the route caller. When routes pass `target_student_id` alone, non-super admins from other organizations could access foreign student records.

---

## 2. Target Invariants

1. **Uniform Role Normalization:**
   - Every route and helper must normalize user roles via `normalize_role(current_user.role)` or use `require_roles(...)`.
   - No direct raw string equality, casing assumptions, or ad-hoc tuples.
   - Admin routes must fail-closed: strictly require `UserRole.SUPER_ADMIN` or `UserRole.ORG_ADMIN`.

2. **Fail-Closed Tenant Isolation:**
   - A non-super-admin user can NEVER access, list, mutate, or delete resources belonging to another organization.
   - If an `ORG_ADMIN` queries a listing endpoint without `organization_id`, the endpoint must automatically scope results to `current_user.organization_id`.
   - Guessed IDs across tenant boundaries must result in HTTP 403 Forbidden or HTTP 404 Not Found, never data disclosure.
   - `enforce_resource_boundaries` must automatically resolve `target_student_id` to its parent organization and enforce tenant isolation when `target_org_id` is omitted.

3. **No Unauthenticated Sensitive Endpoints:**
   - Administrative telemetry, AI observability, AI governance, class rosters, pedagogical instructions, and organization directories must require valid authentication and authorized roles.
   - Legitimate anonymous endpoints remain strictly limited to: public health probes (`/healthz`, `/livez`, `/readyz`, `/api/v1/health`), public UI/static assets, public admissions intake (`/admissions/inquiries`), public CMS pages (`/cms/public/pages`), and auth credential endpoints (`/auth/login`, `/auth/refresh`, `/auth/password-reset`, `/auth/logout`).

---

## 3. Implementation Steps

1. **Update `central_platform/auth/dependencies.py`:**
   - Hardened `enforce_resource_boundaries`: when `target_student_id` is provided and `target_org_id` is omitted, resolve student's organization from DB and enforce tenant isolation against `current_user.organization_id` for non-super admins.

2. **Refactor `central_platform/api/routes/ops_gate.py`:**
   - Standardize role check on `/release-gate` using `normalize_role(current_user.role) in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)`.
   - Protect `/release-manifest` with the same role requirement.

3. **Refactor `central_platform/api/routes/organizations.py`:**
   - Fix `create_organization`: use `normalize_role(current_user.role) != UserRole.SUPER_ADMIN`.
   - Require authentication on `list_organizations` and `get_organization`; scope to caller's tenant unless `SUPER_ADMIN`.

4. **Refactor `central_platform/api/routes/ai.py`:**
   - Require `require_roles(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)` on `/ai/observability/metrics`, `/ai/observability/logs`, `/ai/governance/budgets`, `/ai/governance/circuit-breakers`, `/ai/governance/allowlist`, and `/ai/governance/cost-breakdown`.
   - Standardize `_verify_ai_admin_access` and `_verify_ai_read_access`.

5. **Refactor `central_platform/api/routes/classes.py`:**
   - Standardize role checks with `normalize_role`.
   - Require authentication on `list_classes`, `get_class_group`, `list_cohorts_for_class`; enforce organization scoping for non-super admins.

6. **Refactor `central_platform/api/routes/instructions.py`:**
   - Standardize role checks with `normalize_role`.
   - Require authentication on `list_instructions`, `get_instruction`, `delete_instruction`; enforce tenant boundary on deletion.

7. **Refactor `central_platform/api/routes/users.py`, `admin.py`, `curricula.py`, `enrollments.py`, `courses.py`, `agents.py`:**
   - Eliminate all ad-hoc string comparisons and fail-open role checks.
   - Prevent cross-tenant leaks in `enrollments.py:list_enrollments` and `get_enrollment`.
   - Restrict `users.py:list_users` to `SUPER_ADMIN` and `ORG_ADMIN`, forcing tenant scoping.

8. **Generate Authoritative Route Authorization Matrix:**
   - Generate and commit `docs/qa/REMEDIATION_ROUTE_AUTHORIZATION_MATRIX.md` covering all routes.

9. **Author Test Suite `tests/test_phase06_rbac_tenant_audit.py`:**
   - Positive and negative authorization tests across all affected routes.
   - IDOR prevention across tenants.
   - Role escalation rejection.
   - Regression verification of the entire suite.

---

## 4. Exit Criteria

- Complete route authorization matrix checked into `docs/qa/REMEDIATION_ROUTE_AUTHORIZATION_MATRIX.md`.
- All ad-hoc role comparisons replaced with centralized `normalize_role` and RBAC dependencies.
- Zero IDOR cross-tenant leaks across students, enrollments, classes, instructions, users, and admin endpoints.
- 100% pass rate in `tests/test_phase06_rbac_tenant_audit.py` and zero regressions across existing test suites.
