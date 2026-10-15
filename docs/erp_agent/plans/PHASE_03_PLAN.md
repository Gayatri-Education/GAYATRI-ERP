# Phase 03 Plan — Admissions, Lead CRM and Student Lifecycle

**Document:** `docs/erp_agent/plans/PHASE_03_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 03 — Admissions, Lead CRM and Student Lifecycle  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 03 verifies and validates the end-to-end student intake, admissions CRM, and lifecycle management workflows:
1. **Inquiry CRM Pipeline:** Walk-in, telephone, and web inquiries; source attribution; duplicate detection by email and phone; counselor assignment; follow-up status lifecycle (`NEW`, `CONTACTED`, `QUALIFIED`, `CONVERTED`, `LOST`).
2. **Intake Application Workflow:** Multi-step intake capturing target grade, student details, legal profiles, prior academic records, guardian details, and fee structure linkages.
3. **Atomic Inquiry-to-Student Conversion:** Conversion from approved inquiry/application to registered student in SIS, ensuring that roll number allocation is sequential and collision-safe, and financial fee group assignment is atomic.
4. **Data Minimization & Validation:** Photo upload safety, emergency contact mapping, guardian relationship validation, and resumable draft safety.

---

## 2. Likely Files & Scope Boundary

- `central_platform/admissions/service.py` (`AdmissionsService`)
- `central_platform/sis/service.py` (`SISService`)
- `central_platform/api/routes/admissions.py`
- `central_platform/api/routes/sis.py`
- `central_platform/models/admissions.py`
- `central_platform/models/sis.py`
- `tests/test_qa_phase14_e2e_product_acceptance.py`
- `tests/test_qa_phase12_integrated_journeys.py`

---

## 3. Targeted Test Scenarios

1. Submitting a new inquiry persists correctly and generates a formatted inquiry number (`INQ-YYYY-XXXXXX`).
2. Submitting duplicate email/phone triggers duplicate detection (`find_duplicate_inquiries`).
3. Application creation, document attachment, and verification status tracking.
4. Admission offer generation, acceptance, and atomic conversion into an active student record.
5. Inability to generate duplicate roll numbers or leave dangling finance records upon mid-conversion failure.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Inquiry deduplication and counselor assignment verified.
- [ ] Multi-step application submission and offer generation verified.
- [ ] Atomic inquiry-to-student conversion verified with zero partial or orphaned state.
- [ ] All targeted admission and student lifecycle test suites pass with 100% success.
- [ ] `docs/erp_agent/reports/PHASE_03_REPORT.md` and `docs/erp_agent/regressions/PHASE_03_REGRESSION.md` generated with passing evidence.
