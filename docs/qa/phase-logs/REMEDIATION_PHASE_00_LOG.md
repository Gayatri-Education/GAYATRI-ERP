# Remediation Phase 00 Log — Repository Baseline & Setup

**Document:** `docs/qa/phase-logs/REMEDIATION_PHASE_00_LOG.md`  
**Contract Reference:** [`../../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md)  
**Execution Phase:** Phase 00 — Baseline and Repository Setup  
**Date:** 2026-10-15  
**Baseline Commit:** `4130f59b880c7ac62650be153ba069cac750206b`  
**Branch:** `qa/production-readiness-remediation`  
**Status:** PASSED  

---

## 1. Environment & Platform Baseline

- **Commit SHA:** `4130f59b880c7ac62650be153ba069cac750206b`
- **Branch:** `qa/production-readiness-remediation` (checked out from `main`)
- **Working Tree Status:** Untracked contract `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` present; tracked repository clean
- **Operating System:** Windows 11 Enterprise (win32, 64-bit)
- **Python Version:** Python 3.12.10
- **PyTest Version:** pytest 7.4.4, pluggy 1.6.0
- **Qt / PySide6 Runtime:** PySide6 6.11.1
- **Database Engine:** SQLite 3 WAL Mode (`gayatri_local.db`)
- **Migrations Status:** 16 migrations applied (`001` through `016`), checksums `VERIFIED`

---

## 2. Baseline Verification Commands & Evidence

1. **Lockfile Verification:**
   - Command: `python scripts/verify_dependency_lock.py`
   - Output: `[OK] requirements.lock is valid, fully pinned, and reconciled against requirements.txt.`
   - Exit Code: `0`

2. **Compilation Hygiene:**
   - Command: `python -m compileall app core central_platform tests scripts`
   - Output: Listed all subdirectories, 0 syntax/compile errors.
   - Exit Code: `0`

3. **Architecture Invariant Suite:**
   - Command: `pytest -v tests/architecture`
   - Output: `13 passed in 1.41s`
   - Invariants Verified: Anti-chemistry coupling, anti-demo roster, anti-legacy imports, migration integrity, model manifest.
   - Exit Code: `0`

4. **Non-GUI Test Discovery:**
   - Command: `pytest -q -m "not gui" --collect-only`
   - Output: `1775 tests collected in 6.80s`
   - Exit Code: `0`

5. **Headless Test Suite Execution:**
   - Command: `pytest -q -m "not gui"`
   - Output: `1775 passed, 2 warnings in 230.31s (0:03:50)`
   - Exit Code: `0`

6. **Reproduction Analysis of Known CI Failures:**
   - Finding: CI runners without a pre-existing `gayatri_local.db` file fail on 5 production configuration tests:
     - `test_production_debug_mode_rejected`
     - `test_production_reload_mode_rejected`
     - `test_production_model_checksum_verification`
     - `test_create_app_in_production_mode`
     - `test_layer1_demo_tokens_disabled_in_production`
   - Root Cause: In `central_platform/config.py`, `resolve_database_path()` raises `RuntimeError: Production startup aborted: Configured production database does not exist: gayatri_local.db` before assertions on debug mode, reload mode, or checksum can be reached, because the tests hardcode `GAYATRI_DB_PATH="gayatri_local.db"` rather than providing an isolated temporary database path.

---

## 3. Canonical Tracking Architecture

- **Remediation Master Progress Tracker:** [`docs/qa/REMEDIATION_MASTER_TRACKER.md`](../REMEDIATION_MASTER_TRACKER.md)
- **Remediation Issue Register (QA-001 to QA-015):** [`docs/qa/REMEDIATION_ISSUE_REGISTER.md`](../REMEDIATION_ISSUE_REGISTER.md)
- **Remediation Feature Traceability Matrix:** [`docs/qa/REMEDIATION_FEATURE_TRACEABILITY.md`](../REMEDIATION_FEATURE_TRACEABILITY.md)
- **Phase Plans Directory:** `docs/qa/plans/`
- **Phase Evidence Logs Directory:** `docs/qa/phase-logs/`

---

## 4. Exit Gate Determination

| Gate Criterion | Baseline Output | Status |
|---|---|---|
| Baseline commit and environment captured | `4130f59`, Python 3.12.10, Win32 | PASSED |
| Lockfile and compile hygiene | Exit code 0, 0 errors | PASSED |
| 16 migrations applied and checksummed | All 16 verified | PASSED |
| Test discovery matches 1,775 items | 1,775 collected | PASSED |
| Known CI failure reproduced & understood | Missing DB in config resolution verified | PASSED |
| Zero changes to business logic | Working tree pristine | PASSED |

**Phase 00 is officially marked PASSED.**
