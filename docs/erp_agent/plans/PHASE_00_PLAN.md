# Phase 00 Plan — Discovery and Independent Baseline

**Document:** `docs/erp_agent/plans/PHASE_00_PLAN.md`  
**Contract:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 00 — Discovery and Independent Baseline  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 00 establishes the verified, independent baseline of the Gayatri-ERP repository. Before modifying any application source code or claiming production readiness for features outlined in `ERP_TRANSFORMATION_DEVELOPMENT.md`, the coding agent must:
1. Reconcile documentation with actual code and migrations.
2. Map entry points, package structure, registered routers, identity/auth/RBAC, tenant scoping, database schema, domain services, UI/bridge layers, SLM/RAG invocation, async jobs, sync/outbox, payment workflows, document storage, and testing frameworks.
3. Capture exact commit SHA, working-tree status, OS, Python version, dependency locks, and database schema version.
4. Execute baseline compilation hygiene, dependency reconciliation, architecture guardrails, and full test suites without altering application code.
5. Create the initial `REPOSITORY_MAP.md`, `BASELINE_REPORT.md`, and `FEATURE_TRACEABILITY.md`.

---

## 2. Likely Files & Scope Boundary

### Documents to Generate / Update
- `docs/erp_agent/plans/PHASE_00_PLAN.md` (this file)
- `docs/erp_agent/REPOSITORY_MAP.md` (comprehensive source and router map)
- `docs/erp_agent/BASELINE_REPORT.md` (environment, commit, and baseline test results)
- `docs/erp_agent/FEATURE_TRACEABILITY.md` (traceability of all Sections 5.A through 5.J requirements)
- `docs/erp_agent/reports/PHASE_00_REPORT.md` (Phase 00 closure report)
- `docs/erp_agent/regressions/PHASE_00_REGRESSION.md` (exact regression evidence)
- `docs/erp_agent/MASTER_PROGRESS.md` (phase gate progression)
- `docs/erp_agent/BLOCKERS.md` (blocker updates)

### Files Intentionally Preserved / Not Changed
- All production code in `central_platform/*`, `app/*`, `core/*`, `local_runtime/*`.
- All migration scripts in `migrations/*`.
- All existing tests in `tests/*`.
- Existing historical QA logs and registers in `docs/qa/`, `docs/qa_agent/`, `docs/release/`.

---

## 3. Workflows and Existing Behavior Mapping

1. **FastAPI Platform (`central_platform/api/app.py`)**:
   - Inspect all 38+ registered router modules under `/api/v1/*` and legacy `/api/*`.
   - Verify health probes (`/healthz`, `/livez`, `/readyz`, `/health/deep`).
   - Validate middleware chain: `RequestIDMiddleware`, `SecurityHeadersMiddleware`, `StructuredLoggingMiddleware`, and exception handlers.

2. **Database & Migrations (`central_platform/db.py`, `scripts/migrate_db.py`, `migrations/`)**:
   - SQLite WAL mode with foreign keys enabled.
   - 16 SQL migrations (001 through 016) with SHA-256 integrity checksums.
   - Verify table definitions against `docs/DATA_MODEL.md` and ERP transformation requirements.

3. **Multi-Tenant Identity & RBAC (`central_platform/auth/`, `central_platform/rbac/`)**:
   - Role definitions: `SUPER_ADMIN`, `ORG_ADMIN`, `TEACHER`, `STUDENT`, `PARENT`, `GUEST`.
   - Token creation, JWT validation, database-backed token revocation, and header handling.
   - Tenant isolation via `organization_id` scoping in DAL and services.

4. **ERP Domain Services**:
   - Admissions & CRM (`central_platform/admissions/service.py`)
   - Attendance & Biometrics (`central_platform/attendance/service.py`)
   - Academics & Timetable (`central_platform/academic/service.py`, `central_platform/timetable/service.py`)
   - Examinations & Grading (`central_platform/examinations/service.py`, `central_platform/grading/service.py`)
   - HR & Payroll (`central_platform/hr/service.py`)
   - Finance & Payments (`central_platform/finance/service.py`, `central_platform/payments/`)
   - Campus Facilities (`central_platform/campus/`, `central_platform/transport/service.py`, `central_platform/hostel/service.py`, `central_platform/inventory/service.py`)
   - Communications & Messaging (`central_platform/communications/service.py`, `central_platform/notifications/service.py`)
   - CMS (`central_platform/cms/service.py`)
   - AI Gateway & RAG (`central_platform/ai/`, `central_platform/rag/`, `core/`)
   - Desktop UI Shell & Bridges (`app/`, `central_platform/portals/`)

---

## 4. Verification & Baseline Execution Strategy

1. **Compilation Hygiene**: `python -m compileall app core central_platform tests scripts` (must exit 0 with 0 errors).
2. **Dependency Lock Check**: `python scripts/verify_dependency_lock.py` (must reconcile cleanly).
3. **Architecture Suite**: `pytest -v tests/architecture` (13/13 passing).
4. **Focused Smoke Tests**: `pytest tests/test_qa_phase14_e2e_product_acceptance.py tests/test_qa_phase16_final_audit_handover.py tests/test_server_live_sync.py` (30/30 passing).
5. **Full Headless Suite**: `pytest -q -m "not gui"` (capture exact pass count, duration, and test status).

---

## 5. Exit Criteria (Binary Gate)

- [ ] All codebase modules compile with zero syntax/compilation errors.
- [ ] Database schema migrations 001–016 confirmed verified on disk and in database.
- [ ] Environment, OS, Python version, commit SHA recorded accurately in `BASELINE_REPORT.md`.
- [ ] Comprehensive `REPOSITORY_MAP.md` generated documenting all packages, routers, models, services, and call graphs.
- [ ] Initial `FEATURE_TRACEABILITY.md` established mapping all 72 requirements of Sections 5.A–5.J with initial evidence and disposition.
- [ ] Baseline test results captured and logged in `docs/erp_agent/evidence/`.
- [ ] `docs/erp_agent/reports/PHASE_00_REPORT.md` written and linked in `MASTER_PROGRESS.md`.
- [ ] Zero code changes made to application source during Phase 00.
