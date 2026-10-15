# Phase 06 Plan: Student Learning, Review Lifecycle, and Persistence

**Phase:** PHASE-06  
**Status:** IN_PROGRESS  
**Date:** 2026-10-15  
**Target Findings:** Student learning lifecycle, review queue, spaced review persistence, and cross-student isolation.

---

## 1. Problem Analysis & Objectives

### 1.1 Review Lifecycle and Spaced Review Persistence
- **Current Behavior:**
  - `SpacedReviewScheduler.calculate_next_review()` generates interval days and future review timestamps, but `LearningEngineBridge.process_student_action()` created learning events prior to calculating `next_review_at`, omitting `next_review_at` from the event payload.
  - Spaced review scheduling was not persistently committed into `student_spaced_reviews` during action submission.
  - As a result, concept review status could not be durably reconstructed after server restart or session boundary crossings.
- **Required Invariants:**
  - `LearningEngineBridge.process_student_action()` must calculate the updated spaced review interval and persist `next_review_at` into both the event payload and the `student_spaced_reviews` table.
  - State transitions must be idempotent: repeated reviews update intervals predictably according to the schedule (`1d -> 3d -> 7d -> 14d -> 30d`) without data corruption.
  - Progress and review due state must survive server restarts.

### 1.2 Review Queue API and Student Portal Backend
- **Current Behavior:**
  - `StudentPortalController` lacked a `get_review_queue` method.
  - `central_platform/api/routes/students.py` lacked a `GET /api/v1/students/{student_id}/review-queue` endpoint.
  - The student portal UI had no REST API to load the real review queue from persistence.
- **Required Invariants:**
  - Implement `StudentPortalController.get_review_queue(student_id, course_id, db)` returning authorized `List[ReviewQueueItem]`.
  - Expose `GET /api/v1/students/{student_id}/review-queue` in `central_platform/api/routes/students.py`.
  - Empty review queues must return an explicit `[]` and render the empty state (`No review items due!`), never a silent error or mock fallback.

### 1.3 Strict Student Self-Access and Cross-Tenant Isolation
- **Current Behavior:**
  - Review queue and progress retrieval must enforce student self-access boundaries:
    - Student A cannot access Student B's review queue or progress (HTTP 403 Forbidden).
    - Teachers and Admins can view review queues of students within their tenant.
    - Production mode requires authentication (HTTP 401).

---

## 2. Implementation Steps

1. **Reproduction & Targeted Test Suite:**
   - Author `tests/test_qa_phase06_learning_review_persistence.py`:
     - Spaced review calculation and persistence across restarts.
     - `GET /api/v1/students/{student_id}/review-queue` endpoint contract and empty queue state.
     - Student isolation: Student A attempting to access Student B's review queue receives HTTP 403.
     - Teacher/Admin accessing student review queue within organization is authorized.
     - Idempotent review action submission via `POST /api/v1/students/{student_id}/action`.
     - UI controller `loadReviewQueue` contract in `student.js`.

2. **Persistence Hardening:**
   - In `central_platform/learning/bridge.py`:
     - Calculate spaced review schedule before or during event ingestion, persisting `next_review_at` into event payload.
     - Upsert spaced review schedule into `student_spaced_reviews`.
   - In `central_platform/progress/service.py`:
     - Query `student_spaced_reviews` to accurately detect due reviews.

3. **Backend Service & Route Wiring:**
   - In `central_platform/portals/student.py`:
     - Implement `StudentPortalController.get_review_queue(student_id, course_id, db)`.
   - In `central_platform/api/routes/students.py`:
     - Add `GET /api/v1/students/{student_id}/review-queue` with role and student boundary enforcement.

4. **Frontend Integration:**
   - In `app/ui/design_system/student.js`:
     - Implement `loadReviewQueue(studentId, courseId)` fetching `/api/v1/students/${studentId}/review-queue` and invoking `renderReviewQueue`.

5. **Test Verification & Regression:**
   - Run `tests/test_qa_phase06_learning_review_persistence.py`.
   - Run related learning suites.
   - Run full non-GUI regression suite (`pytest -q -m "not gui"`).
   - Author `PHASE_06_LOG.md` and update trackers.
