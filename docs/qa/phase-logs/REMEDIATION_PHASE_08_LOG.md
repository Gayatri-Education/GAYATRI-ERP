# Remediation Phase 08 Log: Database/App Lifecycle, Transactions, Migration Safety & Service Isolation (QA-008)

**Phase:** Phase 08  
**Issue Code:** QA-008  
**Goal Ref:** [`GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](file:///c:/Users/user/Desktop/gayatri/Gayatri-ERP/GAYATRI_ERP_QA_REMEDIATION_GOAL.md)  
**Status:** PASSED  
**Execution Date:** 2026-10-15  
**Branch:** `qa/production-readiness-remediation`  

---

## 1. Executive Summary
Phase 08 eliminated state leakage across application instances, removed all volatile in-memory storage arrays (`_USERS_STORE`, `_ACTIVE_SESSIONS`), enforced atomic multi-table transaction rollback using nested savepoints in `PlatformDatabase` and domain services (`AdmissionsService.convert_application_to_student`), prohibited synthetic teacher roster seeding in production environments, verified migration reproducibility across all 16 migration steps, and confirmed SQLite runtime PRAGMA invariants (`foreign_keys = ON`, `busy_timeout = 30000`, `journal_mode = WAL`).

---

## 2. Root Cause Analysis
1. **Volatile In-Memory `_USERS_STORE`:** `central_platform/api/routes/users.py` defined a module-level mutable list `_USERS_STORE = [UserResponse(...)]`. The `GET /api/v1/users` and `GET /api/v1/users/{user_id}` endpoints read strictly from this list, ignoring seeded database records.
2. **Volatile In-Memory `_ACTIVE_SESSIONS`:** `central_platform/api/routes/sessions.py` cached tutoring sessions in a module-level Python dict `_ACTIVE_SESSIONS`, creating memory leaks and diverging from persisted sessions in `PlatformDatabase`.
3. **Partial Writes in Multi-Table Workflows:** `AdmissionsService.convert_application_to_student` performed sequential inserts across `persons`, `student_profiles`, `guardian_profiles`, `student_guardian_links`, `student_class_enrollments`, and updates to `admission_applications` without an outer atomic transaction wrapper. If class enrollment failed due to a foreign key or constraint violation, orphan person records remained persisted.
4. **Synthetic Teacher Roster Seeding in Production:** `central_platform/teacher/portal.py` automatically seeded demo students into `TeacherPortalService` regardless of whether `GAYATRI_PRODUCTION_MODE` was active.
5. **Stale Connection Module Singletons:** `central_platform/api/routes/students.py` assigned `_db = get_db()` and `_curriculum_service = CurriculumService(_db)` at module import time, preventing dynamic database path resolution when tests or environments updated `GAYATRI_DB_PATH`.

---

## 3. Implementation Details

### 3.1 Central Data Layer (`central_platform/db.py`)
- Added `list_users(organization_id=None, role=None, limit=50, offset=0, include_deleted=False) -> List[User]` with parameterized SQL filtering and offset pagination.
- Added automatic seeding of standard central organization (`org-central`) and development credentials in non-production mode only (`not is_production_mode()`). In production, zero synthetic records are injected.

### 3.2 User API Route Elimination of `_USERS_STORE` (`central_platform/api/routes/users.py`)
- Removed `_USERS_STORE` list.
- Updated `list_users` to query `db.list_users(...)` via dependency injection (`db: PlatformDatabase = Depends(get_db)`).
- Updated `create_user` to persist `User` into `PlatformDatabase` inside `with db.transaction():` and format role names in uppercase.
- Updated `get_user_by_id` to query `db.get_user(user_id)`.

### 3.3 Sessions API Route Elimination of `_ACTIVE_SESSIONS` (`central_platform/api/routes/sessions.py`)
- Removed `_ACTIVE_SESSIONS` dictionary.
- Updated `start_session` to persist sessions directly into `PlatformDatabase.create_session` within `with db.transaction():`.
- Updated `get_session` to query `PlatformDatabase.get_session(session_id)`.

### 3.4 Admissions Multi-Table Atomic Rollback (`central_platform/admissions/service.py`)
- Wrapped all 6 multi-table steps of `convert_application_to_student` in `with self.db.transaction():`. Any error during person, profile, guardian, class enrollment, application status update, or domain event enqueueing triggers a clean rollback to zero partial writes.

### 3.5 Teacher Portal Demo Roster Production Hardening (`central_platform/teacher/portal.py`)
- Guarded `seed_demo_teacher_roster` and `get_shared_portal_service` with `if os.environ.get("GAYATRI_PRODUCTION_MODE", "").lower() in ("true", "1"): return`.

### 3.6 Student Route Dynamic DB Binding (`central_platform/api/routes/students.py`)
- Replaced static module-level `_db = get_db()` and `_curriculum_service = CurriculumService(_db)` with dynamic getters `_get_db()` and `_get_curriculum_service()`.

---

## 4. Test Verification
Authored [`tests/test_phase08_database_isolation.py`](file:///c:/Users/user/Desktop/gayatri/Gayatri-ERP/tests/test_phase08_database_isolation.py) covering 9 comprehensive test cases:

| Test Case | Description | Result |
|-----------|-------------|--------|
| `test_independent_database_isolation` | Verifies two database instances with separate temp paths never leak records across tenants or processes. | PASSED |
| `test_reproduce_users_route_reads_from_real_database` | Verifies `GET /api/v1/users` returns database-persisted users rather than in-memory placeholders. | PASSED |
| `test_admissions_conversion_atomic_rollback_on_failure` | Verifies atomic rollback on conversion failure; zero orphan persons or student profiles leak. | PASSED |
| `test_nested_savepoint_rollback` | Verifies nested savepoint rollback (`tx_sp_{depth}`) in `PlatformDatabase.transaction()`. | PASSED |
| `test_migration_runner_repeatability_and_checksum_verification` | Verifies running all 16 migrations sequentially, idempotency on re-run, and SHA-256 checksum validation. | PASSED |
| `test_sqlite_pragmas` | Verifies `PRAGMA foreign_keys = 1`, `busy_timeout >= 30000`, and `journal_mode = WAL`. | PASSED |
| `test_sessions_route_persists_and_reads_from_real_database` | Verifies session start and retrieval write to and read from the durable `sessions` table. | PASSED |
| `test_migration_checksum_tamper_detection` | Verifies checksum tampering on applied migration scripts is flagged by `verify_migration_checksums`. | PASSED |
| `test_teacher_portal_service_prohibits_demo_roster_in_production` | Verifies `seed_demo_teacher_roster` is skipped when `GAYATRI_PRODUCTION_MODE=true`. | PASSED |

### Regression Suite Results (Phases 01–08)
```
91 passed in 21.94s (0 failed, 0 skipped, 0 xfailed)
```

Baseline Platform & RBAC Suite:
```
72 passed in 10.08s (0 failed, 0 skipped)
```
