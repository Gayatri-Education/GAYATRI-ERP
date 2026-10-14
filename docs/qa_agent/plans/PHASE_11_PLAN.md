# Phase 11 Plan — Clean Installation, Cross-Platform Packaging, Upgrade, Rollback and Operational Readiness

**Phase:** Phase 11  
**Audit Findings Addressed:**  
- **GQA-001 (P0):** AI health/readiness can be false green on file presence (clean install missing model experience)  
- **GQA-004 (P1):** Provider status is config-based rather than runtime verified  
- **GQA-009 (P1):** Single-platform CI does not verify target matrix (cross-platform packaging & scripts)  
**Related Historical Findings:** QA-017, QA-018  
**Date:** 2026-10-14  

---

## 1. Problem Statement & Audit Evidence

### GQA-009 Cross-Platform Packaging Gap
Historically, the repository contained only Windows `.bat` launch scripts (`launch.bat`, `setup.bat`, `run.bat`). No POSIX/Linux scripts existed for Linux desktop/server environments. Furthermore, `package_release.py` hard-coded `"platform": "windows-x64"` and omitted Linux entrypoints.

### GQA-001 & GQA-004 Operational First-Run Experience
On a clean machine with no pre-existing developer environment:
- If a local GGUF model is not present, first-run must gracefully handle the missing model state:
  - Return transparent diagnostics (`MISSING` / `LOADABLE`).
  - Never report false-green `HEALTHY`.
  - Never substitute deterministic canned fallback responses as real model answers.
- Provider runtime health must reflect actual operational connectivity rather than configuration ordering.

### Upgrade, Backup & Rollback Safety
Clean installations must verify:
- Migration bootstrap from empty disk.
- Online backup snapshot creation.
- Disaster recovery and atomic rollback restoration without state corruption.

---

## 2. Implementation Strategy

### Step 1: Create Linux Launch Scripts
1. `setup.sh`:
   - Checks Python 3.12 availability.
   - Installs locked dependencies via `pip install -r requirements.lock`.
   - Runs database migrations via `python scripts/migrate_db.py up`.
   - Verifies compilation hygiene via `python -m compileall`.
2. `launch.sh`:
   - Checks environment variables (`GAYATRI_ENV`).
   - If headless (`$DISPLAY` unset), sets `QT_QPA_PLATFORM=offscreen`.
   - Launches application entrypoint (`python -m app.main "$@"` or `python -m central_platform.api.app`).

### Step 2: Enhance `scripts/package_release.py`
1. Include `launch.sh` and `setup.sh` in distribution files.
2. Support configurable target platform (`cross-platform`, `windows-x64`, `linux-x64`).
3. Ensure executable permissions on shell scripts during packaging.

### Step 3: Implement Post-Install Smoke Test `scripts/smoke_test_install.py`
1. Verifies Python runtime version (`>=3.12`).
2. Verifies importability of critical dependencies (`PySide6`, `fastapi`, `pydantic`, `cryptography`, `httpx`).
3. Verifies schema initialization in clean sandbox directory.
4. Verifies authoritative configuration resolution.
5. Verifies AI readiness probe behavior: missing model produces explicit `MISSING`/`LOADABLE` rather than false-green `HEALTHY`.

### Step 4: Author `tests/test_qa_phase11_packaging_operations.py`
Authored tests covering:
1. `test_cross_platform_launch_scripts_exist_and_valid`: Verifies both Windows (`.bat`) and Linux (`.sh`) scripts.
2. `test_packaging_cross_platform_manifest`: Verifies release packaging bundles both OS scripts and computes valid SHA-256 hashes.
3. `test_clean_environment_bootstrap_zero_developer_state`: Initializes clean database and runs migrations in isolated temporary directory.
4. `test_missing_model_first_run_experience`: Verifies missing model gives explicit diagnostic state without masquerading.
5. `test_backup_restore_and_rollback_recovery`: Verifies backup snapshot creation, simulated failure, and rollback restore.
6. `test_smoke_test_script_execution`: Runs `scripts/smoke_test_install.py` programmatically.

---

## 3. Exit Gate Criteria
- [ ] Cross-platform launch scripts (`setup.sh`, `launch.sh`, `setup.bat`, `launch.bat`) exist and verified.
- [ ] Release packager bundles cross-platform assets with SHA-256 manifest.
- [ ] Clean install bootstrap and migration safety verified.
- [ ] First-run missing model experience fails explicitly without false green.
- [ ] Backup and rollback recovery verified.
- [ ] All tests in `tests/test_qa_phase11_packaging_operations.py` pass cleanly.
- [ ] Full repository regression passes without regressions.
- [ ] Phase 11 Report, Decision Log (DEC-023), and Master Progress updated.
