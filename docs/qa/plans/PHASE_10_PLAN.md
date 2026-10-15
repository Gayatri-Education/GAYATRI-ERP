# Remediation Plan — Phase 10: Install, Dependency Lock, Packaging & Model Readiness (QA-010)

**Phase:** Phase 10  
**Issue Identifier:** QA-010  
**Priority:** P2  
**Target Branch:** `qa/production-readiness-remediation`  
**Governing Document:** `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` (Section 13)

---

## 1. Problem Statement & Baseline Findings
The repository audit and forensic review identified several inconsistencies in packaging, dependency locking, and application lifecycle entrypoints:
1. **Version Inconsistency:** `pyproject.toml` declared `version = "5.0.0"` while the canonical `VERSION` file, `README.md` badges, Inno Setup script (`packaging/installer.iss`), PyInstaller spec (`packaging/gayatri_demo.spec`), and `app.main --version` declared `3.0.1`.
2. **Setup Script Discrepancy:** `setup.bat` installed directly from `requirements.txt` without checking `requirements.lock` first, contrasting with CI and `setup.sh` which prioritize pinned `requirements.lock` for deterministic reproduction.
3. **Launch Script Discrepancy:** `launch.bat` lacked the multi-mode dispatch options (`server`, `smoke`, `desktop`) present in `launch.sh`.
4. **Transparent Model Readiness:** While `LocalProvider` fails with `LocalModelError` on missing models, `DeploymentValidator` and CLI utilities must explicitly report `CONFIGURED` or `UNGROUNDED` rather than false-positive `HEALTHY` when weights are absent.
5. **Release Manifest Freshness:** `RELEASE_MANIFEST.json` must be regenerated directly from git commits, matching migration files and core source checksums.

---

## 2. Invariants & Guardrails
- **Deterministic Lock Enforcement:** `requirements.lock` must contain strictly pinned `==` dependencies, and `verify_dependency_lock.py` must enforce direct dependency reconciliation with `requirements.txt`.
- **Zero Version Drift:** `pyproject.toml` must match `VERSION` (`3.0.1`).
- **Fail-Closed Launchers:** `setup.bat` and `launch.bat` must exit non-zero immediately on dependency installation, verification, or migration failures.
- **Honest AI State:** If model weights are missing or corrupt, provider status must declare `MISSING`, `CONFIGURED`, or `UNVERIFIED`, never fabricated green inference.

---

## 3. Implementation Steps

### Step 1: Align Product Version
- Update `pyproject.toml` to `version = "3.0.1"`.
- Verify `python -m app.main --version` prints `Gayatri AI v3.0.1`.

### Step 2: Unify Windows Setup & Launcher Scripts
- Update `setup.bat` to:
  - Check for `requirements.lock` first and install with `.venv\Scripts\pip.exe install -r requirements.lock`.
  - Fallback to `requirements.txt` if lock is absent.
  - Run `.venv\Scripts\python.exe scripts\verify_dependency_lock.py`.
  - Run `.venv\Scripts\python.exe scripts\migrate_db.py up`.
  - Run bytecode compilation check `.venv\Scripts\python.exe -m compileall app core central_platform -q`.
- Update `launch.bat` to support mode parameters:
  - `launch.bat server` $\rightarrow$ starts central platform API on port 8000.
  - `launch.bat smoke` $\rightarrow$ executes `scripts\smoke_test_install.py`.
  - `launch.bat desktop` (or default) $\rightarrow$ launches desktop application `app.main`.

### Step 3: Verify and Test Model Readiness
- Verify `scripts/check_model.py` and `core/providers/local.py`:
  - Missing GGUF model raises `LocalModelError`.
  - `DeploymentValidator.validate_model_providers()` reports honest non-healthy state when weights are missing.

### Step 4: Author Comprehensive Test Suite (`tests/test_phase10_packaging_and_readiness.py`)
- Test 1: Version alignment between `pyproject.toml`, `VERSION`, and `app.main --version`.
- Test 2: Dependency lock strict pinning and reconciliation (`verify_dependency_lock.py`).
- Test 3: Launcher script mode dispatch and error handling contracts (`setup.bat`, `setup.sh`, `launch.bat`, `launch.sh`).
- Test 4: Headless CLI arguments (`--help`, `--version`, `--check-startup`).
- Test 5: Post-install smoke test validation (`scripts/smoke_test_install.py`).
- Test 6: Clean sandbox database bootstrap and migration execution.
- Test 7: Model readiness honesty when weights are unpopulated.
- Test 8: Release manifest generator and file integrity checksums (`scripts/generate_release_manifest.py`).

---

## 4. Verification & Regression Plan
- Run `pytest -v tests/test_phase10_packaging_and_readiness.py`.
- Run full regression across Phases 01 through 10.
- Ensure 0 failed, 0 skipped, and 100% test pass rate.
