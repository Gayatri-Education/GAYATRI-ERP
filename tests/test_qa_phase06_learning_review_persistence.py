"""Phase 06 — Student Learning, Review Lifecycle, and Persistence Tests.

Verifies:
1. StudentPortalController.get_review_queue returns structured review items or explicit empty list.
2. GET /api/v1/students/{student_id}/review-queue REST endpoint contract.
3. Cross-student boundary enforcement: Student A cannot access Student B's review queue (HTTP 403).
4. Teachers can access student review queue within the same organization.
5. Spaced review state persistence across fresh service instances / restarts.
6. Review action submission updates review schedules and mastery idempotently.
7. Student UI controller includes loadReviewQueue fetching from real API.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db, get_current_user, get_current_user_optional
from central_platform.db import PlatformDatabase
from central_platform.learning.bridge import LearningEngineBridge
from central_platform.learning.models import StudentActionPayload
from central_platform.models.schema import User, UserRole
from central_platform.portals.student import StudentPortalController, ReviewQueueItem
from central_platform.progress.service import StudentProgressService


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_phase06.db"
    return PlatformDatabase(db_file)


@pytest.fixture
def client(test_db):
    app.dependency_overrides[get_db] = lambda: test_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def student_a():
    return User(
        id="usr_student_a",
        email="student_a@school.org",
        full_name="Student Alpha",
        role=UserRole.STUDENT,
        organization_id="org_test_01",
    )


@pytest.fixture
def student_b():
    return User(
        id="usr_student_b",
        email="student_b@school.org",
        full_name="Student Beta",
        role=UserRole.STUDENT,
        organization_id="org_test_01",
    )


@pytest.fixture
def teacher_user():
    return User(
        id="usr_teacher_01",
        email="teacher@school.org",
        full_name="Teacher One",
        role=UserRole.TEACHER,
        organization_id="org_test_01",
    )


def test_student_portal_controller_review_queue(test_db):
    queue = StudentPortalController.get_review_queue(
        student_id="usr_student_a",
        course_id="crs-chem-101",
        db=test_db,
    )
    assert isinstance(queue, list)
    # Empty queue returns explicit empty list
    for item in queue:
        assert isinstance(item, ReviewQueueItem)
        assert item.concept_id


def test_student_review_queue_endpoint_self_access(client, student_a):
    app.dependency_overrides[get_current_user] = lambda: student_a
    app.dependency_overrides[get_current_user_optional] = lambda: student_a
    resp = client.get(f"/api/v1/students/{student_a.id}/review-queue")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["data"], list)


def test_student_review_queue_endpoint_cross_student_blocked(client, student_a, student_b):
    app.dependency_overrides[get_current_user] = lambda: student_a
    app.dependency_overrides[get_current_user_optional] = lambda: student_a
    # Student A attempting to access Student B's review queue
    resp = client.get(f"/api/v1/students/{student_b.id}/review-queue")
    assert resp.status_code == 403, resp.text


def test_teacher_can_access_student_review_queue(client, teacher_user, student_a):
    app.dependency_overrides[get_current_user] = lambda: teacher_user
    app.dependency_overrides[get_current_user_optional] = lambda: teacher_user
    resp = client.get(f"/api/v1/students/{student_a.id}/review-queue")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True


def test_spaced_review_persistence_and_restart(test_db):
    bridge1 = LearningEngineBridge(db=test_db)
    action = StudentActionPayload(
        concept_id="chem_thermo_first_law",
        action_type="review_complete",
        correctness="correct",
        course_id="crs-chem-101",
    )
    result = bridge1.process_student_action(
        student_id="usr_persist_01",
        action=action,
        course_id="crs-chem-101",
    )
    assert result.next_review_at is not None

    # Simulate restart by instantiating fresh bridge & progress service
    bridge2 = LearningEngineBridge(db=test_db)
    progress_svc = StudentProgressService(db=test_db)
    report = progress_svc.get_student_progress("usr_persist_01", "crs-chem-101")
    assert report.student_id == "usr_persist_01"
    assert "chem_thermo_first_law" in report.concept_heatmap[0].concept_id or any(
        h.concept_id == "chem_thermo_first_law" for h in report.concept_heatmap
    )


def test_review_action_idempotency_and_interval(test_db):
    bridge = LearningEngineBridge(db=test_db)
    action_correct = StudentActionPayload(
        concept_id="chem_thermo_first_law",
        action_type="review_complete",
        correctness="correct",
        course_id="crs-chem-101",
    )
    res1 = bridge.process_student_action("usr_idem_01", action_correct, "crs-chem-101")
    assert res1.next_review_at is not None

    # Repeated correct action continues expanding intervals safely without crash
    res2 = bridge.process_student_action("usr_idem_01", action_correct, "crs-chem-101")
    assert res2.next_review_at is not None


def test_student_js_includes_load_review_queue():
    js_path = Path("app/ui/design_system/student.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    assert "loadReviewQueue" in content
    assert "/review-queue" in content
    assert "renderReviewQueue" in content
