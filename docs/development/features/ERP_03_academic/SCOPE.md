# ERP Feature Scope: Academic Calendars, Classes & Batches (ERP-03)

**Feature ID:** `ERP-03`  
**Governing Contract:** `DEVELOPMENT.md` (Sections 4, 14 & 15.4)  
**Parent Phase:** Phase 02B (Core ERP Foundation)  
**Status:** Approved for Implementation  
**Last Updated:** 2026-10-14  

---

## 1. Business Purpose and Beneficiaries
- **Purpose:** Provide the structural academic backbone for both K–12 schools (academic years, terms, grades, sections) and coaching institutes (courses, target exam batches, weekend/evening sessions, cohorts).
- **Beneficiaries:**
  - **Academic Deans / Principals:** Define official school calendar, working days, exam windows.
  - **Coaching Directors:** Set up fast-track, crash-course, or test-series batches.
  - **Teachers & Faculty:** Manage assigned class sections and batch rosters.
  - **Students:** Understand their batch timetable, term start/end dates, and course offerings.

---

## 2. Institutional Model Flexibility

The system supports two primary tenant operational modes:
1. **K–12 School Mode:**
   - Academic Year (e.g. 2026–2027) -> Terms (Term 1, Term 2, Annual).
   - Grade Levels (Class 9, 10, 11, 12) -> Sections (Section A, B, C).
   - Standard working days (Mon–Fri/Sat) with official public and institutional holidays.
2. **Coaching / Exam Prep Mode:**
   - Program (JEE Advanced, NEET, Foundation) -> Batch (Morning Batch, Weekend Batch).
   - Dynamic start/end dates and rolling admissions.

---

## 3. Data Entities & Schema Extension
- Tables:
  - `academic_years` (`id`, `organization_id`, `name`, `start_date`, `end_date`, `is_current`)
  - `academic_terms` (`id`, `academic_year_id`, `name`, `start_date`, `end_date`, `is_active`)
  - `school_calendar_events` (`id`, `organization_id`, `academic_year_id`, `title`, `event_type`, `start_date`, `end_date`, `is_holiday`)
  - `classes` / `class_groups` (extended with `max_capacity`, `academic_year_id`, `mode`)
  - `class_enrollments` (linking student to class/batch with enrollment dates)

---

## 4. Business Workflow & State Machine
- Academic Year: `PLANNED` -> `ACTIVE` -> `COMPLETED` -> `ARCHIVED`. Only one academic year can be `ACTIVE` per organization at a time.
- Class / Batch: `DRAFT` -> `ACTIVE` -> `CLOSED`.
- Enrollment: `PENDING` -> `ENROLLED` -> `COMPLETED` -> `TRANSFERRED` -> `DROPPED`.

---

## 5. Acceptance Criteria (Given/When/Then)
- **AC-ACAD-01:** Given an organization, when an academic year is marked `ACTIVE`, then previously active years are transitioned to `COMPLETED`.
- **AC-ACAD-02:** Given a class section with capacity 40, when the 41st student is enrolled, then the system enforces the capacity limit unless an explicit override flag is supplied.
- **AC-ACAD-03:** Given working calendar queries, holidays are returned with event metadata and excluded from attendance calculation baselines.
