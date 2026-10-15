# Phase 08 Plan — Staff Directory, Leave and Payroll

**Document:** `docs/erp_agent/plans/PHASE_08_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 08 — Staff Directory, Leave and Payroll  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 08 verifies the institutional Human Resources, staff directory, leave management, and deterministic payroll processing engine:
1. **Staff Directory & Profiles:** Staff records, designations, departments, qualifications, and role assignments in `HRService`.
2. **Leave Management Lifecycle:**
   - Leave applications (`CASUAL`, `SICK`, `EARNED`, `MATERNITY`, `UNPAID`).
   - Overlap detection: prevents a staff member from having overlapping active leave requests.
   - Review and approval lifecycle (`PENDING` $\rightarrow$ `APPROVED` / `REJECTED`) with rejection reason logging.
3. **Staff Attendance Tracking:** Daily check-in/check-out timestamps and status (`PRESENT`, `ABSENT`, `ON_LEAVE`, `HALF_DAY`).
4. **Deterministic Payroll Calculation:**
   - Payroll periods (`OPEN`, `PROCESSING`, `LOCKED`, `PAID`).
   - Salary components (basic salary, structured allowances, structured deductions).
   - Exact gross-to-net arithmetic: $\text{Gross} = \text{Basic} + \sum \text{Allowances}$, $\text{Net} = \text{Gross} - \sum \text{Deductions}$, rounded to 2 decimal places.
   - Immutable payslip records and run finalization.

---

## 2. Likely Files & Scope Boundary

- `central_platform/hr/service.py` (`HRService`, `PayrollService`)
- `central_platform/models/hr.py`
- `central_platform/api/routes/admin.py`
- `tests/test_qa_phase14_e2e_product_acceptance.py`
- `tests/test_qa_phase16_final_audit_handover.py`

---

## 3. Targeted Test Scenarios

1. Submitting overlapping leave requests raises `ValueError("Overlapping leave request exists")`.
2. Leave approval updates status and records approver timestamp.
3. Staff attendance records upsert cleanly without duplicate key violations.
4. Payroll run calculates gross, total deductions, and net accurately for all employee salary specs.
5. Finalizing a payroll run locks the period status to prevent unapproved edits.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Staff directory and leave overlap prevention verified.
- [ ] Leave application and approval workflow verified.
- [ ] Deterministic gross-to-net payroll arithmetic verified.
- [ ] Payroll locking and individual payslip generation verified.
- [ ] `docs/erp_agent/reports/PHASE_08_REPORT.md` and `docs/erp_agent/regressions/PHASE_08_REGRESSION.md` generated with passing evidence.
