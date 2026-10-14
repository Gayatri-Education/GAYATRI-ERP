# Phase 01 Implementation Plan — Authoritative Configuration, Production Mode and Test Isolation

## 1. Context and Objective
Remediate **GQA-007** (autouse test fixture mutates root developer database `gayatri_local.db`) and **GQA-008** (configuration divergence between `central_platform/config.py`, `central_platform/deployment/validator.py`, and `central_platform/auth/tokens.py`).

## 2. Dependencies and Affected Modules
- `central_platform/config.py`: Primary source of authoritative platform settings.
- `central_platform/deployment/validator.py`: Deployment validator checking environment and secrets.
- `central_platform/auth/tokens.py`: Token generation and verification reading JWT secret.
- `tests/conftest.py`: Root pytest fixtures currently targeting root `gayatri_local.db`.
- `tests/test_qa_phase01_authoritative_config.py`: New comprehensive test suite for Phase 01.

## 3. Defect Analysis & Root Causes
1. **Configuration Divergence (GQA-008):**
   - `config.py` checked `GAYATRI_ENV` or `APP_ENV`.
   - `validator.py` checked only `APP_ENV` and rejected when only `GAYATRI_ENV` was set.
   - `config.py` validated `GAYATRI_JWT_SECRET` (min length 32), while `validator.py` validated `SECRET_KEY` or `JWT_SECRET` (min length 16).
   - `validator.py` maintained independent weak secret lists and rule sets that contradicted `config.py`.
   - In production, conflicting secret aliases could pass validator but fail token operations.
2. **Database Test Isolation (GQA-007):**
   - `tests/conftest.py` has an autouse session fixture that runs migrations directly on `gayatri_local.db` in repository root.
   - Developer databases get mutated during test execution, causing pollution and unrepeatable test runs across different developer environments.

## 4. Proposed Architectural Changes
1. **Consolidated Configuration Engine in `central_platform/config.py`:**
   - Define canonical `PlatformSettings` dataclass containing resolved environment, JWT secret, encryption key, allowed origins, debug flags, and database path.
   - Canonical environment resolution: `GAYATRI_ENV` is canonical; `APP_ENV` is recognized as alias; conflicting values raise `RuntimeError` in production.
   - Canonical JWT secret resolution: `GAYATRI_JWT_SECRET` is canonical; `JWT_SECRET` / `SECRET_KEY` are aliases; conflicting values raise `RuntimeError`.
   - Minimum secret length: 32 characters in production.
   - Unify `WEAK_SECRETS` across the codebase.
   - Provide `get_authoritative_settings()` function used by both `validator.py`, `tokens.py`, and `app.py`.
2. **Update `central_platform/deployment/validator.py`:**
   - Delegate environment and secrets validation to `get_authoritative_settings()` and `validate_production_config()` from `central_platform.config`.
   - Eliminate duplicated, diverging rules.
3. **Update `central_platform/auth/tokens.py`:**
   - Delegate secret resolution to `get_authoritative_settings().jwt_secret`.
4. **Isolate Test Database in `tests/conftest.py`:**
   - Change `ensure_local_database` to use a temporary, isolated SQLite database file or provide an isolated environment path override so that tests do not overwrite the user's root developer database.
   - For backwards compatibility with legacy tests that specifically look for `gayatri_local.db`, ensure that if `GAYATRI_TEST_ISOLATED_DB` or test isolation is active, migrations run safely in a temporary sandbox or backup/restore pattern.
   - Let's check how other tests use `gayatri_local.db` before touching `conftest.py`.

## 5. Test Plan
- Write `tests/test_qa_phase01_authoritative_config.py` covering:
  - Canonical `GAYATRI_ENV` vs alias `APP_ENV` and conflict detection.
  - Canonical `GAYATRI_JWT_SECRET` vs aliases `JWT_SECRET` and `SECRET_KEY` and conflict detection.
  - Secret length enforcement (>= 32 chars in production).
  - Weak secret rejection.
  - CORS origin validation (rejection of wildcard `*` or empty origins in production).
  - Debug/reload flag prohibition in production.
  - Validator consistency with authoritative config.
  - Test database isolation verification.

## 6. Exit Gate
- `PlatformSettings` is the single source of truth.
- `validator.py` and `tokens.py` use identical rules.
- Tests pass cleanly without modifying developer's root state.
