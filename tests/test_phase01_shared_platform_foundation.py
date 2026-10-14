"""Phase 01 Test Suite — Shared Platform Foundation and Safe Execution Boundary.

Fulfills Phase 01 Verification:
1. Enhanced database path resolution diagnostics (DEF-P00-01).
2. Migration 009 forward application, table schema integrity, and reversible down migration.
3. Canonical Person, Student, Guardian, and Staff identity models with tenant isolation.
4. Student-Guardian relationship authorization (pickup, emergency contact, portal access).
5. Module entitlement checking preventing synthetic mock fallbacks for disabled ERP modules.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
import pytest
from pathlib import Path

from central_platform.config import resolve_database_path


def test_database_resolution_diagnostic_guidance():
    """Verify that a missing database path in production mode provides actionable migration instructions."""
    envs = {
        "GAYATRI_ENV": "production",
        "GAYATRI_DB_PATH": "non_existent_test_db_file.db",
    }
    with pytest.raises(RuntimeError) as exc_info:
        resolve_database_path(envs, is_prod=True)
    msg = str(exc_info.value)
    assert "Production startup aborted" in msg
    assert "migrate_db.py" in msg


def test_migration_009_schema_and_down_script(tmp_path):
    """Verify migration 009 up and down scripts on an isolated database."""
    test_db = tmp_path / "test_migration_009.db"
    
    # 1. Run migrations 001 through 008 first
    repo_root = Path(__file__).parent.parent
    migrations_dir = repo_root / "migrations"
    
    conn = sqlite3.connect(test_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    
    for i in range(1, 9):
        up_file = list(migrations_dir.glob(f"{i:03d}_*.sql"))
        # filter out down scripts
        up_file = [f for f in up_file if not f.name.endswith("_down.sql")][0]
        with open(up_file, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
            
    # 2. Apply migration 009
    mig_009_up = migrations_dir / "009_shared_identity_and_entitlements.sql"
    assert mig_009_up.exists(), "Migration 009 up script must exist"
    with open(mig_009_up, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
        
    # Check tables exist
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    
    expected_new_tables = {
        "persons",
        "student_profiles",
        "guardian_profiles",
        "student_guardian_links",
        "staff_profiles",
        "module_entitlements",
        "domain_events_outbox",
    }
    for tbl in expected_new_tables:
        assert tbl in tables, f"Expected table {tbl} was not created by migration 009"
        
    # 3. Test down script
    mig_009_down = migrations_dir / "009_shared_identity_and_entitlements_down.sql"
    assert mig_009_down.exists(), "Migration 009 down script must exist"
    with open(mig_009_down, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
        
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    remaining_tables = {row[0] for row in cursor.fetchall()}
    for tbl in expected_new_tables:
        assert tbl not in remaining_tables, f"Table {tbl} should have been dropped by migration 009 down script"
        
    conn.close()


def test_shared_identity_service_and_guardian_linkage(tmp_path):
    """Verify Person, StudentProfile, GuardianProfile creation and relationship linking."""
    from central_platform.db import PlatformDatabase
    
    test_db = str(tmp_path / "test_identity.db")
    db = PlatformDatabase(db_path=test_db)
    
    org_id = f"org_{uuid.uuid4().hex[:8]}"
    db.create_organization(org_id=org_id, name="Test Modern Academy")
    
    # Create Student Person & Profile
    student_person_id = f"per_{uuid.uuid4().hex[:8]}"
    db.create_person(
        person_id=student_person_id,
        organization_id=org_id,
        first_name="Aarav",
        last_name="Sharma",
        email="aarav.sharma@example.edu",
        phone="+919876543210",
        date_of_birth="2010-05-15",
        gender="male",
    )
    
    student_profile_id = f"stu_{uuid.uuid4().hex[:8]}"
    db.create_student_profile(
        student_id=student_profile_id,
        person_id=student_person_id,
        organization_id=org_id,
        admission_number="ADM-2026-001",
        roll_number="10A-01",
        academic_status="active",
    )
    
    # Create Guardian Person & Profile
    guardian_person_id = f"per_{uuid.uuid4().hex[:8]}"
    db.create_person(
        person_id=guardian_person_id,
        organization_id=org_id,
        first_name="Rajesh",
        last_name="Sharma",
        email="rajesh.sharma@example.com",
        phone="+919876543211",
        date_of_birth="1980-02-10",
        gender="male",
    )
    
    guardian_profile_id = f"grd_{uuid.uuid4().hex[:8]}"
    db.create_guardian_profile(
        guardian_id=guardian_profile_id,
        person_id=guardian_person_id,
        organization_id=org_id,
        occupation="Software Architect",
        is_legal_guardian=True,
    )
    
    # Link Student and Guardian with explicit authorizations
    link_id = db.link_student_guardian(
        organization_id=org_id,
        student_id=student_profile_id,
        guardian_id=guardian_profile_id,
        relationship="father",
        is_primary_contact=True,
        is_emergency_contact=True,
        is_pickup_authorized=True,
        can_access_portal=True,
    )
    assert link_id is not None
    
    # Query Guardians for Student
    guardians = db.get_student_guardians(organization_id=org_id, student_id=student_profile_id)
    assert len(guardians) == 1
    g = guardians[0]
    assert g["relationship"] == "father"
    assert g["is_pickup_authorized"] is True
    assert g["first_name"] == "Rajesh"


def test_cross_tenant_identity_isolation(tmp_path):
    """Verify that identity queries strictly isolate tenant records."""
    from central_platform.db import PlatformDatabase
    
    test_db = str(tmp_path / "test_isolation.db")
    db = PlatformDatabase(db_path=test_db)
    
    org_a = f"org_a_{uuid.uuid4().hex[:6]}"
    org_b = f"org_b_{uuid.uuid4().hex[:6]}"
    db.create_organization(org_id=org_a, name="Academy Alpha")
    db.create_organization(org_id=org_b, name="School Beta")
    
    person_a = f"per_{uuid.uuid4().hex[:6]}"
    db.create_person(
        person_id=person_a,
        organization_id=org_a,
        first_name="AlphaStudent",
        last_name="One",
    )
    student_a = f"stu_{uuid.uuid4().hex[:6]}"
    db.create_student_profile(
        student_id=student_a,
        person_id=person_a,
        organization_id=org_a,
        admission_number="ADM-A-1",
    )
    
    # Org B must not see student A
    guardians_under_b = db.get_student_guardians(organization_id=org_b, student_id=student_a)
    assert len(guardians_under_b) == 0
    
    profile_under_b = db.get_student_profile(organization_id=org_b, student_id=student_a)
    assert profile_under_b is None


def test_module_entitlement_enforcement(tmp_path):
    """Verify that unentitled ERP modules fail closed with 403 rather than synthetic mock success."""
    from central_platform.db import PlatformDatabase
    from central_platform.entitlements.manager import EntitlementManager
    
    test_db = str(tmp_path / "test_entitlements.db")
    db = PlatformDatabase(db_path=test_db)
    
    org_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(org_id=org_id, name="Piloting School")
    
    ent_mgr = EntitlementManager(db)
    
    # By default, ERP modules are disabled
    assert ent_mgr.is_entitled(org_id, "erp_admissions") is False
    assert ent_mgr.is_entitled(org_id, "erp_hostel") is False
    
    # Enable erp_admissions
    ent_mgr.set_entitlement(org_id, "erp_admissions", enabled=True, tier="pilot")
    assert ent_mgr.is_entitled(org_id, "erp_admissions") is True
    assert ent_mgr.is_entitled(org_id, "erp_hostel") is False
    
    # Assert requirement dependency raises when module is disabled
    with pytest.raises(PermissionError, match="Feature module 'erp_hostel' is not entitled"):
        ent_mgr.assert_entitled(org_id, "erp_hostel")


def test_identity_api_endpoints_and_rbac():
    """Verify identity and entitlements HTTP endpoints on FastAPI TestClient."""
    from fastapi.testclient import TestClient
    from central_platform.api.app import create_app
    from central_platform.auth.tokens import create_access_token
    from central_platform.db import PlatformDatabase

    db = PlatformDatabase()
    org_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(org_id=org_id, name="HTTP Testing Org")

    app = create_app()
    client = TestClient(app)

    # 1. Admin Token
    admin_token = create_access_token(
        user_id="admin_user_1",
        role="admin",
        organization_id=org_id,
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Create Person via API
    resp = client.post(
        "/api/v1/identity/persons",
        headers=headers,
        json={
            "first_name": "Kavya",
            "last_name": "Patel",
            "email": "kavya.patel@example.edu",
            "phone": "+919123456789",
            "gender": "female",
            "city": "Ahmedabad",
        },
    )
    assert resp.status_code == 201
    person_data = resp.json()["person"]
    person_id = person_data["id"]

    # 3. Retrieve Person via API
    resp = client.get(f"/api/v1/identity/persons/{person_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["person"]["first_name"] == "Kavya"

    # 4. Check Entitlements API
    resp = client.get("/api/v1/identity/entitlements", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["organization_id"] == org_id

    # 5. Set Entitlement via API (Admin permitted)
    resp = client.post(
        "/api/v1/identity/entitlements",
        headers=headers,
        json={"module_key": "erp_admissions", "is_enabled": True, "tier": "enterprise"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is True

    # 6. Non-admin user forbidden to configure entitlements
    student_token = create_access_token(
        user_id="student_user_1",
        role="student",
        organization_id=org_id,
    )
    student_headers = {"Authorization": f"Bearer {student_token}"}
    resp = client.post(
        "/api/v1/identity/entitlements",
        headers=student_headers,
        json={"module_key": "erp_hostel", "is_enabled": True},
    )
    assert resp.status_code == 403

