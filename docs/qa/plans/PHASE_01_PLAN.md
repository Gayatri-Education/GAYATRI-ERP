# Phase 01 Plan — Restore Trustworthy CI and Production Configuration Tests

**Document:** `docs/qa/plans/PHASE_01_PLAN.md`  
**Contract Reference:** [`../../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md) (Section 4)  
**Issue ID:** QA-001  
**Phase:** 01 — Restore Trustworthy CI and Production Configuration Tests (P0 / Release Blocker)  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Problem Statement & Audit Finding

In fresh CI environments (both Ubuntu and Windows runners), five production configuration tests fail:
1. `tests/test_phase01_production_config_hardening.py::test_production_debug_mode_rejected`
2. `tests/test_phase01_production_config_hardening.py::test_production_reload_mode_rejected`
3. `tests/test_phase01_production_config_hardening.py::test_production_model_checksum_verification`
4. `tests/test_phase01_production_config_hardening.py::test_create_app_in_production_mode`
5. `tests/test_phase12_final_forensic_certification.py::test_layer1_demo_tokens_disabled_in_production`

**Root Cause:**
1. The tests hardcode `GAYATRI_DB_PATH="gayatri_local.db"`. In clean CI runners, `gayatri_local.db` does not exist in the working directory (only `test_ci.db` is migrated by CI setup).
2. In `central_platform/config.py:get_authoritative_settings()`, `resolve_database_path()` is executed before the debug/reload invariant checks, aborting with `RuntimeError: Production startup aborted: Configured production database does not exist: gayatri_local.db` before assertions on debug mode, reload mode, or checksum mismatch can be tested.
3. Tests creating FastAPI apps in production mode (`create_app()`) must be hermetic and bind to a valid, temporary SQLite database provided by `tmp_path`, preventing reliance on ambient developer artifacts.

---

## 2. In-Scope Files

- `central_platform/config.py` (`get_authoritative_settings`)
- `tests/test_phase01_production_config_hardening.py`
- `tests/test_phase12_final_forensic_certification.py`
- `tests/conftest.py` / pytest fixtures

---

## 3. Implementation Steps

1. **Assertion Order in `central_platform/config.py`:**
   - In `get_authoritative_settings()`, check `debug`, `reload_mode`, and `fastapi_debug` immediately after environment resolution when `is_prod=True`. If debug/reload is active, fail-fast with `RuntimeError: Production startup aborted: Debug and reload modes are strictly prohibited in production.`
   - Ensure model checksum mismatch check operates on the provided model weights without tripping over ambient missing database files.

2. **Hermetic Test Fixtures in `tests/test_phase01_production_config_hardening.py`:**
   - For tests requiring a valid DB in production (`test_production_model_checksum_verification`, `test_create_app_in_production_mode`), use `tmp_path` to create an initialized temporary SQLite database.
   - For `test_production_debug_mode_rejected` and `test_production_reload_mode_rejected`, use a temporary DB file path to ensure the test is hermetic regardless of assertion ordering.
   - For tests checking missing DB behavior (`test_production_missing_database_path`), retain intentionally non-existent paths.

3. **Hermetic Test in `tests/test_phase12_final_forensic_certification.py`:**
   - In `test_layer1_demo_tokens_disabled_in_production`, inject a temporary initialized database via `tmp_path` instead of hardcoding `gayatri_local.db`.

4. **Environment Isolation:**
   - Ensure all tests use `monkeypatch` to set and cleanly revert `GAYATRI_ENV`, `APP_ENV`, `GAYATRI_DB_PATH`, `GAYATRI_JWT_SECRET`, `GAYATRI_ENCRYPTION_KEY`, `GAYATRI_ALLOWED_ORIGINS`, `DEBUG`, `RELOAD`, `FASTAPI_DEBUG`.

---

## 4. Acceptance & Exit Criteria (Binary Gate)

- [ ] All 5 targeted tests pass cleanly when run in an empty directory without `gayatri_local.db`.
- [ ] Debug/reload checks fail-fast before database lookup.
- [ ] No test assertions are weakened, skipped, or xfailed.
- [ ] Complete `tests/test_phase01_production_config_hardening.py` and `tests/test_phase12_final_forensic_certification.py` pass.
- [ ] Complete architecture invariant suite passes (`pytest -v tests/architecture`).
- [ ] Full headless regression suite passes locally with zero failures.
- [ ] `docs/qa/phase-logs/REMEDIATION_PHASE_01_LOG.md` authored with exact outputs.
