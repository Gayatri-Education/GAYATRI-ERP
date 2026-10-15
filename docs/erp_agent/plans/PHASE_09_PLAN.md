# Phase 09 Plan — LMS and Course Delivery

**Document:** `docs/erp_agent/plans/PHASE_09_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 09 — LMS and Course Delivery  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 09 verifies and validates the Learning Management System (LMS), curriculum ingestion, course versioning, student enrollments, progress tracking, and assessment workflows:
1. **Course Domain & Versioning:** Subject-agnostic course models (`Course`, `CourseVersion`, `OrganizationCourseOffering`, `Enrollment`) in `CourseService`.
2. **Curriculum DAG & Progress Tracking:** Module, topic, and concept progress tracking in `ProgressService` with mastery projections.
3. **Quizzes & Auto-Evaluation:** Assessment generation, student attempts, deterministic rubric scoring, and fail-closed evaluation policy.
4. **Content Governance & Versioning:** Teacher course drafting $\rightarrow$ administrator approval and version publishing.
5. **Scoped Knowledge & Asset Grounding:** Course-version pinned RAG indexing and deletion.

---

## 2. Likely Files & Scope Boundary

- `central_platform/courses/service.py` (`CourseService`)
- `central_platform/progress/service.py` (`ProgressService`)
- `central_platform/assessment/service.py` (`AssessmentService`)
- `central_platform/curriculum/service.py` (`CurriculumService`)
- `central_platform/api/routes/courses.py`
- `central_platform/api/routes/assessments.py`
- `tests/test_qa_phase03_educational_correctness.py`
- `tests/test_phase27_student_portal_ui.py`
- `tests/test_phase6_adaptive_engine_v2.py`

---

## 3. Targeted Test Scenarios

1. Course creation, versioning, and offering registration.
2. Enrollment lifecycle: student enrolled in active offering gains course access; unenrolled student is blocked with `403 Forbidden`.
3. Progress tracking updates completed concepts and recalculates completion percentages.
4. Assessment auto-grading evaluates answers accurately without awarding unearned credit on failed/mock evaluations.
5. Student portal displays enrolled courses, syllabus progress, and due review items.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Course versioning, offering, and enrollment models verified.
- [ ] Student lesson progress and concept mastery tracking verified.
- [ ] Assessment auto-grading and fail-closed evaluation verified.
- [ ] Student LMS portal integration verified.
- [ ] `docs/erp_agent/reports/PHASE_09_REPORT.md` and `docs/erp_agent/regressions/PHASE_09_REGRESSION.md` generated with passing evidence.
