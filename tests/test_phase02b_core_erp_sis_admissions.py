"""Phase 02B: Core ERP Foundation and Student Information System (SIS & Admissions).

Tests cover:
1. Migration 010 schema creation and clean rollback.
2. Academic year, terms, and calendar event lifecycle.
3. Admissions inquiry intake and duplicate applicant detection.
4. Formal application workflow, document verification, and offer issuance.
5. Transactional, idempotent admission-to-student conversion into SIS.
6. Class/section management, capacity constraint enforcement, and roster retrieval.
7. Multi-tenant isolation for ERP entities.
8. REST API endpoints and RBAC authorization matrix.
"""

import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from central_platform.db import PlatformDatabase
from central_platform.models.identity import (
    Person,
    StudentProfile,
    GuardianProfile,
    StudentGuardianLink,
)
from central_platform.models.academic import (
    AcademicYear,
    AcademicTerm,
    CalendarEvent,
)
from central_platform.models.admissions import (
    AdmissionInquiry,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionOffer,
    InquiryStatus,
    ApplicationStatus,
    OfferStatus,
    DocumentType,
    VerificationStatus,
)
from central_platform.models.sis import (
    StudentClass,
    ClassEnrollment,
    EnrollmentStatus,
)
from central_platform.academic.service import AcademicService
from central_platform.admissions.service import AdmissionsService
from central_platform.sis.service import SISService
from central_platform.auth.tokens import create_access_token
from central_platform.api.app import app

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def memory_db():
    """Returns an in-memory SQLite database migrated through 010."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Run migrations 001 to 010
    scripts = sorted([f for f in MIGRATIONS_DIR.glob("*.sql") if not f.name.endswith("_down.sql")])
    for script in scripts:
        conn.executescript(script.read_text(encoding="utf-8"))
    
    # Seed test organizations
    conn.execute(
        "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
        "VALUES ('org-school-1', 'Greenwood High', 'greenwood-high', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
    )
    conn.execute(
        "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
        "VALUES ('org-coaching-2', 'Apex IIT Academy', 'apex-iit', '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
    )
    
    # Enable entitlements
    for mod in ["admissions", "sis", "academic"]:
        conn.execute(
            "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
            f"VALUES ('ent-{mod}-1', 'org-school-1', '{mod}', 1, '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
            f"VALUES ('ent-{mod}-2', 'org-coaching-2', '{mod}', 1, '2026-10-14T00:00:00Z', '2026-10-14T00:00:00Z');"
        )
    conn.commit()
    return conn


@pytest.fixture
def platform_db(tmp_path):
    """File-backed PlatformDatabase instance migrated through 010."""
    db_file = str(tmp_path / "test_phase02b.db")
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
        for mod in ["admissions", "sis", "academic"]:
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


# ── Test 1: Migration 010 Up and Down Verification ───────────────────────────

def test_migration_010_up_and_down():
    """Verify migration 010 creates all ERP tables and down script removes them cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply up through 009
    for i in range(1, 10):
        scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Apply 010
    up_010 = MIGRATIONS_DIR / "010_admissions_and_academic_calendar.sql"
    assert up_010.exists(), "010 forward migration script must exist"
    conn.executescript(up_010.read_text(encoding="utf-8"))

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_up = {r[0] for r in cursor.fetchall()}

    expected_tables = {
        "academic_years",
        "academic_terms",
        "school_calendar_events",
        "admission_inquiries",
        "admission_applications",
        "admission_documents",
        "admission_offers",
        "student_classes",
        "student_class_enrollments",
    }
    for t in expected_tables:
        assert t in tables_after_up, f"Table {t} should exist after migration 010"

    # Roll back 010
    down_010 = MIGRATIONS_DIR / "010_admissions_and_academic_calendar_down.sql"
    assert down_010.exists(), "010 rollback migration script must exist"
    conn.executescript(down_010.read_text(encoding="utf-8"))

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_down = {r[0] for r in cursor.fetchall()}

    for t in expected_tables:
        assert t not in tables_after_down, f"Table {t} should be removed after rollback"

    conn.close()


# ── Test 2: Academic Calendar Lifecycle ──────────────────────────────────────

def test_academic_calendar_lifecycle(platform_db):
    """Test academic year, term, and calendar event creation and current year retrieval."""
    svc = AcademicService(platform_db)
    
    # Create academic year
    ay = svc.create_academic_year(
        organization_id="org-school-1",
        name="Academic Year 2026-2027",
        code="AY-2026-27",
        start_date="2026-06-01",
        end_date="2027-04-30",
        is_current=True,
    )
    assert ay.id is not None
    assert ay.name == "Academic Year 2026-2027"
    assert ay.is_current is True

    # Retrieve current academic year
    curr = svc.get_current_academic_year("org-school-1")
    assert curr is not None
    assert curr.id == ay.id

    # Create terms
    term1 = svc.create_academic_term(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        name="Term 1 (Monsoon)",
        code="T1",
        start_date="2026-06-01",
        end_date="2026-10-31",
    )
    term2 = svc.create_academic_term(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        name="Term 2 (Spring)",
        code="T2",
        start_date="2026-11-01",
        end_date="2027-04-30",
    )
    terms = svc.list_academic_terms("org-school-1", ay.id)
    assert len(terms) == 2

    # Create calendar holiday event
    event = svc.create_calendar_event(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        title="Independence Day",
        event_type="HOLIDAY",
        start_date="2026-08-15",
        end_date="2026-08-15",
        is_holiday=True,
    )
    events = svc.list_calendar_events("org-school-1", ay.id)
    assert len(events) == 1
    assert events[0].is_holiday is True


# ── Test 3: Admissions Inquiry and Duplicate Detection ───────────────────────

def test_admissions_inquiry_and_duplicate_detection(platform_db):
    """Test public inquiry intake and duplicate applicant detection."""
    adm_svc = AdmissionsService(platform_db)

    # Submit first inquiry
    inquiry1 = adm_svc.submit_inquiry(
        organization_id="org-school-1",
        applicant_name="Aarav Sharma",
        guardian_name="Vikram Sharma",
        email="vikram.sharma@example.com",
        phone="+919876543210",
        target_grade="Grade 9",
        notes="Interested in science stream",
    )
    assert inquiry1.id is not None
    assert inquiry1.inquiry_number.startswith("INQ-")
    assert inquiry1.status == InquiryStatus.NEW

    # Submit duplicate inquiry with matching phone and email
    duplicates = adm_svc.find_duplicate_inquiries(
        organization_id="org-school-1",
        email="vikram.sharma@example.com",
        phone="+919876543210",
    )
    assert len(duplicates) == 1
    assert duplicates[0].id == inquiry1.id


# ── Test 4: Application Stage Transitions and Offer Issuance ─────────────────

def test_application_stage_transitions_and_offer(platform_db):
    """Test formal application submission, document attachment, review, and offer."""
    acad_svc = AcademicService(platform_db)
    ay = acad_svc.create_academic_year(
        organization_id="org-school-1",
        name="AY 2026-27",
        code="AY-26-27",
        start_date="2026-06-01",
        end_date="2027-04-30",
        is_current=True,
    )

    adm_svc = AdmissionsService(platform_db)
    app = adm_svc.submit_application(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        applicant_name="Priya Patel",
        date_of_birth="2012-05-14",
        gender="FEMALE",
        email="priya.patel@example.com",
        phone="+919876543211",
        address="123 MG Road, Bengaluru",
        previous_school="Delhi Public School",
        target_grade="Grade 8",
    )
    assert app.id is not None
    assert app.application_number.startswith("APP-")
    assert app.status == ApplicationStatus.SUBMITTED

    # Attach document
    doc = adm_svc.attach_document(
        organization_id="org-school-1",
        application_id=app.id,
        document_type=DocumentType.BIRTH_CERTIFICATE,
        file_name="birth_certificate.pdf",
        file_path="/storage/documents/birth_certificate.pdf",
        file_hash="sha256:abc123mockhash",
    )
    assert doc.id is not None
    assert doc.verification_status == VerificationStatus.PENDING

    # Verify document
    adm_svc.verify_document(
        organization_id="org-school-1",
        document_id=doc.id,
        status=VerificationStatus.VERIFIED,
        verified_by="admin-user-1",
    )

    # Move application to UNDER_REVIEW
    app_updated = adm_svc.update_application_status(
        organization_id="org-school-1",
        application_id=app.id,
        status=ApplicationStatus.UNDER_REVIEW,
        review_notes="Documents verified, interview scheduled",
    )
    assert app_updated.status == ApplicationStatus.UNDER_REVIEW

    # Issue admission offer
    offer = adm_svc.issue_offer(
        organization_id="org-school-1",
        application_id=app.id,
        grade="Grade 8",
        fee_amount=75000.0,
        valid_until="2026-05-30",
        conditions="Subject to payment of first installment",
    )
    assert offer.id is not None
    assert offer.status == OfferStatus.ISSUED

    # Applicant accepts offer
    app_accepted = adm_svc.accept_offer(
        organization_id="org-school-1",
        application_id=app.id,
        offer_id=offer.id,
    )
    assert app_accepted.status == ApplicationStatus.ACCEPTED


# ── Test 5: Idempotent Admission Conversion to SIS ───────────────────────────

def test_idempotent_admission_conversion_to_sis(platform_db):
    """Test transactional conversion of accepted applicant to real SIS student with zero duplicates on retry."""
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
        name="Grade 8-A",
        grade_level="Grade 8",
        section="A",
        capacity=30,
    )

    adm_svc = AdmissionsService(platform_db)
    app = adm_svc.submit_application(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        applicant_name="Rohan Verma",
        date_of_birth="2012-08-20",
        gender="MALE",
        email="rohan.verma@example.com",
        phone="+919876543299",
        address="45 Park Street, Kolkata",
        target_grade="Grade 8",
    )
    adm_svc.update_application_status(
        organization_id="org-school-1",
        application_id=app.id,
        status=ApplicationStatus.ACCEPTED,
    )

    # Perform conversion into SIS
    result = adm_svc.convert_application_to_student(
        organization_id="org-school-1",
        application_id=app.id,
        class_id=cls.id,
        roll_number="08-A-01",
        guardian_name="Sunita Verma",
        guardian_phone="+919876543299",
        guardian_relationship="MOTHER",
    )

    assert result["student_id"] is not None
    assert result["person_id"] is not None
    assert result["guardian_id"] is not None
    assert result["enrollment_id"] is not None

    student_id_first = result["student_id"]

    # Verify student exists in SIS
    student = sis_svc.get_student(result["student_id"], "org-school-1")
    assert student is not None
    assert student.admission_number == app.application_number

    # Retry conversion — must be idempotent and return existing student without creating duplicate records
    result_retry = adm_svc.convert_application_to_student(
        organization_id="org-school-1",
        application_id=app.id,
        class_id=cls.id,
        roll_number="08-A-01",
        guardian_name="Sunita Verma",
        guardian_phone="+919876543299",
        guardian_relationship="MOTHER",
    )
    assert result_retry["student_id"] == student_id_first
    assert result_retry["is_idempotent_replay"] is True


# ── Test 6: Class Roster and Capacity Enforcement ────────────────────────────

def test_class_roster_and_capacity_enforcement(platform_db):
    """Test class capacity constraint and roster retrieval."""
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
    # Class with capacity of 2
    cls = sis_svc.create_class(
        organization_id="org-school-1",
        academic_year_id=ay.id,
        name="Grade 10-Alpha",
        grade_level="Grade 10",
        section="Alpha",
        capacity=2,
    )

    # Create 2 students and enroll them
    s1 = sis_svc.create_student_direct(
        organization_id="org-school-1",
        first_name="Student",
        last_name="One",
        email="s1@test.com",
    )
    s2 = sis_svc.create_student_direct(
        organization_id="org-school-1",
        first_name="Student",
        last_name="Two",
        email="s2@test.com",
    )
    sis_svc.enroll_student_in_class(
        organization_id="org-school-1",
        student_id=s1.id,
        class_id=cls.id,
        academic_year_id=ay.id,
        roll_number="10-A-01",
    )
    sis_svc.enroll_student_in_class(
        organization_id="org-school-1",
        student_id=s2.id,
        class_id=cls.id,
        academic_year_id=ay.id,
        roll_number="10-A-02",
    )

    # Roster has 2 students
    roster = sis_svc.get_class_roster("org-school-1", cls.id)
    assert len(roster) == 2

    # Attempting to enroll a 3rd student must fail capacity check
    s3 = sis_svc.create_student_direct(
        organization_id="org-school-1",
        first_name="Student",
        last_name="Three",
        email="s3@test.com",
    )
    with pytest.raises(ValueError, match="exceeds capacity"):
        sis_svc.enroll_student_in_class(
            organization_id="org-school-1",
            student_id=s3.id,
            class_id=cls.id,
            academic_year_id=ay.id,
            roll_number="10-A-03",
        )


# ── Test 7: Multi-Tenant Isolation ───────────────────────────────────────────

def test_cross_tenant_isolation_erp(platform_db):
    """Verify Org A cannot access or mutate Org B academic, admission, or class records."""
    acad_svc = AcademicService(platform_db)
    ay_school = acad_svc.create_academic_year(
        organization_id="org-school-1",
        name="AY Greenwood",
        code="GW-2026",
        start_date="2026-06-01",
        end_date="2027-04-30",
        is_current=True,
    )

    adm_svc = AdmissionsService(platform_db)
    app = adm_svc.submit_application(
        organization_id="org-school-1",
        academic_year_id=ay_school.id,
        applicant_name="Greenwood Applicant",
        email="gw@example.com",
        target_grade="Grade 1",
    )

    # Org B (Apex Coaching) attempting to query Org A's application must return None
    app_cross = adm_svc.get_application(app.id, organization_id="org-coaching-2")
    assert app_cross is None

    # Org B listing academic years must not see Org A's academic year
    ay_list_org2 = acad_svc.list_academic_years("org-coaching-2")
    assert not any(y.id == ay_school.id for y in ay_list_org2)


# ── Test 8: REST API Endpoints and RBAC Authorization ────────────────────────

def test_admissions_and_academic_api_endpoints():
    """Verify REST API routes for academic calendar and admissions intake."""
    import uuid
    from central_platform.models import Organization

    db = PlatformDatabase()
    org_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org_id, name="API Test Org", slug=f"api-org-{org_id}"))

    client = TestClient(app)

    # Public inquiry endpoint (no auth required)
    resp = client.post(
        "/api/v1/admissions/inquiries",
        json={
            "organization_id": org_id,
            "applicant_name": "Public Lead",
            "guardian_name": "Parent Lead",
            "email": "lead@test.com",
            "phone": "+919999999999",
            "target_grade": "Grade 5",
            "notes": "Looking for admission info",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "inquiry_number" in data

    # Admin route requires valid auth
    token = create_access_token(
        user_id="user-admin-1",
        role="org_admin",
        organization_id=org_id,
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Query inquiries as admin
    resp_inquiries = client.get("/api/v1/admissions/inquiries", headers=headers)
    assert resp_inquiries.status_code == 200
    assert len(resp_inquiries.json()) >= 1

    # Create academic year via API
    resp_ay = client.post(
        "/api/v1/academic/years",
        headers=headers,
        json={
            "name": "API Academic Year 2026-27",
            "code": "API-26-27",
            "start_date": "2026-06-01",
            "end_date": "2027-04-30",
            "is_current": True,
        },
    )
    assert resp_ay.status_code == 201
    ay_data = resp_ay.json()
    assert ay_data["code"] == "API-26-27"
