# Phase 10 Plan — Dependency Locking, CI Design and Release Reproducibility

**Phase:** Phase 10  
**Audit Findings Addressed:**  
- **GQA-009 (P1):** Single-platform CI does not verify target matrix (`windows-latest` only, single platform)  
- **GQA-014 (P1):** CI installs loose dependencies ignoring lock file (`pip install -r requirements.txt`)  
- **GQA-016 (P2):** Latest CI run was incomplete or unverified at audit time  
**Related Historical Findings:** QA-017, QA-018  
**Date:** 2026-10-14  

---

## 1. Problem Statement & Audit Evidence

### GQA-009: Single-Platform CI Gap
In `.github/workflows/ci.yml`:
```yaml
jobs:
  test:
    runs-on: windows-latest
    strategy:
      matrix:
        python-version: ["3.12"]
```
The application promises cross-platform support: Windows native desktop application and Linux headless server/central platform runtime. Testing solely on `windows-latest` fails to verify Linux compatibility (POSIX paths, file permissions, headless PySide6 offscreen rendering, and Linux container operations).

### GQA-014: Loose Dependency Installation
In `.github/workflows/ci.yml`:
```yaml
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
```
Even though the project repository maintains a pinned `requirements.lock` file with exact pinned versions, CI installs loose dependencies from `requirements.txt`. Over time, unpinned dependency updates can silently break builds or introduce security regressions without trace.

### GQA-016: CI Incompleteness & Verification Harness Gap
The audit noted that CI runs were either incomplete or lacked programmatic verification of workflow steps, lock file reconciliation, and target architecture execution.

---

## 2. Implementation Strategy

### Step 1: Update `.github/workflows/ci.yml`
1. **Multi-Platform OS Matrix (GQA-009):**
   - Add `matrix.os: [windows-latest, ubuntu-latest]`.
   - Add `matrix.python-version: ["3.12"]`.
2. **Locked Dependency Installation (GQA-014):**
   - Update pip install to strictly use `requirements.lock`:
     `pip install -r requirements.lock`
   - Add dependency lock reconciliation step before tests run.
3. **Least Privilege Security:**
   - Add `permissions: contents: read` to the workflow.
4. **Structured Pipeline Stages:**
   - Compile hygiene (`python -m compileall`).
   - Dependency lock integrity verification.
   - Clean temporary database schema migration (`python scripts/migrate_db.py up`).
   - Architecture guardrails (`pytest -v tests/architecture`).
   - Headless test execution (`pytest -v -m "not gui"` with `QT_QPA_PLATFORM: offscreen`).
   - Fail-closed execution: zero ignored errors, zero `continue-on-error: true`.

### Step 2: Implement Dependency Lock Verifier `scripts/verify_dependency_lock.py`
Create a standalone validation tool that:
1. Verifies `requirements.lock` exists, is non-empty, and contains strictly pinned exact versions (`==`).
2. Parses `requirements.txt` and verifies that every required top-level dependency is pinned in `requirements.lock`.
3. Detects drift or missing pins and exits with code 1 if unpinned dependencies are introduced.

### Step 3: Implement CI Workflow Verifier `scripts/verify_ci_pipeline.py`
Create a programmatic audit harness that:
1. Validates YAML syntax of `.github/workflows/ci.yml`.
2. Verifies presence of both `windows-latest` and `ubuntu-latest` in matrix.
3. Verifies `requirements.lock` is installed.
4. Verifies `permissions: contents: read`.
5. Verifies all required build and test steps are present and fail-closed.

### Step 4: Author Dedicated Test Suite `tests/test_qa_phase10_dependency_ci_reproducibility.py`
Authored tests covering:
1. `test_ci_workflow_multi_platform_matrix` (GQA-009).
2. `test_ci_workflow_installs_exact_lock_file` (GQA-014).
3. `test_dependency_lock_exact_pinning_and_completeness` (GQA-014).
4. `test_dependency_lock_reconciliation_against_requirements_txt` (GQA-014).
5. `test_ci_workflow_least_privilege_permissions` (GQA-016).
6. `test_ci_workflow_fail_closed_error_handling` (GQA-016).
7. `test_clean_environment_schema_and_migrations` (reproducibility).

---

## 3. Exit Gate Criteria
- [ ] Multi-platform matrix (`windows-latest`, `ubuntu-latest`) configured in CI (GQA-009).
- [ ] `requirements.lock` strictly installed and verified against `requirements.txt` (GQA-014).
- [ ] Programmatic CI verification harness passes (GQA-016).
- [ ] All tests in `tests/test_qa_phase10_dependency_ci_reproducibility.py` and `tests/test_qa_phase10_packaging_deployment.py` pass cleanly.
- [ ] Full repository regression passes without regressions.
- [ ] Phase 10 Report, Decision Log (DEC-022), and Master Progress updated.
