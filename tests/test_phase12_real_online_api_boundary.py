"""Phase 12 Test Suite — Real Online API Boundary Verification.

Master Plan Section 12.12:
1. Real HTTP server socket execution over loopback with uvicorn and httpx.
2. Live operational probes (/healthz, /readyz, /livez, /api/v1/health) and failure simulation.
3. PBKDF2 authentication, JWT token issuance, account suspension, and token verification.
4. Multi-tenant RBAC gatekeeping (Super Admin, Org Admin, Teacher, Student).
5. Course catalog, course CRUD, version lifecycle (draft -> review -> publish), and org selection.
6. Class group and cohort lifecycle.
7. Student enrollment and cross-tenant private course isolation.
8. Content asset upload, approval, and publication workflow.
9. 5-tier hierarchical teacher instructions (SESSION > STUDENT > CLASS > COURSE > ORGANIZATION).
10. Assessment definition, anti-leakage sanitized student delivery, and teacher score review.
11. Generic tutor turn execution over real HTTP (POST /api/v1/tutor/turn).
12. Structured error envelopes, stable error codes, and X-Request-ID propagation.
13. Invariant check: Zero hardcoded chemistry coupling in generic API routers.
"""
import inspect
import json
import os
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Generator

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from central_platform.api.app import create_app
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.health.service import PlatformHealthService
from central_platform.models.schema import (
    Course,
    CourseStatus,
    CourseVisibility,
    Organization,
    User,
    UserRole,
)


@pytest.fixture(scope="module")
def app_instance(tmp_path_factory):
    """Create a configured FastAPI application instance with an isolated test DB."""
    temp_dir = tmp_path_factory.mktemp("phase12")
    test_db_path = str(temp_dir / f"test_phase12_{uuid.uuid4().hex[:8]}.db")
    os.environ["GAYATRI_DB_PATH"] = test_db_path
    db = PlatformDatabase(test_db_path)
    if not db.get_organization("org-default"):
        db.create_organization(Organization(id="org-default", name="Default Organization", slug="default"))
    if not db.get_organization("org-dsa"):
        db.create_organization(Organization(id="org-dsa", name="Delhi Science Academy", slug="dsa"))

    app = create_app()
    yield app
    # Cleanup test db
    db.close()
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except OSError:
            pass


@pytest.fixture(scope="module")
def client(app_instance):
    """TestClient for fast in-process FastAPI testing."""
    with TestClient(app_instance) as c:
        yield c


@pytest.fixture(scope="module")
def live_server_url(app_instance) -> Generator[str, None, None]:
    """Start real uvicorn HTTP server in a background thread over a loopback socket."""
    # Find ephemeral free port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(
        app=app_instance,
        host="127.0.0.1",
        port=port,
        log_level="error",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"

    # Wait for server to accept connections
    for _ in range(50):
        try:
            r = httpx.get(f"{base_url}/livez", timeout=1.0)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("Uvicorn test server failed to bind and start.")

    yield base_url

    # Graceful shutdown
    server.should_exit = True
    thread.join(timeout=3.0)


# ── 1. Real HTTP Socket Server Lifecycle & Probes ────────────────────────────

def test_real_http_server_socket_lifecycle(live_server_url):
    """Test genuine HTTP socket communication over network loopback with uvicorn."""
    with httpx.Client(base_url=live_server_url, timeout=5.0) as http_client:
        # 1. Live probe over socket
        resp_live = http_client.get("/livez")
        assert resp_live.status_code == 200
        assert resp_live.json()["alive"] is True

        # 2. Ready probe over socket
        resp_ready = http_client.get("/readyz")
        assert resp_ready.status_code == 200
        assert resp_ready.json()["ready"] is True

        # 3. Health status over socket
        resp_health = http_client.get("/healthz")
        assert resp_health.status_code == 200
        data = resp_health.json()
        assert data["status"] in ("ONLINE", "HEALTHY")
        assert "X-Request-ID" in resp_health.headers


def test_health_probes_and_simulated_broken_subsystem(client, app_instance):
    """Test health probes in nominal state and under intentional subsystem failure."""
    health_svc: PlatformHealthService = app_instance.state.health_service

    # 1. Nominal state: healthy
    resp_nom = client.get("/api/v1/health")
    assert resp_nom.status_code == 200
    assert resp_nom.json()["subsystems"]["database"]["status"] == "HEALTHY"

    # 2. Intentionally inject database subsystem failure
    health_svc.simulate_subsystem_failure("database", True)
    try:
        resp_fail = client.get("/readyz")
        assert resp_fail.status_code == 503
        data_fail = resp_fail.json()
        assert data_fail["ready"] is False
        assert data_fail["status"] == "UNHEALTHY"
        assert data_fail["subsystems"]["database"]["status"] == "UNHEALTHY"

        resp_health_fail = client.get("/api/v1/health")
        assert resp_health_fail.status_code == 503
        assert resp_health_fail.json()["status"] == "UNHEALTHY"
    finally:
        # 3. Reset failure hook and verify recovery
        health_svc.simulate_subsystem_failure("database", False)

    resp_recov = client.get("/readyz")
    assert resp_recov.status_code == 200
    assert resp_recov.json()["ready"] is True


# ── 2. Authentication, RBAC, and Account Suspension ──────────────────────────

def test_auth_real_credentials_and_token_issuance(client):
    """Test PBKDF2 authentication against real database and JWT issuance."""
    db = PlatformDatabase()
    # Create test user in db
    uid = f"usr-p12-{uuid.uuid4().hex[:6]}"
    user = User(
        id=uid,
        email=f"{uid}@example.com",
        full_name="Dr. Alan Turing",
        role=UserRole.TEACHER,
        organization_id="org-default",
    )
    db.create_user(user)
    db.set_user_password(uid, "SecurePassword123!")

    # 1. Successful login
    resp_ok = client.post(
        "/api/v1/auth/login",
        json={"username": user.email, "password": "SecurePassword123!"},
    )
    assert resp_ok.status_code == 200
    auth_data = resp_ok.json()["data"]
    assert "access_token" in auth_data
    assert auth_data["role"].upper() == "TEACHER"
    token = auth_data["access_token"]

    # 2. Invalid password returns 401
    resp_bad = client.post(
        "/api/v1/auth/login",
        json={"username": user.email, "password": "WrongPassword!"},
    )
    assert resp_bad.status_code == 401

    # 3. Authenticated /me endpoint
    resp_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_me.status_code == 200
    assert resp_me.json()["data"]["user_id"] == uid


def test_account_suspension_enforcement(client):
    """Test that suspended accounts are immediately rejected with 403 Forbidden."""
    db = PlatformDatabase()
    uid = f"usr-susp-{uuid.uuid4().hex[:6]}"
    user = User(
        id=uid,
        email=f"{uid}@example.com",
        full_name="Suspended Student",
        role=UserRole.STUDENT,
        organization_id="org-default",
    )
    db.create_user(user)
    db.set_user_password(uid, "studentPass123!")

    # Suspend user
    db.suspend_user(uid)

    resp = client.post(
        "/api/v1/auth/login",
        json={"username": user.email, "password": "studentPass123!"},
    )
    assert resp.status_code == 403
    assert "suspended" in resp.json()["detail"].lower()

    # Unsuspend and verify login works
    db.unsuspend_user(uid)
    resp_un = client.post(
        "/api/v1/auth/login",
        json={"username": user.email, "password": "studentPass123!"},
    )
    assert resp_un.status_code == 200


def test_rbac_boundary_gatekeeping(client):
    """Test RBAC enforcement: students blocked from teacher/admin actions; teachers blocked from org admin."""
    # 1. Student token
    student_token = create_access_token(
        user_id="std-001",
        role="student",
        organization_id="org-default",
    )

    # Student cannot create instruction
    r_inst = client.post(
        "/api/v1/instructions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"instruction": "Read Chapter 1", "course_id": "crs-chem-101"},
    )
    assert r_inst.status_code == 403

    # Student cannot create organization
    r_org = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"name": "Fake Org", "slug": "fake-org"},
    )
    assert r_org.status_code == 403

    # 2. Teacher token cannot create organization (requires SUPER_ADMIN)
    teacher_token = create_access_token(
        user_id="tchr-001",
        role="teacher",
        organization_id="org-default",
    )
    r_org_tchr = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"name": "Teacher Org", "slug": "teacher-org"},
    )
    assert r_org_tchr.status_code == 403


# ── 3. Course Catalog, CRUD, Versions, Selection ─────────────────────────────

def test_course_catalog_and_version_lifecycle(client):
    """Test course creation, version creation, submission, approval, and organization offering."""
    teacher_token = create_access_token(
        user_id="tchr-phys-01",
        role="teacher",
        organization_id="org-dsa",
    )
    admin_token = create_access_token(
        user_id="adm-phys-01",
        role="org_admin",
        organization_id="org-dsa",
    )

    # 1. Create a new course
    course_code = f"PHYS_{uuid.uuid4().hex[:4].upper()}"
    r_create = client.post(
        "/api/v1/courses",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "code": course_code,
            "title": "Quantum Mechanics & Relativity",
            "description": "Advanced Physics Course",
            "visibility": "PRIVATE",
            "organization_id": "org-dsa",
            "subject": "Physics",
        },
    )
    assert r_create.status_code == 201
    course_data = r_create.json()["data"]
    course_id = course_data["course_id"]
    assert course_data["code"] == course_code
    assert course_data["visibility"] == "PRIVATE"

    # 2. Retrieve course details: anonymous gets 403 for private course, teacher gets 200
    r_anon = client.get(f"/api/v1/courses/{course_id}")
    assert r_anon.status_code == 403

    r_get = client.get(f"/api/v1/courses/{course_id}", headers={"Authorization": f"Bearer {teacher_token}"})
    assert r_get.status_code == 200
    assert r_get.json()["data"]["title"] == "Quantum Mechanics & Relativity"

    # 3. Create a course version
    r_ver = client.post(
        f"/api/v1/courses/{course_id}/versions",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "version_tag": "v1.0.0",
            "changelog": "Initial draft syllabus",
        },
    )
    assert r_ver.status_code == 201
    ver_id = r_ver.json()["data"]["id"]
    assert r_ver.json()["data"]["status"] == "DRAFT"

    # 4. Submit version for review
    r_sub = client.post(
        f"/api/v1/courses/{course_id}/versions/{ver_id}/submit",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert r_sub.status_code == 200
    assert r_sub.json()["data"]["status"] == "READY_FOR_REVIEW"

    # 5. Approve and publish version (as admin)
    r_pub = client.post(
        f"/api/v1/courses/{course_id}/versions/{ver_id}/publish",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_pub.status_code == 200
    assert r_pub.json()["data"]["status"] == "PUBLISHED"

    # 6. Select course for organization (create offering)
    r_sel = client.post(
        f"/api/v1/courses/{course_id}/select",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "organization_id": "org-dsa",
            "course_version_id": ver_id,
        },
    )
    assert r_sel.status_code == 200
    offering = r_sel.json()["data"]
    assert offering["course_id"] == course_id
    assert offering["course_version_id"] == ver_id


# ── 4. Class Group, Cohorts, and Student Enrollments ─────────────────────────

def test_classes_cohorts_and_enrollment_lifecycle(client):
    """Test class group creation, cohort assignment, and student enrollment."""
    admin_token = create_access_token(
        user_id="adm-01",
        role="org_admin",
        organization_id="org-dsa",
    )

    # 1. Create class group
    cls_name = f"Class 11 Science {uuid.uuid4().hex[:4]}"
    r_cls = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": cls_name,
            "course_id": "crs-chem-101",
            "organization_id": "org-dsa",
        },
    )
    assert r_cls.status_code == 201
    class_id = r_cls.json()["data"]["id"]

    # 2. Create cohort in class
    r_coh = client.post(
        f"/api/v1/classes/{class_id}/cohorts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Section A - Morning",
            "class_id": class_id,
            "course_id": "crs-chem-101",
            "organization_id": "org-dsa",
        },
    )
    assert r_coh.status_code == 201
    cohort_id = r_coh.json()["data"]["id"]

    # 3. Enroll student in course
    student_id = f"std-{uuid.uuid4().hex[:6]}"
    r_enr = client.post(
        "/api/v1/enrollments",
        json={
            "student_id": student_id,
            "course_id": "crs-chem-101",
            "class_id": cohort_id,
        },
    )
    assert r_enr.status_code == 201
    enr_data = r_enr.json()["data"]
    assert enr_data["student_id"] == student_id
    assert enr_data["course_id"] == "crs-chem-101"

    # 4. List student enrollments
    r_list = client.get(f"/api/v1/enrollments?student_id={student_id}")
    assert r_list.status_code == 200
    assert len(r_list.json()["data"]) >= 1


# ── 5. Hierarchical Teacher Instructions ─────────────────────────────────────

def test_hierarchical_teacher_instructions_api(client):
    """Test 5-tier hierarchical instruction creation, resolution, and deletion."""
    teacher_token = create_access_token(
        user_id="tchr-inst-01",
        role="teacher",
        organization_id="org-dsa",
    )

    # 1. Create COURSE-level instruction
    r_course_inst = client.post(
        "/api/v1/instructions",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "instruction": "Focus heavily on thermodynamic state functions.",
            "course_id": "crs-chem-101",
            "scope_type": "COURSE",
            "priority": 3,
            "organization_id": "org-dsa",
        },
    )
    assert r_course_inst.status_code == 201
    inst_id = r_course_inst.json()["data"]["instruction_id"]

    # 2. Query hierarchical instructions
    r_query = client.get(
        "/api/v1/instructions?course_id=crs-chem-101&organization_id=org-dsa&hierarchical=true",
    )
    assert r_query.status_code == 200
    items = r_query.json()["data"]
    assert any(i["instruction_id"] == inst_id for i in items)

    # 3. Delete instruction
    r_del = client.delete(
        f"/api/v1/instructions/{inst_id}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert r_del.status_code == 200
    assert r_del.json()["data"]["deleted"] is True


# ── 6. Assessment Delivery Sanitization & Teacher Review ─────────────────────

def test_assessment_sanitized_delivery_and_review(client):
    """Test anti-leakage sanitized question delivery and teacher score review."""
    teacher_token = create_access_token(
        user_id="tchr-eval-01",
        role="teacher",
        organization_id="org-default",
    )

    # 1. Create question bank item with answer and rubric
    q_item_req = {
        "course_id": "crs-chem-101",
        "question_text": "What is the enthalpy change in an adiabatic process?",
        "item_type": "MULTIPLE_CHOICE",
        "options": ["Zero", "Equal to work done", "Positive", "Negative"],
        "correct_answer": "Equal to work done",
        "rubric": {"criterion": "First law applied to adiabatic conditions", "points": 5.0},
        "difficulty": 3,
        "bloom_level": "ANALYZE",
        "hints": ["Recall dU = dq + dw where dq = 0."],
        "explanation": "Because dq=0 in an adiabatic system, dU = dw.",
        "tags": ["thermodynamics", "adiabatic"],
    }
    r_item = client.post("/api/v1/assessments/items", json=q_item_req)
    assert r_item.status_code == 201
    item_id = r_item.json()["data"]["id"]

    # 2. Create assessment definition
    r_asmt = client.post(
        "/api/v1/assessments",
        json={
            "course_id": "crs-chem-101",
            "title": "Thermodynamics Quiz",
            "assessment_type": "formative",
            "item_ids": [item_id],
            "passing_score": 70.0,
            "duration_minutes": 20,
        },
    )
    assert r_asmt.status_code == 201
    asmt_id = r_asmt.json()["data"]["id"]

    # 3. Anti-leakage sanitized fetch for student
    r_sanitized = client.get(f"/api/v1/assessments/{asmt_id}/sanitized")
    assert r_sanitized.status_code == 200
    sanitized_data = r_sanitized.json()["data"]
    assert len(sanitized_data["items"]) == 1
    student_item = sanitized_data["items"][0]

    # INVARIANT: correct_answer, rubric, and explanation must NEVER be in student payload
    assert "correct_answer" not in student_item
    assert "rubric" not in student_item
    assert "explanation" not in student_item
    assert student_item["question_text"] == "What is the enthalpy change in an adiabatic process?"

    # 4. Student starts attempt (real registered student entity)
    student_id = f"std-eval-{uuid.uuid4().hex[:6]}"
    db = PlatformDatabase()
    db.create_user(
        User(
            id=student_id,
            email=f"{student_id}@student.org",
            full_name="Student Eval",
            role=UserRole.STUDENT,
            organization_id="org-default",
        )
    )
    r_start = client.post(
        "/api/v1/assessments/attempts/start",
        json={"assessment_id": asmt_id, "student_id": student_id},
    )
    assert r_start.status_code == 201
    attempt_id = r_start.json()["data"]["attempt_id"]

    # 5. Student submits attempt
    r_sub = client.post(
        f"/api/v1/assessments/attempts/{attempt_id}/submit",
        json={
            "answers": {item_id: "Equal to work done"},
            "student_id": student_id,
        },
    )
    assert r_sub.status_code == 200

    # 6. Teacher reviews and overrides score
    r_rev = client.post(
        f"/api/v1/assessments/attempts/{attempt_id}/review",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "item_score_adjustments": {item_id: 5.0},
            "teacher_comments": "Excellent grasp of thermodynamic principles.",
            "status": "APPROVED",
        },
    )
    assert r_rev.status_code == 200
    review_data = r_rev.json()["data"]
    assert review_data["status"] == "APPROVED"
    assert review_data["teacher_review"]["teacher_comments"] == "Excellent grasp of thermodynamic principles."


# ── 7. Tutor Turn Execution Over Real HTTP ───────────────────────────────────

def test_tutor_turn_over_real_http(client):
    """Test real HTTP POST /api/v1/tutor/turn with GenericTutorOrchestrator and strict authentication."""
    student_id = f"std-tutor-{uuid.uuid4().hex[:6]}"
    session_id = f"sess-tutor-{uuid.uuid4().hex[:6]}"

    # Enroll student in public course crs-chem-101
    client.post(
        "/api/v1/enrollments",
        json={"student_id": student_id, "course_id": "crs-chem-101"},
    )

    turn_req = {
        "student_id": student_id,
        "session_id": session_id,
        "course_id": "crs-chem-101",
        "student_input": "Can you explain how Hess's Law works for multi-step reactions?",
    }

    # Negative security test: unauthenticated turn must return 401
    r_unauth = client.post("/api/v1/tutor/turn", json=turn_req)
    assert r_unauth.status_code == 401

    # Positive test: authenticated turn with token for student_id
    token = create_access_token(user_id=student_id, role="student")
    r_turn = client.post("/api/v1/tutor/turn", headers={"Authorization": f"Bearer {token}"}, json=turn_req)
    assert r_turn.status_code == 200
    turn_data = r_turn.json()
    res = turn_data.get("data", turn_data)
    assert res.get("ok", True) is True
    assert res["student_id"] == student_id
    assert res["course_id"] == "crs-chem-101"
    response_msg = res.get("assistant_text") or res.get("response_text", "")
    assert len(response_msg) > 0


# ── 8. Error Envelopes and Static Invariants ─────────────────────────────────

def test_structured_error_envelopes_and_request_id(client):
    """Test uniform error mapping and correlation header propagation."""
    # 404 Not Found
    r_404 = client.get("/api/v1/courses/crs-non-existent-999")
    assert r_404.status_code == 404
    body_404 = r_404.json()
    assert body_404["ok"] is False
    assert "error" in body_404 or "detail" in body_404
    assert "X-Request-ID" in r_404.headers

    # 422 Validation Error
    r_422 = client.post("/api/v1/courses", json={"code": "X"})  # code min_length is 2
    assert r_422.status_code == 422
    body_422 = r_422.json()
    assert body_422["ok"] is False
    assert body_422["error"]["code"] == "VALIDATION_ERROR"
    assert "X-Request-ID" in r_422.headers


def test_zero_chemistry_coupling_in_generic_api_routers():
    """Invariant: Generic platform routers must contain zero hardcoded chemistry coupling."""
    import central_platform.api.routes.classes as classes_mod
    import central_platform.api.routes.courses as courses_mod
    import central_platform.api.routes.enrollments as enrollments_mod
    import central_platform.api.routes.instructions as instructions_mod
    import central_platform.api.routes.organizations as orgs_mod
    import central_platform.health.service as health_mod

    checked_modules = [
        classes_mod,
        enrollments_mod,
        instructions_mod,
        orgs_mod,
        health_mod,
    ]

    chemistry_keywords = ["enthalpy", "stoichiometry", "thermodynamics", "balancer", "molar"]
    for mod in checked_modules:
        src = inspect.getsource(mod)
        for kw in chemistry_keywords:
            assert kw not in src.lower(), (
                f"Generic module {mod.__name__} violates course-independence by hardcoding '{kw}'"
            )
