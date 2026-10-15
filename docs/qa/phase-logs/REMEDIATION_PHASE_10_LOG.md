# Remediation Phase 10 Log — Install, Dependency Lock, Packaging & Model Readiness (QA-010)

**Phase:** Phase 10  
**Issue Identifier:** QA-010  
**Status:** PASSED  
**Date:** 2026-10-15  
**Branch:** `qa/production-readiness-remediation`  
**Test Suite:** `tests/test_phase10_packaging_and_readiness.py` (9/9 passed, 108/108 regression passed)

---

## 1. Objectives & Executive Summary
Phase 10 eliminated packaging, version declaration, dependency locking, and launcher script discrepancies across Windows and POSIX environments.

Key results:
1. **Product Version Alignment:** Resolved version discrepancy where `pyproject.toml` declared `5.0.0` while `VERSION`, `README.md`, `packaging/installer.iss`, `packaging/gayatri_demo.spec`, and `app.main --version` declared `3.0.1`. Synchronized `pyproject.toml` to `3.0.1`.
2. **Deterministic Setup Scripting (`setup.bat`):** Aligned Windows setup to prioritize pinned `requirements.lock` before falling back to `requirements.txt`, added dependency lock validation via `scripts/verify_dependency_lock.py`, database schema migration, and bytecode compilation verification.
3. **Multi-Mode Application Launcher (`launch.bat`):** Enhanced Windows launcher to support `launch.bat server` (FastAPI central platform on port 8000), `launch.bat smoke` (post-install smoke test validator), and `launch.bat desktop` (PySide6 desktop UI with argument forwarding and fail-closed exit code propagation).
4. **Dependency Lock Strict Pinning:** Confirmed `requirements.lock` contains 77 strictly pinned (`==`) packages and reconciled all direct runtime dependencies from `requirements.txt`.
5. **Transparent AI Model Readiness:** Verified `LocalProvider` fails closed with `LocalModelError` on missing weights and `DeploymentValidator` declares non-healthy (`CONFIGURED`/`UNVERIFIED`) status rather than false positive `HEALTHY` when weights are absent.
6. **Cryptographic Release Manifest Generation:** Validated `scripts/generate_release_manifest.py` correctly hashes all 16 migration scripts, core source files, git commit SHA, and generates canonical `manifest_sha256`.

---

## 2. Root Cause Analysis
- **Version Discrepancy:** Stale `pyproject.toml` from early prototyping retained `5.0.0` while the formal release lineage across `VERSION`, Inno Setup, PyInstaller, and documentation anchored on `3.0.1`.
- **Setup Drift:** `setup.bat` historically executed `pip install -r requirements.txt`, risking dependency drift, whereas CI and `setup.sh` utilized `requirements.lock`.
- **Launcher Mode Divergence:** `launch.sh` supported `server`, `smoke`, and `desktop` CLI modes, while `launch.bat` only supported launching `app.main`.

---

## 3. Remediation & Implementation Details
- **`pyproject.toml`:** Updated `version = "3.0.1"`.
- **`setup.bat`:**
  - Added check for `requirements.lock` as primary target.
  - Added post-install lock verifier invocation (`scripts/verify_dependency_lock.py`).
  - Added automated database migration (`scripts/migrate_db.py up --db-path gayatri_local.db`).
  - Added bytecode compilation hygiene (`python -m compileall app core central_platform scripts -q`).
- **`launch.bat`:**
  - Added argument parsing for `%1` (`server`, `smoke`, `desktop`).
  - Added exit code propagation (`exit /b %errorlevel%`) to prevent swallowed failures.
- **`scripts/generate_release_manifest.py`:** Regenerated `RELEASE_MANIFEST.json` against current commit SHA.
- **`tests/test_phase10_packaging_and_readiness.py`:** Authored 9 test cases covering version consistency, dependency lock verification, launcher script parity, headless CLI flags, smoke testing, clean sandbox migrations, model readiness, and release manifest validation.

---

## 4. Verification Results
- **Phase 10 Test Suite:** 9 passed in 5.23s
- **Full Regression (Phases 01–10):** 108 passed in 32.60s (0 failed, 0 skipped)
  - `test_phase01_production_config_hardening.py`: 22 passed
  - `test_phase02_parent_portal_remediation.py`: 2 passed
  - `test_phase03_fee_admin_remediation.py`: 10 passed
  - `test_phase04_payment_webhook_remediation.py`: 11 passed
  - `test_phase05_edge_sync_remediation.py`: 15 passed
  - `test_phase06_rbac_tenant_audit.py`: 12 passed
  - `test_phase07_ai_task_rag_trust.py`: 10 passed
  - `test_phase08_database_isolation.py`: 9 passed
  - `test_phase09_ui_api_db_e2e.py`: 8 passed
  - `test_phase10_packaging_and_readiness.py`: 9 passed
- **Total Tests Passing:** 108/108
