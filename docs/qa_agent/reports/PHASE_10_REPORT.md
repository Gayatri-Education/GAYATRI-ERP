# Phase 10 Verification Report: Dependency Locking, CI Design and Release Reproducibility

**Phase:** Phase 10  
**Defects Addressed:**  
- **GQA-009 (P1):** Single-platform CI does not verify target matrix  
- **GQA-014 (P1):** CI installs loose dependencies ignoring lock file  
- **GQA-016 (P2):** Latest CI run was incomplete or unverified at audit time  
**Related Findings:** QA-017, QA-018  
**Date:** 2026-10-14  
**Status:** PASSED  
**Certified By:** Gayatri QA Autonomous Agent  

---

## 1. Executive Summary

In Phase 10, the repository's continuous integration and dependency management were hardened to achieve reproducible, verified releases.

Historically:
1. **GQA-009:** `.github/workflows/ci.yml` executed solely on `windows-latest`, ignoring Linux (`ubuntu-latest`) despite platform claims of cross-platform API server and container support.
2. **GQA-014:** CI installed dependencies from loose unpinned `requirements.txt` via `pip install -r requirements.txt`, even though `requirements.lock` existed. Furthermore, several core dependencies (`fastapi`, `uvicorn`, `pyjwt`, `psutil`, `psycopg2-binary`, `pypdf`) were declared in `requirements.txt` but absent from `requirements.lock`.
3. **GQA-016:** CI lacked automated pipeline verification, least-privilege security declarations, and strict lock reconciliation.

In Phase 10:
- Updated `.github/workflows/ci.yml` to a multi-platform runner matrix (`windows-latest` and `ubuntu-latest`).
- Changed CI dependency installation to strictly consume `requirements.lock` (`pip install -r requirements.lock`).
- Reconciled `requirements.lock` with `requirements.txt`, adding exact pins for all 6 missing direct packages (76 total locked packages, 100% pinned with `==`).
- Added `scripts/verify_dependency_lock.py` to reconcile lock completeness on every build.
- Added `scripts/verify_ci_pipeline.py` to programmatically verify workflow syntax, runner matrices, and security permissions.
- Added least-privilege `permissions: contents: read` to the CI workflow.
- Changed CI database setup to use a temporary disposable database (`test_ci.db`) preventing developer database mutation.

---

## 2. Invariant & Compliance Matrix

| Requirement / Invariant | Pre-Fix State | Post-Fix State | Verification Test | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Multi-Platform Matrix** | Windows-only runner | `windows-latest` & `ubuntu-latest` matrix | `test_ci_workflow_multi_platform_matrix` | **PASSED** |
| **Python Version Support** | Single version implicit | Explicitly tested `3.12` | `test_ci_workflow_multi_platform_matrix` | **PASSED** |
| **Locked Install in CI** | `pip install -r requirements.txt` | `pip install -r requirements.lock` | `test_ci_workflow_installs_exact_lock_file` | **PASSED** |
| **Lock Exact Pinning** | Partial coverage | 76 packages with exact `==` pins | `test_dependency_lock_exact_pinning_and_completeness` | **PASSED** |
| **Dependency Reconciliation** | 6 packages missing from lock | 100% of `requirements.txt` reconciled | `test_dependency_lock_reconciliation_against_requirements_txt` | **PASSED** |
| **Drift / Missing Package Detection** | Undetected | `verify_dependency_lock` fails closed | `test_dependency_lock_verifier_detects_missing_packages` | **PASSED** |
| **Package Normalization** | Case-sensitive / inconsistent | PEP 503 lowercase hyphenated normalization | `test_package_normalization_pep503` | **PASSED** |
| **Least Privilege Security** | Default implicit permissions | `permissions: contents: read` | `test_ci_workflow_least_privilege_permissions` | **PASSED** |
| **Fail-Closed Error Handling** | Unverified | Zero `continue-on-error: true` steps | `test_ci_workflow_fail_closed_error_handling` | **PASSED** |
| **Disposable DB Migration** | Root `gayatri_local.db` | Temporary sandbox `test_ci.db` | `test_ci_database_migration_target_is_temporary` | **PASSED** |

---

## 3. Implementation Changes

1. **`.github/workflows/ci.yml`:**
   - Multi-platform matrix with `os: [windows-latest, ubuntu-latest]`.
   - Least privilege `permissions: contents: read`.
   - Strict `pip install -r requirements.lock`.
   - Added dependency lock reconciliation step `python scripts/verify_dependency_lock.py`.
   - Replaced root DB migration target with `test_ci.db`.
2. **`requirements.lock`:**
   - Reconciled and pinned 76 total dependencies alphabetically, resolving missing direct requirements (`fastapi==0.141.1`, `psutil==7.2.2`, `psycopg2-binary==2.9.13`, `pyjwt==2.13.0`, `pypdf==6.14.2`, `uvicorn==0.52.0`).
3. **`scripts/verify_dependency_lock.py`:**
   - Authored PEP 503 compliant lock verifier and dependency reconciler.
4. **`scripts/verify_ci_pipeline.py`:**
   - Authored workflow linter and runner matrix auditor.
5. **`tests/test_qa_phase10_dependency_ci_reproducibility.py`:**
   - Authored 10 comprehensive tests covering all Phase 10 invariants.

---

## 4. Verification Evidence

- **Targeted Test Suites:**
  - `tests/test_qa_phase10_dependency_ci_reproducibility.py` (10 passed in 1.28s)
  - `tests/test_qa_phase10_packaging_deployment.py` (5 passed in 1.42s)
- **Regression Status:** Full repository test suite executed cleanly with 0 failures.

---

## 5. Exit Gate Certification

- [x] Multi-platform matrix (`windows-latest` and `ubuntu-latest`) configured in CI (GQA-009).
- [x] Exact `requirements.lock` installed in CI and reconciled against `requirements.txt` (GQA-014).
- [x] Programmatic CI verification harness passes with least privilege and fail-closed posture (GQA-016).
- [x] Full regression suite passes without regressions.
- [x] Exit gate passed. Ready to proceed to Phase 11.
