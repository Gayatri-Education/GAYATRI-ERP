# Phase 09 Plan: Attendance, Academic Workflows, Instructions, Notifications, and Sync

**Phase:** PHASE-09  
**Status:** IN_PLANNING  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer  

---

## 1. Goal & Scope
Harden and certify canonical service routing across academic workflows, attendance tracking, teacher instructions, multi-channel notifications, and offline-to-central synchronization. Eliminate in-memory-only legacy bypasses (ERP-015), enforce role boundaries (students blocked from taking attendance, teachers isolated by organization), certify durable restart persistence, and verify sync idempotency and conflict reconciliation.

---

## 2. Target Findings & Invariants
- **ERP-015**: Legacy endpoints in `central_platform/api/app.py` (`/api/sync/events`, `/api/teacher/instruction`, `/instruction`) bypass canonical database persistence, keeping state only in volatile in-memory singletons that disappear upon restart.
- **Attendance Workflow & Role Invariant**:
  - `POST /api/v1/attendance/sessions` and `POST /api/v1/attendance/sessions/{id}/records` MUST be restricted to `TEACHER`, `ORG_ADMIN`, and `SUPER_ADMIN`. Students and parents must be rejected with HTTP 403.
  - `POST /api/v1/attendance/excuses` must enforce student self-access (students cannot submit excuse requests on behalf of other students, HTTP 403 IDOR block).
  - Excuse approval (`POST /api/v1/attendance/excuses/{id}/approve`) must require administrative roles.
- **Sync & Durability Invariant**:
  - Events posted to `/api/sync/events` or `/api/v1/sync/events` must be processed by `SyncService` and committed into `PlatformDatabase` (learning events and sync operation records must survive application restart).
  - Replayed sync batches with identical `operation_id` or duplicate event IDs must be idempotent (`duplicate_count` reported, zero redundant database rows).
  - Device bindings and queries must enforce student self-access (HTTP 403 when a student queries devices of another student).
- **Teacher Instruction Invariant**:
  - Instructions added via `/api/teacher/instruction` or `/instruction` must be persisted to `PlatformDatabase` and retrievable after process restart.
  - Cross-organization instruction creation is strictly forbidden (HTTP 403).
  - Safety validation violations must reject with HTTP 400.
- **Notifications DI & Privacy Invariant**:
  - `get_notification_service` must receive `db: PlatformDatabase = Depends(get_db)` to harmonize DI across the platform.
  - Students cannot inspect notifications belonging to other recipients (HTTP 403).

---

## 3. Implementation Plan
1. **Remediate `central_platform/api/routes/attendance.py`**:
   - Enforce role guard on `create_session` and `submit_roll_call` (`_get_roles` must include `teacher`, `admin`, `org_admin`, or `super_admin`).
   - In `submit_excuse`, check that student callers can only submit for their own `student_id`.
2. **Remediate `central_platform/api/app.py` (Legacy Endpoints)**:
   - In `legacy_sync_events`, route batch through `SyncService(db=get_db()).process_sync_batch(student_id=student_id, events=events)` before notifying legacy in-memory manager.
   - In `legacy_add_instruction`, persist instruction through `TeacherInstructionEngine(db=get_db()).add_instruction(inst, actor=current_user)`.
   - In `legacy_teacher_instructions`, query `PlatformDatabase` to ensure persisted instructions are returned after restart.
3. **Remediate `central_platform/api/routes/notifications.py` & `central_platform/api/routes/sync.py`**:
   - Harmonize DI: inject `db: PlatformDatabase = Depends(get_db)` into `get_notification_service` and `get_sync_service`.
   - Ensure all route endpoints receive injected service dependencies.
4. **Author Reproduction Suite (`tests/test_qa_phase09_workflows_sync_integrity.py`)**:
   - Test 1: Attendance session creation by student -> HTTP 403.
   - Test 2: Roll call submission by student -> HTTP 403.
   - Test 3: Attendance session creation and roll call by teacher -> HTTP 201/200.
   - Test 4: Student submitting excuse for another student -> HTTP 403 (IDOR).
   - Test 5: Legacy sync `/api/sync/events` persists events to `PlatformDatabase` (restart simulation).
   - Test 6: Canonical sync `/api/v1/sync/events` idempotency (duplicate operation replay).
   - Test 7: Device binding and listing IDOR isolation (student querying another student's devices -> HTTP 403).
   - Test 8: Legacy teacher instruction `/api/teacher/instruction` persists to database (survives restart).
   - Test 9: Cross-tenant teacher instruction creation rejected with HTTP 403.
   - Test 10: Notification recipient isolation (student querying another student's notifications -> HTTP 403).
5. **Run targeted tests, debug, and execute full regression suite (`python -m pytest -q -m "not gui"`)**.
6. **Update logs, trackers, issue register, and commit**.
