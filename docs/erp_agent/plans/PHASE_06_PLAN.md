# Phase 06 Plan — Academics, Timetable Solver and Substitutions

**Document:** `docs/erp_agent/plans/PHASE_06_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 06 — Academics, Timetable Solver and Substitutions  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 06 verifies the institutional academic structure, timetable generation with hard constraint conflict resolution, and teacher substitution dispatching:
1. **Academic Framework:** Academic years, terms, classes, sections, subject assignments, and teacher allocations in `AcademicService`.
2. **Timetable Scheduling Engine:** Bell periods, break definitions, and schedule slots.
3. **Deterministic Constraint Validation:**
   - Teacher double-booking prevention: a teacher cannot be assigned to two classes simultaneously in the same period.
   - Room double-booking prevention: a room cannot host multiple classes in the same period.
   - Conflict reporting: actionable errors returned when clashes occur.
4. **Teacher Substitution Lifecycle:** Assignment of qualified substitute teachers to periods where the regular faculty is on leave or absent.

---

## 2. Likely Files & Scope Boundary

- `central_platform/academic/service.py` (`AcademicService`)
- `central_platform/timetable/service.py` (`TimetableService`)
- `central_platform/models/academic.py`
- `central_platform/models/timetable.py`
- `central_platform/api/routes/academic.py`
- `central_platform/api/routes/timetable.py`
- `tests/test_qa_phase14_e2e_product_acceptance.py`
- `tests/test_phase8_curriculum_validation.py`

---

## 3. Targeted Test Scenarios

1. Creation of academic years, terms, and classes with validation.
2. Period definition with start/end time and break tags.
3. Attempting to schedule a slot with an already-booked teacher raises `ValueError("Teacher already booked for this period on this day")`.
4. Attempting to schedule a slot in an already-booked room raises `ValueError("Room already booked for this period on this day")`.
5. Valid substitution creation assigns the substitute teacher and records the original faculty.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Academic session and class/section hierarchy verified.
- [ ] Timetable period and slot scheduling verified.
- [ ] Teacher and room clash detection verified with zero silent double-booking.
- [ ] Teacher substitution workflow verified.
- [ ] `docs/erp_agent/reports/PHASE_06_REPORT.md` and `docs/erp_agent/regressions/PHASE_06_REGRESSION.md` generated with passing evidence.
