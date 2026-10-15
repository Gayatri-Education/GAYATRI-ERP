# Phase 07 Plan — Exams, Marks Moderation, Results and Report Cards

**Document:** `docs/erp_agent/plans/PHASE_07_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 07 — Exams, Marks Moderation, Results and Report Cards  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 07 verifies and hardens the institutional examination, grading, results, and report card generation workflows:
1. **Exam Series & Schedules:** Term exam series creation (`MID_TERM`, `FINAL`, `UNIT_TEST`), date sheets, maximum marks, and passing criteria in `ExaminationService`.
2. **Marks Entry & Validation:**
   - Numerical score boundaries ($0 \le \text{marks\_obtained} \le \text{max\_marks}$).
   - Absent vs exempt vs zero distinction (`MarksStatus.SUBMITTED`, `ABSENT`, `EXEMPT`).
   - Duplicate entry prevention per student, schedule, and exam series.
3. **Moderation, Locking & Audited Reopen:**
   - Teacher submission $\rightarrow$ Admin/HOD review $\rightarrow$ `LOCKED` status.
   - Guard against unauthorized edits on locked marks. Audited reopen requires authorized administrator credentials and reason logging.
4. **Grading & Report Cards:**
   - Multi-tier grading scales (CBSE 9-point, percentage tiers).
   - Term result calculation with weighted component marks, percentage calculation, and grade determination.
   - Report card generation with layout metadata.

---

## 2. Likely Files & Scope Boundary

- `central_platform/examinations/service.py` (`ExaminationService`)
- `central_platform/grading/service.py` (`GradingService`)
- `central_platform/models/examinations.py`
- `central_platform/models/grading.py`
- `central_platform/api/routes/examinations.py`
- `central_platform/api/routes/grading.py`
- `tests/test_qa_phase07_assessment_integrity.py`
- `tests/test_qa_phase14_e2e_product_acceptance.py`

---

## 3. Targeted Test Scenarios

1. Out-of-range marks ($> \text{max\_marks}$ or $< 0$) are rejected with validation errors.
2. Finalizing marks sets status to `LOCKED`; subsequent edit attempts without reopening are rejected.
3. Reopening marks requires explicit reason and updates status back to `REOPENED` with audit trail.
4. Grading calculation maps percentages to correct grade points and letter grades.
5. Report card generation compiles student details, subject marks, grades, and attendance summary.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Exam series and schedule creation verified.
- [ ] Marks validation, absent/exempt handling, and duplicate prevention verified.
- [ ] Marks lock and audited reopen workflow verified.
- [ ] Deterministic grade calculation and report card generation verified.
- [ ] `docs/erp_agent/reports/PHASE_07_REPORT.md` and `docs/erp_agent/regressions/PHASE_07_REGRESSION.md` generated with passing evidence.
