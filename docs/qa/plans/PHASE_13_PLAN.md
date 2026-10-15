# Remediation Plan — Phase 13: Final Forensic Review, Full Regression & Release Gate (QA-013)

**Phase:** Phase 13  
**Issue Identifier:** QA-013  
**Priority:** P0/P1  
**Target Branch:** `qa/production-readiness-remediation`  
**Governing Document:** `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` (Section 16)

---

## 1. Problem Statement & Release Gate Objectives
Phase 13 is the terminal production release gate of the 14-phase QA remediation program. No release candidate may be declared production-ready without passing comprehensive, independent forensic verification across all 12 prior phases:
1. **Compilation & Dependency Rigor:** Verification of clean bytecode compilation across all modules (`app`, `core`, `central_platform`, `tests`, `scripts`) and strict dependency lockfile reconciliation.
2. **Database Migration & Schema Repeatability:** Automated verification of fresh sandbox database migration through all 16 DDL migrations (`001` through `016`).
3. **Architectural & Design Invariants:** Execution of architectural boundaries (`tests/architecture`).
4. **Comprehensive Remediation Test Matrix:** Execution of all focused remediation test suites (`tests/test_phase01_*` through `tests/test_phase12_*`) proving durable persistence, zero IDOR leaks, constant-time HMAC webhooks, atomic billing rollbacks, edge punch deduplication, and honest degraded AI/RAG states.
5. **Headless Test Suite Health:** Execution of non-GUI test suite ensuring 0 unexpected skips, 0 broad xfails, and 0 weakened assertions.
6. **Fresh Packaging, Smoke & Manifest Generation:** Generation and cryptographic verification of `RELEASE_MANIFEST.json` against candidate commit SHA.
7. **Forensic Security & Secret Scan:** `git diff --check`, secret scanning (no committed keys/tokens), and absence of cosmetic toast substitutions.
8. **Final GO / NO-GO Release Gate Decision:** Evidence-backed audit determining whether Gayatri ERP v3.0.1 achieves production-ready status with clearly disclosed hardware blockers (`BLK-003`).

---

## 2. Invariants & Guardrails
- **Zero Fabricated Passes:** Every check must execute directly on the live environment and log its real stdout/exit code.
- **Fail-Closed Gate:** If any P0/P1 defect remains unresolved or any assertion fails, the release gate decision is strictly **NO-GO**.
- **Truthful Scope Disclosure:** Physical biometric/RFID/GPS hardware must remain recorded as `BLOCKED` (`BLK-003`) with software simulators verified.

---

## 3. Implementation Steps

### Step 1: Execute Platform Compilation & Dependency Checks
- Run `python -m compileall app core central_platform tests scripts -q`.
- Run `python scripts/verify_dependency_lock.py`.

### Step 2: Execute Fresh Sandbox Migration Lifecycle
- Run `python scripts/migrate_db.py up --db-path <temp_db>`.
- Run `python scripts/migrate_db.py status --db-path <temp_db>`.
- Verify all 16 migrations applied with matching checksums.

### Step 3: Run Full Remediation Test Suite (Phases 01–12)
- Execute `pytest -v tests/test_phase01_*` through `tests/test_phase12_*`.
- Confirm 100% pass rate.

### Step 4: Run Architectural Tests & Smoke Tests
- Run `pytest -v tests/architecture`.
- Run `python scripts/smoke_test_install.py`.

### Step 5: Regenerate Canonical Release Manifest
- Run `python scripts/generate_release_manifest.py`.
- Validate `RELEASE_MANIFEST.json` schema, commit SHA, and migration hashes.

### Step 6: Author Phase 13 Release Gate Test Suite (`tests/test_phase13_final_release_gate.py`)
- Test 1: Complete bytecode compilation hygiene.
- Test 2: Dependency lock reconciliation.
- Test 3: Sandbox migration repeatability (clean up, status, idempotency).
- Test 4: Release manifest integrity against current checked-out commit.
- Test 5: Master progress tracker (Phases 00–12 PASSED) and issue register (QA-001–QA-012 FIXED_VERIFIED).
- Test 6: Final GO / NO-GO readiness criteria evaluation.

---

## 4. Verification & Release Decision Criteria
- **GO** Decision: All 12 prior phases PASSED, all 125+ remediation tests passing, zero P0/P1 defects open, hardware blockers disclosed (`BLK-003`), release manifest cryptographic digest verified.
