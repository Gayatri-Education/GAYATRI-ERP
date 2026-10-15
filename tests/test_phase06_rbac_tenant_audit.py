"""Phase 06 — Central Authorization & Tenant-Isolation Audit Test Suite (QA-006).

Tests:
1. Role normalization across all routes: rejection of ad-hoc string and casing mismatches.
2. Access control on /ops/release-gate and /ops/release-manifest.
3. Access control on AI observability and governance endpoints.
4. Access control and tenant isolation on classes, cohorts, instructions, and organizations.
5. Prevention of IDOR cross-tenant leaks in enrollments, students, and user management.
6. Role escalation rejection (e.g. parent/student trying admin routes).
"""

import os
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import ClassGroup, Cohort, Course, Enrollment, Organization, User, UserRole


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_phase06.db")
    monkeypatch.setenv("GAYATRI_DB_PATH", test_db_path)
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "super-secret-test-jwt-key-phase06-12345678")

    db = PlatformDatabase(test_db_path)

    # Seed two distinct organizations
    org0 = Organization(id="org_global", name="Global Admin", slug="global-admin")
    org1 = Organization(id="org_alpha", name="Alpha Academy", slug="alpha-academy")
    org2 = Organization(id="org_beta", name="Beta College", slug="beta-college")
    db.create_organization(org0)
    db.create_organization(org1)
    db.create_organization(org2)

    # Seed users across both orgs
    superadmin = User(
        id="usr_super",
        email="super@central.gov",
        full_name="Super Admin",
        role=UserRole.SUPER_ADMIN,
        organization_id="org_global",
        is_active=True,
    )
    admin_alpha = User(
        id="usr_admin_alpha",
        email="admin@alpha.edu",
        full_name="Admin Alpha",
        role=UserRole.ORG_ADMIN,
        organization_id="org_alpha",
        is_active=True,
    )
    admin_beta = User(
        id="usr_admin_beta",
        email="admin@beta.edu",
        full_name="Admin Beta",
        role=UserRole.ORG_ADMIN,
        organization_id="org_beta",
        is_active=True,
    )
    teacher_alpha = User(
        id="usr_teacher_alpha",
        email="teacher@alpha.edu",
        full_name="Teacher Alpha",
        role=UserRole.TEACHER,
        organization_id="org_alpha",
        is_active=True,
    )
    teacher_beta = User(
        id="usr_teacher_beta",
        email="teacher@beta.edu",
        full_name="Teacher Beta",
        role=UserRole.TEACHER,
        organization_id="org_beta",
        is_active=True,
    )
    student_alpha = User(
        id="usr_student_alpha",
        email="student@alpha.edu",
        full_name="Student Alpha",
        role=UserRole.STUDENT,
        organization_id="org_alpha",
        is_active=True,
    )
    student_beta = User(
        id="usr_student_beta",
        email="student@beta.edu",
        full_name="Student Beta",
        role=UserRole.STUDENT,
        organization_id="org_beta",
        is_active=True,
    )
    parent_alpha = User(
        id="usr_parent_alpha",
        email="parent@alpha.family",
        full_name="Parent Alpha",
        role=UserRole.PARENT,
        organization_id="org_alpha",
        is_active=True,
    )

    for u in [superadmin, admin_alpha, admin_beta, teacher_alpha, teacher_beta, student_alpha, student_beta, parent_alpha]:
        db.create_user(u)

    # Seed courses and classes
    course_alpha = Course(
        id="crs-alpha-101",
        organization_id="org_alpha",
        code="ALPHA101",
        title="Physics Alpha",
        description="Physics course for Alpha",
    )
    course_beta = Course(
        id="crs-beta-101",
        organization_id="org_beta",
        code="BETA101",
        title="Physics Beta",
        description="Physics course for Beta",
    )
    db.create_course(course_alpha)
    db.create_course(course_beta)

    # Seed class groups
    cls_alpha = ClassGroup(
        id="cls_alpha_1",
        organization_id="org_alpha",
        course_id="crs-alpha-101",
        name="Alpha 11-A",
        section="A",
    )
    cls_beta = ClassGroup(
        id="cls_beta_1",
        organization_id="org_beta",
        course_id="crs-beta-101",
        name="Beta 11-B",
        section="B",
    )
    db.create_class_group(cls_alpha)
    db.create_class_group(cls_beta)

    # Seed cohorts
    coh_alpha = Cohort(
        id="coh_alpha_1",
        class_group_id="cls_alpha_1",
        name="Cohort Alpha A1",
        academic_year="2026-2027",
    )
    coh_beta = Cohort(
        id="coh_beta_1",
        class_group_id="cls_beta_1",
        name="Cohort Beta B1",
        academic_year="2026-2027",
    )
    db.create_cohort(coh_alpha)
    db.create_cohort(coh_beta)

    # Seed enrollments
    enr_alpha = Enrollment(
        id="enr_alpha_1",
        student_id="usr_student_alpha",
        course_id="crs-alpha-101",
        cohort_id="coh_alpha_1",
        is_active=True,
    )
    enr_beta = Enrollment(
        id="enr_beta_1",
        student_id="usr_student_beta",
        course_id="crs-beta-101",
        cohort_id="coh_beta_1",
        is_active=True,
    )
    db.create_enrollment(enr_alpha)
    db.create_enrollment(enr_beta)

    yield db


def auth_header(user_id: str, role: str, org_id: str) -> dict:
    token = create_access_token(user_id=user_id, role=role, organization_id=org_id)
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. Ops Gate & Manifest Authorization
# =====================================================================

def test_reproduce_ops_manifest_student_access():
    client = TestClient(app)
    headers = auth_header("usr_student_alpha", "student", "org_alpha")
    response = client.get("/api/v1/ops/release-manifest", headers=headers)
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"


def test_ops_gate_and_manifest_rbac():
    client = TestClient(app)
    # Parent blocked
    parent_hdr = auth_header("usr_parent_alpha", "parent", "org_alpha")
    resp_gate_parent = client.get("/api/v1/ops/release-gate", headers=parent_hdr)
    assert resp_gate_parent.status_code == 403

    resp_man_parent = client.get("/api/v1/ops/release-manifest", headers=parent_hdr)
    assert resp_man_parent.status_code == 403

    # Admin allowed
    admin_hdr = auth_header("usr_admin_alpha", "org_admin", "org_alpha")
    resp_gate_admin = client.get("/api/v1/ops/release-gate", headers=admin_hdr)
    assert resp_gate_admin.status_code == 200
    assert "decision" in resp_gate_admin.json()


# =====================================================================
# 2. AI Governance & Observability Authorization
# =====================================================================

def test_reproduce_ai_observability_unauthenticated_leak():
    client = TestClient(app)
    response = client.get("/api/v1/ai/observability/metrics")
    assert response.status_code in (401, 403), f"Expected 401 or 403, got {response.status_code}: {response.text}"


def test_ai_observability_and_governance_rbac():
    client = TestClient(app)
    endpoints = [
        "/api/v1/ai/observability/metrics",
        "/api/v1/ai/observability/logs",
        "/api/v1/ai/governance/budgets",
        "/api/v1/ai/governance/circuit-breakers",
        "/api/v1/ai/governance/allowlist",
        "/api/v1/ai/governance/cost-breakdown",
    ]

    # Anonymous blocked
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code in (401, 403), f"Expected 401/403 for anonymous on {ep}, got {resp.status_code}"

    # Student blocked
    student_hdr = auth_header("usr_student_alpha", "student", "org_alpha")
    for ep in endpoints:
        resp = client.get(ep, headers=student_hdr)
        assert resp.status_code == 403, f"Expected 403 for student on {ep}, got {resp.status_code}"

    # Parent blocked
    parent_hdr = auth_header("usr_parent_alpha", "parent", "org_alpha")
    for ep in endpoints:
        resp = client.get(ep, headers=parent_hdr)
        assert resp.status_code == 403, f"Expected 403 for parent on {ep}, got {resp.status_code}"

    # Super admin allowed
    super_hdr = auth_header("usr_super", "super_admin", "org_global")
    for ep in endpoints:
        resp = client.get(ep, headers=super_hdr)
        assert resp.status_code == 200, f"Expected 200 for super admin on {ep}, got {resp.status_code}: {resp.text}"


# =====================================================================
# 3. Organizations RBAC & Casing
# =====================================================================

def test_reproduce_super_admin_create_organization_casing():
    client = TestClient(app)
    headers = auth_header("usr_super", "SUPER_ADMIN", "org_global")
    payload = {"name": "Gamma School", "slug": "gamma-school"}
    response = client.post("/api/v1/organizations", json=payload, headers=headers)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"


def test_organization_rbac_rejections():
    client = TestClient(app)
    payload = {"name": "Delta School", "slug": "delta-school"}

    # Org admin cannot create organizations
    admin_hdr = auth_header("usr_admin_alpha", "org_admin", "org_alpha")
    resp_admin = client.post("/api/v1/organizations", json=payload, headers=admin_hdr)
    assert resp_admin.status_code == 403

    # Student cannot create organizations
    student_hdr = auth_header("usr_student_alpha", "student", "org_alpha")
    resp_student = client.post("/api/v1/organizations", json=payload, headers=student_hdr)
    assert resp_student.status_code == 403

    # Parent cannot create organizations
    parent_hdr = auth_header("usr_parent_alpha", "parent", "org_alpha")
    resp_parent = client.post("/api/v1/organizations", json=payload, headers=parent_hdr)
    assert resp_parent.status_code == 403

    # Org admin can read own organization
    resp_get_own = client.get("/api/v1/organizations/org_alpha", headers=admin_hdr)
    assert resp_get_own.status_code == 200

    # Org admin cannot read another organization
    resp_get_other = client.get("/api/v1/organizations/org_beta", headers=admin_hdr)
    assert resp_get_other.status_code == 403


# =====================================================================
# 4. Enrollments Multi-Tenant Isolation
# =====================================================================

def test_reproduce_cross_tenant_enrollment_idor():
    client = TestClient(app)
    headers = auth_header("usr_admin_alpha", "org_admin", "org_alpha")
    response = client.get("/api/v1/enrollments/enr_beta_1", headers=headers)
    assert response.status_code in (403, 404), f"Expected 403 or 404 for foreign enrollment, got {response.status_code}"


def test_enrollments_listing_isolation():
    client = TestClient(app)
    # Admin Alpha only sees Alpha enrollment
    admin_hdr = auth_header("usr_admin_alpha", "org_admin", "org_alpha")
    resp = client.get("/api/v1/enrollments", headers=admin_hdr)
    assert resp.status_code == 200
    enrollments = resp.json()["data"]
    ids = [e["id"] for e in enrollments]
    assert "enr_alpha_1" in ids
    assert "enr_beta_1" not in ids


# =====================================================================
# 5. Classes & Cohorts Multi-Tenant Isolation
# =====================================================================

def test_classes_and_cohorts_tenant_isolation():
    client = TestClient(app)
    admin_alpha_hdr = auth_header("usr_admin_alpha", "org_admin", "org_alpha")
    admin_beta_hdr = auth_header("usr_admin_beta", "org_admin", "org_beta")

    # Alpha admin can read Alpha class
    resp_alpha = client.get("/api/v1/classes/cls_alpha_1", headers=admin_alpha_hdr)
    assert resp_alpha.status_code == 200

    # Beta admin is forbidden from reading Alpha class
    resp_beta_cross = client.get("/api/v1/classes/cls_alpha_1", headers=admin_beta_hdr)
    assert resp_beta_cross.status_code == 403

    # Beta admin is forbidden from reading Alpha cohorts
    resp_beta_cohorts = client.get("/api/v1/classes/cls_alpha_1/cohorts", headers=admin_beta_hdr)
    assert resp_beta_cohorts.status_code == 403

    # Student cannot create class
    student_hdr = auth_header("usr_student_alpha", "student", "org_alpha")
    resp_student_create = client.post(
        "/api/v1/classes",
        json={"name": "Class 10", "course_id": "crs-alpha-101", "organization_id": "org_alpha"},
        headers=student_hdr,
    )
    assert resp_student_create.status_code == 403

    # Parent cannot create class
    parent_hdr = auth_header("usr_parent_alpha", "parent", "org_alpha")
    resp_parent_create = client.post(
        "/api/v1/classes",
        json={"name": "Class 10", "course_id": "crs-alpha-101", "organization_id": "org_alpha"},
        headers=parent_hdr,
    )
    assert resp_parent_create.status_code == 403


# =====================================================================
# 6. Instructions Tenant & Role Isolation
# =====================================================================

def test_instructions_tenant_isolation():
    client = TestClient(app)
    teacher_alpha_hdr = auth_header("usr_teacher_alpha", "teacher", "org_alpha")
    student_alpha_hdr = auth_header("usr_student_alpha", "student", "org_alpha")
    parent_alpha_hdr = auth_header("usr_parent_alpha", "parent", "org_alpha")

    # Teacher Alpha creates valid instruction
    payload = {
        "instruction": "Focus on Newtonian kinematics derivation.",
        "course_id": "crs-alpha-101",
        "organization_id": "org_alpha",
    }
    resp_create = client.post("/api/v1/instructions", json=payload, headers=teacher_alpha_hdr)
    assert resp_create.status_code == 201
    inst_id = resp_create.json()["data"]["instruction_id"]

    # Teacher Alpha attempting cross-tenant instruction creation for Beta org gets 403
    cross_payload = {
        "instruction": "Cross tenant instruction injection.",
        "course_id": "crs-beta-101",
        "organization_id": "org_beta",
    }
    resp_cross = client.post("/api/v1/instructions", json=cross_payload, headers=teacher_alpha_hdr)
    assert resp_cross.status_code == 403

    # Student attempting to create instruction gets 403
    resp_student = client.post("/api/v1/instructions", json=payload, headers=student_alpha_hdr)
    assert resp_student.status_code == 403

    # Parent attempting to create instruction gets 403
    resp_parent = client.post("/api/v1/instructions", json=payload, headers=parent_alpha_hdr)
    assert resp_parent.status_code == 403

    # Teacher Beta cannot delete Teacher Alpha's instruction
    teacher_beta_hdr = auth_header("usr_teacher_beta", "teacher", "org_beta")
    resp_del_cross = client.delete(f"/api/v1/instructions/{inst_id}", headers=teacher_beta_hdr)
    assert resp_del_cross.status_code in (403, 404)


# =====================================================================
# 7. Users & Admin Dashboard Isolation
# =====================================================================

def test_users_and_admin_rbac():
    client = TestClient(app)
    student_alpha_hdr = auth_header("usr_student_alpha", "student", "org_alpha")
    parent_alpha_hdr = auth_header("usr_parent_alpha", "parent", "org_alpha")
    admin_alpha_hdr = auth_header("usr_admin_alpha", "org_admin", "org_alpha")
    admin_beta_hdr = auth_header("usr_admin_beta", "org_admin", "org_beta")

    # Student blocked from admin dashboard
    resp_student_dash = client.get("/api/v1/admin/dashboard", headers=student_alpha_hdr)
    assert resp_student_dash.status_code == 403

    # Parent blocked from admin dashboard
    resp_parent_dash = client.get("/api/v1/admin/dashboard", headers=parent_alpha_hdr)
    assert resp_parent_dash.status_code == 403

    # Student blocked from listing users
    resp_student_users = client.get("/api/v1/users", headers=student_alpha_hdr)
    assert resp_student_users.status_code == 403

    # Parent blocked from listing users
    resp_parent_users = client.get("/api/v1/users", headers=parent_alpha_hdr)
    assert resp_parent_users.status_code == 403

    # Admin Alpha querying Beta users explicitly gets 403
    resp_cross_users = client.get("/api/v1/users?organization_id=org_beta", headers=admin_alpha_hdr)
    assert resp_cross_users.status_code == 403

    # Admin Beta trying to view Alpha student details via IDOR gets 403
    resp_idor_user = client.get("/api/v1/users/usr_student_alpha", headers=admin_beta_hdr)
    assert resp_idor_user.status_code in (403, 404)


# =====================================================================
# 8. Curricula & Teachers Portal RBAC
# =====================================================================

def test_curricula_and_teachers_role_rejection():
    client = TestClient(app)
    student_hdr = auth_header("usr_student_alpha", "student", "org_alpha")
    parent_hdr = auth_header("usr_parent_alpha", "parent", "org_alpha")

    # Student blocked from creating curriculum version
    version_payload = {"version_num": "2.0.0", "change_log": "Unauthorized draft"}
    resp_curr_student = client.post("/api/v1/curricula/curr-alpha-1/versions", json=version_payload, headers=student_hdr)
    assert resp_curr_student.status_code == 403

    # Parent blocked from creating curriculum version
    resp_curr_parent = client.post("/api/v1/curricula/curr-alpha-1/versions", json=version_payload, headers=parent_hdr)
    assert resp_curr_parent.status_code == 403

    # Student blocked from teacher dashboard
    resp_teacher_dash_student = client.get("/api/v1/teachers/dashboard", headers=student_hdr)
    assert resp_teacher_dash_student.status_code == 403

    # Parent blocked from teacher dashboard
    resp_teacher_dash_parent = client.get("/api/v1/teachers/dashboard", headers=parent_hdr)
    assert resp_teacher_dash_parent.status_code == 403
