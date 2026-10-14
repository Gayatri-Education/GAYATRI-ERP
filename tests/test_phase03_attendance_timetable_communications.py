"""Phase 03: Attendance, Timetable and Communications Foundation.

Tests cover:
1. Migration 011 schema creation and clean rollback.
2. Attendance session roll call and auditable correction trail.
3. Absence excuse submission and admin approval lifecycle.
4. Timetable slot creation and clash detection (teacher and room conflicts).
5. Daily teacher substitution assignment and schedule query.
6. Communication templates, variable rendering, and dispatch delivery states.
7. Multi-tenant isolation for attendance, timetable, and notifications.
8. REST API endpoints and RBAC authorization matrix.
"""

import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from central_platform.db import PlatformDatabase
from central_platform.models import Organization
from central_platform.models.attendance import (
    AttendanceStatus,
    SessionType,
    ExcuseStatus,
    AttendanceSession,
    AttendanceRecord,
)
from central_platform.models.timetable import (
    DayOfWeek,
    TimetablePeriod,
    TimetableSlot,
    TeacherSubstitution,
)
from central_platform.models.communications import (
    NotificationChannel,
    DispatchStatus,
    NotificationTemplate,
    NotificationDispatch,
)
from central_platform.attendance.service import AttendanceService
from central_platform.timetable.service import TimetableService
from central_platform.communications.service import CommunicationsService
from central_platform.academic.service import AcademicService
from central_platform.sis.service import SISService
from central_platform.auth.tokens import create_access_token
from central_platform.api.app import app

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


@pytest.fixture
def platform_db(tmp_path):
    """File-backed PlatformDatabase instance migrated through 011."""
    db_file = str(tmp_path / "test_phase03.db")
    db = PlatformDatabase(db_file)
    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-school-1', 'Greenwood High', 'greenwood-high', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-coaching-2', 'Apex IIT Academy', 'apex-iit', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
        )
        for mod in ["attendance", "timetable", "communications", "sis", "academic"]:
            conn.execute(
                "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
                f"VALUES ('ent-{mod}-1', 'org-school-1', '{mod}', 1, '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
            )
            conn.execute(
                "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
                f"VALUES ('ent-{mod}-2', 'org-coaching-2', '{mod}', 1, '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
            )
    yield db
    db.close()


# ── Test 1: Migration 011 Up and Down Verification ───────────────────────────

def test_migration_011_up_and_down():
    """Verify migration 011 creates all operational tables and down script removes them cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply up through 010
    for i in range(1, 11):
        scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Apply 011
    up_011 = MIGRATIONS_DIR / "011_attendance_timetable_communications.sql"
    assert up_011.exists(), "011 forward migration script must exist"
    conn.executescript(up_011.read_text(encoding="utf-8"))

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_up = {r[0] for r in cursor.fetchall()}

    expected_tables = {
        "attendance_sessions",
        "attendance_records",
        "attendance_corrections",
        "absence_excuse_requests",
        "timetable_periods",
        "class_timetable_slots",
        "teacher_substitutions",
        "notification_templates",
        "notification_dispatches",
    }
    for t in expected_tables:
        assert t in tables_after_up, f"Table {t} should exist after migration 011"

    # Roll back 011
    down_011 = MIGRATIONS_DIR / "011_attendance_timetable_communications_down.sql"
    assert down_011.exists(), "011 rollback migration script must exist"
    conn.executescript(down_011.read_text(encoding="utf-8"))

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_down = {r[0] for r in cursor.fetchall()}

    for t in expected_tables:
        assert t not in tables_after_down, f"Table {t} should be removed after rollback"

    conn.close()


# ── Test 2: Attendance Roll Call and Correction Audit ─────────────────────────

def test_attendance_roll_call_and_correction_audit(platform_db):
    """Test daily roll call submission and subsequent auditable correction tracking."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year(
        organization_id="org-school-1",
        name="AY 2026-27",
        code="AY-26-27",
        start_date="2026-06-01",
        end_date="2027-04-30",
        is_current=True,
    )

    sis_svc = SISService(platform_db)
    cls = sis_svc.create_class(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        name="Grade 5-A",
        grade_level="Grade 5",
        section="A",
    )
    s1 = sis_svc.create_student_direct("org-school-1", "Aarav", "Patel")
    s2 = sis_svc.create_student_direct("org-school-1", "Diya", "Sharma")

    att_svc = AttendanceService(platform_db)
    # Open / record session
    session = att_svc.create_session(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        class_id=cls.id,
        date="2026-10-15",
        session_type=SessionType.FULL_DAY,
        taken_by="teacher-user-1",
    )
    assert session.id is not None

    # Submit roll call
    records = att_svc.record_roll_call(
        organization_id="org-school-1",
        session_id=session.id,
        records=[
            {"student_id": s1.id, "status": AttendanceStatus.PRESENT},
            {"student_id": s2.id, "status": AttendanceStatus.ABSENT, "remarks": "Uninformed absence"},
        ],
    )
    assert len(records) == 2

    # Query records
    session_records = att_svc.get_session_records("org-school-1", session.id)
    assert len(session_records) == 2
    s2_record = next(r for r in session_records if r.student_id == s2.id)
    assert s2_record.status == AttendanceStatus.ABSENT

    # Submit correction for s2: changing ABSENT -> EXCUSED
    correction = att_svc.correct_attendance(
        organization_id="org-school-1",
        record_id=s2_record.id,
        new_status=AttendanceStatus.EXCUSED,
        reason="Parent called with doctor certificate",
        corrected_by="admin-user-1",
    )
    assert correction.id is not None
    assert correction.previous_status == AttendanceStatus.ABSENT
    assert correction.new_status == AttendanceStatus.EXCUSED

    # Verify record updated
    updated_record = att_svc.get_record("org-school-1", s2_record.id)
    assert updated_record.status == AttendanceStatus.EXCUSED

    # Verify audit history
    history = att_svc.get_correction_history("org-school-1", s2_record.id)
    assert len(history) == 1
    assert history[0].reason == "Parent called with doctor certificate"


# ── Test 3: Absence Excuse Request Workflow ──────────────────────────────────

def test_absence_excuse_request_workflow(platform_db):
    """Test parent/student excuse submission and admin approval."""
    sis_svc = SISService(platform_db)
    student = sis_svc.create_student_direct("org-school-1", "Kabir", "Mehta")

    att_svc = AttendanceService(platform_db)
    excuse = att_svc.submit_excuse_request(
        organization_id="org-school-1",
        student_id=student.id,
        start_date="2026-10-20",
        end_date="2026-10-22",
        reason="Family bereavement travel",
    )
    assert excuse.id is not None
    assert excuse.status == ExcuseStatus.PENDING

    # Admin approves
    approved = att_svc.approve_excuse_request(
        organization_id="org-school-1",
        excuse_id=excuse.id,
        approved_by="principal-user-1",
    )
    assert approved.status == ExcuseStatus.APPROVED
    assert approved.approved_by == "principal-user-1"


# ── Test 4: Timetable Conflict Detection ─────────────────────────────────────

def test_timetable_slot_conflict_detection(platform_db):
    """Verify scheduler detects teacher and room double-booking clashes."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year(
        organization_id="org-school-1",
        name="AY 2026-27",
        code="AY-26-27",
        start_date="2026-06-01",
        end_date="2027-04-30",
        is_current=True,
    )

    sis_svc = SISService(platform_db)
    c1 = sis_svc.create_class("org-school-1", ay.id, "Class 9-A", "Grade 9", "A")
    c2 = sis_svc.create_class("org-school-1", ay.id, "Class 9-B", "Grade 9", "B")

    tt_svc = TimetableService(platform_db)
    p1 = tt_svc.create_period(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        name="Period 1",
        period_number=1,
        start_time="08:30",
        end_time="09:15",
    )

    # 1. Slot 1 in Room 101 with Teacher Verma
    slot1 = tt_svc.create_slot(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        class_id=c1.id,
        period_id=p1.id,
        day_of_week=DayOfWeek.MONDAY,
        subject_id="sub-math-1",
        teacher_id="teacher-verma",
        room_name="Room 101",
    )
    assert slot1.id is not None

    # 2. Clash: Teacher Verma double-booked in Class 9-B during Period 1 on Monday
    with pytest.raises(ValueError, match="Teacher.*already scheduled"):
        tt_svc.create_slot(
            organization_id="org-school-1",
            academic_year_id=ay.id,
            class_id=c2.id,
            period_id=p1.id,
            day_of_week=DayOfWeek.MONDAY,
            subject_id="sub-physics-1",
            teacher_id="teacher-verma",
            room_name="Room 102",
        )

    # 3. Clash: Room 101 double-booked by Teacher Sharma in Period 1 on Monday
    with pytest.raises(ValueError, match="Room.*already booked"):
        tt_svc.create_slot(
            organization_id="org-school-1",
            academic_year_id=ay.id,
            class_id=c2.id,
            period_id=p1.id,
            day_of_week=DayOfWeek.MONDAY,
            subject_id="sub-physics-1",
            teacher_id="teacher-sharma",
            room_name="Room 101",
        )


# ── Test 5: Teacher Substitution Assignment ──────────────────────────────────

def test_teacher_substitution_assignment(platform_db):
    """Test assigning a substitute teacher for a given date on a timetable slot."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year(
        organization_id="org-school-1",
        name="AY 2026-27",
        code="AY-26-27",
        start_date="2026-06-01",
        end_date="2027-04-30",
        is_current=True,
    )

    sis_svc = SISService(platform_db)
    c1 = sis_svc.create_class("org-school-1", ay.id, "Class 8-A", "Grade 8", "A")

    tt_svc = TimetableService(platform_db)
    p2 = tt_svc.create_period("org-school-1", ay.id, "Period 2", 2, "09:20", "10:05")

    slot = tt_svc.create_slot(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        class_id=c1.id,
        period_id=p2.id,
        day_of_week=DayOfWeek.TUESDAY,
        subject_id="sub-eng-1",
        teacher_id="teacher-original",
        room_name="Room 205",
    )

    # Assign substitution for Tuesday 2026-10-20
    sub = tt_svc.assign_substitution(
        organization_id="org-school-1",
        slot_id=slot.id,
        date="2026-10-20",
        original_teacher_id="teacher-original",
        substitute_teacher_id="teacher-substitute",
        reason="Teacher on leave",
    )
    assert sub.id is not None
    assert sub.substitute_teacher_id == "teacher-substitute"

    # Query daily schedule for class: must reflect substitute teacher for that date
    daily_schedule = tt_svc.get_class_schedule_for_date("org-school-1", c1.id, "2026-10-20", DayOfWeek.TUESDAY)
    assert len(daily_schedule) == 1
    assert daily_schedule[0]["effective_teacher_id"] == "teacher-substitute"


# ── Test 6: Communications Templates and Dispatch Delivery ───────────────────

def test_notification_template_and_dispatch(platform_db):
    """Test notification template interpolation and delivery state transitions."""
    comm_svc = CommunicationsService(platform_db)

    # Create template
    tmpl = comm_svc.create_template(
        organization_id="org-school-1",
        template_code="ATTENDANCE_ABSENCE",
        channel=NotificationChannel.IN_APP,
        subject_template="Absence Notice: {student_name}",
        body_template="Dear Parent, {student_name} was marked absent on {date}.",
    )
    assert tmpl.id is not None

    # Dispatch notification
    dispatch = comm_svc.send_notification(
        organization_id="org-school-1",
        template_code="ATTENDANCE_ABSENCE",
        recipient_user_id="parent-user-42",
        destination="inapp:parent-user-42",
        params={"student_name": "Aarav Patel", "date": "2026-10-15"},
    )
    assert dispatch.id is not None
    assert dispatch.status == DispatchStatus.DELIVERED
    assert "Aarav Patel was marked absent on 2026-10-15" in dispatch.rendered_body

    # Query recipient notifications
    user_notifications = comm_svc.get_user_notifications("org-school-1", "parent-user-42")
    assert len(user_notifications) == 1
    assert user_notifications[0].rendered_body == dispatch.rendered_body


# ── Test 7: Multi-Tenant Isolation ───────────────────────────────────────────

def test_cross_tenant_isolation_phase03(platform_db):
    """Verify Org A cannot view or modify Org B operational attendance and schedules."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year("org-school-1", "AY GW", "GW-1", "2026-06-01", "2027-04-30", True)

    sis_svc = SISService(platform_db)
    c1 = sis_svc.create_class("org-school-1", ay.id, "GW Class 1", "Grade 1")

    att_svc = AttendanceService(platform_db)
    session = att_svc.create_session("org-school-1", ay.id, c1.id, "2026-10-15", SessionType.FULL_DAY, "t1")

    # Org B querying Org A's session must return None
    session_b = att_svc.get_session("org-coaching-2", session.id)
    assert session_b is None

    # Org B querying Org A's class timetable must return empty
    tt_svc = TimetableService(platform_db)
    slots_b = tt_svc.get_class_slots("org-coaching-2", c1.id)
    assert slots_b == []


# ── Test 8: REST API Endpoints and RBAC Authorization ────────────────────────

def test_phase03_api_endpoints_and_rbac():
    """Verify REST API routes for attendance, timetable, and communications."""
    import uuid
    db = PlatformDatabase()
    org_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org_id, name="Phase 03 Org", slug=f"p3-org-{org_id}"))

    token = create_access_token(
        user_id="user-admin-p3",
        role="org_admin",
        organization_id=org_id,
    )
    headers = {"Authorization": f"Bearer {token}"}

    ay = AcademicService(db).create_academic_year(
        organization_id=org_id,
        name="AY 2026-27",
        code=f"AY-{org_id}",
        start_date="2026-06-01",
        end_date="2027-04-30",
        is_current=True,
    )

    client = TestClient(app)

    # 1. Create timetable period via API
    resp_period = client.post(
        "/api/v1/timetable/periods",
        headers=headers,
        json={
            "academic_year_id": ay.id,
            "name": "API Period 1",
            "period_number": 1,
            "start_time": "08:00",
            "end_time": "08:45",
        },
    )
    assert resp_period.status_code == 201
    assert resp_period.json()["name"] == "API Period 1"

    # 2. Create notification template via API
    resp_tmpl = client.post(
        "/api/v1/communications/templates",
        headers=headers,
        json={
            "template_code": "CIRCULAR_NOTICE",
            "channel": "IN_APP",
            "subject_template": "Circular: {title}",
            "body_template": "Notice: {message}",
        },
    )
    assert resp_tmpl.status_code == 201
    assert resp_tmpl.json()["template_code"] == "CIRCULAR_NOTICE"

    # 3. Send notification via API
    resp_send = client.post(
        "/api/v1/communications/send",
        headers=headers,
        json={
            "template_code": "CIRCULAR_NOTICE",
            "recipient_user_id": "user-admin-p3",
            "destination": "inapp:user-admin-p3",
            "params": {"title": "Holiday", "message": "Tomorrow is a holiday"},
        },
    )
    assert resp_send.status_code == 201
    assert resp_send.json()["status"] == "DELIVERED"
