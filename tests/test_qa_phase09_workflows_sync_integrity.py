"""Phase 09: Workflows, Attendance, Instructions, Notifications, and Sync Integrity Suite.

Verifies:
- ERP-015: Legacy endpoints (/api/sync/events, /api/teacher/instruction) persist to PlatformDatabase.
- Attendance session creation and roll call blocked for student role (HTTP 403).
- Attendance excuse submission enforces student self-scoping (HTTP 403 IDOR block).
- Teacher role authorized for attendance sessions and roll call.
- Authoritative sync idempotency (replayed batches do not duplicate database records).
- Device binding and query IDOR enforcement.
- Legacy teacher instruction survives in-memory cache clearing / simulated restart.
- Cross-tenant teacher instruction creation rejected with HTTP 403.
- Notifications query enforces recipient isolation for students (HTTP 403).
"""
from __future__ import annotations

import os
import uuid
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import create_app
from central_platform.auth.dependencies import get_db
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Course,
    CourseStatus,
    CourseVersion,
    CourseVisibility,
    Enrollment,
    Organization,
    User,
    UserRole,
)


@pytest.fixture
def workflow_env(tmp_path):
    """Provides isolated database, test client, and role-based auth tokens."""
    db_file = tmp_path / "workflow_test.db"
    db = PlatformDatabase(str(db_file))

    # Organizations
    org_alpha = Organization(id="org-wf-alpha", name="Alpha High", slug="alpha-high")
    org_beta = Organization(id="org-wf-beta", name="Beta Academy", slug="beta-acad")
    db.create_organization(org_alpha)
    db.create_organization(org_beta)

    # Users
    alice = User(
        id="stu-wf-alice",
        email="alice@alpha.edu",
        full_name="Alice Student",
        role=UserRole.STUDENT,
        organization_id="org-wf-alpha",
    )
    bob = User(
        id="stu-wf-bob",
        email="bob@alpha.edu",
        full_name="Bob Student",
        role=UserRole.STUDENT,
        organization_id="org-wf-alpha",
    )
    carol = User(
        id="stu-wf-carol",
        email="carol@beta.edu",
        full_name="Carol Student",
        role=UserRole.STUDENT,
        organization_id="org-wf-beta",
    )
    teacher_alpha = User(
        id="tch-wf-smith",
        email="smith@alpha.edu",
        full_name="Mr. Smith",
        role=UserRole.TEACHER,
        organization_id="org-wf-alpha",
    )
    admin_alpha = User(
        id="adm-wf-jones",
        email="jones@alpha.edu",
        full_name="Principal Jones",
        role=UserRole.ORG_ADMIN,
        organization_id="org-wf-alpha",
    )
    db.create_user(alice)
    db.create_user(bob)
    db.create_user(carol)
    db.create_user(teacher_alpha)
    db.create_user(admin_alpha)

    # Seed Academic and SIS tables for Attendance foreign keys
    with db._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO academic_years (id, organization_id, name, code, start_date, end_date, is_current, created_at, updated_at)
            VALUES ('ay-2026', 'org-wf-alpha', 'AY 2026-27', 'AY-26', '2026-06-01', '2027-04-30', 1, '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO student_classes (id, organization_id, academic_year_id, name, grade_level, section, capacity, created_at, updated_at)
            VALUES ('cls-chem-101', 'org-wf-alpha', 'ay-2026', 'Chem 101 Class', '11', 'A', 40, '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO persons (id, organization_id, first_name, last_name, email, created_at, updated_at)
            VALUES ('per-wf-alice', 'org-wf-alpha', 'Alice', 'Student', 'alice@alpha.edu', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO student_profiles (id, person_id, organization_id, admission_number, academic_status, created_at, updated_at)
            VALUES ('stu-wf-alice', 'per-wf-alice', 'org-wf-alpha', 'ADM-ALICE', 'active', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO persons (id, organization_id, first_name, last_name, email, created_at, updated_at)
            VALUES ('per-wf-bob', 'org-wf-alpha', 'Bob', 'Student', 'bob@alpha.edu', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO student_profiles (id, person_id, organization_id, admission_number, academic_status, created_at, updated_at)
            VALUES ('stu-wf-bob', 'per-wf-bob', 'org-wf-alpha', 'ADM-BOB', 'active', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');
            """
        )

    # Courses & Enrollments
    course = Course(
        id="crs-wf-chem",
        organization_id="org-wf-alpha",
        code="CHEM-101",
        title="Chemistry Basics",
        visibility=CourseVisibility.PUBLIC,
    )
    db.create_course(course)

    version = CourseVersion(
        id="ver-wf-chem-1",
        course_id="crs-wf-chem",
        version_number="1.0.0",
        status=CourseStatus.PUBLISHED,
        created_by="system",
    )
    db.create_course_version(version)

    db.create_enrollment(
        Enrollment(
            id="enr-wf-alice",
            student_id="stu-wf-alice",
            course_id="crs-wf-chem",
            is_active=True,
        )
    )

    app = create_app()
    import central_platform.auth.dependencies as auth_deps
    old_instance = auth_deps._DB_INSTANCE
    old_env = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = str(db_file)
    auth_deps._DB_INSTANCE = db
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)

    tokens = {
        "alice": create_access_token(user_id="stu-wf-alice", role="STUDENT", organization_id="org-wf-alpha"),
        "bob": create_access_token(user_id="stu-wf-bob", role="STUDENT", organization_id="org-wf-alpha"),
        "carol": create_access_token(user_id="stu-wf-carol", role="STUDENT", organization_id="org-wf-beta"),
        "teacher": create_access_token(user_id="tch-wf-smith", role="TEACHER", organization_id="org-wf-alpha"),
        "admin": create_access_token(user_id="adm-wf-jones", role="ORG_ADMIN", organization_id="org-wf-alpha"),
    }

    yield {
        "db": db,
        "client": client,
        "tokens": tokens,
        "course_id": "crs-wf-chem",
    }

    auth_deps._DB_INSTANCE = old_instance
    if old_env is not None:
        os.environ["GAYATRI_DB_PATH"] = old_env
    else:
        os.environ.pop("GAYATRI_DB_PATH", None)


# ── 1. Attendance Role & IDOR Guards ──────────────────────────────────────────

def test_student_blocked_from_creating_attendance_session(workflow_env):
    """Students must not be permitted to create attendance sessions (HTTP 403)."""
    client = workflow_env["client"]
    token = workflow_env["tokens"]["alice"]

    resp = client.post(
        "/api/v1/attendance/sessions",
        json={
            "academic_year_id": "ay-2026",
            "class_id": "cls-chem-101",
            "date": "2026-10-15",
            "session_type": "FULL_DAY",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, f"Expected 403 for student creating session, got {resp.status_code}: {resp.text}"


def test_student_blocked_from_submitting_roll_call(workflow_env):
    """Students must not be permitted to submit roll call records (HTTP 403)."""
    client = workflow_env["client"]
    token = workflow_env["tokens"]["alice"]

    resp = client.post(
        "/api/v1/attendance/sessions/sess-123/records",
        json={"records": [{"student_id": "stu-wf-alice", "status": "present"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, f"Expected 403 for student roll call, got {resp.status_code}: {resp.text}"


def test_teacher_authorized_for_attendance_workflows(workflow_env):
    """Teachers must be authorized to create sessions and record roll calls."""
    client = workflow_env["client"]
    token = workflow_env["tokens"]["teacher"]

    # 1. Create session
    resp = client.post(
        "/api/v1/attendance/sessions",
        json={
            "academic_year_id": "ay-2026",
            "class_id": "cls-chem-101",
            "date": "2026-10-15",
            "session_type": "FULL_DAY",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, f"Expected 201 for teacher creating session, got {resp.status_code}: {resp.text}"
    sess_id = resp.json()["id"]

    # 2. Record roll call
    resp_rc = client.post(
        f"/api/v1/attendance/sessions/{sess_id}/records",
        json={"records": [{"student_id": "stu-wf-alice", "status": "PRESENT"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_rc.status_code == 200, f"Expected 200 for teacher roll call, got {resp_rc.status_code}: {resp_rc.text}"
    records = resp_rc.json()
    assert len(records) == 1
    assert records[0]["student_id"] == "stu-wf-alice"


def test_student_excuse_submission_idor_protection(workflow_env):
    """Students can only submit attendance excuses for their own account; peer submissions return HTTP 403."""
    client = workflow_env["client"]
    token = workflow_env["tokens"]["alice"]

    # Attempting to submit for Bob
    resp_idor = client.post(
        "/api/v1/attendance/excuses",
        json={
            "student_id": "stu-wf-bob",
            "start_date": "2026-10-16",
            "end_date": "2026-10-17",
            "reason": "Medical leave on behalf of peer",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_idor.status_code == 403, f"Expected 403 for IDOR excuse submission, got {resp_idor.status_code}: {resp_idor.text}"

    # Submitting for herself
    resp_ok = client.post(
        "/api/v1/attendance/excuses",
        json={
            "student_id": "stu-wf-alice",
            "start_date": "2026-10-16",
            "end_date": "2026-10-17",
            "reason": "Dentist appointment",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_ok.status_code == 201, f"Expected 201 for self excuse submission, got {resp_ok.status_code}: {resp_ok.text}"


# ── 2. ERP-015: Legacy Sync Persistence & Durability ─────────────────────────

def test_erp015_legacy_sync_events_persists_to_database(workflow_env):
    """Legacy POST /api/sync/events must persist learning events and sync operations to PlatformDatabase."""
    client = workflow_env["client"]
    db = workflow_env["db"]
    token = workflow_env["tokens"]["alice"]

    ev_id = f"ev-legacy-{uuid.uuid4().hex[:8]}"
    payload = {
        "student_id": "stu-wf-alice",
        "course_id": "crs-wf-chem",
        "operation_id": f"op-legacy-{uuid.uuid4().hex[:6]}",
        "events": [
            {
                "event_id": ev_id,
                "student_id": "stu-wf-alice",
                "course_id": "crs-wf-chem",
                "event_type": "turn_completed",
                "concept_id": "c-matter-01",
                "sequence_num": 1,
                "timestamp": "2026-10-15T10:00:00Z",
                "metrics": {"duration_ms": 1200},
            }
        ],
    }

    resp = client.post(
        "/api/sync/events",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["ok"] is True
    assert data["synced_count"] == 1

    # Invariant: events must be durably stored in the database, not just in-memory
    op_record = db.get_sync_operation(payload["operation_id"])
    assert op_record is not None, "Sync operation record was not persisted to PlatformDatabase!"
    assert ev_id in op_record.acknowledged_ids


def test_canonical_sync_idempotency_and_replay_protection(workflow_env):
    """Replaying an identical sync batch must be idempotent (zero duplicate events)."""
    client = workflow_env["client"]
    token = workflow_env["tokens"]["alice"]

    op_id = f"op-canon-{uuid.uuid4().hex[:6]}"
    ev_id = f"ev-canon-{uuid.uuid4().hex[:8]}"
    batch = {
        "student_id": "stu-wf-alice",
        "course_id": "crs-wf-chem",
        "operation_id": op_id,
        "events": [
            {
                "event_id": ev_id,
                "student_id": "stu-wf-alice",
                "course_id": "crs-wf-chem",
                "event_type": "turn_completed",
                "concept_id": "c-matter-01",
                "sequence_num": 1,
                "timestamp": "2026-10-15T11:00:00Z",
            }
        ],
    }

    # First submission
    resp1 = client.post("/api/v1/sync/events", json=batch, headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 200
    res1_data = resp1.json()["data"]
    assert res1_data["synced_count"] == 1
    assert res1_data["is_replay"] is False

    # Second submission (replay of identical operation)
    resp2 = client.post("/api/v1/sync/events", json=batch, headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    res2_data = resp2.json()["data"]
    assert res2_data["is_replay"] is True
    assert res2_data["synced_count"] == 1


def test_sync_device_listing_idor_protection(workflow_env):
    """Students cannot inspect devices bound to other students (HTTP 403)."""
    client = workflow_env["client"]
    token_alice = workflow_env["tokens"]["alice"]

    resp = client.get(
        "/api/v1/sync/devices?student_id=stu-wf-bob",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert resp.status_code == 403, f"Expected 403 for IDOR device inspection, got {resp.status_code}: {resp.text}"

    resp_own = client.get(
        "/api/v1/sync/devices?student_id=stu-wf-alice",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert resp_own.status_code == 200, f"Expected 200 for own device inspection, got {resp_own.status_code}: {resp_own.text}"


# ── 3. ERP-015: Teacher Instructions Durability & Tenant Isolation ───────────

def test_erp015_legacy_teacher_instruction_persists_to_database(workflow_env):
    """Legacy POST /api/teacher/instruction must persist to PlatformDatabase and survive restart."""
    client = workflow_env["client"]
    db = workflow_env["db"]
    token = workflow_env["tokens"]["teacher"]

    inst_text = "Emphasize molecular structures when teaching covalent bonds."
    inst_id = f"inst-leg-{uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/teacher/instruction",
        json={
            "instruction_id": inst_id,
            "course_id": "crs-wf-chem",
            "instruction": inst_text,
            "priority": 3,
            "concept_scope": "c-matter-01",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    saved_id = resp.json()["instruction_id"]

    # Invariant: Persisted in PlatformDatabase
    db_rec = db.get_teacher_instruction(saved_id)
    assert db_rec is not None, "Teacher instruction was not persisted in PlatformDatabase!"
    assert db_rec.instruction_text == inst_text

    # Clear volatile singleton in app.py to simulate process restart
    import central_platform.api.app as app_mod
    app_mod._instruction_engine._instructions.clear()

    # Query GET /api/teacher/instructions after simulated restart
    list_resp = client.get(
        "/api/teacher/instructions?course_id=crs-wf-chem",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    instructions = list_resp.json()["instructions"]
    found = any(i["instruction_id"] == saved_id for i in instructions)
    assert found, f"Instruction {saved_id} was lost after clearing in-memory cache!"


def test_cross_tenant_teacher_instruction_blocked(workflow_env):
    """Teacher cannot create instructions for a foreign organization (HTTP 403)."""
    client = workflow_env["client"]
    token = workflow_env["tokens"]["teacher"]

    resp = client.post(
        "/api/v1/instructions",
        json={
            "organization_id": "org-wf-beta",  # Teacher is in org-wf-alpha
            "course_id": "crs-wf-chem",
            "instruction": "Cross-organization directive attempt.",
            "priority": 2,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403, f"Expected 403 for cross-tenant instruction, got {resp.status_code}: {resp.text}"


# ── 4. Notifications Recipient Privacy ───────────────────────────────────────

def test_notifications_recipient_isolation(workflow_env):
    """Students cannot query notifications directed to other recipients (HTTP 403)."""
    client = workflow_env["client"]
    token_alice = workflow_env["tokens"]["alice"]

    resp = client.get(
        "/api/v1/notifications?recipient_id=stu-wf-bob",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert resp.status_code == 403, f"Expected 403 for inspecting peer notifications, got {resp.status_code}: {resp.text}"

    resp_own = client.get(
        "/api/v1/notifications?recipient_id=stu-wf-alice",
        headers={"Authorization": f"Bearer {token_alice}"},
    )
    assert resp_own.status_code == 200, f"Expected 200 for own notifications, got {resp_own.status_code}: {resp_own.text}"
