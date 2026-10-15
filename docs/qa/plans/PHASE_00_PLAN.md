# Phase 00 Plan — Baseline and Repository Setup

**Document:** `docs/qa/plans/PHASE_00_PLAN.md`  
**Contract Reference:** [`../../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md)  
**Phase:** 00 — Baseline and Repository Setup  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective & Scope

Establish an empirical baseline for the Gayatri-ERP QA Remediation without altering business logic:
1. Record commit SHA, branch name, working tree cleanliness, environment versions (Python 3.12.10, Windows 11 Enterprise, pytest 7.4.4, PySide6 6.11.1).
2. Validate lockfile integrity via `python scripts/verify_dependency_lock.py`.
3. Check database migrations and schema checksums on SQLite WAL (`gayatri_local.db`).
4. Execute static compile check across all packages (`app`, `core`, `central_platform`, `tests`, `scripts`).
5. Execute architecture invariant suite (`pytest -v tests/architecture`).
6. Enumerate and collect complete non-GUI test suite (1,775 items).
7. Confirm current names and paths for the canonical progress tracker, issue register, phase plans, and phase logs.
8. Resolve root-level vs `docs/` duplicates and map dependencies across modules, routes, entry points, and UI bridges.
9. Construct a feature traceability matrix distinguishing verified, partial, simulated, and blocked features.

---

## 2. Likely Files & Scope Boundary

- `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` (Governing Contract)
- `docs/qa/plans/PHASE_00_PLAN.md`
- `docs/qa/phase-logs/REMEDIATION_PHASE_00_LOG.md`
- `docs/qa/REMEDIATION_MASTER_TRACKER.md`
- `docs/qa/REMEDIATION_ISSUE_REGISTER.md`
- `docs/qa/REMEDIATION_FEATURE_TRACEABILITY.md`
- `scripts/verify_dependency_lock.py`
- `scripts/migrate_db.py`

---

## 3. Targeted Baseline Checks

1. `git rev-parse HEAD` & `git status --short`.
2. Python, OS, and PyTest version capture.
3. Lockfile verification result.
4. Database migration status (16 migrations).
5. Code compilation check (`python -m compileall`).
6. Architecture suite execution (`pytest -v tests/architecture`).
7. Full non-GUI test suite collection (`pytest -q -m "not gui" --collect-only`).
8. Reproduction analysis of CI failure defect (missing DB in production config tests).

---

## 4. Exit Criteria (Binary Gate)

- [ ] Baseline commit, branch, and environment captured.
- [ ] Lockfile, compilation, and architecture checks pass cleanly.
- [ ] Migration inventory (16 migrations) verified with checksum validation.
- [ ] Test discovery count accurately recorded (1,775 tests).
- [ ] Canonical tracking and documentation files identified and initialized.
- [ ] Traceability matrix authored with truthful statuses.
- [ ] Zero changes made to production business logic in Phase 00.
