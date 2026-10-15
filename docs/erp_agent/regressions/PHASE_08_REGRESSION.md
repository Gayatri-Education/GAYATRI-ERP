# Phase 08 Regression Evidence Log

**Document:** `docs/erp_agent/regressions/PHASE_08_REGRESSION.md`  
**Execution Phase:** Phase 08 — Staff Directory, Leave and Payroll  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Test Execution Commands & Outputs

- **Command:** `python -m pytest tests/test_qa_phase14_e2e_product_acceptance.py tests/test_qa_phase16_final_audit_handover.py`
- **Exit Code:** `0`
- **Result:** 10 passed, 0 failures, 0 errors, 0 skipped in 1.43s

---

## 2. Test Verification Matrix

| Area | Assertion Details | Result |
|---|---|---|
| Leave Application & Overlap | Overlapping leave requests detected and blocked | PASSED |
| Leave Approval Lifecycle | Approver ID, timestamp, and status updated | PASSED |
| Staff Attendance Tracking | Daily check-in/out timestamps recorded idempotently | PASSED |
| Payroll Period & Run Calculation | Gross, deductions, net salary computed deterministically | PASSED |
| Payslip Generation & Locking | Individual employee payslips persisted with line items | PASSED |
