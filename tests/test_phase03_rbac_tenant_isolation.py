"""Phase 03 Test Suite — Authorization, RBAC & Tenant Isolation (Section 9 Actor Matrix).

Master Plan Section 9 / Release Remediation Matrix:
1. Anonymous -> Protected API -> 401 Unauthorized in production
2. Student -> Own data -> 200 OK
3. Student -> Other student -> 403 Forbidden
4. Student -> Teacher dashboard -> 403 Forbidden
5. Teacher -> Assigned course -> 200 OK
6. Teacher -> Other tenant course -> 403 Forbidden
7. Org admin -> Own org -> 200/201 OK
8. Org admin -> Other org -> 403 Forbidden
9. Super admin -> Global admin resources -> 200/201 OK (policy-based)
10. Deleted / Inactive / Suspended user -> Protected resources -> 403 Forbidden
"""

import os
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Course,
    CourseVisibility,
    Organization,
    User,
    UserRole,
)
from central_platform.rbac.engine import hash_password


@pytest.fixture(scope="module")
def client():
    """FastAPI platform test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Isolated database fixture with default seed data."""
    db_file = str(tmp_path / "test_phase03_rbac.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", db_file)
    db = PlatformDatabase(db_file)
    # Seed default organizations and courses required for foreign key integrity
    if not db.get_organization("org-default"):
        db.create_organization(Organization(id="org-default", name="Default Organization", slug="default"))
    if not db.get_organization("org-root"):
        db.create_organization(Organization(id="org-root", name="Root Organization", slug="root"))
    if not db.get_course("crs-chem-101"):
        db.create_course(Course(
            id="crs-chem-101",
            code="CHEM101",
            title="Chemistry",
            visibility=CourseVisibility.PUBLIC,
            organization_id="org-default",
        ))
    yield db
    db.close()


# ── Row 1: Anonymous -> Protected API -> 401 in Production ─────────────────

def test_row01_anonymous_protected_api_fails_in_production(client, monkeypatch, test_db):
    """Anonymous access to protected APIs must fail with 401 Unauthorized in production."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("APP_ENV", "production")

    endpoints_get = [
        "/api/v1/admin/system-health",
        "/api/v1/teachers/dashboard",
        "/api/v1/students/student_alice",
        "/api/v1/students/student_alice/slr",
        "/api/v1/users",
        "/api/v1/enrollments",
        "/api/v1/analytics/student/student_alice",
        "/api/v1/notifications",
        "/api/v1/learning/events",
        "/api/v1/sync/status?student_id=student_alice",
    ]

    for ep in endpoints_get:
        resp = client.get(ep)
        assert resp.status_code == 401, f"Expected 401 for GET {ep}, got {resp.status_code}: {resp.text}"

    endpoints_post = [
        ("/api/v1/classes", {"organization_id": "org-default", "course_id": "crs-chem-101", "name": "Class A"}),
        ("/api/v1/courses", {"code": "CRS99", "title": "Test Course", "visibility": "PUBLIC"}),
        ("/api/v1/enrollments", {"student_id": "student_alice", "course_id": "crs-chem-101"}),
        ("/api/v1/instructions", {"instruction": "Focus on thermo", "course_id": "crs-chem-101"}),
        ("/api/v1/learning/events", {"event_id": "ev-01", "student_id": "st-01", "session_id": "sess-01", "course_id": "crs-chem-101", "event_type": "EXERCISE_COMPLETED"}),
        ("/api/v1/sessions", {"student_id": "student_alice", "course_id": "crs-chem-101"}),
        ("/api/v1/sync/events", {"student_id": "student_alice", "events": []}),
        ("/api/v1/tools/execute", {"tool_id": "calculator", "course_id": "crs-chem-101", "arguments": {"expr": "1+1"}}),
        ("/api/v1/curricula/101/versions", {"version_num": "2.0", "change_log": "Updated"}),
    ]

    for ep, payload in endpoints_post:
        resp = client.post(ep, json=payload)
        assert resp.status_code == 401, f"Expected 401 for POST {ep}, got {resp.status_code}: {resp.text}"


# ── Row 2: Student -> Own Data -> 200 OK ─────────────────────────────────────

def test_row02_student_own_data_succeeds(client, test_db):
    """Student must have full 200 OK access to their own profile, learning record, and enrollments."""
    alice_token = create_access_token(
        user_id="student_alice",
        role="student",
        organization_id="org-default",
    )
    headers = {"Authorization": f"Bearer {alice_token}"}

    # Profile
    r_prof = client.get("/api/v1/students/student_alice", headers=headers)
    assert r_prof.status_code == 200

    # Learning Record (SLR)
    r_slr = client.get("/api/v1/students/student_alice/slr", headers=headers)
    assert r_slr.status_code == 200

    # Enrollments
    r_enr = client.get("/api/v1/enrollments?student_id=student_alice", headers=headers)
    assert r_enr.status_code == 200


# ── Row 3: Student -> Other Student -> 403 Forbidden ─────────────────────────

def test_row03_student_other_student_forbidden(client, test_db):
    """Student attempting to view or manipulate another student's data must receive 403 Forbidden."""
    alice_token = create_access_token(
        user_id="student_alice",
        role="student",
        organization_id="org-default",
    )
    headers = {"Authorization": f"Bearer {alice_token}"}

    # Other student's profile
    r_prof = client.get("/api/v1/students/student_bob", headers=headers)
    assert r_prof.status_code == 403

    # Other student's SLR
    r_slr = client.get("/api/v1/students/student_bob/slr", headers=headers)
    assert r_slr.status_code == 403

    # Submit action for other student
    r_act = client.post(
        "/api/v1/students/student_bob/action",
        headers=headers,
        json={"action_type": "HINT_REQUEST", "concept_id": "chem_thermo_first_law", "payload": {}},
    )
    assert r_act.status_code == 403

    # Other student's enrollments
    r_enr = client.get("/api/v1/enrollments?student_id=student_bob", headers=headers)
    assert r_enr.status_code == 403

    # Enrolling another student
    r_create_enr = client.post(
        "/api/v1/enrollments",
        headers=headers,
        json={"student_id": "student_bob", "course_id": "crs-chem-101"},
    )
    assert r_create_enr.status_code == 403


# ── Row 4: Student -> Teacher Dashboard -> 403 Forbidden ─────────────────────

def test_row04_student_teacher_dashboard_forbidden(client, test_db):
    """Student attempting to access teacher dashboard or authoring must receive 403 Forbidden."""
    alice_token = create_access_token(
        user_id="student_alice",
        role="student",
        organization_id="org-default",
    )
    headers = {"Authorization": f"Bearer {alice_token}"}

    # Teacher dashboard
    r_dash = client.get("/api/v1/teachers/dashboard", headers=headers)
    assert r_dash.status_code == 403

    # Teacher instructions
    r_inst = client.post(
        "/api/v1/instructions",
        headers=headers,
        json={"instruction": "Read Chapter 1", "course_id": "crs-chem-101"},
    )
    assert r_inst.status_code == 403

    # Course review queue
    r_q = client.get("/api/v1/courses/review-queue", headers=headers)
    assert r_q.status_code == 403

    # Class creation
    r_cls = client.post(
        "/api/v1/classes",
        headers=headers,
        json={"organization_id": "org-default", "course_id": "crs-chem-101", "name": "Class 10"},
    )
    assert r_cls.status_code == 403

    # Curriculum import
    r_curr = client.post(
        "/api/v1/curricula/import",
        headers=headers,
        json={"course_id": "crs-chem-101", "package": {"title": "NCERT", "modules": []}},
    )
    assert r_curr.status_code == 403


# ── Row 5: Teacher -> Assigned Course -> 200 OK ──────────────────────────────

def test_row05_teacher_assigned_course_succeeds(client, test_db):
    """Teacher must be permitted 200 OK access to courses within their organization."""
    # Seed org and course
    org_alpha = Organization(id="org-alpha", name="Alpha School", slug="alpha")
    test_db.create_organization(org_alpha)
    course_alpha = Course(
        id="crs-alpha-101",
        code="ALPHA101",
        title="Alpha Chemistry",
        visibility=CourseVisibility.PRIVATE,
        organization_id="org-alpha",
    )
    test_db.create_course(course_alpha)

    teacher_token = create_access_token(
        user_id="teacher_alpha",
        role="teacher",
        organization_id="org-alpha",
    )
    headers = {"Authorization": f"Bearer {teacher_token}"}

    r_dash = client.get("/api/v1/teachers/dashboard?course_id=crs-alpha-101", headers=headers)
    assert r_dash.status_code == 200


# ── Row 6: Teacher -> Other Tenant Course -> 403 Forbidden ───────────────────

def test_row06_teacher_other_tenant_course_forbidden(client, test_db):
    """Teacher must receive 403 Forbidden when attempting to view another tenant's course dashboard."""
    # Seed org-beta and course
    org_beta = Organization(id="org-beta", name="Beta Academy", slug="beta")
    test_db.create_organization(org_beta)
    course_beta = Course(
        id="crs-beta-101",
        code="BETA101",
        title="Beta Physics",
        visibility=CourseVisibility.PRIVATE,
        organization_id="org-beta",
    )
    test_db.create_course(course_beta)

    # Teacher belongs to org-alpha
    teacher_alpha_token = create_access_token(
        user_id="teacher_alpha",
        role="teacher",
        organization_id="org-alpha",
    )
    headers = {"Authorization": f"Bearer {teacher_alpha_token}"}

    # Attempt to access org-beta's course dashboard
    r_cross = client.get("/api/v1/teachers/dashboard?course_id=crs-beta-101", headers=headers)
    assert r_cross.status_code == 403
    assert "Forbidden" in r_cross.json()["detail"]


# ── Row 7: Org Admin -> Own Org -> 200/201 OK ───────────────────────────────

def test_row07_org_admin_own_org_succeeds(client, test_db):
    """Organization administrator must be able to create classes and courses within their own org."""
    org_gamma = Organization(id="org-gamma", name="Gamma Institute", slug="gamma")
    test_db.create_organization(org_gamma)

    # Pre-seed course in org-gamma to satisfy class_groups foreign key
    crs_gamma = Course(
        id="crs-gamma-01",
        code="GAM100",
        title="Gamma Foundation",
        visibility=CourseVisibility.PRIVATE,
        organization_id="org-gamma",
    )
    test_db.create_course(crs_gamma)

    admin_token = create_access_token(
        user_id="admin_gamma",
        role="org_admin",
        organization_id="org-gamma",
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create class in org-gamma
    r_cls = client.post(
        "/api/v1/classes",
        headers=headers,
        json={"organization_id": "org-gamma", "course_id": "crs-gamma-01", "name": "Grade 11 Gamma"},
    )
    assert r_cls.status_code == 201
    assert r_cls.json()["data"]["organization_id"] == "org-gamma"

    # Create course in org-gamma
    r_crs = client.post(
        "/api/v1/courses",
        headers=headers,
        json={"code": "GAM101", "title": "Gamma Biology", "visibility": "PRIVATE", "organization_id": "org-gamma"},
    )
    assert r_crs.status_code == 201


# ── Row 8: Org Admin -> Other Org -> 403 Forbidden ───────────────────────────

def test_row08_org_admin_other_org_forbidden(client, test_db):
    """Organization administrator attempting actions in another organization must receive 403 Forbidden."""
    org_delta = Organization(id="org-delta", name="Delta School", slug="delta")
    test_db.create_organization(org_delta)

    admin_gamma_token = create_access_token(
        user_id="admin_gamma",
        role="org_admin",
        organization_id="org-gamma",
    )
    headers = {"Authorization": f"Bearer {admin_gamma_token}"}

    # Attempt class creation in org-delta
    r_cls = client.post(
        "/api/v1/classes",
        headers=headers,
        json={"organization_id": "org-delta", "course_id": "crs-delta-01", "name": "Cross Org Class"},
    )
    assert r_cls.status_code == 403
    assert "cross-organization" in r_cls.json()["detail"].lower()

    # Attempt teacher instruction in org-delta
    r_inst = client.post(
        "/api/v1/instructions",
        headers=headers,
        json={"instruction": "Read notes", "course_id": "crs-delta-01", "organization_id": "org-delta"},
    )
    assert r_inst.status_code == 403
    assert "cross-organization" in r_inst.json()["detail"].lower()


# ── Row 9: Super Admin -> Global Admin Resources -> 200/201 OK ───────────────

def test_row09_super_admin_global_admin_resources_succeeds(client, test_db):
    """Super administrator must have policy-based access to global admin controls and cross-org management."""
    super_admin_token = create_access_token(
        user_id="super_admin_01",
        role="super_admin",
        organization_id="org-root",
    )
    headers = {"Authorization": f"Bearer {super_admin_token}"}

    # Global system health
    r_health = client.get("/api/v1/admin/system-health", headers=headers)
    assert r_health.status_code == 200

    # Toggle kill switch
    r_ks = client.post("/api/v1/admin/kill-switch?active=false", headers=headers)
    assert r_ks.status_code == 200

    # Pre-seed course for class group foreign key
    org_any = Organization(id="org-any", name="Any Org", slug="any")
    test_db.create_organization(org_any)
    crs_any = Course(
        id="crs-any",
        code="ANY01",
        title="Any Course",
        visibility=CourseVisibility.PUBLIC,
        organization_id="org-any",
    )
    test_db.create_course(crs_any)

    # Cross-org class creation
    r_cls = client.post(
        "/api/v1/classes",
        headers=headers,
        json={"organization_id": "org-any", "course_id": "crs-any", "name": "Global Class"},
    )
    assert r_cls.status_code == 201

    # Global review queue
    r_queue = client.get("/api/v1/courses/review-queue", headers=headers)
    assert r_queue.status_code == 200


# ── Row 10: Deleted / Inactive / Suspended User -> 403 Rejected ──────────────

def test_row10_deleted_inactive_suspended_user_forbidden(client, test_db):
    """Users marked deleted, inactive, or suspended must have all requests rejected with 403 Forbidden."""
    pwd_hash, salt = hash_password("Password#2026")

    # 1. Deleted user
    user_deleted = User(
        id="usr-deleted-01",
        email="deleted@platform.local",
        full_name="Deleted User",
        role=UserRole.STUDENT,
        organization_id="org-default",
        is_active=False,
        is_deleted=True,
    )
    test_db.create_user(user_deleted)
    test_db.set_user_password(user_deleted.id, "Password#2026")

    token_deleted = create_access_token(user_id=user_deleted.id, role="student", organization_id="org-default")
    r_del = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_deleted}"})
    assert r_del.status_code == 403
    assert "inactive or deleted" in r_del.json()["detail"].lower()

    # 2. Inactive user (not deleted, but deactivated)
    user_inactive = User(
        id="usr-inactive-01",
        email="inactive@platform.local",
        full_name="Inactive User",
        role=UserRole.STUDENT,
        organization_id="org-default",
        is_active=False,
        is_deleted=False,
    )
    test_db.create_user(user_inactive)
    test_db.set_user_password(user_inactive.id, "Password#2026")

    token_inactive = create_access_token(user_id=user_inactive.id, role="student", organization_id="org-default")
    r_inact = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_inactive}"})
    assert r_inact.status_code == 403
    assert "inactive or deleted" in r_inact.json()["detail"].lower()

    # 3. Suspended user
    user_suspended = User(
        id="usr-suspended-01",
        email="suspended@platform.local",
        full_name="Suspended User",
        role=UserRole.STUDENT,
        organization_id="org-default",
        is_active=True,
        is_deleted=False,
    )
    test_db.create_user(user_suspended)
    test_db.set_user_password(user_suspended.id, "Password#2026")
    test_db.suspend_user(user_suspended.id)

    token_suspended = create_access_token(user_id=user_suspended.id, role="student", organization_id="org-default")
    r_susp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_suspended}"})
    assert r_susp.status_code == 403
    assert "suspended" in r_susp.json()["detail"].lower()
