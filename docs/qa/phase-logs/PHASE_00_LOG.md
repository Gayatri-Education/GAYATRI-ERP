# PHASE-00 — Repository baseline, inventory, and reproducibility

## Current status: PASSED
## Baseline commit / branch: `becd081b295cbad6c0920a352f493d57671bb0e8` / `dev/phase-00-baseline`

---

## 1. Discovery and dependency map

### 1.1 Environment & Platform Specifications
- **Operating System:** Windows 11 Enterprise (64-bit)
- **Python Version:** 3.12.10
- **PyTest Version:** 7.4.4
- **FastAPI / Pydantic:** FastAPI 0.141.1, Pydantic 2.13.4
- **PySide6 / Qt Runtime:** 6.11.1
- **SQLite Engine:** SQLite 3 WAL Mode, 16 sequential migrations applied (`001` through `016`), checksums verified.
- **Git Remotes:**
  - `origin`: `https://github.com/Gayatri-Education/GAYATRI-ERP.git`
  - `upstream`: `https://github.com/Gayatri-Education/Gayatri.git`
- **Environment Variables Checked (Keys Only):**
  - `GAYATRI_ENV`, `GAYATRI_DB_PATH`, `GAYATRI_JWT_SECRET`, `GAYATRI_ENCRYPTION_KEY`, `GAYATRI_ALLOWED_ORIGINS`, `GAYATRI_LOCAL_MODEL_PATH`, `DEBUG`, `RELOAD`, `FASTAPI_DEBUG`

### 1.2 Route & Subsystem Inventory
All 21 REST router groups mounted under `/api/v1/*` in `central_platform/api/app.py`:
1. `/api/v1/auth` (`central_platform/api/routes/auth.py`)
2. `/api/v1/users` (`central_platform/api/routes/users.py`)
3. `/api/v1/organizations` (`central_platform/api/routes/organizations.py`)
4. `/api/v1/classes` (`central_platform/api/routes/classes.py`)
5. `/api/v1/enrollments` (`central_platform/api/routes/enrollments.py`)
6. `/api/v1/students` (`central_platform/api/routes/students.py`)
7. `/api/v1/teachers` (`central_platform/api/routes/teachers.py`)
8. `/api/v1/courses` (`central_platform/api/routes/courses.py`)
9. `/api/v1/curricula` (`central_platform/api/routes/curricula.py`)
10. `/api/v1/rag` (`central_platform/api/routes/rag.py`)
11. `/api/v1/tutor` (`central_platform/api/routes/tutor.py`)
12. `/api/v1/sessions` (`central_platform/api/routes/sessions.py`)
13. `/api/v1/learning` (`central_platform/api/routes/learning.py`)
14. `/api/v1/assessments` (`central_platform/api/routes/assessments.py`)
15. `/api/v1/instructions` (`central_platform/api/routes/instructions.py`)
16. `/api/v1/tools` (`central_platform/api/routes/tools.py`)
17. `/api/v1/ai` (`central_platform/api/routes/ai.py`)
18. `/api/v1/analytics` (`central_platform/api/routes/analytics.py`)
19. `/api/v1/notifications` (`central_platform/api/routes/notifications.py`)
20. `/api/v1/sync` (`central_platform/api/routes/sync.py`)
21. `/api/v1/admin` (`central_platform/api/routes/admin.py`)
Health Probes: `/healthz`, `/readyz`, `/livez`, `/health`

ERP Module Subsystems:
- SIS & Admissions (`central_platform/sis/`, `central_platform/admissions/`)
- Attendance & Timetable (`central_platform/attendance/`, `central_platform/timetable/`)
- Examinations & Grading (`central_platform/examinations/`, `central_platform/grading/`)
- Finance & Invoicing (`central_platform/finance/`, `central_platform/fees/`, `central_platform/payments/`)
- HR & Payroll (`central_platform/hr/`)
- Transport & Logistics (`central_platform/transport/`)
- Hostel & Boarding (`central_platform/hostel/`)
- Inventory & Assets (`central_platform/inventory/`)
- Visitors & Gate Passes (`central_platform/campus/`)
- Official Certificates (`central_platform/academic/`)
- Public CMS (`central_platform/operations/`)
- Edge Biometric Daemon (`central_platform/edge/daemon.py`)

---

## 2. Reproduction steps and evidence

### 2.1 Full Compilation Check
- **Command:** `python -m compileall central_platform app core local_runtime scripts`
- **Result:** Exit Code 0, 0 compilation errors across all modules.

### 2.2 Database Migration Integrity
- **Command:** `python scripts/migrate_db.py status --db-path gayatri_local.db`
- **Result:** Exit Code 0. 16/16 migrations applied up (`001` to `016`). Checksum integrity VERIFIED.

### 2.3 Automated Test Suite Baseline
- **Command:** `python -m pytest -q -m "not gui"`
- **Collected:** 1,651 tests
- **Result:** 1,651 passed in 235.45s (0 failures, 0 errors, 0 skipped)
- **Exit Code:** 0

---

## 3. Plan and acceptance criteria

### Acceptance Criteria for PHASE-00:
1. `A1`: Repository environment, runtime versions, and git remotes recorded. [VERIFIED]
2. `A2`: Compilation and migration integrity verified. [VERIFIED]
3. `A3`: Full automated test suite executed and exact baseline metrics captured. [VERIFIED]
4. `A4`: Initial issue register (`ERP-001` through `ERP-022`) audited and scheduled. [VERIFIED]
5. `A5`: Canonical tracking files established under `docs/qa/` and `docs/development/`. [VERIFIED]

---

## 4. Human approval (if required)
Autonomous execution under `/goal` following `GAYATRI_ERP_DEVELOPMENT_GUIDE.md` execution loop.

---

## 5. Implementation summary
- Created `docs/qa/phase-logs/` directory.
- Reconciled and placed canonical files:
  - `docs/development/DEVELOPMENT_GUIDE.md`
  - `docs/qa/PROGRESS_TRACKER.yaml`
  - `docs/qa/ISSUE_REGISTER.md`
  - `docs/qa/FILE_CLEANUP_REPORT.md`
- Captured baseline test suite evidence (1,651 passed).

---

## 6. Tests run (commands, environment, exit codes)
1. `python -m compileall central_platform app core local_runtime scripts` (Exit Code 0)
2. `python scripts/migrate_db.py status --db-path gayatri_local.db` (Exit Code 0)
3. `python -m pytest --collect-only -q -m "not gui"` (Exit Code 0, 1651 collected)
4. `python -m pytest -q -m "not gui"` (Exit Code 0, 1651 passed in 235.45s)

---

## 7. Debugging and root cause
No active failures in the test baseline; existing 1,651 regression tests pass cleanly on current checkout. Seed audit findings (`ERP-001` through `ERP-022`) are scheduled for targeted re-validation in their respective phases.

---

## 8. Regression results
1,651 of 1,651 passing tests (100% pass rate).

---

## 9. Security / privacy / data-integrity review
- Multi-worker token revocation store verified (`DatabaseRevocationStore`).
- Multi-tenant query isolation verified across DAL.
- No secrets or credentials leaked in logs.

---

## 10. Documentation and cleanup impact
- Synced development guide and trackers to canonical paths in `docs/qa/` and `docs/development/`.

---

## 11. GitHub issue / PR / commit links
- Branch: `dev/phase-00-baseline`
- Baseline SHA: `becd081b295cbad6c0920a352f493d57671bb0e8`

---

## 12. Residual risks / blockers
- Seed findings ERP-001 through ERP-022 must be systematically re-audited and proven with targeted regression tests in Phases 01 through 14.

---

## 13. Gate decision: PASS
All Phase 00 exit criteria have been satisfied with reproducible evidence. Ready to advance to Phase 01.
