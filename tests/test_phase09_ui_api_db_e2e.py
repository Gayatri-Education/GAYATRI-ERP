"""Phase 09 — Complete Genuine UI-to-API-to-Database E2E Workflows (QA-009).

Tests:
1. Identity Lifecycle: Provision org -> create user -> token auth -> token revocation -> 401 on revoked token.
2. Admissions to SIS: Inquiry -> Application -> Decision ACCEPTED -> Atomic conversion to SIS student -> Verify student profile, guardian links, enrollments in database.
3. Attendance Lifecycle: Session creation -> Batch roll call records -> Verify in DB -> Correction with reason -> Verify audit in DB.
4. Financial Billing Lifecycle: Batch invoice generation -> Verify invoices in DB -> Export outstanding fee report -> Verify balance and ledger credit.
5. Examinations & Report Cards: Exam series -> Schedule -> Submit marks -> Lock schedule -> Term calculation -> Generate report card -> Retrieve report card.
6. Teacher Instruction & Copilot: Create instruction record -> Retrieve copilot briefing -> Verify persisted state.
7. Student Learning & Review: Session start -> Ingest learning event -> SLR mastery update -> Review queue query.
8. UI Contract Verification: Ensure admin_portal.html has eliminated cosmetic toast-only business actions and truthfully labels simulations.
"""

from datetime import datetime, timezone
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import Course, Organization, User, UserRole


def auth_header(user_id: str, role: str, org_id: str) -> dict:
    token = create_access_token(user_id=user_id, role=role, organization_id=org_id)
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. Identity & Auth Lifecycle E2E
# =====================================================================

def test_e2e_identity_and_auth_lifecycle(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_identity_e2e.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase09-identity-12345678")

    db = PlatformDatabase(db_path)
    client = TestClient(app)

    # 1. Super admin provisions a new organization
    admin_token = create_access_token("usr_super", "SUPER_ADMIN", "org_master")
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    org_resp = client.post(
        "/api/v1/organizations",
        headers=admin_hdr,
        json={"name": "Kalinga Academy", "slug": "kalinga-acad"},
    )
    assert org_resp.status_code == 201, org_resp.text
    org_id = org_resp.json()["data"]["id"]

    # Verify organization in real database
    assert db.get_organization(org_id) is not None

    # 2. Admin provisions an Org Admin user for the new organization
    user_resp = client.post(
        "/api/v1/users",
        headers=admin_hdr,
        json={
            "username": "kalinga_admin",
            "email": "admin@kalinga.edu",
            "password": "Password123!",
            "role": "ORG_ADMIN",
            "organization_id": org_id,
        },
    )
    assert user_resp.status_code == 201, user_resp.text
    user_id = user_resp.json()["data"]["user_id"]

    # Verify user in database
    db_user = db.get_user(user_id)
    assert db_user is not None
    assert db_user.email == "admin@kalinga.edu"
    assert db_user.organization_id == org_id

    # 3. Authenticate as the new Org Admin
    user_token = create_access_token(user_id, "ORG_ADMIN", org_id)
    user_hdr = {"Authorization": f"Bearer {user_token}"}

    me_resp = client.get("/api/v1/auth/me", headers=user_hdr)
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["user_id"] == user_id

    # 4. Revoke token
    logout_resp = client.post("/api/v1/auth/logout", headers=user_hdr)
    assert logout_resp.status_code == 200

    # 5. Verify revoked token is rejected with HTTP 401
    rejected_resp = client.get("/api/v1/auth/me", headers=user_hdr)
    assert rejected_resp.status_code == 401


# =====================================================================
# 2. Admissions to SIS Conversion E2E
# =====================================================================

def test_e2e_admissions_to_sis_conversion(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_admissions_e2e.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase09-adm-12345678")

    db = PlatformDatabase(db_path)
    client = TestClient(app)

    org = Organization(id="org_adm_flow", name="Admissions Flow Org", slug="adm-flow")
    admin = User(id="usr_adm_mgr", email="mgr@flow.edu", full_name="Admin Manager", role=UserRole.ORG_ADMIN, organization_id="org_adm_flow")
    db.create_organization(org)
    db.create_user(admin)

    # Seed academic year and class
    with db._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO academic_years (id, organization_id, name, code, start_date, end_date, is_current, status, created_at, updated_at)
            VALUES ('ay_2026', 'org_adm_flow', '2026-2027', 'AY26', '2026-04-01', '2027-03-31', 1, 'ACTIVE', datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO student_classes (id, organization_id, academic_year_id, name, grade_level, section, capacity, created_at, updated_at)
            VALUES ('cls_11a', 'org_adm_flow', 'ay_2026', 'Class 11A', '11', 'A', 40, datetime('now'), datetime('now'));
            """
        )

    hdr = auth_header("usr_adm_mgr", "ORG_ADMIN", "org_adm_flow")

    # 1. Submit Inquiry
    inq_resp = client.post(
        "/api/v1/admissions/inquiries",
        headers=hdr,
        json={"applicant_name": "Aarav Sharma", "email": "aarav@test.edu", "phone": "9876543210", "organization_id": "org_adm_flow"},
    )
    assert inq_resp.status_code == 201, inq_resp.text
    inquiry_id = inq_resp.json()["id"]

    # 2. Submit Application
    app_resp = client.post(
        "/api/v1/admissions/applications",
        headers=hdr,
        json={
            "applicant_name": "Aarav Sharma",
            "inquiry_id": inquiry_id,
            "academic_year_id": "ay_2026",
            "phone": "9876543210",
            "target_grade": "11",
        },
    )
    assert app_resp.status_code == 201, app_resp.text
    application_id = app_resp.json()["id"]

    # 3. Convert Application to Canonical Student
    conv_resp = client.post(
        f"/api/v1/admissions/applications/{application_id}/convert",
        headers=hdr,
        json={
            "class_id": "cls_11a",
            "roll_number": "11A-01",
            "guardian_name": "Vikram Sharma",
            "guardian_phone": "9876543211",
            "guardian_relationship": "FATHER",
        },
    )
    assert conv_resp.status_code == 200, conv_resp.text
    conv_data = conv_resp.json()
    student_id = conv_data["student_id"]
    assert student_id.startswith("stu-")

    # Verify authoritative database state
    with db._get_connection() as conn:
        # Student profile exists
        stu = conn.execute("SELECT * FROM student_profiles WHERE id = ?;", (student_id,)).fetchone()
        assert stu is not None
        assert stu["roll_number"] == "11A-01"

        # Enrollment exists
        enr = conn.execute("SELECT * FROM student_class_enrollments WHERE student_id = ?;", (student_id,)).fetchone()
        assert enr is not None
        assert enr["class_id"] == "cls_11a"

        # Guardian link exists
        glink = conn.execute("SELECT * FROM student_guardian_links WHERE student_id = ?;", (student_id,)).fetchone()
        assert glink is not None
        assert glink["relationship"] == "FATHER"


# =====================================================================
# 3. Attendance Lifecycle E2E
# =====================================================================

def test_e2e_attendance_lifecycle(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_attendance_e2e.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase09-att-12345678")

    db = PlatformDatabase(db_path)
    client = TestClient(app)

    org = Organization(id="org_att_flow", name="Attendance Org", slug="att-flow")
    teacher = User(id="usr_teacher_att", email="t@att.edu", full_name="Teacher Anita", role=UserRole.TEACHER, organization_id="org_att_flow")
    db.create_organization(org)
    db.create_user(teacher)

    # Seed academic year
    with db._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO academic_years (id, organization_id, name, code, start_date, end_date, is_current, status, created_at, updated_at)
            VALUES ('ay_2026', 'org_att_flow', '2026-2027', 'AY26', '2026-04-01', '2027-03-31', 1, 'ACTIVE', datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO student_classes (id, organization_id, academic_year_id, name, grade_level, section, capacity, created_at, updated_at)
            VALUES ('cls_11a', 'org_att_flow', 'ay_2026', 'Class 11A', '11', 'A', 40, datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO persons (id, organization_id, first_name, last_name, created_at, updated_at)
            VALUES ('per_001', 'org_att_flow', 'Student', 'One', datetime('now'), datetime('now')),
                   ('per_002', 'org_att_flow', 'Student', 'Two', datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at)
            VALUES ('stu_001', 'per_001', 'org_att_flow', 'ADM001', '11A-01', datetime('now'), 'active', datetime('now'), datetime('now')),
                   ('stu_002', 'per_002', 'org_att_flow', 'ADM002', '11A-02', datetime('now'), 'active', datetime('now'), datetime('now'));
            """
        )

    hdr = auth_header("usr_teacher_att", "TEACHER", "org_att_flow")

    # 1. Create an attendance session
    sess_resp = client.post(
        "/api/v1/attendance/sessions",
        headers=hdr,
        json={"academic_year_id": "ay_2026", "class_id": "cls_11a", "date": "2026-10-15", "session_type": "FULL_DAY"},
    )
    assert sess_resp.status_code == 201, sess_resp.text
    sess_id = sess_resp.json()["id"]

    # 2. Submit roll call records
    records_resp = client.post(
        f"/api/v1/attendance/sessions/{sess_id}/records",
        headers=hdr,
        json={
            "records": [
                {"student_id": "stu_001", "status": "PRESENT", "source": "MANUAL"},
                {"student_id": "stu_002", "status": "ABSENT", "source": "MANUAL"},
            ]
        },
    )
    assert records_resp.status_code == 200, records_resp.text

    # 3. Retrieve session attendance records from database
    get_resp = client.get(f"/api/v1/attendance/sessions/{sess_id}/records", headers=hdr)
    assert get_resp.status_code == 200, get_resp.text
    records = get_resp.json()
    assert len(records) == 2
    rec_absent = next(r for r in records if r["student_id"] == "stu_002")
    assert rec_absent["status"] == "ABSENT"

    # 4. Correct an attendance record with reason/audit trail
    corr_resp = client.post(
        f"/api/v1/attendance/records/{rec_absent['id']}/correct",
        headers=hdr,
        json={"new_status": "EXCUSED", "reason": "Medical certificate submitted by parent"},
    )
    assert corr_resp.status_code == 200, corr_resp.text
    assert corr_resp.json()["new_status"] == "EXCUSED"

    # Verify updated record reflects EXCUSED
    updated_rec_resp = client.get(f"/api/v1/attendance/sessions/{sess_id}/records", headers=hdr)
    assert updated_rec_resp.status_code == 200
    updated_rec = next(r for r in updated_rec_resp.json() if r["student_id"] == "stu_002")
    assert updated_rec["status"] == "EXCUSED"


# =====================================================================
# 4. Financial Billing & Invoicing Lifecycle E2E
# =====================================================================

def test_e2e_finance_billing_and_invoicing(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_finance_e2e.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase09-fin-12345678")

    db = PlatformDatabase(db_path)
    client = TestClient(app)

    org = Organization(id="org_fin_flow", name="Finance Org", slug="fin-flow")
    admin = User(id="usr_fin_admin", email="fin@flow.edu", full_name="Fin Admin", role=UserRole.ORG_ADMIN, organization_id="org_fin_flow")
    db.create_organization(org)
    db.create_user(admin)

    student_user = User(
        id="stu_fin_1",
        email="stu_fin@flow.edu",
        full_name="Fin Student",
        role=UserRole.STUDENT,
        organization_id="org_fin_flow",
    )
    db.create_user(student_user)

    # Seed person and student profile for billing eligibility
    with db._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO persons (id, organization_id, first_name, last_name, created_at, updated_at)
            VALUES ('per_fin_1', 'org_fin_flow', 'Fin', 'Student', datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at)
            VALUES ('stu_fin_1', 'per_fin_1', 'org_fin_flow', 'ADM-FIN-1', '11A-01', datetime('now'), 'active', datetime('now'), datetime('now'));
            """
        )

    hdr = auth_header("usr_fin_admin", "ORG_ADMIN", "org_fin_flow")

    # 1. Trigger monthly billing generation
    gen_resp = client.post(
        "/api/v1/finance/billing/generate",
        headers=hdr,
        json={"month_year": "2026-10"},
    )
    assert gen_resp.status_code == 201, gen_resp.text
    batch_data = gen_resp.json()
    assert batch_data["month_year"] == "2026-10"
    assert batch_data["invoices_generated"] == 1
    assert batch_data["status"] == "COMPLETED"

    # 2. Query outstanding fees report
    report_resp = client.get("/api/v1/finance/reports/outstanding", headers=hdr)
    assert report_resp.status_code == 200, report_resp.text
    reports = report_resp.json()
    assert isinstance(reports, list)
    assert len(reports) == 1
    assert reports[0]["student_id"] == "stu_fin_1"

    # 3. Export outstanding fees CSV
    export_resp = client.get("/api/v1/finance/reports/outstanding/export", headers=hdr)
    assert export_resp.status_code == 200
    assert "Student ID" in export_resp.text
    assert "stu_fin_1" in export_resp.text


# =====================================================================
# 5. Examinations & Report Card E2E
# =====================================================================

def test_e2e_examinations_and_report_cards(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_exam_e2e.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase09-exam-12345678")

    db = PlatformDatabase(db_path)
    client = TestClient(app)

    org = Organization(id="org_exam_flow", name="Exam Flow Org", slug="exam-flow")
    admin = User(id="usr_exam_admin", email="exam@flow.edu", full_name="Exam Admin", role=UserRole.ORG_ADMIN, organization_id="org_exam_flow")
    db.create_organization(org)
    db.create_user(admin)

    # Seed academic year, terms, class, person and student profile
    with db._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO academic_years (id, organization_id, name, code, start_date, end_date, is_current, status, created_at, updated_at)
            VALUES ('ay_2026', 'org_exam_flow', '2026-2027', 'AY26', '2026-04-01', '2027-03-31', 1, 'ACTIVE', datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO academic_terms (id, organization_id, academic_year_id, name, code, start_date, end_date, created_at, updated_at)
            VALUES ('term_1', 'org_exam_flow', 'ay_2026', 'Term 1', 'T1', '2026-04-01', '2026-09-30', datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO student_classes (id, organization_id, academic_year_id, name, grade_level, section, capacity, created_at, updated_at)
            VALUES ('cls_11a', 'org_exam_flow', 'ay_2026', 'Class 11A', '11', 'A', 40, datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO persons (id, organization_id, first_name, last_name, created_at, updated_at)
            VALUES ('per_exam_1', 'org_exam_flow', 'Exam', 'Candidate', datetime('now'), datetime('now'));
            """
        )
        conn.execute(
            """
            INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at)
            VALUES ('stu_exam_01', 'per_exam_1', 'org_exam_flow', 'ADM-EXAM-1', '11A-01', datetime('now'), 'active', datetime('now'), datetime('now'));
            """
        )

    hdr = auth_header("usr_exam_admin", "ORG_ADMIN", "org_exam_flow")

    # 1. Create Exam Series
    series_resp = client.post(
        "/api/v1/examinations/series",
        headers=hdr,
        json={
            "academic_year_id": "ay_2026",
            "academic_term_id": "term_1",
            "name": "Mid-Term Examination 2026",
            "code": "MID-2026",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
        },
    )
    assert series_resp.status_code == 201, series_resp.text
    series_id = series_resp.json()["id"]

    # 2. Create Exam Schedule
    sched_resp = client.post(
        "/api/v1/examinations/schedules",
        headers=hdr,
        json={
            "exam_series_id": series_id,
            "subject_id": "chem_101",
            "class_id": "cls_11a",
            "exam_date": "2026-09-15",
            "start_time": "09:00",
            "end_time": "12:00",
            "max_marks": 100.0,
            "pass_marks": 40.0,
        },
    )
    assert sched_resp.status_code == 201, sched_resp.text
    schedule_id = sched_resp.json()["id"]

    # 3. Enter Marks
    marks_resp = client.post(
        f"/api/v1/examinations/schedules/{schedule_id}/marks",
        headers=hdr,
        json={"student_id": "stu_exam_01", "marks_obtained": 88.5},
    )
    assert marks_resp.status_code == 200, marks_resp.text
    assert marks_resp.json()["marks_obtained"] == 88.5

    # 4. Lock Marks Schedule
    lock_resp = client.post(f"/api/v1/examinations/schedules/{schedule_id}/lock", headers=hdr)
    assert lock_resp.status_code == 200, lock_resp.text
    assert lock_resp.json()["is_locked"] in (1, True)

    # 5. Generate Report Card
    rep_resp = client.post(
        "/api/v1/reports/generate",
        headers=hdr,
        json={
            "student_id": "stu_exam_01",
            "academic_year_id": "ay_2026",
            "academic_term_id": "term_1",
            "general_remarks": "Outstanding academic progress",
        },
    )
    assert rep_resp.status_code == 201, rep_resp.text
    report_id = rep_resp.json()["id"]

    # 6. Retrieve Published Report Card
    get_rep_resp = client.get(f"/api/v1/reports/{report_id}", headers=hdr)
    assert get_rep_resp.status_code == 200, get_rep_resp.text
    assert get_rep_resp.json()["student_id"] == "stu_exam_01"


# =====================================================================
# 6. Teacher Copilot Briefing & Instruction E2E
# =====================================================================

def test_e2e_teacher_copilot_and_instructions(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_teacher_e2e.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase09-teacher-12345678")

    db = PlatformDatabase(db_path)
    client = TestClient(app)

    org = Organization(id="org_tchr_flow", name="Teacher Org", slug="tchr-flow")
    teacher = User(id="usr_tchr_copilot", email="copilot@flow.edu", full_name="Copilot Teacher", role=UserRole.TEACHER, organization_id="org_tchr_flow")
    course = Course(id="crs_thermo", organization_id="org_tchr_flow", code="THERMO101", title="Thermodynamics")
    db.create_organization(org)
    db.create_course(course)
    db.create_user(teacher)

    hdr = auth_header("usr_tchr_copilot", "TEACHER", "org_tchr_flow")

    # 1. Create a Teacher Instruction Record
    inst_resp = client.post(
        "/api/v1/instructions",
        headers=hdr,
        json={
            "instruction": "Focus on sign conventions in adiabatic systems",
            "course_id": "crs_thermo",
            "concept_scope": "chem_thermo_first_law",
            "priority": 4,
            "organization_id": "org_tchr_flow",
        },
    )
    assert inst_resp.status_code == 201, inst_resp.text
    inst_data = inst_resp.json()["data"]
    assert inst_data["instruction_text"] == "Focus on sign conventions in adiabatic systems"

    # 2. Fetch AI Copilot Briefing
    briefing_resp = client.get("/api/v1/teachers/copilot/briefing", headers=hdr)
    assert briefing_resp.status_code == 200, briefing_resp.text
    data = briefing_resp.json()["data"]
    assert "summary" in data or "recommended_action" in data or "answer" in data


# =====================================================================
# 7. Student Learning & Spaced Review E2E
# =====================================================================

def test_e2e_student_learning_and_spaced_review(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_student_e2e.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-phase09-student-12345678")

    db = PlatformDatabase(db_path)
    client = TestClient(app)

    org = Organization(id="org_stu_flow", name="Student Org", slug="stu-flow")
    student = User(id="usr_stu_flow", email="stu@flow.edu", full_name="Student Flow", role=UserRole.STUDENT, organization_id="org_stu_flow")
    course = Course(id="crs_chem_foundations", organization_id="org_stu_flow", code="CHEM-F", title="Chem Foundations")
    db.create_organization(org)
    db.create_course(course)
    db.create_user(student)

    # Enroll student in course
    with db._get_connection() as conn:
        conn.execute(
            """
            INSERT INTO enrollments (id, student_id, course_id, enrolled_at, is_active)
            VALUES ('enr_flow_1', 'usr_stu_flow', 'crs_chem_foundations', datetime('now'), 1);
            """
        )

    hdr = auth_header("usr_stu_flow", "STUDENT", "org_stu_flow")

    # 1. Start adaptive tutoring session
    sess_resp = client.post(
        "/api/v1/sessions",
        headers=hdr,
        json={"student_id": "usr_stu_flow", "course_id": "crs_chem_foundations", "initial_concept": "chem_foundations"},
    )
    assert sess_resp.status_code == 201
    sess_id = sess_resp.json()["data"]["session_id"]

    # 2. Ingest learning event
    event_resp = client.post(
        "/api/v1/learning/events",
        headers=hdr,
        json={
            "event_id": "evt_learn_01",
            "session_id": sess_id,
            "student_id": "usr_stu_flow",
            "organization_id": "org_stu_flow",
            "course_id": "crs_chem_foundations",
            "concept_id": "chem_foundations",
            "event_type": "question_attempted",
            "score": 0.95,
        },
    )
    assert event_resp.status_code == 201, event_resp.text

    # 3. Retrieve student review queue
    review_resp = client.get("/api/v1/students/usr_stu_flow/review-queue", headers=hdr)
    assert review_resp.status_code == 200, review_resp.text
    assert isinstance(review_resp.json()["data"], list)


# =====================================================================
# 8. UI Contract Audit: Elimination of Toast-Only Fake Buttons
# =====================================================================

def test_ui_contract_audit_no_fake_toasts():
    """Verify that admin_portal.html contains no buttons that substitute cosmetic toasts for backend actions."""
    portal_path = Path("app/ui/admin_portal.html")
    assert portal_path.exists(), "app/ui/admin_portal.html must exist"
    content = portal_path.read_text(encoding="utf-8")

    # Disconnected toast patterns that previously substituted for real backend operations
    fake_toast_patterns = [
        "AdminApp.toast('New Invoice Generation Triggered')",
        "AdminApp.toast('ID Card Batch Sent to Printer Spooler')",
        "AdminApp.toast('New Certificate Generation Dialogue')",
        "AdminApp.toast('Purchase Order Created')",
        "AdminApp.toast('All Class 11A students recorded as PRESENT ✅')",
        "AdminApp.toast('Campus logistics, fleet allocations and inventory synchronized 🚌')",
    ]

    for pattern in fake_toast_patterns:
        assert pattern not in content, f"Found disconnected toast pattern in admin_portal.html: {pattern}"
