"""Phase 17 Verification Test Suite — Student Multi-Course Workflow UI.

Tests:
1. Enrolled courses listing with live mastery and current active concept.
2. Course selector default and context resolution.
3. Dynamic course switching with active context preservation.
4. Safe course switching invariant (concurrency guard against switching during active turn).
5. Unauthorized course switching prevention (student boundary enforcement).
6. Scoped curriculum hierarchy with concept mastery overlays.
7. Scoped assignments isolation per course.
8. Scoped assignments class group boundary enforcement.
9. Scoped knowledge sources and remedial notes per course and student target.
10. Real-time offline caching and synchronization status indicators.
11. PySide6 Desktop Bridge slots for multi-course operations.
12. UI Dashboard structure and control binding in student_dashboard.html.
"""
from __future__ import annotations

import json
import os
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Assignment,
    ClassGroup,
    Cohort,
    Concept,
    Course,
    CourseVisibility,
    Curriculum,
    CurriculumVersion,
    Enrollment,
    MasteryState,
    Module,
    Organization,
    RAGSource,
    StudentLearningRecord,
    Topic,
    User,
    UserRole,
)
from app.portals.student.controller import StudentPortalController
from app.bridge.facade import Bridge, reset_student_controller_singleton


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def setup_multi_course_env(tmp_path):
    """Sets up an isolated database environment with 1 student enrolled in 3 courses."""
    db_file = str(tmp_path / f"test_phase17_{uuid.uuid4().hex[:8]}.db")
    db = PlatformDatabase(db_path=db_file)

    org_id = f"org_{uuid.uuid4().hex[:6]}"
    org = Organization(id=org_id, name="DPS Delhi", slug=f"dps-{org_id}")
    db.create_organization(org)

    student_id = f"std_{uuid.uuid4().hex[:6]}"
    other_student_id = f"std_other_{uuid.uuid4().hex[:6]}"

    student = User(
        id=student_id,
        email="student17@example.com",
        full_name="Aarav Sharma",
        role=UserRole.STUDENT,
        organization_id=org_id,
    )
    db.create_user(student)

    # Create 3 courses
    math_course = Course(
        id=f"crs_math_{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        code="MATH-101",
        title="Calculus and Linear Algebra",
        description="Core mathematics curriculum",
        visibility=CourseVisibility.PUBLIC,
    )
    phys_course = Course(
        id=f"crs_phys_{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        code="PHYS-101",
        title="Classical Mechanics",
        description="Newtonian mechanics and waves",
        visibility=CourseVisibility.PUBLIC,
    )
    chem_course = Course(
        id=f"crs_chem_{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        code="CHEM-101",
        title="Physical Chemistry",
        description="Thermodynamics and equilibrium",
        visibility=CourseVisibility.PUBLIC,
    )
    db.create_course(math_course)
    db.create_course(phys_course)
    db.create_course(chem_course)

    # Class Groups & Cohorts
    cg1 = ClassGroup(id=f"cg_math_{uuid.uuid4().hex[:6]}", name="Grade 11-A Math", course_id=math_course.id, organization_id=org_id)
    cg2 = ClassGroup(id=f"cg_chem1_{uuid.uuid4().hex[:6]}", name="Grade 11-A Chem", course_id=chem_course.id, organization_id=org_id)
    cg3 = ClassGroup(id=f"cg_chem2_{uuid.uuid4().hex[:6]}", name="Grade 11-B Chem", course_id=chem_course.id, organization_id=org_id)
    db.create_class_group(cg1)
    db.create_class_group(cg2)
    db.create_class_group(cg3)

    cohort1 = Cohort(id=f"coh_1_{uuid.uuid4().hex[:6]}", name="Cohort 2026 Math", class_group_id=cg1.id)
    cohort2 = Cohort(id=f"coh_2_{uuid.uuid4().hex[:6]}", name="Cohort 2026 Chem", class_group_id=cg2.id)
    db.create_cohort(cohort1)
    db.create_cohort(cohort2)

    # Enroll student in all 3 courses (Chem is in cg2/cohort2, Math is in cg1/cohort1, Phys has no cohort)
    enr1 = Enrollment(id=f"enr_1_{uuid.uuid4().hex[:6]}", student_id=student_id, course_id=math_course.id, cohort_id=cohort1.id)
    enr2 = Enrollment(id=f"enr_2_{uuid.uuid4().hex[:6]}", student_id=student_id, course_id=phys_course.id, cohort_id=None)
    enr3 = Enrollment(id=f"enr_3_{uuid.uuid4().hex[:6]}", student_id=student_id, course_id=chem_course.id, cohort_id=cohort2.id)
    db.create_enrollment(enr1)
    db.create_enrollment(enr2)
    db.create_enrollment(enr3)

    # Curricula for courses
    curr_math = Curriculum(id=f"cur_math_{uuid.uuid4().hex[:6]}", course_id=math_course.id, title="Math Curriculum", version="v1.0")
    curr_chem = Curriculum(id=f"cur_chem_{uuid.uuid4().hex[:6]}", course_id=chem_course.id, title="Chem Curriculum", version="v1.0")
    db.create_curriculum(curr_math)
    db.create_curriculum(curr_chem)

    v_math = CurriculumVersion(
        id=f"ver_m_{uuid.uuid4().hex[:6]}",
        curriculum_id=curr_math.id,
        version_num="v1.0",
        status="published",
        schema_data=json.dumps({
            "modules": [{
                "id": "mod_calc",
                "title": "Calculus",
                "topics": [{
                    "id": "top_diff",
                    "title": "Differentiation",
                    "concepts": [{"id": "c_derivatives", "name": "Derivatives", "difficulty": 0.6}]
                }]
            }]
        })
    )
    v_chem = CurriculumVersion(
        id=f"ver_c_{uuid.uuid4().hex[:6]}",
        curriculum_id=curr_chem.id,
        version_num="v1.0",
        status="published",
        schema_data=json.dumps({
            "modules": [{
                "id": "mod_thermo",
                "title": "Thermodynamics",
                "topics": [{
                    "id": "top_first_law",
                    "title": "First Law",
                    "concepts": [{"id": "c_first_law", "name": "First Law of Thermodynamics", "difficulty": 0.7}]
                }]
            }]
        })
    )
    db.create_curriculum_version(v_math)
    db.create_curriculum_version(v_chem)

    # Mastery states via SLR
    slr_math = StudentLearningRecord(
        id=f"slr_m_{uuid.uuid4().hex[:6]}",
        student_id=student_id,
        course_id=math_course.id,
        authoritative=True,
    )
    slr_chem = StudentLearningRecord(
        id=f"slr_c_{uuid.uuid4().hex[:6]}",
        student_id=student_id,
        course_id=chem_course.id,
        authoritative=True,
    )
    db.create_slr(slr_math)
    db.create_slr(slr_chem)

    db.upsert_mastery_state(MasteryState(
        slr_id=slr_math.id,
        concept_id="c_derivatives",
        score=0.90,
    ))
    db.upsert_mastery_state(MasteryState(
        slr_id=slr_chem.id,
        concept_id="c_first_law",
        score=0.45,
    ))

    yield {
        "db": db,
        "db_file": db_file,
        "student_id": student_id,
        "other_student_id": other_student_id,
        "org_id": org_id,
        "math_course": math_course,
        "phys_course": phys_course,
        "chem_course": chem_course,
        "cg1": cg1,
        "cg2": cg2,
        "cg3": cg3,
    }

    db.close()
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass


# ── Test 1: Enrolled Courses Listing ───────────────────────────────────────

def test_student_enrolled_courses_listing(setup_multi_course_env, client, monkeypatch):
    """Verify enrolled courses endpoint lists all active enrollments with live mastery."""
    env = setup_multi_course_env
    monkeypatch.setattr("central_platform.api.routes.students._db", env["db"])
    monkeypatch.setattr("central_platform.api.routes.students._curriculum_service.db", env["db"])

    res = client.get(f"/api/v1/students/{env['student_id']}/courses")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 3

    codes = {c["code"]: c for c in data}
    assert "MATH-101" in codes
    assert "PHYS-101" in codes
    assert "CHEM-101" in codes

    assert codes["MATH-101"]["overall_mastery"] == 0.90
    assert codes["MATH-101"]["active_concept"] == "c_derivatives"
    assert codes["MATH-101"]["cohort_name"] == "Cohort 2026 Math"
    assert codes["MATH-101"]["class_name"] == "Grade 11-A Math"

    assert codes["CHEM-101"]["overall_mastery"] == 0.45
    assert codes["CHEM-101"]["active_concept"] == "c_first_law"
    assert codes["CHEM-101"]["class_name"] == "Grade 11-A Chem"


# ── Test 2: Course Selector Default & Context Resolution ───────────────────

def test_student_course_selector_default_and_context(setup_multi_course_env):
    """Verify StudentPortalController defaults to first enrolled course and builds full context."""
    env = setup_multi_course_env
    ctrl = StudentPortalController(db=env["db"])

    context = ctrl.get_dashboard_context(user_id=env["student_id"])
    assert context["portal"] == "student"
    assert context["student_id"] == env["student_id"]
    assert context["course_id"] in [env["math_course"].id, env["phys_course"].id, env["chem_course"].id]
    assert len(context["enrolled_courses"]) == 3
    assert "curriculum" in context
    assert "active_course" in context
    assert context["active_course"]["title"] is not None


# ── Test 3: Course Switching with Active Context Preservation ──────────────

def test_student_course_switching_active_context_preservation(setup_multi_course_env, client, monkeypatch):
    """Verify switching courses updates active context and subsequent queries reflect target course."""
    env = setup_multi_course_env
    monkeypatch.setattr("central_platform.api.routes.students._db", env["db"])
    monkeypatch.setattr("central_platform.api.routes.students._curriculum_service.db", env["db"])

    ctrl = StudentPortalController(db=env["db"])
    switch_res = ctrl.switch_course(
        student_id=env["student_id"],
        target_course_id=env["chem_course"].id,
        active_turn_generating=False,
    )
    assert switch_res["active_course_id"] == env["chem_course"].id
    assert switch_res["course_title"] == "Physical Chemistry"
    assert switch_res["active_concept"] == "c_first_law"
    assert switch_res["overall_mastery"] == 0.45

    # Test via API
    res = client.post(
        f"/api/v1/students/{env['student_id']}/courses/switch",
        json={"target_course_id": env["math_course"].id, "active_turn_generating": False},
    )
    assert res.status_code == 200
    api_data = res.json()["data"]
    assert api_data["active_course_id"] == env["math_course"].id
    assert api_data["course_title"] == "Calculus and Linear Algebra"
    assert api_data["active_concept"] == "c_derivatives"
    assert api_data["overall_mastery"] == 0.90


# ── Test 4: Safe Course Switching Concurrency Invariant ────────────────────

def test_safe_course_switching_invariant_turn_generating_blocked(setup_multi_course_env, client, monkeypatch):
    """Verify safe switching invariant: course switch is strictly rejected while AI turn is generating."""
    env = setup_multi_course_env
    monkeypatch.setattr("central_platform.api.routes.students._db", env["db"])
    monkeypatch.setattr("central_platform.api.routes.students._curriculum_service.db", env["db"])

    ctrl = StudentPortalController(db=env["db"])
    ctrl.set_turn_generating(env["student_id"], True)

    with pytest.raises(RuntimeError) as exc_info:
        ctrl.switch_course(env["student_id"], env["phys_course"].id)
    assert "Cannot switch courses while an AI turn is generating" in str(exc_info.value)

    # API returns 409 Conflict
    res = client.post(
        f"/api/v1/students/{env['student_id']}/courses/switch",
        json={"target_course_id": env["phys_course"].id, "active_turn_generating": True},
    )
    assert res.status_code == 409
    assert "Cannot switch course while an AI turn is actively generating" in res.json()["detail"]


# ── Test 5: Course Switching Unauthorized Course Rejected ─────────────────

def test_course_switching_unauthorized_course_rejected(setup_multi_course_env, client, monkeypatch):
    """Verify student cannot switch to a course they are not enrolled in."""
    env = setup_multi_course_env
    monkeypatch.setattr("central_platform.api.routes.students._db", env["db"])

    ctrl = StudentPortalController(db=env["db"])
    with pytest.raises(PermissionError) as exc:
        ctrl.switch_course(env["student_id"], "crs_unregistered_999")
    assert "is not enrolled in course" in str(exc.value)

    res = client.post(
        f"/api/v1/students/{env['student_id']}/courses/switch",
        json={"target_course_id": "crs_unregistered_999", "active_turn_generating": False},
    )
    assert res.status_code == 403


# ── Test 6: Scoped Curriculum Navigation Per Course ───────────────────────

def test_scoped_curriculum_navigation_per_course(setup_multi_course_env, client, monkeypatch):
    """Verify curriculum DAG navigation is strictly isolated per course and overlays mastery."""
    env = setup_multi_course_env
    monkeypatch.setattr("central_platform.api.routes.students._db", env["db"])
    monkeypatch.setattr("central_platform.api.routes.students._curriculum_service.db", env["db"])

    res_math = client.get(f"/api/v1/students/{env['student_id']}/courses/{env['math_course'].id}/curriculum")
    assert res_math.status_code == 200
    math_hier = res_math.json()["data"]
    concept_math = math_hier["modules"][0]["topics"][0]["concepts"][0]
    assert concept_math["id"] == "c_derivatives"
    assert concept_math["mastery_score"] == 0.90

    res_chem = client.get(f"/api/v1/students/{env['student_id']}/courses/{env['chem_course'].id}/curriculum")
    assert res_chem.status_code == 200
    chem_hier = res_chem.json()["data"]
    concept_chem = chem_hier["modules"][0]["topics"][0]["concepts"][0]
    assert concept_chem["id"] == "c_first_law"
    assert concept_chem["mastery_score"] == 0.45


# ── Test 7: Scoped Assignments Isolation Per Course ────────────────────────

def test_scoped_assignments_isolation_per_course(setup_multi_course_env, client, monkeypatch):
    """Verify assignments are strictly scoped per course with zero leakage across courses."""
    env = setup_multi_course_env
    db = env["db"]
    monkeypatch.setattr("central_platform.api.routes.students._db", db)

    asgn_math = Assignment(
        id=f"asgn_m_{uuid.uuid4().hex[:6]}",
        course_id=env["math_course"].id,
        assessment_id="asm-m1",
        title="Derivative Problem Set 1",
    )
    asgn_phys = Assignment(
        id=f"asgn_p_{uuid.uuid4().hex[:6]}",
        course_id=env["phys_course"].id,
        assessment_id="asm-p1",
        title="Projectile Motion Lab",
    )
    db.create_assignment(asgn_math)
    db.create_assignment(asgn_phys)

    res_m = client.get(f"/api/v1/students/{env['student_id']}/courses/{env['math_course'].id}/assignments")
    assert res_m.status_code == 200
    math_items = res_m.json()["data"]
    assert len(math_items) == 1
    assert math_items[0]["title"] == "Derivative Problem Set 1"

    res_p = client.get(f"/api/v1/students/{env['student_id']}/courses/{env['phys_course'].id}/assignments")
    assert res_p.status_code == 200
    phys_items = res_p.json()["data"]
    assert len(phys_items) == 1
    assert phys_items[0]["title"] == "Projectile Motion Lab"


# ── Test 8: Scoped Assignments Class Group Boundary ───────────────────────

def test_scoped_assignments_class_group_boundary(setup_multi_course_env, client, monkeypatch):
    """Verify assignments assigned to Class Group 2 do not leak to student in Class Group 1."""
    env = setup_multi_course_env
    db = env["db"]
    monkeypatch.setattr("central_platform.api.routes.students._db", db)

    # Student is enrolled in cg2 (Grade 11-A Chem)
    asgn_for_cg2 = Assignment(
        id=f"asgn_c2_{uuid.uuid4().hex[:6]}",
        course_id=env["chem_course"].id,
        assessment_id="asm-c2",
        class_group_id=env["cg2"].id,
        title="11-A Hess Law Exercise",
    )
    asgn_for_cg3 = Assignment(
        id=f"asgn_c3_{uuid.uuid4().hex[:6]}",
        course_id=env["chem_course"].id,
        assessment_id="asm-c3",
        class_group_id=env["cg3"].id,
        title="11-B Specific Heat Capacity",
    )
    db.create_assignment(asgn_for_cg2)
    db.create_assignment(asgn_for_cg3)

    res = client.get(f"/api/v1/students/{env['student_id']}/courses/{env['chem_course'].id}/assignments")
    assert res.status_code == 200
    items = res.json()["data"]
    titles = [i["title"] for i in items]
    assert "11-A Hess Law Exercise" in titles
    assert "11-B Specific Heat Capacity" not in titles


# ── Test 9: Scoped Knowledge Sources and Remedial Notes ────────────────────

def test_scoped_knowledge_sources_and_remedial_notes(setup_multi_course_env, client, monkeypatch):
    """Verify RAG sources and remedial notes are scoped strictly to course and student target."""
    env = setup_multi_course_env
    db = env["db"]
    monkeypatch.setattr("central_platform.api.routes.students._db", db)

    src_public = RAGSource(
        id=f"rag_pub_{uuid.uuid4().hex[:6]}",
        organization_id=env["org_id"],
        course_id=env["chem_course"].id,
        subject="Chemistry",
        title="NCERT Thermodynamics Official Text",
        status="published",
        visibility_scope="course",
    )
    src_remedial_student = RAGSource(
        id=f"rag_rem_{uuid.uuid4().hex[:6]}",
        organization_id=env["org_id"],
        course_id=env["chem_course"].id,
        subject="Chemistry",
        title="Targeted Enthalpy Remediation Note",
        status="published",
        visibility_scope="student_targeted",
        target_student_ids=[env["student_id"]],
    )
    src_other_student = RAGSource(
        id=f"rag_oth_{uuid.uuid4().hex[:6]}",
        organization_id=env["org_id"],
        course_id=env["chem_course"].id,
        subject="Chemistry",
        title="Secret Remedial For Someone Else",
        status="published",
        visibility_scope="student_targeted",
        target_student_ids=[env["other_student_id"]],
    )
    db.create_rag_source(src_public)
    db.create_rag_source(src_remedial_student)
    db.create_rag_source(src_other_student)

    res = client.get(f"/api/v1/students/{env['student_id']}/courses/{env['chem_course'].id}/knowledge")
    assert res.status_code == 200
    items = res.json()["data"]
    titles = [s["title"] for s in items]
    assert "NCERT Thermodynamics Official Text" in titles
    assert "Targeted Enthalpy Remediation Note" in titles
    assert "Secret Remedial For Someone Else" not in titles


# ── Test 10: Real-time Offline Status and Caching Indicator ────────────────

def test_offline_status_and_caching_indicator(setup_multi_course_env, client, monkeypatch):
    """Verify offline status endpoint returns accurate caching indicators."""
    env = setup_multi_course_env
    monkeypatch.setattr("central_platform.api.routes.students._db", env["db"])

    res = client.get(f"/api/v1/students/{env['student_id']}/courses/{env['math_course'].id}/offline-status")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["student_id"] == env["student_id"]
    assert data["course_id"] == env["math_course"].id
    assert data["is_cached"] is True
    assert data["offline_available"] is True
    assert data["last_synced_at"] is not None


# ── Test 11: PySide6 Desktop Bridge Facade Student Slots ───────────────────

def test_desktop_bridge_facade_student_multi_course_slots(setup_multi_course_env, monkeypatch):
    """Verify PySide6 Bridge facade multi-course slots integrate seamlessly with student controller."""
    env = setup_multi_course_env
    reset_student_controller_singleton()

    ctrl = StudentPortalController(db=env["db"])
    monkeypatch.setattr("app.bridge.facade.get_student_portal_controller", lambda: ctrl)

    bridge = Bridge()

    # 1. get_student_courses
    courses_raw = bridge.get_student_courses(env["student_id"])
    courses_res = json.loads(courses_raw)
    assert courses_res["ok"] is True
    assert len(courses_res["courses"]) == 3

    # 2. switch_student_course
    switch_raw = bridge.switch_student_course(env["student_id"], env["phys_course"].id, active_turn_generating=False)
    switch_res = json.loads(switch_raw)
    assert switch_res["ok"] is True
    assert switch_res["data"]["active_course_id"] == env["phys_course"].id

    # 3. switch_student_course with active turn generation blocked
    bridge._generation_active = True
    blocked_raw = bridge.switch_student_course(env["student_id"], env["math_course"].id, active_turn_generating=False)
    blocked_res = json.loads(blocked_raw)
    assert blocked_res["ok"] is False
    assert "Cannot switch courses while an AI turn is generating" in blocked_res["error"]
    bridge._generation_active = False

    # 4. get_student_course_offline_status
    off_raw = bridge.get_student_course_offline_status(env["student_id"], env["phys_course"].id)
    off_res = json.loads(off_raw)
    assert off_res["ok"] is True
    assert off_res["offline_status"]["offline_available"] is True


# ── Test 12: UI Dashboard Structure and Control Binding ────────────────────

def test_student_dashboard_html_structure_and_controls():
    """Verify student_dashboard.html contains course switcher dropdown, offline badge, and JS handlers."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "app", "ui", "student_dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify Course Selector in Header
    assert 'id="courseSelector"' in content
    assert 'id="courseSwitcherContainer"' in content
    assert 'id="courseOfflineBadge"' in content
    assert 'StudentDashboardController.switchCourse' in content

    # Verify Controller logic
    assert 'loadCourses()' in content
    assert 'updateCourseMetaUI()' in content
    assert 'checkOfflineStatus()' in content
    assert 'Cannot switch course while an AI turn is actively generating' in content
    assert 'active_turn_generating' in content
