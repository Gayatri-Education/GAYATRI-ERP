# Phase 14 Plan — Custom Fields, Navigation, Modules & Multi-Branch Governance

**Document:** `docs/erp_agent/plans/PHASE_14_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 14 — Custom Fields, Navigation, Modules & Multi-Branch Governance  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 14 verifies safe configuration, modular governance, custom fields, and multi-tenant/multi-branch authorization:
1. **Module Governance & Feature Flags:** Dynamic activation/deactivation of modules (`hr`, `payroll`, `transport`, `hostel`, `inventory`, `campus`, `cms`) per tenant without server restart.
2. **Multi-Level RBAC Boundaries:** Super Admin, Org Admin, Course Admin, Teacher, and Student roles with strict boundary enforcement. Org Admin cannot escalate privileges or mutate cross-organization records.
3. **Multi-Branch Isolation:** Strict organization-scoped data isolation across users, courses, admissions, fees, and operational aggregates.
4. **Audit Trail Immutability & Searchability:** All administrative actions (user provisioning, org creation, config mutation, privilege changes) generate structured, immutable audit log entries.
5. **Safe Configurable Fields & Validation:** Parameterized SQL queries without arbitrary code execution or unsanitized dynamic SQL interpolation.
6. **Reversible Configuration:** Granular permissions and versioned configurations with fail-closed safety.

---

## 2. Likely Files & Scope Boundary

- `central_platform/admin/service.py` (`AdminService`)
- `central_platform/models/identity.py` (`ModuleEntitlement`, `StaffProfile`, `StudentProfile`)
- `central_platform/models/schema.py` (`Organization`, `User`, `UserRole`, `AuditLog`)
- `central_platform/security/auditor.py` (`SecurityAuditor`)
- `central_platform/db.py` (`PlatformDatabase`)
- `tests/test_phase13_admin_portal.py`
- `tests/test_qa_phase08_security_adversarial.py`
- `tests/test_qa_phase11_contracts_validation_idempotency.py`
- `tests/test_audit_phase30_33.py`

---

## 3. Targeted Test Scenarios

1. Organization lifecycle: Super Admin creates organizations and verifies initial audit trail.
2. Global config mutations: Super Admin can update global configuration; Org Admin is rejected with `PermissionError`.
3. Tenant isolation & user provisioning: Org Admin creates users strictly within their organization; cross-tenant provisioning attempts raise `PermissionError`.
4. Role escalation prevention: Org Admin cannot create Super Admin users or escalate their own privileges.
5. Cross-tenant IDOR defense: Reading or mutating resources across organization boundaries is rejected.
6. Safe parameter binding: SQL injection attempts are safely treated as literal strings without dynamic SQL interpolation.
7. Contract validation: Invalid roles rejected with HTTP 422 at API perimeter.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Multi-tenant organization isolation verified.
- [ ] Multi-level RBAC role boundaries and escalation prevention verified.
- [ ] Audit log immutability and tracking verified.
- [ ] Safe parameter binding and anti-SQL injection verified.
- [ ] Zero unauthorized cross-branch or cross-tenant data leaks.
- [ ] `docs/erp_agent/reports/PHASE_14_REPORT.md` and `docs/erp_agent/regressions/PHASE_14_REGRESSION.md` generated with passing evidence.
