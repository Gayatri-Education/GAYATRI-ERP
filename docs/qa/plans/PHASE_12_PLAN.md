# Remediation Plan — Phase 12: Consolidate Documentation, Trackers & Release Claims (QA-012)

**Phase:** Phase 12  
**Issue Identifier:** QA-012  
**Priority:** P1  
**Target Branch:** `qa/production-readiness-remediation`  
**Governing Document:** `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` (Section 15)

---

## 1. Problem Statement & Baseline Findings
The repository audit revealed several competing, stale, or duplicate planning and tracking artifacts across the root directory and `docs/`:
1. **Duplicate Root Trackers:** `GAYATRI_ERP_ISSUE_REGISTER.md` and `GAYATRI_ERP_FILE_CLEANUP_REPORT.md` are unmaintained duplicates of files in `docs/qa/`.
2. **Competing Development Guides:** `GAYATRI_ERP_DEVELOPMENT_GUIDE.md` and `ERP_TRANSFORMATION_DEVELOPMENT.md` compete with `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` as primary guidance.
3. **Outdated Fix Plans:** `GAYATRI_PHASE_BY_PHASE_PRODUCTION_FIX_PLAN.md` and `Gayatri_QA_Production_Fix_Plan.md` were pre-remediation roadmaps that lack references to the authoritative 14-phase QA goal.
4. **Stale Schema Inventory in Handover:** `docs/qa/RELEASE_HANDOVER.md` references "8 DDL migrations", whereas the live codebase contains 16 verified migrations (`001` through `016`).
5. **Missing Claims vs Evidence Matrix:** `README.md` and release documentation require an honest, structured Claims vs Evidence matrix that discloses physical hardware (`BLK-003`), third-party gateway modes, and air-gapped limitations without overstating capabilities.

---

## 2. Invariants & Guardrails
- **Single Canonical Source of Truth:**
  - Canonical Development & QA Contract: [`GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md)
  - Canonical Remediation Progress Tracker: [`docs/qa/REMEDIATION_MASTER_TRACKER.md`](REMEDIATION_MASTER_TRACKER.md)
  - Canonical Remediation Issue Register: [`docs/qa/REMEDIATION_ISSUE_REGISTER.md`](REMEDIATION_ISSUE_REGISTER.md)
  - Canonical Hardware & Cloud Disclosures: [`docs/operations/HARDWARE_AND_THIRD_PARTY_DISCLOSURES.md`](../operations/HARDWARE_AND_THIRD_PARTY_DISCLOSURES.md)
- **Do Not Blindly Delete Historical Records:** Older QA artifacts (e.g. `docs/erp_agent/`, historical logs) are preserved as dated lineage; root-level duplicate copies are replaced with short pointers to canonical documents.
- **Truth in Advertising:** Product `README.md` must truthfully disclose physical hardware boundaries (`BLK-003`) and external API dependencies alongside software capabilities.

---

## 3. Implementation Steps

### Step 1: Replace Root-Level Duplicates with Canonical Pointers
- Update `GAYATRI_ERP_ISSUE_REGISTER.md` with a clean pointer to canonical `docs/qa/REMEDIATION_ISSUE_REGISTER.md`.
- Update `GAYATRI_ERP_FILE_CLEANUP_REPORT.md` with a clean pointer to `docs/qa/FILE_CLEANUP_REPORT.md`.
- Update `GAYATRI_ERP_DEVELOPMENT_GUIDE.md` with a clean pointer to `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` and `docs/development/DEVELOPMENT_GUIDE.md`.
- Add deprecation banners with canonical pointers to `GAYATRI_PHASE_BY_PHASE_PRODUCTION_FIX_PLAN.md` and `Gayatri_QA_Production_Fix_Plan.md`.

### Step 2: Reconcile Release Handover Metadata
- Update `docs/qa/RELEASE_HANDOVER.md`:
  - Point to `REMEDIATION_MASTER_TRACKER.md` and `REMEDIATION_ISSUE_REGISTER.md`.
  - Update migration count to the actual 16 DDL migrations (`001` to `016`).
  - Reference `HARDWARE_AND_THIRD_PARTY_DISCLOSURES.md` and `BLK-003`.

### Step 3: Embed Claims vs Evidence Matrix in README.md & Docs
- In `README.md`, update governance links to point to canonical remediation trackers.
- Add an explicit **Claims vs Evidence** matrix table to `README.md` and `docs/qa/RELEASE_HANDOVER.md` detailing:
  - 100% Student Data Sovereignty (Evidence: `core/providers/local.py`, verified local inference).
  - True Offline-First Architecture (Evidence: `LocalSyncOutbox`, verified WAL crash recovery).
  - Multi-Modal Attendance (Evidence: `EdgeSyncService`, software packet normalization; physical hardware `BLOCKED` under `BLK-003`).
  - Double-Entry Fee Ledger (Evidence: `financial_ledger_entries`, HMAC webhook verification; live production accounts required for live payment).
  - 16 DDL Database Migrations (Evidence: `scripts/migrate_db.py`, verified checksum registry).

### Step 4: Author Comprehensive Test Suite (`tests/test_phase12_docs_and_claims_consolidation.py`)
- Test 1: Verify single canonical pointer resolution for root documents.
- Test 2: Verify migration count consistency (16 migrations).
- Test 3: Verify Claims vs Evidence matrix presence and truthful `BLOCKED` / `SIMULATED` status mapping.
- Test 4: Verify cross-links between README, trackers, issue register, and disclosures exist and resolve.
- Test 5: Verify version consistency across all canonical documents (`3.0.1`).

---

## 4. Verification & Regression Plan
- Run `pytest -v tests/test_phase12_docs_and_claims_consolidation.py`.
- Run full regression across Phases 01 through 12.
- Verify 100% test pass rate with 0 failures and 0 skipped tests.
