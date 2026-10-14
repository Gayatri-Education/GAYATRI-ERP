# Gayatri School OS — Active Defect Ledger

**Specification:** `DEVELOPMENT.md` (Sections 2.3 & 12)  
**Status:** Living Defect Ledger  
**Last Updated:** 2026-10-14  

---

## Severity Criteria
- **P0 — Critical Blocker:** Unauthorized data access, tenant leakage, authentication bypass, fabricated payment success, incorrect marks/payroll, lost/corrupted durable records, real secret exposure, false AI execution status.
- **P1 — High Blocker:** Major workflow dead-end, incorrect balances, duplicate financial/attendance events, invalid report cards, missing authorization on sensitive actions, unsafe fallback, serious sync loss.
- **P2 — Important:** Usability or maintainability issue, edge-case failure, incomplete analytics.
- **P3 — Low:** Cosmetic or minor refinement.

---

## Active Defect Register

| Defect ID | Severity | Phase | Subsystem | Description & Reproduction | Expected Behavior | Actual Behavior | Status | Evidence / Fix |
|---|---|---|---|---|---|---|---|---|
| **DEF-P00-01** | P1 | Phase 00 / 01 | Configuration & Startup | `validate_production_config` fails on uninitialized `gayatri_local.db` during fresh checkout. <br>**Repro:** Fresh git clone without running `migrate_db.py`, run `pytest test_phase01_production_config_hardening.py`. | Clear, actionable diagnostic indicating database migration is required before starting production mode. | Startup crashes with `RuntimeError: Production startup aborted: Configured production database does not exist: gayatri_local.db` without indicating `migrate_db.py` is needed. | **RESOLVED** (Baseline Operational Workaround: `python scripts/migrate_db.py up` initializes database and resolves all 5 failures. Phase 01 will harden error messaging). | `docs/development/evidence/baseline/pytest_baseline_post_migration.log` |

---

## Historical Defect Register (Inherited from GQA-001 through GQA-016)

All 16 findings from the prior independent platform audit (`GQA-001` through `GQA-016`) were successfully remediated and verified in the base platform. See [`docs/qa_agent/MASTER_PROGRESS.md`](file:///c:/Users/user/Desktop/gayatri/Gayatri-ERP/docs/qa_agent/MASTER_PROGRESS.md) for full traceability.
