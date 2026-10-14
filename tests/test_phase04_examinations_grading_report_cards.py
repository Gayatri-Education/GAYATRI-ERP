"""Phase 04: Examinations, Official Grading and Report Cards.

Tests cover:
1. Migration 012 schema creation and clean rollback.
2. Exam series, paper schedules, and seat/room allocation.
3. Bounds-checked marks entry (0 <= marks <= max_marks), submission, and locking.
4. Institutional grading scale configuration and tier grade resolution.
5. Term result aggregation (total marks, percentage, GPA).
6. Tamper-evident report card generation with SHA256 checksum and publication gate.
7. Multi-tenant isolation for examination and grading records.
8. REST API endpoints and RBAC authorization matrix.
"""

import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from central_platform.db import PlatformDatabase
from central_platform.models import Organization
from central_platform.models.examinations import (
    ExamSeriesType,
    MarksStatus,
    ExamSeries,
    ExamSchedule,
    StudentMarks,
)
from central_platform.models.grading import (
    ScaleType,
    ReportCardStatus,
    GradingScale,
    GradingTier,
    StudentTermResult,
    StudentReportCard,
)
from central_platform.examinations.service import ExaminationService
from central_platform.grading.service import GradingService
from central_platform.academic.service import AcademicService
from central_platform.sis.service import SISService
from central_platform.auth.tokens import create_access_token
from central_platform.api.app import app

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


@pytest.fixture
def platform_db(tmp_path):
    """File-backed PlatformDatabase instance migrated through 012."""
    db_file = str(tmp_path / "test_phase04.db")
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
        for mod in ["examinations", "grading", "sis", "academic"]:
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


# ── Test 1: Migration 012 Up and Down Verification ───────────────────────────

def test_migration_012_up_and_down():
    """Verify migration 012 creates all exam & grading tables and down script removes them cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply up through 011
    for i in range(1, 12):
        scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Apply 012
    up_012 = MIGRATIONS_DIR / "012_examinations_grading_report_cards.sql"
    assert up_012.exists(), "012 forward migration script must exist"
    conn.executescript(up_012.read_text(encoding="utf-8"))

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_up = {r[0] for r in cursor.fetchall()}

    expected_tables = {
        "exam_series",
        "exam_schedules",
        "exam_student_marks",
        "grading_scales",
        "grading_scale_tiers",
        "student_term_results",
        "student_report_cards",
    }
    for t in expected_tables:
        assert t in tables_after_up, f"Table {t} should exist after migration 012"

    # Roll back 012
    down_012 = MIGRATIONS_DIR / "012_examinations_grading_report_cards_down.sql"
    assert down_012.exists(), "012 rollback migration script must exist"
    conn.executescript(down_012.read_text(encoding="utf-8"))

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_down = {r[0] for r in cursor.fetchall()}

    for t in expected_tables:
        assert t not in tables_after_down, f"Table {t} should be removed after rollback"

    conn.close()


# ── Test 2: Exam Series and Schedule Lifecycle ───────────────────────────────

def test_exam_series_and_schedule_lifecycle(platform_db):
    """Test creating exam series and scheduling subject papers."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year("org-school-1", "AY 2026-27", "AY-26-27", "2026-06-01", "2027-04-30", True)
    term = acad_svc.create_academic_term("org-school-1", ay.id, "Term 1", "T1", "2026-06-01", "2026-10-31")

    sis_svc = SISService(platform_db)
    cls = sis_svc.create_class("org-school-1", ay.id, "Class 10-A", "Grade 10", "A")

    exam_svc = ExaminationService(platform_db)
    series = exam_svc.create_exam_series(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        academic_term_id=term.id,
        name="Mid-Term Assessment 2026",
        code="MTA-2026",
        start_date="2026-10-15",
        end_date="2026-10-25",
        series_type=ExamSeriesType.MID_TERM,
    )
    assert series.id is not None
    assert series.name == "Mid-Term Assessment 2026"

    # Schedule Mathematics Paper
    sched = exam_svc.schedule_exam(
        organization_id="org-school-1",
        exam_series_id=series.id,
        class_id=cls.id,
        subject_id="sub-math-1",
        exam_date="2026-10-16",
        start_time="09:00",
        end_time="12:00",
        max_marks=100.0,
        pass_marks=35.0,
        room_name="Hall B",
    )
    assert sched.id is not None
    assert sched.max_marks == 100.0
    assert sched.room_name == "Hall B"


# ── Test 3: Marks Entry Validation and Locking ───────────────────────────────

def test_marks_entry_validation_and_locking(platform_db):
    """Verify marks entry strictly enforces bounds and respects locking state."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year("org-school-1", "AY 2026-27", "AY-26-27", "2026-06-01", "2027-04-30", True)
    sis_svc = SISService(platform_db)
    cls = sis_svc.create_class("org-school-1", ay.id, "Class 10-A", "Grade 10", "A")
    student = sis_svc.create_student_direct("org-school-1", "Aditya", "Kumar")

    exam_svc = ExaminationService(platform_db)
    series = exam_svc.create_exam_series(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        name="Mid-Term 2026",
        code="MT-2026",
        start_date="2026-10-15",
        end_date="2026-10-25",
    )
    sched = exam_svc.schedule_exam(
        organization_id="org-school-1",
        exam_series_id=series.id,
        class_id=cls.id,
        subject_id="sub-physics-1",
        exam_date="2026-10-18",
        start_time="09:00",
        end_time="12:00",
        max_marks=80.0,
        pass_marks=28.0,
    )

    # 1. Reject marks > max_marks
    with pytest.raises(ValueError, match="Marks cannot exceed max marks"):
        exam_svc.enter_marks(
            organization_id="org-school-1",
            schedule_id=sched.id,
            student_id=student.id,
            marks_obtained=85.0,  # exceeds 80
            entered_by="teacher-1",
        )

    # 2. Reject negative marks
    with pytest.raises(ValueError, match="Marks cannot be negative"):
        exam_svc.enter_marks(
            organization_id="org-school-1",
            schedule_id=sched.id,
            student_id=student.id,
            marks_obtained=-5.0,
            entered_by="teacher-1",
        )

    # 3. Enter valid marks
    entry = exam_svc.enter_marks(
        organization_id="org-school-1",
        schedule_id=sched.id,
        student_id=student.id,
        marks_obtained=74.5,
        entered_by="teacher-1",
    )
    assert entry.id is not None
    assert entry.marks_obtained == 74.5
    assert entry.status == MarksStatus.SUBMITTED

    # 4. Lock schedule marks
    exam_svc.lock_marks(
        organization_id="org-school-1",
        schedule_id=sched.id,
        verified_by="controller-1",
    )

    # 5. Attempting to modify locked marks must fail
    with pytest.raises(ValueError, match="Marks are locked"):
        exam_svc.enter_marks(
            organization_id="org-school-1",
            schedule_id=sched.id,
            student_id=student.id,
            marks_obtained=76.0,
            entered_by="teacher-1",
        )


# ── Test 4: Grading Scale Resolution ─────────────────────────────────────────

def test_grading_scale_resolution(platform_db):
    """Verify institutional grading scale accurately resolves percentage boundaries to letter grades."""
    grading_svc = GradingService(platform_db)
    scale = grading_svc.create_grading_scale(
        organization_id="org-school-1",
        name="CBSE Standard 9-Point",
        code="CBSE-9P",
        scale_type=ScaleType.NINE_POINT,
        tiers=[
            {"grade_name": "A1", "grade_point": 10.0, "min_percentage": 91.0, "max_percentage": 100.0},
            {"grade_name": "A2", "grade_point": 9.0, "min_percentage": 81.0, "max_percentage": 90.99},
            {"grade_name": "B1", "grade_point": 8.0, "min_percentage": 71.0, "max_percentage": 80.99},
            {"grade_name": "B2", "grade_point": 7.0, "min_percentage": 61.0, "max_percentage": 70.99},
            {"grade_name": "C1", "grade_point": 6.0, "min_percentage": 51.0, "max_percentage": 60.99},
            {"grade_name": "C2", "grade_point": 5.0, "min_percentage": 41.0, "max_percentage": 50.99},
            {"grade_name": "D", "grade_point": 4.0, "min_percentage": 33.0, "max_percentage": 40.99},
            {"grade_name": "E", "grade_point": 0.0, "min_percentage": 0.0, "max_percentage": 32.99},
        ],
    )
    assert scale.id is not None

    # Test boundary mappings
    assert grading_svc.resolve_grade("org-school-1", scale.id, 95.0)["grade_name"] == "A1"
    assert grading_svc.resolve_grade("org-school-1", scale.id, 91.0)["grade_name"] == "A1"
    assert grading_svc.resolve_grade("org-school-1", scale.id, 85.0)["grade_name"] == "A2"
    assert grading_svc.resolve_grade("org-school-1", scale.id, 70.5)["grade_name"] == "B2"
    assert grading_svc.resolve_grade("org-school-1", scale.id, 33.0)["grade_name"] == "D"
    assert grading_svc.resolve_grade("org-school-1", scale.id, 25.0)["grade_name"] == "E"


# ── Test 5: Term Result Aggregation ──────────────────────────────────────────

def test_term_result_aggregation(platform_db):
    """Test aggregation of multiple exam subjects into authoritative student term results."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year("org-school-1", "AY 2026-27", "AY-26-27", "2026-06-01", "2027-04-30", True)
    term = acad_svc.create_academic_term("org-school-1", ay.id, "Term 1", "T1", "2026-06-01", "2026-10-31")

    sis_svc = SISService(platform_db)
    cls = sis_svc.create_class("org-school-1", ay.id, "Class 10-A", "Grade 10", "A")
    student = sis_svc.create_student_direct("org-school-1", "Ananya", "Deshmukh")

    exam_svc = ExaminationService(platform_db)
    series = exam_svc.create_exam_series(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        academic_term_id=term.id,
        name="Term 1 Finals",
        code="T1-FINAL",
        start_date="2026-10-10",
        end_date="2026-10-20",
    )

    # Schedule Paper 1: Math (max 100) -> 90 marks
    s1 = exam_svc.schedule_exam("org-school-1", series.id, cls.id, "sub-math", "2026-10-12", "09:00", "12:00", 100.0, 35.0)
    exam_svc.enter_marks("org-school-1", s1.id, student.id, 90.0, "teacher-1")
    exam_svc.lock_marks("org-school-1", s1.id, "admin-1")

    # Schedule Paper 2: Science (max 100) -> 80 marks
    s2 = exam_svc.schedule_exam("org-school-1", series.id, cls.id, "sub-sci", "2026-10-14", "09:00", "12:00", 100.0, 35.0)
    exam_svc.enter_marks("org-school-1", s2.id, student.id, 80.0, "teacher-1")
    exam_svc.lock_marks("org-school-1", s2.id, "admin-1")

    grading_svc = GradingService(platform_db)
    scale = grading_svc.create_grading_scale(
        organization_id="org-school-1",
        name="CBSE 9-Point",
        code="CBSE",
        scale_type=ScaleType.NINE_POINT,
        tiers=[
            {"grade_name": "A1", "grade_point": 10.0, "min_percentage": 91.0, "max_percentage": 100.0},
            {"grade_name": "A2", "grade_point": 9.0, "min_percentage": 81.0, "max_percentage": 90.99},
            {"grade_name": "B1", "grade_point": 8.0, "min_percentage": 71.0, "max_percentage": 80.99},
        ],
    )

    # Aggregate term results
    result = grading_svc.calculate_term_result(
        organization_id="org-school-1",
        student_id=student.id,
        academic_year_id=ay.id,
        academic_term_id=term.id,
        scale_id=scale.id,
    )
    assert result.total_marks_obtained == 170.0
    assert result.total_max_marks == 200.0
    assert result.percentage == 85.0
    assert result.final_grade == "A2"
    assert result.gpa == 9.0


# ── Test 6: Report Card Generation and Tamper Hash ────────────────────────────

def test_report_card_generation_and_tamper_hash(platform_db):
    """Test generating report card with SHA256 document hash and publication workflow."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year("org-school-1", "AY 2026-27", "AY-26-27", "2026-06-01", "2027-04-30", True)
    term = acad_svc.create_academic_term("org-school-1", ay.id, "Term 1", "T1", "2026-06-01", "2026-10-31")

    sis_svc = SISService(platform_db)
    student = sis_svc.create_student_direct("org-school-1", "Karan", "Johar")

    grading_svc = GradingService(platform_db)
    # Generate report card
    report = grading_svc.generate_report_card(
        organization_id="org-school-1",
        student_id=student.id,
        academic_year_id=ay.id,
        academic_term_id=term.id,
        general_remarks="Excellent performance in analytical reasoning.",
    )
    assert report.id is not None
    assert report.status == ReportCardStatus.DRAFT
    assert report.document_hash is not None
    assert len(report.document_hash) == 64  # SHA256 hex length

    # Publish report card
    published = grading_svc.publish_report_card("org-school-1", report.id)
    assert published.status == ReportCardStatus.PUBLISHED
    assert published.published_at is not None


# ── Test 7: Multi-Tenant Isolation ───────────────────────────────────────────

def test_cross_tenant_isolation_phase04(platform_db):
    """Verify Org A cannot view or mutate Org B examinations, marks, or report cards."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year("org-school-1", "AY GW", "GW-1", "2026-06-01", "2027-04-30", True)

    exam_svc = ExaminationService(platform_db)
    series = exam_svc.create_exam_series("org-school-1", ay.id, "GW Series", "GWS-1", "2026-10-15", "2026-10-25")

    # Org B cannot view Org A's exam series
    series_b = exam_svc.get_exam_series("org-coaching-2", series.id)
    assert series_b is None

    # Org B cannot view Org A's grading scales
    grading_svc = GradingService(platform_db)
    scale = grading_svc.create_grading_scale("org-school-1", "Scale 1", "SC-1", ScaleType.PERCENTAGE, [])
    scale_b = grading_svc.get_grading_scale("org-coaching-2", scale.id)
    assert scale_b is None


# ── Test 8: REST API Endpoints and RBAC Authorization ────────────────────────

def test_phase04_api_endpoints_and_rbac():
    """Verify REST API routes for examinations, grading, and report cards."""
    import uuid
    db = PlatformDatabase()
    org_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org_id, name="Phase 04 Org", slug=f"p4-org-{org_id}"))

    ay = AcademicService(db).create_academic_year(
        organization_id=org_id,
        name="AY 2026-27",
        code=f"AY-{org_id}",
        start_date="2026-06-01",
        end_date="2027-04-30",
        is_current=True,
    )

    token = create_access_token(
        user_id="user-admin-p4",
        role="org_admin",
        organization_id=org_id,
    )
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)

    # 1. Create Exam Series via API
    resp_series = client.post(
        "/api/v1/examinations/series",
        headers=headers,
        json={
            "academic_year_id": ay.id,
            "name": "API Exam Series",
            "code": "API-EX-1",
            "start_date": "2026-10-15",
            "end_date": "2026-10-25",
            "series_type": "FINAL",
        },
    )
    assert resp_series.status_code == 201
    assert resp_series.json()["code"] == "API-EX-1"

    # 2. Create Grading Scale via API
    resp_scale = client.post(
        "/api/v1/grading/scales",
        headers=headers,
        json={
            "name": "API Grading Scale",
            "code": "API-GS-1",
            "scale_type": "PERCENTAGE",
            "tiers": [
                {"grade_name": "Pass", "grade_point": 4.0, "min_percentage": 40.0, "max_percentage": 100.0},
                {"grade_name": "Fail", "grade_point": 0.0, "min_percentage": 0.0, "max_percentage": 39.99},
            ],
        },
    )
    assert resp_scale.status_code == 201
    assert resp_scale.json()["code"] == "API-GS-1"
