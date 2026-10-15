# Remediation Plan — Phase 08: Database/App Lifecycle, Transactions, Migration Safety, and Service Isolation (QA-008)

**Phase ID:** 08  
**Target Vulnerability / Finding:** QA-008 (Database Lifecycle Leaks, In-Memory Global Stores, Transaction Rollback Semantics & Migration Safety)  
**Contract Reference:** [`../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md) Section 11  
**Branch:** `qa/production-readiness-remediation`  
**Status:** IN_PROGRESS  

---

## 1. Inspection Findings & Root Cause Analysis

1. **In-Memory Global Data Stores Bypassing Database:**
   - In `central_platform/api/routes/users.py`, `_USERS_STORE` is a module-level mutable Python list containing default hardcoded users (`usr-admin-01`, `usr-teacher-01`, `usr-student-01`).
   - `list_users`, `create_user`, and `get_user_by_id` operate on `_USERS_STORE` instead of querying the database.
   - **Impact:** State leaks across multiple application instances and test runs. Users created in database tests are invisible to `/api/v1/users` unless appended to the shared global list.
   - In `central_platform/api/routes/sessions.py`, `_ACTIVE_SESSIONS` is an in-memory dictionary duplicating database sessions.

2. **Module-Level Service Singletons Capturing Stale Database Connections:**
   - `central_platform/api/routes/admin.py` (`_admin_service`) and `analytics.py` (`_analytics_service`) cache service instances globally without verifying if the underlying `PlatformDatabase` reference matches the current request's DB.
   - `central_platform/api/routes/students.py` and `teachers.py` instantiate `CurriculumService`, `SLRService`, `StudentProgressService`, `TeacherInstructionEngine`, and `TeacherInterventionEngine` at import time using `_db = get_db()`, capturing whatever DB was initialized at module load.
   - **Impact:** Changing `GAYATRI_DB_PATH` in tests or running multiple application instances causes operations to execute against stale or closed connections from previous test runs.

3. **Multi-Table Atomic Mutation Gaps:**
   - In `central_platform/admissions/service.py`: `convert_application_to_student()` executes 6 separate SQL inserts/updates across `persons`, `student_profiles`, `guardian_profiles`, `student_guardian_links`, `student_class_enrollments`, and `admission_applications` within `with self.db._get_connection() as conn:`.
   - If an error occurs midway (e.g., duplicate enrollment or constraint violation), previous inserts are not rolled back via the savepoint/nested transaction mechanism, creating orphan records.

4. **Demo Teacher Roster Seeding in Production Mode:**
   - In `central_platform/teacher/portal.py`, `get_shared_portal_service()` automatically calls `seed_demo_teacher_roster()` whenever the singleton is instantiated, risking synthetic demo roster injection in production.

---

## 2. Remediation Strategy

### Step 1: Eliminate `_USERS_STORE` and `_ACTIVE_SESSIONS`
- Add canonical `list_users()` method to `PlatformDatabase` with `organization_id`, `role`, `limit`, and `offset` filtering.
- Refactor `central_platform/api/routes/users.py`:
  - `list_users()` queries `db.list_users()`.
  - `create_user()` calls `db.create_user()` and commits durably.
  - `get_user_by_id()` calls `db.get_user(user_id)`.
  - Remove `_USERS_STORE` completely.
- Refactor `central_platform/api/routes/sessions.py`:
  - `start_session()` and `get_session()` interact directly with `db.create_session()` and `db.get_session()`.
  - Remove `_ACTIVE_SESSIONS` completely.

### Step 2: Dynamic Service Resolution & Dependency Injection
- In `central_platform/api/routes/admin.py`:
  - Update `get_admin_service(db: PlatformDatabase = Depends(get_db))` to check `if _admin_service is None or _admin_service.db is not db:` before returning.
- In `central_platform/api/routes/analytics.py`:
  - Update `get_analytics_service(db: PlatformDatabase = Depends(get_db))` to check `if _analytics_service is None or _analytics_service.db is not db:`.
- In `central_platform/api/routes/students.py` and `teachers.py`:
  - Convert module-level singletons into dependency-injected getters (`get_slr_service`, `get_progress_service`, `get_curriculum_service`) bound to `db`.
- In `central_platform/teacher/portal.py`:
  - Restrict `seed_demo_teacher_roster()` to non-production mode only (`if not is_production_mode():`).

### Step 3: Explicit Transaction & Rollback Semantics in Admissions Conversion
- Wrap `convert_application_to_student()` in `with self.db.transaction():`.
- Ensure atomic rollback of all entities (`persons`, `student_profiles`, `guardians`) upon failure.

### Step 4: Verification of Database Isolation, Concurrency & Migration Safety
- Author `tests/test_phase08_database_isolation.py` proving:
  1. Two separate `PlatformDatabase` instances on distinct temp paths never share records or state.
  2. Nested transactions (savepoints) roll back cleanly on injected exceptions.
  3. Admissions conversion rolls back completely if any step fails.
  4. Migration runner idempotency, forward application, and checksum verification.
  5. SQLite PRAGMAs (WAL mode, foreign keys, busy timeout).

---

## 3. Exit Criteria

1. Independent DB isolation test passes; two app/db instances never share state.
2. Transaction and restart tests cover all critical mutations with verified rollback.
3. Zero module-level in-memory stores (`_USERS_STORE`, `_ACTIVE_SESSIONS`) remain in route modules.
4. Migrations are repeatable, checksummed, and verified.
5. All test assertions pass with zero weakened assertions or broad xfails.
