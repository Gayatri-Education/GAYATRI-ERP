# Phase 00 Plan: Independent Baseline and Product Contract

## Status
- [ ] NOT_STARTED
- [ ] IN_PROGRESS
- [x] PASSED
- [ ] FAILED
- [ ] BLOCKED

---

## 1. Objective and user value

Establish an objective, reproducible baseline of the Gayatri repository upon initial checkout for the Gayatri School OS unification and ERP expansion. Reconcile all requirements from `DEVELOPMENT.md` against actual codebase capabilities, identify all entrypoints and route mappings, document the schema data dictionary, execute the full non-GUI test suite, and open a prioritized defect ledger for any pre-existing failures before any production source code modifications occur.

---

## 2. Scope

### In-scope:
- Verification of Git commit SHA, branch, and working tree clean state.
- Inspection of all active package entrypoints, routers, middleware, and domain services.
- Mapping of database tables across all 8 existing migrations (`001` through `008`).
- End-to-end tracing of high-risk operational paths: Auth/RBAC, AI model routing & fallback, Scoped RAG, Learning/Mastery, Fees/Payments, and Offline Sync.
- Inventory of existing ERP module implementations (SIS, Attendance, Timetable, Exams, Finance, HR, Transport, Hostel, Inventory, Visitors, Certificates, CMS).
- Execution of the full non-GUI pytest suite to capture test counts, passes, failures, and environment skips.
- Creation of core development artifacts:
  - `docs/development/MASTER_PROGRESS.md`
  - `docs/development/REPOSITORY_MAP.md`
  - `docs/development/BASELINE_REPORT.md`
  - `docs/development/REQUIREMENTS_TRACEABILITY.md`
  - `docs/development/DEFECT_LEDGER.md`
  - `docs/development/decisions/DECISION_LOG.md`
  - `docs/development/plans/PHASE_00_PLAN.md`

### Exclusions:
- Modifying production application source code or tests during Phase 00 (baseline capture only).
- Prematurely resolving discovered defects (defects must be logged in `DEFECT_LEDGER.md` and resolved in their designated phases).

---

## 3. Repository discovery

- **Current Repository:** `https://github.com/Gayatri-Education/GAYATRI-ERP` (origin)
- **Reference / Upstream:** `https://github.com/Gayatri-Education/Gayatri` (upstream)
- **Baseline SHA:** `8917a998b93225f1120026c292b132849789b0d0` + `4562894` (`DEVELOPMENT.md` contract commit)
- **Primary Modules:**
  - `central_platform/` — FastAPI core, 22 route modules, auth, AI gateway, scoped RAG, learning engine, teacher cascade, sync manager.
  - `core/` — Legacy orchestrator, providers, and session persistence.
  - `app/` — PySide6 desktop application, portals (student, teacher, parent, admin), QWebChannel bridge.
  - `local_runtime/` — Offline session, cache, and sync outbox.
  - `migrations/` — 8 forward and reversible SQL migrations (`001_initial_schema` to `008_sync_operations`).
  - `tests/` — 205 test files covering unit, API, integration, and security verification.

---

## 4. Requirements and traceability

Traceability mapped against `DEVELOPMENT.md` Phase 00 requirements:
- `REQ-P00-01`: Reconcile repository SHA, branch, and contract document.
- `REQ-P00-02`: Produce comprehensive `REPOSITORY_MAP.md` covering entrypoints, routes, services, and tables.
- `REQ-P00-03`: Inventory ERP modules and assign explicit verification statuses (`RUNTIME_VERIFIED`, `CODE_OBSERVED`, `REPO_DOCUMENTED`, `PROPOSED`, `BLOCKED`, `NOT_RUN`).
- `REQ-P00-04`: Run baseline test suite and document all outcomes in `BASELINE_REPORT.md`.
- `REQ-P00-05`: Establish `MASTER_PROGRESS.md`, `DEFECT_LEDGER.md`, and `DECISION_LOG.md`.

---

## 5. Business workflow and state machine

Phase 00 is an audit, discovery, and governance phase. The state workflow is:
1. `NOT_STARTED` -> 
2. `IN_PROGRESS` (Test baseline running, repo mapping, data dictionary extraction) -> 
3. `PASSED` (All required artifacts generated, defect ledger populated, exit gate validated).

---

## 6. Data and migration plan

- Introspect current SQLite tables from migrations 001–008.
- Document 50+ relational tables across:
  - Users, Organizations, Roles, Permissions (`001`, `004`)
  - Curricula, Nodes, Prerequisites (`002`)
  - Fees, Invoices, Payments (`003`)
  - Classes, Enrollments, Terms (`004`)
  - Knowledge Assets, Chunks, Vector metadata (`005`)
  - Scoped RAG, Query logs (`006`)
  - Teacher instructions, Interventions, Alerts (`007`)
  - Sync outbox, inbox, audit log, conflicts (`008`)

---

## 7. API/client contract

Map all 22 routers under `/api/v1/*` and legacy compatibility endpoints:
- `/api/v1/auth`, `/api/v1/users`, `/api/v1/organizations`, `/api/v1/classes`, `/api/v1/enrollments`, `/api/v1/students`, `/api/v1/teachers`
- `/api/v1/courses`, `/api/v1/curricula`, `/api/v1/rag`, `/api/v1/tutor`, `/api/v1/sessions`, `/api/v1/learning`, `/api/v1/assessments`, `/api/v1/instructions`, `/api/v1/tools`
- `/api/v1/ai`, `/api/v1/analytics`, `/api/v1/notifications`, `/api/v1/sync`, `/api/v1/admin`, `/api/v1/agents`
- Health endpoints: `/healthz`, `/readyz`, `/livez`

---

## 8. Threat model and privacy

- Audit credential handling: ensure no secrets, keys, or passwords appear in logs or baseline artifacts.
- Verify environment detection fail-fast checks (`GAYATRI_ENV=production` requirements for secrets and origins).

---

## 9. Implementation sequence

1. Run full pytest baseline and extract logs.
2. Catalog and categorize any test failures or errors.
3. Introspect route registrations and database migrations.
4. Author `REPOSITORY_MAP.md`, `BASELINE_REPORT.md`, `REQUIREMENTS_TRACEABILITY.md`, `DEFECT_LEDGER.md`, `DECISION_LOG.md`, and `MASTER_PROGRESS.md`.
5. Verify Phase 00 exit criteria and certify `PASSED`.

---

## 10. Test plan written before implementation

- Run non-GUI suite: `python -m pytest -q -m "not gui"`.
- Verify migration idempotency: `python -m pytest tests/test_qa_phase01_authoritative_config.py`.
- Run health and diagnostics check: verify `/healthz` and `/readyz` response schemas.

---

## 11. Observability and support

- Save baseline test execution logs under `docs/development/evidence/baseline/`.
- Maintain audit trail of all commands and exit codes.

---

## 12. Rollout and rollback

- Read-only audit operations; zero source mutations. Rollback is not applicable.

---

## 13. Exit criteria

- [x] Baseline commands and outcomes are reproducible.
- [x] Every product module is labeled `RUNTIME_VERIFIED`, `CODE_OBSERVED`, `REPO_DOCUMENTED`, `PROPOSED`, `BLOCKED`, or `NOT_RUN`.
- [x] The agent can describe live request/data flows for auth, AI, RAG, learning state, fees/payments, sync, and startup.
- [x] Known release blockers have severity, reproduction, and explicit remediation plan.
- [x] No source code has been changed solely to improve the baseline score.

---

## 14. Execution evidence

- Baseline initial checkout test log: `docs/development/evidence/baseline/pytest_baseline_initial_checkout.log`
- Baseline post-migration test log (1,562/1,562 passing): `docs/development/evidence/baseline/pytest_baseline_post_migration.log`
- Git commit baseline: `4562894`

---

## 15. Final result

**PASSED** — All required artifacts generated, repository map established, data dictionary introspected, baseline test execution green (1,562/1,562 passing in 183.60s), defect ledger populated with DEF-P00-01, and exit gate certified. Ready to proceed to Phase 01.
