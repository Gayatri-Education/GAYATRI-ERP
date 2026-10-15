"""Phase 08 — Database Lifecycle, Service Isolation & Transaction Safety (QA-008).

Tests:
1. Strict database isolation: two app/database instances using separate temp DB paths never share records, users, or state.
2. Elimination of in-memory stores (_USERS_STORE, _ACTIVE_SESSIONS) — all user and session queries read from and write to the real database.
3. Multi-table transaction rollback: admissions conversion rolls back completely if any sub-operation fails.
4. Nested savepoint transaction rollback in PlatformDatabase.
5. Migration repeatability, forward progression, and checksum tamper detection.
6. SQLite PRAGMA verification (foreign keys, WAL mode, busy timeout).
"""

from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient

from central_platform.admissions.service import AdmissionsService
from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.admissions import AdmissionApplication, ApplicationStatus
from central_platform.models.schema import Course, Organization, Session, SessionStatus, User, UserRole
from scripts.migrate_db import (
    MigrationChecksumMismatchError,
    compute_file_checksum,
    get_applied_migrations,
    run_all_migrations,
    verify_migration_checksums,
)


def auth_header(user_id: str, role: str, org_id: str) -> dict:
    token = create_access_token(user_id=user_id, role=role, organization_id=org_id)
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. Independent Database Isolation (QA-008 Invariant 1)
# =====================================================================

def test_independent_database_isolation(tmp_path):
    path_a = str(tmp_path / "instance_a.db")
    path_b = str(tmp_path / "instance_b.db")

    db_a = PlatformDatabase(path_a)
    db_b = PlatformDatabase(path_b)

    # Seed organization and user in instance A only
    org_a = Organization(id="org_alpha_test", name="Alpha Institute", slug="alpha-inst")
    user_a = User(
        id="usr_alpha_1",
        email="alpha1@test.edu",
        full_name="Alpha User",
        role=UserRole.ORG_ADMIN,
        organization_id="org_alpha_test",
        is_active=True,
    )
    db_a.create_organization(org_a)
    db_a.create_user(user_a)

    # Assert instance A has the records
    assert db_a.get_organization("org_alpha_test") is not None
    assert db_a.get_user("usr_alpha_1") is not None

    # Assert instance B is completely isolated and has zero records from A
    assert db_b.get_organization("org_alpha_test") is None
    assert db_b.get_user("usr_alpha_1") is None
    assert len(db_b.get_users_by_organization("org_alpha_test")) == 0


# =====================================================================
# 2. Elimination of _USERS_STORE — Routes Bound to Real Database
# =====================================================================

def test_reproduce_users_route_reads_from_real_database(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_users_db.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase08-users-12345678")

    db = PlatformDatabase(db_path)
    org = Organization(id="org_test_real", name="Real Test Org", slug="real-test-org")
    admin = User(
        id="usr_admin_real",
        email="admin@real.edu",
        full_name="Real Admin",
        role=UserRole.ORG_ADMIN,
        organization_id="org_test_real",
        is_active=True,
    )
    user_seeded = User(
        id="usr_seeded_in_db_only",
        email="seeded@real.edu",
        full_name="Seeded User",
        role=UserRole.STUDENT,
        organization_id="org_test_real",
        is_active=True,
    )
    db.create_organization(org)
    db.create_user(admin)
    db.create_user(user_seeded)

    client = TestClient(app)
    headers = auth_header("usr_admin_real", "org_admin", "org_test_real")

    # Calling /api/v1/users must retrieve users from the actual database
    resp = client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 200
    user_ids = [u["user_id"] for u in resp.json()["data"]]

    # Under remediated code, usr_seeded_in_db_only must be returned
    assert "usr_seeded_in_db_only" in user_ids, f"Expected seeded user from DB, got: {user_ids}"


# =====================================================================
# 3. Multi-Table Atomic Transaction Rollback in Admissions
# =====================================================================

def test_admissions_conversion_atomic_rollback_on_failure(tmp_path):
    db_path = str(tmp_path / "test_admissions_tx.db")
    db = PlatformDatabase(db_path)

    org = Organization(id="org_adm_test", name="Admissions Org", slug="adm-org")
    db.create_organization(org)

    service = AdmissionsService(db)

    # Seed academic year in the database
    with db._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO academic_years (id, organization_id, name, code, start_date, end_date, is_current, status, created_at, updated_at)
            VALUES ('ay_2026', 'org_adm_test', '2026-2027', 'AY26', '2026-04-01', '2027-03-31', 1, 'ACTIVE', datetime('now'), datetime('now'));
            """
        )

    # Submit an inquiry and application
    inquiry = service.submit_inquiry(organization_id="org_adm_test", applicant_name="John Doe", phone="1234567890")
    application = service.submit_application(
        organization_id="org_adm_test",
        applicant_name="John Doe",
        inquiry_id=inquiry.id,
        academic_year_id="ay_2026",
        phone="1234567890",
    )
    # Accept application
    service.update_application_status("org_adm_test", application.id, ApplicationStatus.ACCEPTED)

    # Count persons before conversion
    with db._get_connection() as conn:
        persons_before = conn.execute("SELECT COUNT(*) FROM persons WHERE organization_id = 'org_adm_test';").fetchone()[0]

    # Inject failure by passing invalid class_id with non-existent academic year causing FK/constraint violation or exception
    with pytest.raises(Exception):
        service.convert_application_to_student(
            organization_id="org_adm_test",
            application_id=application.id,
            class_id="non_existent_class_id",
            roll_number="ROLL-001",
            guardian_name="Jane Doe",
            guardian_phone="0987654321",
        )

    # Verify atomic rollback: no orphan persons or student profiles were persisted
    with db._get_connection() as conn:
        persons_after = conn.execute("SELECT COUNT(*) FROM persons WHERE organization_id = 'org_adm_test';").fetchone()[0]
        students_after = conn.execute("SELECT COUNT(*) FROM student_profiles WHERE organization_id = 'org_adm_test';").fetchone()[0]
        app_after = conn.execute("SELECT status, converted_student_id FROM admission_applications WHERE id = ?;", (application.id,)).fetchone()

    assert persons_after == persons_before, f"Persons leaked on failed conversion: {persons_before} -> {persons_after}"
    assert students_after == 0, f"Orphan student profiles created on failure: {students_after}"
    assert app_after["status"] != "CONVERTED"
    assert app_after["converted_student_id"] is None


# =====================================================================
# 4. Nested Savepoint Transaction Rollback
# =====================================================================

def test_nested_savepoint_rollback(tmp_path):
    db_path = str(tmp_path / "test_nested_tx.db")
    db = PlatformDatabase(db_path)

    org = Organization(id="org_tx_parent", name="Parent Org", slug="parent-org")
    db.create_organization(org)

    with db.transaction():
        # Outer transaction write
        u1 = User(id="u_outer", email="outer@test.com", full_name="Outer User", role=UserRole.STUDENT, organization_id="org_tx_parent")
        db.create_user(u1)

        # Inner transaction that rolls back
        try:
            with db.transaction():
                u2 = User(id="u_inner", email="inner@test.com", full_name="Inner User", role=UserRole.STUDENT, organization_id="org_tx_parent")
                db.create_user(u2)
                raise RuntimeError("Injected error inside inner transaction savepoint")
        except RuntimeError:
            pass  # Inner transaction rolled back

    # Outer user should be committed, inner user should have been rolled back
    assert db.get_user("u_outer") is not None
    assert db.get_user("u_inner") is None


# =====================================================================
# 5. Migration Repeatability & Checksum Integrity
# =====================================================================

def test_migration_runner_repeatability_and_checksum_verification(tmp_path):
    db_path = str(tmp_path / "test_migrations.db")
    conn = sqlite3.connect(db_path)

    # 1. Apply all migrations to clean database
    applied = run_all_migrations(conn)
    assert len(applied) >= 16, f"Expected at least 16 migrations applied, got {applied}"

    # 2. Re-running migrations on up-to-date database is idempotent and returns 0 new migrations
    applied_again = run_all_migrations(conn)
    assert len(applied_again) == 0

    # 3. Checksums must verify cleanly
    mismatches = verify_migration_checksums(conn)
    assert len(mismatches) == 0, f"Checksum mismatches detected: {mismatches}"

    conn.close()


# =====================================================================
# 6. SQLite PRAGMA Verification (WAL, Foreign Keys, Busy Timeout)
# =====================================================================

def test_sqlite_pragmas(tmp_path):
    db_path = str(tmp_path / "test_pragmas.db")
    db = PlatformDatabase(db_path)

    with db._get_connection() as conn:
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]

    assert fk == 1, "Foreign keys must be enabled (PRAGMA foreign_keys = 1)"
    assert busy_timeout >= 30000, f"Busy timeout must be >= 30000ms, got {busy_timeout}"
    assert journal_mode.upper() == "WAL", f"Journal mode must be WAL, got {journal_mode}"


# =====================================================================
# 7. Elimination of _ACTIVE_SESSIONS — DB Persistence
# =====================================================================

def test_sessions_route_persists_and_reads_from_real_database(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_sessions_db.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase08-sessions-12345678")

    db = PlatformDatabase(db_path)
    org = Organization(id="org_sess_real", name="Session Real Org", slug="sess-real")
    course = Course(
        id="crs_chem_101",
        organization_id="org_sess_real",
        code="CHEM101",
        title="Chemistry 101",
    )
    student = User(
        id="usr_sess_student",
        email="sess_stu@real.edu",
        full_name="Session Student",
        role=UserRole.STUDENT,
        organization_id="org_sess_real",
        is_active=True,
    )
    db.create_organization(org)
    db.create_course(course)
    db.create_user(student)

    client = TestClient(app)
    headers = auth_header("usr_sess_student", "student", "org_sess_real")

    # Start session via API
    start_resp = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={"student_id": "usr_sess_student", "course_id": "crs_chem_101", "initial_concept": "chem_thermo_first_law"},
    )
    assert start_resp.status_code == 201
    sess_id = start_resp.json()["data"]["session_id"]

    # Verify session is directly queryable from PlatformDatabase
    db_sess = db.get_session(sess_id)
    assert db_sess is not None
    assert db_sess.student_id == "usr_sess_student"
    assert db_sess.course_id == "crs_chem_101"

    # Query GET /sessions/{id}
    get_resp = client.get(f"/api/v1/sessions/{sess_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["session_id"] == sess_id
    assert get_resp.json()["data"]["active_concept"] == "chem_thermo_first_law"


# =====================================================================
# 8. Migration Checksum Tampering Detection
# =====================================================================

def test_migration_checksum_tamper_detection(tmp_path):
    db_path = str(tmp_path / "test_tamper_db.db")
    conn = sqlite3.connect(db_path)
    run_all_migrations(conn)

    # Tamper with recorded checksum in schema_migrations
    conn.execute("UPDATE schema_migrations SET checksum = 'tampered_bad_sha256_hash' WHERE version = '001';")
    conn.commit()

    mismatches = verify_migration_checksums(conn)
    assert len(mismatches) == 1
    assert mismatches[0]["version"] == "001"
    assert mismatches[0]["recorded_checksum"] == "tampered_bad_sha256_hash"
    conn.close()


# =====================================================================
# 9. Teacher Demo Roster Prohibited in Production Mode
# =====================================================================

def test_teacher_portal_service_prohibits_demo_roster_in_production(monkeypatch):
    from central_platform.teacher.portal import TeacherPortalService, seed_demo_teacher_roster
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")

    portal = TeacherPortalService()
    seed_demo_teacher_roster(portal)
    assert len(portal._students) == 0, "Demo roster must never be seeded when GAYATRI_PRODUCTION_MODE=true"
