# Phase 10 Plan — Packaging, Deployment & Upgrade Safety

**Objective:** Prove that the platform cleanly installs, bootstraps, migrates schemas, preserves backups, and executes without developer-only environment assumptions or hidden dependencies.

---

## 1. Scope & Targeted Subsystems

1. **Clean-Install Validation (Task 10.1):**
   - Bootstrap from a clean, non-existent database file in an isolated temporary directory.
   - Run complete forward migrations (001 through 008) and verify tables exist and have valid foreign keys and indexes.

2. **Launch & Entry Point Verification (Task 10.2):**
   - Batch script presence and syntax integrity: `setup.bat`, `run.bat`, `run_gayatri.bat`, `launch.bat`.
   - Python entry points: `app.main`, `central_platform.db.PlatformDatabase`.
   - Handling of missing local models with clear user warnings instead of unhandled crashes.

3. **User Workflow Lifecycle (Task 10.3):**
   - Session lifecycle: provision student -> create course/enrollment -> start turn -> evaluate response -> commit state to DB -> close -> reload session and verify continuity.

4. **Upgrade Migration & Disaster Recovery (Task 10.4):**
   - Live database snapshot backup creation.
   - Catastrophic database destruction simulation.
   - Database restore from snapshot and 100% record integrity verification.

5. **Deployment Configuration & Production Gate (Task 10.5):**
   - `DeploymentValidator` execution across all 8 production categories (Environment, Security, Database, Models, Storage, Network, Observability, Governance).
   - Validation that production mode strictly enforces secret hygiene and physical model presence.

---

## 2. Dev Loop Steps

1. **Plan Authoring:** Commit `docs/qa_agent/plans/PHASE_10_PLAN.md`.
2. **Focused Tests:**
   - Author `tests/test_qa_phase10_packaging_deployment.py`.
   - Run focused suite (`pytest tests/test_qa_phase10_packaging_deployment.py tests/test_phase26_packaging_clean_install.py tests/test_phase26_data_migration_backup_restore_master.py tests/architecture/test_migration_integrity.py -v`).
3. **Full Regression:**
   - Run `pytest -q` across the entire codebase.
4. **Decisions & Reporting:**
   - Log `DEC-010` in `docs/qa_agent/decisions/DECISION_LOG.md`.
   - Write `docs/qa_agent/reports/PHASE_10_REPORT.md`.
   - Update `docs/qa_agent/MASTER_PROGRESS.md`.
