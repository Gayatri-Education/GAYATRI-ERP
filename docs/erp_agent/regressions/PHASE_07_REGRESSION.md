# Phase 07 Regression Evidence Log

**Document:** `docs/erp_agent/regressions/PHASE_07_REGRESSION.md`  
**Execution Phase:** Phase 07 — Exams, Marks Moderation, Results and Report Cards  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Test Execution Commands & Outputs

- **Command:** `python -m pytest tests/test_qa_phase07_assessment_integrity.py tests/test_qa_phase14_e2e_product_acceptance.py`
- **Exit Code:** `0`
- **Result:** 13 passed, 0 failures, 0 errors, 0 skipped in 7.21s

---

## 2. Test Verification Matrix

| Area | Assertion Details | Result |
|---|---|---|
| Exam Series & Schedules | Series types, dates, subject allocations | PASSED |
| Marks Boundary Checks | Negative or $> \text{max\_marks}$ scores rejected | PASSED |
| Attempt & Mark Immutability | Marks finalization locks state; bypass prevented | PASSED |
| Audited Reopen | Admin role required, reason logged, status updated to REOPENED | PASSED |
| Grading Calculation | Deterministic mapping from percentages to grades | PASSED |
| Report Card Assembly | Student profile, subject scores, grades, and remarks compiled | PASSED |
