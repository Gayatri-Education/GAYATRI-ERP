"""Phase 02 — Parent Portal Remediation Test Suite (QA-002).

Verifies:
1. Real domain metrics derived from database and domain services (no hardcoded 84%/96.5%).
2. Empty evidence returns honest zero and empty states (differentiating zero from error).
3. Unauthenticated context returns clean baseline without fake child data.
4. Unrelated parent-child access rejected with PermissionError.
5. Cross-tenant child access rejected with PermissionError.
6. Disabled/revoked parent accounts rejected with PermissionError.
7. Privacy BLOCKED policy rejected with PermissionError.
8. Subsystem exceptions do not silently fall back to plausible fake metrics.
9. Child switching fails closed and never leaks stale child data on failure.
10. Demo mode is marked with is_demo=True in non-production.
11. Production mode strictly forbids demo mode and sample content.
12. Restart/read-back test verifies persisted parent-child metrics across DB instances.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest

from app.portals.parent.controller import ParentPortalController
from central_platform.db import PlatformDatabase
from central_platform.models.fees import FeeAccount
from central_platform.models.schema import (
    Course,
    MasteryState,
    Organization,
    Session,
    StudentLearningRecord,
    User,
    UserRole,
)
from central_platform.privacy.policies import (
    ParentVisibilityLevel,
    PrivacyRulesEngine,
    StudentPrivacySetting,
)


@pytest.fixture(autouse=True)
def reset_privacy_rules():
    """Ensure clean privacy rule state before and after each test."""
    PrivacyRulesEngine._policy_store.clear()
    PrivacyRulesEngine._parent_student_links.clear()
    yield
    PrivacyRulesEngine._policy_store.clear()
    PrivacyRulesEngine._parent_student_links.clear()


@pytest.fixture
def clean_parent_db(tmp_path: Path):
    """Isolated temporary database for parent portal tests."""
    db_file = tmp_path / "test_parent_portal.db"
    db = PlatformDatabase(db_path=str(db_file))
    return db


def _setup_linked_family(
    db: PlatformDatabase,
    org_id: str,
    parent_id: str,
    child_id: str,
    parent_name: str = "Parent User",
    child_name: str = "Student User",
    can_access_portal: bool = True,
    is_active: bool = True,
):
    """Helper to seed complete relational persons, profiles, user accounts, and links."""
    p_per = f"per_{parent_id}"
    c_per = f"per_{child_id}"

    db.create_person(
        person_id=p_per,
        organization_id=org_id,
        first_name=parent_name.split()[0],
        last_name=parent_name.split()[-1] if len(parent_name.split()) > 1 else "",
        email=f"{parent_id}@test.org",
    )
    db.create_person(
        person_id=c_per,
        organization_id=org_id,
        first_name=child_name.split()[0],
        last_name=child_name.split()[-1] if len(child_name.split()) > 1 else "",
        email=f"{child_id}@test.org",
    )
    db.create_student_profile(student_id=child_id, person_id=c_per, organization_id=org_id)
    db.create_guardian_profile(guardian_id=parent_id, person_id=p_per, organization_id=org_id)

    db.create_user(
        User(
            id=parent_id,
            organization_id=org_id,
            email=f"{parent_id}@test.org",
            full_name=parent_name,
            role=UserRole.PARENT,
            is_active=is_active,
        )
    )
    db.create_user(
        User(
            id=child_id,
            organization_id=org_id,
            email=f"{child_id}@test.org",
            full_name=child_name,
            role=UserRole.STUDENT,
        )
    )

    db.link_student_guardian(
        organization_id=org_id,
        student_id=child_id,
        guardian_id=parent_id,
        relationship="PARENT",
        can_access_portal=can_access_portal,
    )
    if can_access_portal:
        PrivacyRulesEngine.link_parent_student(parent_id, child_id)


def test_real_metrics_from_database_and_services(clean_parent_db: PlatformDatabase):
    """Real database records populate genuine metrics rather than static defaults."""
    db = clean_parent_db
    org_id = "org_parent_real"
    parent_id = "usr_parent_real"
    child_id = "usr_child_real"

    db.create_organization(Organization(id=org_id, name="Parent Real Org", slug="parent-real-org"))
    _setup_linked_family(
        db,
        org_id=org_id,
        parent_id=parent_id,
        child_id=child_id,
        parent_name="Savitri Devi",
        child_name="Aarav Real",
    )

    # Seed learning progress (SLR + Mastery)
    course_id = "crs_math_real"
    db.create_course(Course(id=course_id, organization_id=org_id, code="MATH-10", title="Grade 10 Mathematics"))
    slr_id = "slr_aarav_real"
    db.create_slr(StudentLearningRecord(id=slr_id, student_id=child_id, course_id=course_id))
    db.upsert_mastery_state(MasteryState(id="ms_aarav_1", slr_id=slr_id, concept_id="algebra_linear", p_mastery=0.91, score=0.91, state="mastered"))
    db.upsert_mastery_state(MasteryState(id="ms_aarav_2", slr_id=slr_id, concept_id="geometry_triangles", p_mastery=0.75, score=0.75, state="in_progress"))

    # Seed attendance sessions
    for i in range(3):
        db.create_session(
            Session(
                id=f"sess_aarav_{i}",
                student_id=child_id,
                course_id=course_id,
                concept_id="algebra_linear",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
        )

    # Seed fee account
    db.create_fee_account(FeeAccount(id="fa_aarav_real", org_id=org_id, student_id=child_id, balance_due=1500.0))

    ctrl = ParentPortalController(db=db)
    ctx = ctrl.get_dashboard_context(user_id=parent_id, child_id=child_id, organization_id=org_id)

    assert ctx["portal"] == "parent"
    assert ctx["version"] == "v4.0"
    assert ctx["parent_id"] == parent_id
    assert ctx["user_name"] == "Savitri Devi"
    assert ctx["selected_child_id"] == child_id
    assert ctx["child_name"] == "Aarav Real"
    assert ctx["state"] == "ACTIVE"

    summary = ctx["summary"]
    assert summary is not None
    # Expected average of 0.91 and 0.75 is 0.83 -> 83%
    assert summary["overall_mastery_pct"] == 83
    assert summary["mastery_status"] == "AVAILABLE"
    assert summary["attendance_pct"] == 95.0
    assert summary["fee_balance"] == 1500.0


def test_empty_database_returns_honest_zeros(clean_parent_db: PlatformDatabase):
    """Empty database for linked child returns honest zero metrics without fake percentages."""
    db = clean_parent_db
    org_id = "org_parent_empty"
    parent_id = "usr_parent_empty"
    child_id = "usr_child_empty"

    db.create_organization(Organization(id=org_id, name="Empty Org", slug="empty-org"))
    _setup_linked_family(
        db,
        org_id=org_id,
        parent_id=parent_id,
        child_id=child_id,
        parent_name="Ramesh Kumar",
        child_name="Suresh Kumar",
    )

    ctrl = ParentPortalController(db=db)
    ctx = ctrl.get_dashboard_context(user_id=parent_id, child_id=child_id, organization_id=org_id)

    assert ctx["state"] == "ACTIVE"
    summary = ctx["summary"]
    assert summary is not None
    # Must be honest 0, NEVER fallback to 84 or 96.5
    assert summary["overall_mastery_pct"] == 0
    assert summary["attendance_pct"] == 0.0
    assert summary["pending_assignments_count"] == 0
    assert summary["fee_balance"] == 0.0


def test_unauthenticated_baseline_returns_honest_empty_context(clean_parent_db: PlatformDatabase):
    """Calling get_dashboard_context without identity returns honest baseline without fake child data."""
    ctrl = ParentPortalController(db=clean_parent_db)
    ctx = ctrl.get_dashboard_context()

    assert ctx["portal"] == "parent"
    assert ctx["version"] == "v4.0"
    assert ctx["parent_id"] is None
    assert ctx["selected_child_id"] is None
    assert ctx["children"] == []
    assert ctx["state"] == "UNAUTHENTICATED"
    assert ctx["summary"] is None


def test_unrelated_parent_child_raises_permission_error(clean_parent_db: PlatformDatabase):
    """Parent attempting to access unlinked child is rejected with PermissionError."""
    db = clean_parent_db
    org_id = "org_iso_test"
    parent_a = "usr_parent_a"
    child_b = "usr_child_b"

    db.create_organization(Organization(id=org_id, name="Iso Org", slug="iso-org"))
    db.create_user(User(id=parent_a, organization_id=org_id, email="pa@iso.org", full_name="Parent A", role=UserRole.PARENT))
    db.create_user(User(id=child_b, organization_id=org_id, email="cb@iso.org", full_name="Child B", role=UserRole.STUDENT))

    ctrl = ParentPortalController(db=db)

    with pytest.raises(PermissionError) as exc_info:
        ctrl.get_dashboard_context(user_id=parent_a, child_id=child_b, organization_id=org_id)
    assert "not linked or authorized" in str(exc_info.value).lower()


def test_cross_tenant_child_access_raises_permission_error(clean_parent_db: PlatformDatabase):
    """Parent from Org Alpha querying child in Org Beta is rejected with PermissionError."""
    db = clean_parent_db
    org_alpha = "org_tenant_alpha"
    org_beta = "org_tenant_beta"
    parent_id = "usr_parent_alpha"
    child_id = "usr_child_beta"

    db.create_organization(Organization(id=org_alpha, name="Alpha", slug="alpha"))
    db.create_organization(Organization(id=org_beta, name="Beta", slug="beta"))
    db.create_user(User(id=parent_id, organization_id=org_alpha, email="p@alpha.org", full_name="Alpha Parent", role=UserRole.PARENT))
    db.create_user(User(id=child_id, organization_id=org_beta, email="c@beta.org", full_name="Beta Child", role=UserRole.STUDENT))

    # Even if linked in PrivacyRulesEngine, tenant mismatch must fail
    PrivacyRulesEngine.link_parent_student(parent_id, child_id)

    ctrl = ParentPortalController(db=db)
    with pytest.raises(PermissionError) as exc_info:
        ctrl.get_dashboard_context(user_id=parent_id, child_id=child_id, organization_id=org_alpha)
    assert "cross-tenant" in str(exc_info.value).lower()


def test_disabled_parent_account_raises_permission_error(clean_parent_db: PlatformDatabase):
    """Parent account marked inactive/disabled is rejected with PermissionError."""
    db = clean_parent_db
    org_id = "org_disabled_test"
    parent_id = "usr_parent_disabled"
    child_id = "usr_child_active"

    db.create_organization(Organization(id=org_id, name="Dis Org", slug="dis-org"))
    _setup_linked_family(
        db,
        org_id=org_id,
        parent_id=parent_id,
        child_id=child_id,
        parent_name="Disabled Parent",
        child_name="Active Child",
        is_active=False,
    )

    ctrl = ParentPortalController(db=db)
    with pytest.raises(PermissionError) as exc_info:
        ctrl.get_dashboard_context(user_id=parent_id, child_id=child_id, organization_id=org_id)
    assert "disabled or revoked" in str(exc_info.value).lower()


def test_privacy_blocked_child_access_raises_permission_error(clean_parent_db: PlatformDatabase):
    """Parent querying child with BLOCKED privacy level is rejected with PermissionError."""
    db = clean_parent_db
    org_id = "org_blocked_test"
    parent_id = "usr_parent_blocked"
    child_id = "usr_child_blocked"

    db.create_organization(Organization(id=org_id, name="Block Org", slug="block-org"))
    _setup_linked_family(
        db,
        org_id=org_id,
        parent_id=parent_id,
        child_id=child_id,
        parent_name="Blocked Parent",
        child_name="Blocked Child",
    )
    PrivacyRulesEngine.set_privacy_setting(
        StudentPrivacySetting(
            student_id=child_id,
            parent_id=parent_id,
            visibility_level=ParentVisibilityLevel.BLOCKED,
        )
    )

    ctrl = ParentPortalController(db=db)
    with pytest.raises(PermissionError) as exc_info:
        ctrl.get_dashboard_context(user_id=parent_id, child_id=child_id, organization_id=org_id)
    assert "blocked by institutional privacy policy" in str(exc_info.value).lower()


def test_subsystem_failure_does_not_fall_back_to_fake_numbers(clean_parent_db: PlatformDatabase, monkeypatch):
    """A database error in attendance or fee lookup produces explicit degraded state, not fake metrics."""
    db = clean_parent_db
    org_id = "org_failover_test"
    parent_id = "usr_parent_deg"
    child_id = "usr_child_deg"

    db.create_organization(Organization(id=org_id, name="Deg Org", slug="deg-org"))
    _setup_linked_family(
        db,
        org_id=org_id,
        parent_id=parent_id,
        child_id=child_id,
        parent_name="Deg Parent",
        child_name="Deg Child",
    )

    ctrl = ParentPortalController(db=db)

    # Invalidate sessions query to simulate attendance subsystem failure
    def broken_sessions(sid):
        raise RuntimeError("Attendance DB connection timeout")

    monkeypatch.setattr(db, "get_sessions_for_student", broken_sessions)

    summary = ctrl.get_child_summary(parent_id, child_id, organization_id=org_id, db=db)
    assert summary["attendance_status"] == "UNAVAILABLE"
    assert summary["attendance_pct"] == 0.0
    # Mastery remains honest 0 and available, not corrupted by attendance failure
    assert summary["overall_mastery_pct"] == 0
    assert summary["mastery_status"] == "AVAILABLE"


def test_child_switch_isolation_no_stale_data_on_failure(clean_parent_db: PlatformDatabase):
    """Failed child switch resets active context and never leaks previous child's data."""
    db = clean_parent_db
    org_id = "org_switch_test"
    parent_id = "usr_parent_sw"
    child_valid = "usr_child_valid"
    child_unauthorized = "usr_child_unauth"

    db.create_organization(Organization(id=org_id, name="Sw Org", slug="sw-org"))
    _setup_linked_family(
        db,
        org_id=org_id,
        parent_id=parent_id,
        child_id=child_valid,
        parent_name="Switch Parent",
        child_name="Valid Child",
    )
    db.create_user(User(id=child_unauthorized, organization_id=org_id, email="cu@sw.org", full_name="Unauthorized Child", role=UserRole.STUDENT))

    ctrl = ParentPortalController(db=db)

    # 1. Switch to valid child
    ctx1 = ctrl.switch_child(parent_id=parent_id, target_child_id=child_valid, organization_id=org_id)
    assert ctx1["selected_child_id"] == child_valid
    assert ctrl._active_children[parent_id] == child_valid

    # 2. Switch to unauthorized child -> must fail closed
    with pytest.raises(PermissionError):
        ctrl.switch_child(parent_id=parent_id, target_child_id=child_unauthorized, organization_id=org_id)

    # 3. Active child MUST be cleared, preventing stale child leakage
    assert ctrl._active_children[parent_id] is None


def test_explicit_demo_mode_in_non_production(monkeypatch):
    """In non-production, demo_mode=True returns sample data marked with is_demo=True and visual banner."""
    monkeypatch.delenv("GAYATRI_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    ctrl = ParentPortalController()
    ctx = ctrl.get_dashboard_context(user_id="parent_001", child_id="child_101", demo_mode=True)

    assert ctx["is_demo"] is True
    assert "DEMO MODE" in ctx.get("demo_banner", "")
    assert ctx["selected_child_id"] == "child_101"
    assert ctx["summary"]["overall_mastery_pct"] == 84


def test_production_mode_forbids_demo_mode_and_sample_content(monkeypatch, clean_parent_db: PlatformDatabase):
    """When GAYATRI_ENV=production, requesting demo_mode raises ValueError, and sample identities return empty/fail."""
    monkeypatch.setenv("GAYATRI_ENV", "production")

    ctrl = ParentPortalController(db=clean_parent_db)

    # 1. Explicit demo_mode in production raises ValueError
    with pytest.raises(ValueError) as exc_info:
        ctrl.get_dashboard_context(user_id="parent_001", demo_mode=True)
    assert "prohibited in production" in str(exc_info.value).lower()

    # 2. In production, unlinked demo placeholder does NOT get fake metrics
    with pytest.raises(PermissionError):
        ctrl.get_dashboard_context(user_id="parent_001", child_id="child_101", demo_mode=False)


def test_restart_read_back_persistence(tmp_path: Path):
    """Metrics written to database persist across connection restart and are read back accurately."""
    db_path = str(tmp_path / "durable_parent_test.db")

    # Instance 1: write records
    db1 = PlatformDatabase(db_path=db_path)
    org_id = "org_restart_par"
    parent_id = "usr_p_restart"
    child_id = "usr_c_restart"

    db1.create_organization(Organization(id=org_id, name="Restart Org", slug="restart-org"))
    _setup_linked_family(
        db1,
        org_id=org_id,
        parent_id=parent_id,
        child_id=child_id,
        parent_name="Durable Parent",
        child_name="Durable Child",
    )

    course_id = "crs_durable"
    db1.create_course(Course(id=course_id, organization_id=org_id, code="DUR-1", title="Durable Science"))
    slr_id = "slr_durable"
    db1.create_slr(StudentLearningRecord(id=slr_id, student_id=child_id, course_id=course_id))
    db1.upsert_mastery_state(MasteryState(id="ms_dur", slr_id=slr_id, concept_id="durable_atoms", p_mastery=0.88, score=0.88, state="mastered"))

    del db1

    # Instance 2: read back using separate instance
    db2 = PlatformDatabase(db_path=db_path)
    ctrl = ParentPortalController(db=db2)
    ctx = ctrl.get_dashboard_context(user_id=parent_id, child_id=child_id, organization_id=org_id)

    assert ctx["parent_id"] == parent_id
    assert ctx["selected_child_id"] == child_id
    assert ctx["user_name"] == "Durable Parent"
    assert ctx["child_name"] == "Durable Child"
    assert ctx["summary"]["overall_mastery_pct"] == 88
    assert ctx["summary"]["mastery_status"] == "AVAILABLE"
