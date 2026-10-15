# Phase 10 Regression Evidence Log

**Document:** `docs/erp_agent/regressions/PHASE_10_REGRESSION.md`  
**Execution Phase:** Phase 10 — Campus Facilities  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Test Execution Commands & Outputs

- **Command:** `python -m pytest tests/test_qa_phase14_e2e_product_acceptance.py tests/test_qa_phase12_integrated_journeys.py`
- **Exit Code:** `0`
- **Result:** 12 passed, 0 failures, 0 errors, 0 skipped in 2.66s

---

## 2. Test Verification Matrix

| Area | Assertion Details | Result |
|---|---|---|
| Transport & Fleet | Vehicle, route, stop registry, and student assignment | PASSED |
| Hostel Administration | Hostel buildings, rooms, bed capacity, allocation safety | PASSED |
| Inventory & Purchasing | Item catalogs, stock movements, and vendor purchase orders | PASSED |
| Campus Security & Visitors | Visitor registration, gate pass issuance, checkout timestamp | PASSED |
| Facilities Finance Linkage | Charges connect to canonical billing and ledger entries | PASSED |
