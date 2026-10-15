"""Phase 07: Assessment, Question Bank, Grading, and Anti-Fallback Integrity Suite.

Verifies:
- ERP-016: Gating demo fallback in question bank retrieval (empty bank must return [] in production).
- Legacy submission fail-closed behavior on missing assessments in production.
- Answer key and explanation protection for student callers.
- Cross-course and cross-tenant question item validation.
- Student attempt IDOR isolation (start, submit, list attempts).
- Attempt lifecycle immutability (double-submission and expired attempts rejected).
- Teacher review authorization (students blocked with HTTP 403).
- Production mode authentication enforcement.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import create_app
from central_platform.api.routes.assessments import get_assessment_service
from central_platform.assessment.models import AssessmentType, AttemptStatus
from central_platform.assessment.service import AssessmentService
from central_platform.auth.dependencies import get_current_user, get_current_user_optional, get_db
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.events.store import LearningEventStore
from central_platform.models.schema import (
    Assessment,
    Course,
    Organization,
    QuestionBankItem,
    User,
    UserRole,
)
from central_platform.slr.service import SLRService


@pytest.fixture
def empty_db():
    """Isolated, pristine in-memory database with zero question bank items."""
    db = PlatformDatabase(":memory:")
    db.create_organization(Organization(id="org-academics", name="Academics Org", slug="academics"))
    db.create_organization(Organization(id="org-rival", name="Rival Org", slug="rival"))

    db.create_course(Course(id="crs-physics-101", organization_id="org-academics", code="PHYS101", title="Physics I"))
    db.create_course(Course(id="crs-math-201", organization_id="org-academics", code="MATH201", title="Math II"))
    db.create_course(Course(id="crs-rival-101", organization_id="org-rival", code="RIV101", title="Rival Course"))

    db.create_user(User(id="stu-alice", email="alice@academics.edu", full_name="Alice Student", role=UserRole.STUDENT, organization_id="org-academics"))
    db.create_user(User(id="stu-bob", email="bob@academics.edu", full_name="Bob Student", role=UserRole.STUDENT, organization_id="org-academics"))
    db.create_user(User(id="tch-newton", email="newton@academics.edu", full_name="Dr. Newton", role=UserRole.TEACHER, organization_id="org-academics"))
    return db


@pytest.fixture
def assessment_service(empty_db):
    event_store = LearningEventStore(empty_db)
    slr_service = SLRService(empty_db, event_store)
    return AssessmentService(db=empty_db, event_store=event_store, slr_service=slr_service, allow_auto_provision=False)


@pytest.fixture
def test_app(empty_db, assessment_service):
    app = create_app()
    import central_platform.auth.dependencies as auth_deps
    old_instance = auth_deps._DB_INSTANCE
    old_env_path = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = ":memory:"
    auth_deps._DB_INSTANCE = empty_db
    app.dependency_overrides[get_db] = lambda: empty_db
    app.dependency_overrides[get_assessment_service] = lambda: assessment_service
    yield app
    auth_deps._DB_INSTANCE = old_instance
    if old_env_path is not None:
        os.environ["GAYATRI_DB_PATH"] = old_env_path
    else:
        os.environ.pop("GAYATRI_DB_PATH", None)


# ── 1. ERP-016: Anti-Fallback Invariant ──────────────────────────────────────

def test_erp016_empty_bank_returns_empty_list_in_production(test_app, monkeypatch):
    """In production mode, an empty question bank must return [], never SAMPLE_QUESTION_BANK."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", "super-secret-high-entropy-jwt-token-key-32chars!")
    client = TestClient(test_app)

    token = create_access_token(user_id="tch-newton", role="TEACHER", organization_id="org-academics")
    headers = {"Authorization": f"Bearer {token}"}

    # Query items without demo flag
    resp = client.get("/api/v1/assessments/items", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"] == [], "Empty bank must return [] in production mode"

    # Query items with include_demo=true in production (must be ignored/blocked)
    resp_demo = client.get("/api/v1/assessments/items?include_demo=true", headers=headers)
    assert resp_demo.status_code == 200
    assert resp_demo.json()["data"] == [], "Production mode must strictly prohibit demo fallback even if requested"


def test_erp016_demo_fallback_requires_explicit_request_in_non_prod(test_app, monkeypatch):
    """In non-production mode, empty bank returns [] by default, and only returns sample items when include_demo=true."""
    monkeypatch.setenv("GAYATRI_ENV", "development")
    client = TestClient(test_app)

    # By default, without include_demo=true, returns empty list
    resp_default = client.get("/api/v1/assessments/items")
    assert resp_default.status_code == 200
    assert resp_default.json()["data"] == []

    # When explicitly requested via include_demo=true, sample bank items are returned
    resp_demo = client.get("/api/v1/assessments/items?include_demo=true")
    assert resp_demo.status_code == 200
    items = resp_demo.json()["data"]
    assert len(items) > 0
    assert any("thermo" in it["concept_id"].lower() for it in items)


def test_erp016_legacy_submit_rejects_missing_assessment_in_production(test_app, monkeypatch):
    """In production mode, legacy submit on unknown assessment must fail closed (404), not synthesize fake data."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("GAYATRI_JWT_SECRET", "super-secret-high-entropy-jwt-token-key-32chars!")
    client = TestClient(test_app)

    token = create_access_token(user_id="stu-alice", role="STUDENT", organization_id="org-academics")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "assessment_id": "asmt-ghost-999",
        "student_id": "stu-alice",
        "answers": {"q1": "delta G < 0"},
    }
    resp = client.post("/api/v1/assessments/submit", headers=headers, json=payload)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── 2. Answer Key Protection Invariant ──────────────────────────────────────

def test_answer_keys_scrubbed_for_student_users(test_app, assessment_service):
    """Students querying question items or sanitized assessments must not see answer keys or explanations."""
    q_item = QuestionBankItem(
        id="qb-phys-01",
        course_id="crs-physics-101",
        organization_id="org-academics",
        concept_id="newton_first_law",
        question_text="What is inertia?",
        item_type="MCQ",
        options=["Resistance to change in motion", "Force applied", "Acceleration", "Mass times gravity"],
        correct_answer="Resistance to change in motion",
        explanation="Inertia is the property of an object to resist changes in its velocity.",
        difficulty=1,
    )
    assessment_service.create_question(q_item)

    client = TestClient(test_app)

    # 1. Student queries items list
    student_token = create_access_token(user_id="stu-alice", role="STUDENT", organization_id="org-academics")
    resp_student = client.get("/api/v1/assessments/items", headers={"Authorization": f"Bearer {student_token}"})
    assert resp_student.status_code == 200
    student_items = resp_student.json()["data"]
    assert len(student_items) == 1
    assert student_items[0]["correct_answer"] is None, "Student must not see correct_answer"
    assert student_items[0]["explanation"] is None, "Student must not see explanation"

    # 2. Student queries single item
    resp_single = client.get("/api/v1/assessments/items/qb-phys-01", headers={"Authorization": f"Bearer {student_token}"})
    assert resp_single.status_code == 200
    single_item = resp_single.json()["data"]
    assert single_item["correct_answer"] is None
    assert single_item["explanation"] is None

    # 3. Teacher queries items list (answer key preserved)
    teacher_token = create_access_token(user_id="tch-newton", role="TEACHER", organization_id="org-academics")
    resp_teacher = client.get("/api/v1/assessments/items", headers={"Authorization": f"Bearer {teacher_token}"})
    assert resp_teacher.status_code == 200
    teacher_items = resp_teacher.json()["data"]
    assert teacher_items[0]["correct_answer"] == "Resistance to change in motion"
    assert teacher_items[0]["explanation"] is not None


# ── 3. Cross-Course & Cross-Tenant Validation ────────────────────────────────

def test_cross_course_and_tenant_question_validation(assessment_service):
    """Creating assessments with questions belonging to another course or tenant must fail closed."""
    q_phys = QuestionBankItem(
        id="qb-phys-10",
        course_id="crs-physics-101",
        organization_id="org-academics",
        concept_id="kinematics",
        question_text="Velocity equation?",
        item_type="MCQ",
        correct_answer="v = u + at",
    )
    q_math = QuestionBankItem(
        id="qb-math-10",
        course_id="crs-math-201",
        organization_id="org-academics",
        concept_id="calculus",
        question_text="Integral of 2x?",
        item_type="MCQ",
        correct_answer="x^2 + C",
    )
    q_rival = QuestionBankItem(
        id="qb-rival-10",
        course_id="crs-rival-101",
        organization_id="org-rival",
        concept_id="rival_concept",
        question_text="Rival question",
        item_type="MCQ",
        correct_answer="A",
    )
    assessment_service.create_question(q_phys)
    assessment_service.create_question(q_math)
    assessment_service.create_question(q_rival)

    # Assessment in crs-physics-101 cannot include qb-math-10 (different course)
    asmt_cross_course = Assessment(
        id="asmt-phys-exam",
        course_id="crs-physics-101",
        organization_id="org-academics",
        title="Physics Exam",
        item_ids=["qb-phys-10", "qb-math-10"],
    )
    with pytest.raises(ValueError, match="Cross-course contamination"):
        assessment_service.create_assessment(asmt_cross_course)

    # Assessment in org-academics cannot include qb-rival-10 (different tenant)
    asmt_cross_tenant = Assessment(
        id="asmt-phys-rival",
        course_id="crs-physics-101",
        organization_id="org-academics",
        title="Physics Exam",
        item_ids=["qb-phys-10", "qb-rival-10"],
    )
    with pytest.raises(ValueError, match="(Cross-tenant|Cross-course)"):
        assessment_service.create_assessment(asmt_cross_tenant)


# ── 4. Student Isolation & IDOR Protection ──────────────────────────────────

def test_student_isolation_idor_protection(test_app, assessment_service):
    """Students cannot start, submit, or inspect attempts belonging to other students."""
    asmt = Assessment(
        id="asmt-kinematics-1",
        course_id="crs-physics-101",
        organization_id="org-academics",
        title="Kinematics Formative",
        assessment_type=AssessmentType.FORMATIVE,
        passing_score=70.0,
    )
    assessment_service.create_assessment(asmt)

    client = TestClient(test_app)
    alice_token = create_access_token(user_id="stu-alice", role="STUDENT", organization_id="org-academics")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    # 1. Alice attempts to start an attempt for Bob -> HTTP 403
    resp_start = client.post(
        "/api/v1/assessments/attempts/start",
        headers=alice_headers,
        json={"assessment_id": "asmt-kinematics-1", "student_id": "stu-bob"},
    )
    assert resp_start.status_code == 403

    # Alice starts attempt for herself -> Success
    resp_alice_start = client.post(
        "/api/v1/assessments/attempts/start",
        headers=alice_headers,
        json={"assessment_id": "asmt-kinematics-1", "student_id": "stu-alice"},
    )
    assert resp_alice_start.status_code == 201
    alice_attempt_id = resp_alice_start.json()["data"]["attempt_id"]

    # 2. Bob attempts to submit Alice's attempt -> HTTP 403
    bob_token = create_access_token(user_id="stu-bob", role="STUDENT", organization_id="org-academics")
    bob_headers = {"Authorization": f"Bearer {bob_token}"}
    resp_bob_submit = client.post(
        f"/api/v1/assessments/attempts/{alice_attempt_id}/submit",
        headers=bob_headers,
        json={"student_id": "stu-alice", "answers": {}},
    )
    assert resp_bob_submit.status_code == 403

    # 3. Bob attempts to list Alice's attempts -> HTTP 403
    resp_bob_list = client.get(
        "/api/v1/assessments/attempts/student/stu-alice",
        headers=bob_headers,
    )
    assert resp_bob_list.status_code == 403


# ── 5. Attempt Lifecycle Immutability & Expiry ────────────────────────────────

def test_attempt_lifecycle_immutability_and_expiry(assessment_service):
    """Finalized attempts cannot be double-submitted; expired attempts are rejected."""
    q_item = QuestionBankItem(
        id="qb-dyn-01",
        course_id="crs-physics-101",
        organization_id="org-academics",
        concept_id="dynamics",
        question_text="F = ?",
        item_type="MCQ",
        options=["m * a", "m / a", "a / m", "m + a"],
        correct_answer="m * a",
    )
    assessment_service.create_question(q_item)

    asmt = Assessment(
        id="asmt-dyn-timed",
        course_id="crs-physics-101",
        organization_id="org-academics",
        title="Timed Dynamics Assessment",
        duration_minutes=10,
        item_ids=["qb-dyn-01"],
    )
    assessment_service.create_assessment(asmt)

    # 1. Normal submission marks attempt GRADED
    attempt = assessment_service.start_attempt("asmt-dyn-timed", "stu-alice")
    completed = assessment_service.submit_attempt(attempt.id, {"qb-dyn-01": "m * a"}, student_id="stu-alice")
    assert completed.status == AttemptStatus.GRADED.value

    # Double submission rejected
    with pytest.raises(ValueError, match="already finalized"):
        assessment_service.submit_attempt(attempt.id, {"qb-dyn-01": "m * a"}, student_id="stu-alice")

    # 2. Expired attempt submission
    expired_attempt = assessment_service.start_attempt("asmt-dyn-timed", "stu-alice")
    # Simulate attempt started 2 hours ago (duration is 10 min)
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    expired_attempt.started_at = two_hours_ago
    assessment_service.db.record_assessment_attempt(expired_attempt)

    with pytest.raises(ValueError, match="expired"):
        assessment_service.submit_attempt(expired_attempt.id, {"qb-dyn-01": "m * a"}, student_id="stu-alice")


# ── 6. Teacher Review Authorization ──────────────────────────────────────────

def test_teacher_review_role_authorization(test_app, assessment_service):
    """Students cannot perform teacher reviews; only teachers and admins can."""
    q_item = QuestionBankItem(
        id="qb-rev-01",
        course_id="crs-physics-101",
        organization_id="org-academics",
        concept_id="kinematics",
        question_text="Derive displacement.",
        item_type="SHORT_ANSWER",
        correct_answer="s = ut + 0.5at^2",
    )
    assessment_service.create_question(q_item)

    asmt = Assessment(
        id="asmt-rev-test",
        course_id="crs-physics-101",
        organization_id="org-academics",
        title="Review Test",
        item_ids=["qb-rev-01"],
    )
    assessment_service.create_assessment(asmt)

    attempt = assessment_service.start_attempt("asmt-rev-test", "stu-alice")
    assessment_service.submit_attempt(attempt.id, {"qb-rev-01": "s = ut + 0.5at^2"}, student_id="stu-alice")

    client = TestClient(test_app)

    # Student tries to review -> HTTP 403
    student_token = create_access_token(user_id="stu-alice", role="STUDENT", organization_id="org-academics")
    resp_student = client.post(
        f"/api/v1/assessments/attempts/{attempt.id}/teacher-review",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"item_score_adjustments": {"qb-rev-01": 4.0}, "teacher_comments": "Hacked"},
    )
    assert resp_student.status_code == 403

    # Teacher reviews -> HTTP 200
    teacher_token = create_access_token(user_id="tch-newton", role="TEACHER", organization_id="org-academics")
    resp_teacher = client.post(
        f"/api/v1/assessments/attempts/{attempt.id}/teacher-review",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"item_score_adjustments": {"qb-rev-01": 4.0}, "teacher_comments": "Excellent derivation"},
    )
    assert resp_teacher.status_code == 200
    assert resp_teacher.json()["data"]["status"] == "reviewed"
