"""Phase 02 Test Suite — Production FastAPI Platform API Verification.

Tests:
1. Health, readiness, and liveness probes (/healthz, /readyz, /livez).
2. Backwards-compatibility routes (/api/health, /api/student/snapshot, /api/teacher/*).
3. 16 versioned route groups under /api/v1/*.
4. Request correlation ID propagation (X-Request-ID).
5. Structured error envelopes on 404, 422 validation errors.
6. HTML Teacher Command Center rendering at /.
"""
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token


@pytest.fixture(scope="module")
def client():
    """Create test client for FastAPI application."""
    with TestClient(app) as c:
        yield c


# ── 1. Probes & Health Checks ────────────────────────────────────────────

def test_healthz_probe(client):
    """Test /healthz endpoint returns 200 with service metadata."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ONLINE"
    assert data["database"] == "CONNECTED"
    assert "X-Request-ID" in resp.headers


def test_readyz_and_livez_probes(client):
    """Test /readyz and /livez endpoints return ready/alive states."""
    r_ready = client.get("/readyz")
    assert r_ready.status_code == 200
    assert r_ready.json()["ready"] is True

    r_live = client.get("/livez")
    assert r_live.status_code == 200
    assert r_live.json()["alive"] is True


# ── 2. Backwards-Compatibility Endpoints ─────────────────────────────────

def test_legacy_api_health(client):
    """Test legacy /api/health endpoint returns expected status for existing clients."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["service"] == "TeacherPortalServer"
    assert data["students_monitored"] >= 5


def test_legacy_student_snapshot_sync(client):
    """Test legacy /api/student/snapshot route accepts telemetry and updates roster."""
    payload = {
        "student_id": "test_sync_std_01",
        "student_name": "Test Student 01",
        "mastery": 0.88,
        "needs_attention": False,
        "misconceptions": ["THERMO_SIGN_CONVENTION"],
        "hint_count": 1,
        "retention_rate": 0.92,
    }
    resp = client.post("/api/student/snapshot", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["student_id"] == "test_sync_std_01"


def test_legacy_teacher_instruction_lifecycle(client):
    """Test creating, fetching, and toggling teacher instructions via legacy routes."""
    # Create instruction
    create_payload = {
        "instruction": "Enforce strict sign conventions on thermodynamics problems.",
        "student_id": "test_sync_std_01",
        "course_id": "crs-chem-101",
        "priority": 3,
    }
    r_create = client.post("/api/teacher/instruction", json=create_payload)
    assert r_create.status_code == 200
    inst_id = r_create.json()["instruction_id"]

    # Fetch instruction
    r_get = client.get(f"/api/teacher/instructions?student_id=test_sync_std_01&course_id=crs-chem-101")
    assert r_get.status_code == 200
    instructions = r_get.json()["instructions"]
    assert any(i["instruction_id"] == inst_id for i in instructions)

    # Toggle instruction
    r_toggle = client.post("/instruction/toggle", json={"instruction_id": inst_id, "active": False})
    assert r_toggle.status_code == 200
    assert r_toggle.json()["active"] is False


def test_legacy_alert_resolve(client):
    """Test legacy /alert/resolve endpoint."""
    r_resolve = client.post("/alert/resolve", json={"alert_id": "alrt-001", "resolution_note": "Addressed in tutoring"})
    assert r_resolve.status_code == 200
    assert r_resolve.json()["alert_id"] == "alrt-001"


# ── 3. Versioned API Endpoints (/api/v1/*) ────────────────────────────────

def test_v1_auth_endpoints(client):
    """Test /api/v1/auth/login and /api/v1/auth/me."""
    # Valid login
    login_resp = client.post("/api/v1/auth/login", json={"username": "teacher_1", "password": "password"})
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["ok"] is True
    assert body["data"]["role"] == "TEACHER"
    assert "access_token" in body["data"]

    # Current user
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['data']['access_token']}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["role"] == "TEACHER"


def test_v1_users_endpoints(client):
    """Test /api/v1/users listing, creation, and lookup."""
    # List users
    r_list = client.get("/api/v1/users?role=TEACHER")
    assert r_list.status_code == 200
    users = r_list.json()["data"]
    assert len(users) >= 1
    assert all(u["role"] == "TEACHER" for u in users)

    # Create user
    new_user_payload = {
        "username": "new_tutor_user",
        "email": "tutor@gayatri.ai",
        "password": "securepass123",
        "role": "TEACHER",
        "organization_id": "org-central",
    }
    r_create = client.post("/api/v1/users", json=new_user_payload)
    assert r_create.status_code == 201
    created = r_create.json()["data"]
    assert created["username"] == "new_tutor_user"

    # Lookup user
    r_get = client.get(f"/api/v1/users/{created['user_id']}")
    assert r_get.status_code == 200
    assert r_get.json()["data"]["email"] == "tutor@gayatri.ai"


def test_v1_students_endpoints(client):
    """Test /api/v1/students profile, snapshot, and SLR."""
    # Snapshot
    snap_payload = {
        "student_id": "v1_std_01",
        "student_name": "V1 Test Student",
        "course_id": "crs-chem-101",
        "mastery": 0.85,
        "needs_attention": False,
        "misconceptions": [],
        "hint_count": 0,
        "retention_rate": 0.90,
    }
    r_snap = client.post("/api/v1/students/snapshot", json=snap_payload)
    assert r_snap.status_code == 200
    assert r_snap.json()["data"]["status"] == "ACCEPTED"

    # Profile lookup
    r_prof = client.get("/api/v1/students/v1_std_01")
    assert r_prof.status_code == 200
    prof = r_prof.json()["data"]
    assert prof["student_id"] == "v1_std_01"
    assert prof["mastery"] == 0.85

    # SLR lookup
    r_slr = client.get("/api/v1/students/v1_std_01/slr")
    assert r_slr.status_code == 200
    assert r_slr.json()["data"]["authoritative"] is True


def test_v1_teachers_endpoints(client):
    """Test /api/v1/teachers dashboard, instruction creation, and copilot briefing."""
    # Dashboard
    r_dash = client.get("/api/v1/teachers/dashboard?course_id=crs-chem-101")
    assert r_dash.status_code == 200
    dash = r_dash.json()["data"]
    assert dash["total_students"] >= 5
    assert "mastery_distribution" in dash

    # Create instruction
    inst_payload = {
        "instruction": "Explain Gibbs free energy from first principles.",
        "student_id": "v1_std_01",
        "course_id": "crs-chem-101",
        "priority": 4,
    }
    r_inst = client.post("/api/v1/teachers/instructions", json=inst_payload)
    assert r_inst.status_code == 201
    created_inst = r_inst.json()["data"]
    assert created_inst["priority"] == 4

    # Copilot briefing
    r_copilot = client.get("/api/v1/teachers/copilot/briefing")
    assert r_copilot.status_code == 200
    assert "summary" in r_copilot.json()["data"]


def test_v1_admin_endpoints(client):
    """Test /api/v1/admin organizations, health, and kill switch."""
    # Organizations
    r_orgs = client.get("/api/v1/admin/organizations")
    assert r_orgs.status_code == 200
    if len(r_orgs.json()["data"]) == 0:
        client.post("/api/v1/admin/organizations", json={"name": "Default Organization", "slug": "default-org"})
        r_orgs = client.get("/api/v1/admin/organizations")
    assert len(r_orgs.json()["data"]) >= 1

    # Health
    r_health = client.get("/api/v1/admin/system-health")
    assert r_health.status_code == 200
    assert r_health.json()["data"]["api_server"] == "ONLINE"

    # Kill switch
    r_kill = client.post("/api/v1/admin/kill-switch?active=false&reason=test_nominal")
    assert r_kill.status_code == 200
    assert r_kill.json()["data"]["kill_switch_active"] is False


def test_v1_courses_and_curricula(client):
    """Test /api/v1/courses and /api/v1/curricula endpoints."""
    # Courses
    r_courses = client.get("/api/v1/courses")
    assert r_courses.status_code == 200
    assert len(r_courses.json()["data"]) >= 1

    # Specific course
    r_course = client.get("/api/v1/courses/crs-chem-101")
    assert r_course.status_code == 200
    assert r_course.json()["data"]["subject"] == "Chemistry"

    # Curriculum
    r_curr = client.get("/api/v1/curricula/crs-chem-101")
    assert r_curr.status_code == 200
    curr_data = r_curr.json()["data"]
    assert curr_data["total_concepts"] >= 10
    assert len(curr_data["chapters"]) >= 4


def test_v1_sessions_endpoints(client):
    """Test /api/v1/sessions lifecycle."""
    start_payload = {
        "student_id": "sess_std_01",
        "course_id": "crs-chem-101",
        "initial_concept": "chem_thermo_first_law",
    }
    r_start = client.post("/api/v1/sessions/start", json=start_payload)
    assert r_start.status_code == 201
    sess = r_start.json()["data"]
    assert sess["status"] == "ACTIVE"

    # Fetch session
    r_get = client.get(f"/api/v1/sessions/{sess['session_id']}")
    assert r_get.status_code == 200
    assert r_get.json()["data"]["student_id"] == "sess_std_01"


def test_v1_learning_events_and_recommendations(client):
    """Test /api/v1/learning/events and /recommendations."""
    event_payload = {
        "event_id": "ev-test-01",
        "student_id": "std-learn-01",
        "session_id": "sess-01",
        "turn_id": "turn-01",
        "concept_id": "chem_thermo_first_law",
        "correctness": "correct",
        "hint_used": 0,
        "difficulty": 0.6,
    }
    r_ev = client.post("/api/v1/learning/events", json=event_payload)
    assert r_ev.status_code == 201
    assert r_ev.json()["data"]["status"] == "RECORDED"

    r_rec = client.get("/api/v1/learning/recommendations/std-learn-01")
    assert r_rec.status_code == 200
    rec = r_rec.json()["data"]
    assert rec["recommended_action"] == "QUESTION"


def test_v1_assessments_endpoints(client):
    """Test /api/v1/assessments/items and /submit."""
    r_items = client.get("/api/v1/assessments/items")
    assert r_items.status_code == 200
    items = r_items.json()["data"]
    assert len(items) >= 1

    submit_payload = {
        "assessment_id": "asmt-001",
        "student_id": "std-asmt-01",
        "answers": {"q1": "delta G < 0"},
    }
    r_sub = client.post("/api/v1/assessments/submit", json=submit_payload)
    assert r_sub.status_code == 200
    assert r_sub.json()["data"]["passed"] is True


def test_v1_rag_query(client):
    """Test /api/v1/rag/query returns grounded NCERT evidence cards."""
    # Negative assertion: Unauthenticated call is rejected with 401
    assert client.post("/api/v1/rag/query", json={"query": "Hess law enthalpy summation", "top_k": 2}).status_code == 401

    token = create_access_token(user_id="std_api_01", role="STUDENT", organization_id="org-default")
    r_rag = client.post(
        "/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "Hess law enthalpy summation", "top_k": 2},
    )
    assert r_rag.status_code == 200
    data = r_rag.json()["data"]
    assert data["status"] == "RAG_OK"
    assert len(data["results"]) >= 1
    assert "citation" in data["results"][0]


def test_v1_ai_gateway_and_analytics(client):
    """Test /api/v1/ai/status and /api/v1/analytics/cohort."""
    # AI Gateway
    r_ai = client.get("/api/v1/ai/status")
    assert r_ai.status_code == 200
    assert r_ai.json()["data"]["gateway_status"] == "HEALTHY"

    # Analytics
    r_analytics = client.get("/api/v1/analytics/cohort/cohort_chem_101")
    assert r_analytics.status_code == 200
    assert "average_mastery" in r_analytics.json()["data"]


def test_v1_notifications_and_sync(client):
    """Test /api/v1/notifications and /api/v1/sync/events."""
    # Notifications
    r_notif = client.get("/api/v1/notifications?recipient_id=usr-01")
    assert r_notif.status_code == 200
    assert len(r_notif.json()["data"]) >= 1

    # Batch Sync
    sync_payload = {
        "student_id": "sync_batch_std",
        "events": [
            {"event_id": "sync-ev-1", "event_type": "turn_completed", "score": 1.0},
            {"event_id": "sync-ev-2", "event_type": "hint_used", "hint_level": 1},
        ],
    }
    r_sync = client.post("/api/v1/sync/events", json=sync_payload)
    assert r_sync.status_code == 200
    assert r_sync.json()["data"]["synced_count"] == 2


# ── 4. Error Handling & Request Tracing ──────────────────────────────────

def test_request_id_propagation(client):
    """Verify that custom X-Request-ID is preserved and echoed."""
    custom_id = "custom-test-trace-999"
    resp = client.get("/healthz", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == custom_id


def test_structured_validation_error_envelope(client):
    """Verify that invalid payload produces structured 422 error envelope."""
    # Missing required 'password' field in LoginRequest
    resp = client.post("/api/v1/auth/login", json={"username": "user"})
    assert resp.status_code == 422
    data = resp.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "meta" in data
    assert "request_id" in data["meta"]


def test_structured_404_error_envelope(client):
    """Verify that non-existent route produces structured 404 error envelope."""
    resp = client.get("/api/v1/non_existent_route")
    assert resp.status_code == 404
    data = resp.json()
    assert data["ok"] is False
    assert data["error"]["code"] == "HTTP_404"


def test_dashboard_html_rendering(client):
    """Verify that GET / returns the Teacher Command Center HTML."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Teacher Command Center" in resp.text
    assert "Cohort Mastery Distribution" in resp.text


def test_static_assets_and_tutor_serving(client):
    """Verify that static assets and /tutor serve properly without 404 errors."""
    r_tutor = client.get("/tutor")
    assert r_tutor.status_code == 200

    r_fav = client.get("/favicon.ico")
    assert r_fav.status_code in (200, 204)

    r_png = client.get("/gai3.png")
    assert r_png.status_code in (200, 204)

    r_ico = client.get("/gai3.ico")
    assert r_ico.status_code in (200, 204)

    r_js = client.get("/marked.min.js")
    assert r_js.status_code in (200, 204)

