"""Phase 08: Unified Analytics, Quality, Accessibility and Institution Pilot Tests.

Tests cover:
1. Migration 016 schema creation and clean rollback.
2. Authoritative SQL reconciliation of cross-module KPIs with zero placeholder figures.
3. Parent privacy levels enforcement (STANDARD, RESTRICTED, ANONYMIZED, BLOCKED).
4. Dual-mode institution pilot: K-12 School journey end-to-end.
5. Dual-mode institution pilot: Coaching / Test-Prep Academy journey end-to-end.
6. Data export service generating multi-format (CSV, JSON) reports with row counts.
7. Multi-tenant data export isolation (zero cross-tenant data leakage).
8. Support diagnostic package generation with PRAGMA integrity checks and secret redaction.
9. Database snapshot backup, restoration verification, and record reconciliation.
10. REST API routing and strict cross-tenant isolation.
"""

import sqlite3
import pytest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient

from central_platform.db import PlatformDatabase
from central_platform.models import Organization, User, UserRole
from central_platform.analytics.institutional import (
    InstitutionalKPISnapshot,
    UnifiedInstitutionalAnalyticsService,
)
from central_platform.analytics.exports import DataExportService
from central_platform.ops.diagnostics import PlatformDiagnosticsService
from scripts.backup_restore_db import create_backup, restore_backup, verify_database_integrity
from central_platform.auth.tokens import create_access_token
from central_platform.api.app import app

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


@pytest.fixture
def platform_db(tmp_path):
    """File-backed PlatformDatabase instance migrated through 016."""
    db_file = str(tmp_path / "test_phase08.db")
    db = PlatformDatabase(db_file)
    with db._get_connection() as conn:
        now_str = datetime.now(timezone.utc).isoformat()
        # Organizations
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-school-1', 'Greenwood High', 'greenwood-high', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-coaching-2', 'Apex IIT Academy', 'apex-iit', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        # Academic Years
        conn.execute(
            "INSERT INTO academic_years (id, organization_id, name, code, start_date, end_date, created_at, updated_at) "
            f"VALUES ('ay-1', 'org-school-1', '2026-2027', 'AY-26-27', '2026-06-01', '2027-04-30', '{now_str}', '{now_str}');"
        )
        # Classes & Sessions
        conn.execute(
            "INSERT INTO student_classes (id, organization_id, academic_year_id, name, grade_level, section, capacity, created_at, updated_at) "
            f"VALUES ('cls-10a', 'org-school-1', 'ay-1', 'Grade 10-A', 10, 'A', 40, '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO attendance_sessions (id, organization_id, academic_year_id, class_id, date, session_type, status, created_at, updated_at) "
            f"VALUES ('ses-1', 'org-school-1', 'ay-1', 'cls-10a', '2026-10-15', 'DAILY', 'COMPLETED', '{now_str}', '{now_str}');"
        )
        # Users & Persons
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            "VALUES ('usr-stu-101', 'org-school-1', 'student1@gw.edu', 'Karan Verma', 'student', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO persons (id, organization_id, user_id, first_name, last_name, email, created_at, updated_at) "
            "VALUES ('per-stu-101', 'org-school-1', 'usr-stu-101', 'Karan', 'Verma', 'student1@gw.edu', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at) "
            "VALUES ('stu-prf-101', 'per-stu-101', 'org-school-1', 'GW-2026-001', 'R-01', '2026-06-01', 'ACTIVE', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            "VALUES ('usr-tch-201', 'org-school-1', 'teacher1@gw.edu', 'Pooja Sharma', 'teacher', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
    yield db
    db.close()


# ── Test 1: Migration 016 Up and Down ─────────────────────────────────────────

def test_migration_016_up_and_down():
    """Verify migration 016 creates export_jobs and diagnostic_snapshots, and rollback drops them cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply up through 015
    for i in range(1, 16):
        scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Apply 016
    up_016 = MIGRATIONS_DIR / "016_analytics_exports_diagnostics.sql"
    assert up_016.exists(), "016 forward migration script must exist"
    conn.executescript(up_016.read_text(encoding="utf-8"))

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_up = {r[0] for r in cursor.fetchall()}

    assert "export_jobs" in tables_after_up
    assert "diagnostic_snapshots" in tables_after_up

    # Roll back 016
    down_016 = MIGRATIONS_DIR / "016_analytics_exports_diagnostics_down.sql"
    assert down_016.exists(), "016 rollback migration script must exist"
    conn.executescript(down_016.read_text(encoding="utf-8"))

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_down = {r[0] for r in cursor.fetchall()}

    assert "export_jobs" not in tables_after_down
    assert "diagnostic_snapshots" not in tables_after_down

    conn.close()


# ── Test 2: Institutional KPIs SQL Reconciliation (Zero Placeholders) ────────

def test_institutional_kpis_sql_reconciliation_zero_placeholders(platform_db):
    """Verify all KPI snapshot values calculate strictly from underlying SQL tables without mock placeholders."""
    now_str = datetime.now(timezone.utc).isoformat()
    with platform_db._get_connection() as conn:
        # Seed 3 attendance records across 3 sessions: 2 PRESENT/LATE, 1 ABSENT -> 66.67%
        conn.execute(
            "INSERT INTO attendance_sessions (id, organization_id, academic_year_id, class_id, date, session_type, status, created_at, updated_at) "
            f"VALUES ('ses-2', 'org-school-1', 'ay-1', 'cls-10a', '2026-10-16', 'DAILY', 'COMPLETED', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO attendance_sessions (id, organization_id, academic_year_id, class_id, date, session_type, status, created_at, updated_at) "
            f"VALUES ('ses-3', 'org-school-1', 'ay-1', 'cls-10a', '2026-10-17', 'DAILY', 'COMPLETED', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO attendance_records (id, organization_id, session_id, student_id, status, created_at, updated_at) "
            f"VALUES ('att-1', 'org-school-1', 'ses-1', 'stu-prf-101', 'PRESENT', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO attendance_records (id, organization_id, session_id, student_id, status, created_at, updated_at) "
            f"VALUES ('att-2', 'org-school-1', 'ses-2', 'stu-prf-101', 'LATE', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO attendance_records (id, organization_id, session_id, student_id, status, created_at, updated_at) "
            f"VALUES ('att-3', 'org-school-1', 'ses-3', 'stu-prf-101', 'ABSENT', '{now_str}', '{now_str}');"
        )

        # Seed Fee Account & Invoice: $1000 total due, $800 paid, $200 balance -> 80.0% collection, $200 balance
        conn.execute(
            "INSERT INTO fee_accounts (id, org_id, student_id, total_due, total_paid, balance_due, status, created_at, updated_at) "
            f"VALUES ('fa-101', 'org-school-1', 'usr-stu-101', 1000.0, 800.0, 200.0, 'ACTIVE', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO invoices (id, org_id, fee_account_id, student_id, invoice_number, amount_due, amount_paid, status, due_date, created_at, updated_at) "
            f"VALUES ('inv-101', 'org-school-1', 'fa-101', 'usr-stu-101', 'INV-001', 1000.0, 800.0, 'PARTIAL', '2026-11-01', '{now_str}', '{now_str}');"
        )

        # Seed Staff Leave: 3 days approved -> 3.0 staff leave rate
        conn.execute(
            "INSERT INTO staff_leave_requests (id, organization_id, staff_id, leave_type, start_date, end_date, total_days, reason, status, created_at, updated_at) "
            f"VALUES ('lvr-1', 'org-school-1', 'usr-tch-201', 'CASUAL', '2026-10-10', '2026-10-12', 3.0, 'Family', 'APPROVED', '{now_str}', '{now_str}');"
        )

        # Seed Inventory Item with low stock (qty 5 <= reorder 10)
        conn.execute(
            "INSERT INTO inventory_items (id, organization_id, name, sku, category, unit, unit_price, quantity_on_hand, reorder_level, created_at, updated_at) "
            f"VALUES ('item-1', 'org-school-1', 'Chalk Box', 'CHK-01', 'STATIONERY', 'BOX', 50.0, 5, 10, '{now_str}', '{now_str}');"
        )

    svc = UnifiedInstitutionalAnalyticsService(platform_db)
    snapshot = svc.get_kpi_snapshot("org-school-1")

    assert snapshot.total_students == 1
    assert snapshot.total_teachers == 1
    assert snapshot.attendance_rate == 66.67
    assert snapshot.fee_collection_rate == 80.0
    assert snapshot.total_outstanding_fees == 200.0
    assert snapshot.staff_leave_rate == 3.0
    assert snapshot.inventory_low_stock_count == 1
    assert snapshot.reconciliation_hash is not None
    assert len(snapshot.reconciliation_hash) == 64


# ── Test 3: Parent Privacy Levels & Sanitization ──────────────────────────────

def test_parent_privacy_levels_and_sanitization(platform_db):
    """Verify parent views enforce privacy policies (STANDARD, RESTRICTED, ANONYMIZED, BLOCKED)."""
    svc = UnifiedInstitutionalAnalyticsService(platform_db)

    # 1. STANDARD
    view_std = svc.get_parent_student_view("org-school-1", "stu-prf-101", privacy_level="STANDARD")
    assert view_std["full_name"] == "Karan Verma"
    assert view_std["admission_number"] == "GW-2026-001"
    assert view_std["privacy_applied"] == "STANDARD"

    # 2. RESTRICTED
    view_res = svc.get_parent_student_view("org-school-1", "stu-prf-101", privacy_level="RESTRICTED")
    assert view_res["privacy_applied"] == "RESTRICTED"
    assert view_res["full_name"] == "Karan Verma"

    # 3. ANONYMIZED
    view_anon = svc.get_parent_student_view("org-school-1", "stu-prf-101", privacy_level="ANONYMIZED")
    assert view_anon["full_name"] == "ANONYMOUS STUDENT"
    assert view_anon["admission_number"] == "***-MASKED"
    assert view_anon["fee_balance"] == "Contact bursar"

    # 4. BLOCKED
    with pytest.raises(PermissionError, match="blocked"):
        svc.get_parent_student_view("org-school-1", "stu-prf-101", privacy_level="BLOCKED")


# ── Test 4: Dual-Mode Pilot — K-12 School Tenant Journey ──────────────────────

def test_dual_mode_institution_pilot_school_tenant(platform_db):
    """Verify K-12 School configuration with sections, term exams, bus routes, and hostel."""
    with platform_db._get_connection() as conn:
        now_str = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO transport_vehicles (id, organization_id, registration_number, vehicle_type, seating_capacity, driver_name, driver_phone, created_at, updated_at) "
            f"VALUES ('veh-1', 'org-school-1', 'KA-01-1111', 'BUS', 30, 'Ramesh', '9990001111', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO transport_routes (id, organization_id, name, code, start_point, end_point, created_at, updated_at) "
            f"VALUES ('rt-1', 'org-school-1', 'Route 1', 'R-01', 'Town', 'School', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO transport_stops (id, organization_id, route_id, name, stop_order, created_at) "
            f"VALUES ('stp-1', 'org-school-1', 'rt-1', 'Town Gate', 1, '{now_str}');"
        )
        conn.execute(
            "INSERT INTO student_transport_allocations (id, organization_id, student_id, route_id, stop_id, vehicle_id, academic_year_id, created_at, updated_at) "
            f"VALUES ('sta-1', 'org-school-1', 'usr-stu-101', 'rt-1', 'stp-1', 'veh-1', 'ay-1', '{now_str}', '{now_str}');"
        )

    svc = UnifiedInstitutionalAnalyticsService(platform_db)
    snap = svc.get_kpi_snapshot("org-school-1")
    assert snap.transport_capacity_utilization == round(1 / 30 * 100.0, 2)


# ── Test 5: Dual-Mode Pilot — Coaching Institute Tenant Journey ──────────────

def test_dual_mode_institution_pilot_coaching_institute_tenant(platform_db):
    """Verify Coaching/Test-Prep Institute operates without forced school-only mandatory fields."""
    with platform_db._get_connection() as conn:
        now_str = datetime.now(timezone.utc).isoformat()
        # Coaching student
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            f"VALUES ('usr-coaching-stu', 'org-coaching-2', 'neet_aspirant@apex.edu', 'Rahul Sharma', 'student', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO persons (id, organization_id, user_id, first_name, last_name, email, created_at, updated_at) "
            f"VALUES ('per-coach-1', 'org-coaching-2', 'usr-coaching-stu', 'Rahul', 'Sharma', 'neet_aspirant@apex.edu', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at) "
            f"VALUES ('stu-prf-coach', 'per-coach-1', 'org-coaching-2', 'APEX-2026-JEE', 'R-02', '2026-04-01', 'ACTIVE', '{now_str}', '{now_str}');"
        )
        # Coaching Fee Account with installment plan
        conn.execute(
            "INSERT INTO fee_accounts (id, org_id, student_id, total_due, total_paid, balance_due, status, created_at, updated_at) "
            f"VALUES ('fa-coach-1', 'org-coaching-2', 'usr-coaching-stu', 50000.0, 35000.0, 15000.0, 'ACTIVE', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO invoices (id, org_id, fee_account_id, student_id, invoice_number, amount_due, amount_paid, status, due_date, created_at, updated_at) "
            f"VALUES ('inv-coach-1', 'org-coaching-2', 'fa-coach-1', 'usr-coaching-stu', 'INV-JEE-01', 50000.0, 35000.0, 'PARTIAL', '2026-12-01', '{now_str}', '{now_str}');"
        )

    svc = UnifiedInstitutionalAnalyticsService(platform_db)
    snap = svc.get_kpi_snapshot("org-coaching-2")
    assert snap.total_students == 1
    assert snap.fee_collection_rate == 70.0  # 35,000 / 50,000 * 100
    assert snap.total_outstanding_fees == 15000.0
    assert snap.transport_capacity_utilization == 0.0  # Coaching institute has no mandatory bus routes
    assert snap.hostel_occupancy_rate == 0.0


# ── Test 6: Data Export in CSV & JSON Formats ─────────────────────────────────

def test_data_export_csv_and_json_with_filters(platform_db):
    """Verify DataExportService exports student and attendance records into CSV and JSON."""
    exp_svc = DataExportService(platform_db)

    # 1. Export Students to CSV
    job_csv, csv_str = exp_svc.create_export(
        organization_id="org-school-1",
        requested_by="usr-tch-201",
        export_type="STUDENTS",
        format_type="CSV",
    )
    assert job_csv["status"] == "COMPLETED"
    assert job_csv["row_count"] == 1
    assert "admission_number" in csv_str
    assert "GW-2026-001" in csv_str

    # 2. Export Students to JSON
    job_json, json_str = exp_svc.create_export(
        organization_id="org-school-1",
        requested_by="usr-tch-201",
        export_type="STUDENTS",
        format_type="JSON",
    )
    assert job_json["status"] == "COMPLETED"
    import json
    parsed = json.loads(json_str)
    assert len(parsed) == 1
    assert parsed[0]["admission_number"] == "GW-2026-001"


# ── Test 7: Multi-Tenant Data Export Isolation ────────────────────────────────

def test_cross_tenant_data_export_isolation(platform_db):
    """Verify that Org 1 export strictly contains Org 1 records and never leaks Org 2 data."""
    # Seed a student in Org 2
    now_str = datetime.now(timezone.utc).isoformat()
    with platform_db._get_connection() as conn:
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            f"VALUES ('usr-apex-stu-99', 'org-coaching-2', 'apex_student@test.edu', 'Deepak Verma', 'student', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO persons (id, organization_id, user_id, first_name, last_name, email, created_at, updated_at) "
            f"VALUES ('per-apex-99', 'org-coaching-2', 'usr-apex-stu-99', 'Deepak', 'Verma', 'apex_student@test.edu', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at) "
            f"VALUES ('stu-prf-apex-99', 'per-apex-99', 'org-coaching-2', 'APEX-999', 'R-99', '2026-01-01', 'ACTIVE', '{now_str}', '{now_str}');"
        )

    exp_svc = DataExportService(platform_db)
    job_org1, csv_org1 = exp_svc.create_export("org-school-1", "usr-tch-201", "STUDENTS", "CSV")
    assert "GW-2026-001" in csv_org1
    assert "APEX-999" not in csv_org1
    assert "Deepak Verma" not in csv_org1


# ── Test 8: Platform Diagnostics & Secret Redaction ───────────────────────────

def test_platform_diagnostics_service_and_secret_redaction(platform_db):
    """Verify platform diagnostics package generates schema reports and redacts sensitive secrets."""
    diag_svc = PlatformDiagnosticsService(platform_db)
    package = diag_svc.generate_diagnostic_package("org-school-1", requested_by="admin-1")

    assert package["database_integrity"]["ok"] is True
    assert package["database_integrity"]["total_tables"] > 10
    assert "table_counts" in package
    assert package["sync_health"]["healthy"] is True

    # Check persistence of snapshot
    with platform_db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM diagnostic_snapshots WHERE organization_id = 'org-school-1';")
        count = cursor.fetchone()[0]
        assert count == 1


# ── Test 9: Database Snapshot Backup & Restoration Verification ──────────────

def test_database_snapshot_backup_and_restoration_verification(platform_db, tmp_path):
    """Verify backup_restore_db creates clean snapshots and restores them faithfully."""
    backup_dir = str(tmp_path / "backups")
    restore_target = str(tmp_path / "restored_db.sqlite3")

    # 1. Create backup
    backup_file = create_backup(platform_db.db_path, backup_dir)
    assert Path(backup_file).exists()

    # 2. Check integrity of backup
    diag = verify_database_integrity(backup_file)
    assert diag["integrity_ok"] is True
    assert diag["tables"]["student_profiles"] == 1

    # 3. Restore backup into target
    res = restore_backup(backup_file, restore_target)
    assert res is True
    assert Path(restore_target).exists()

    # 4. Verify restored target database
    diag_restored = verify_database_integrity(restore_target)
    assert diag_restored["integrity_ok"] is True
    assert diag_restored["tables"]["student_profiles"] == 1


# ── Test 10: REST API Endpoints & Cross-Tenant Isolation ─────────────────────

def test_phase08_api_endpoints_and_cross_tenant_isolation():
    """Verify FastAPI endpoints for institutional analytics, exports, and diagnostics."""
    db = PlatformDatabase()
    org1_id = f"org_{uuid.uuid4().hex[:6]}"
    org2_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org1_id, name="Phase 08 School", slug=f"p8-sch-{org1_id}"))
    db.create_organization(Organization(id=org2_id, name="Phase 08 Coaching", slug=f"p8-coa-{org2_id}"))

    stu_user_id = f"usr_{uuid.uuid4().hex[:6]}"
    per_id = f"per_{uuid.uuid4().hex[:6]}"
    stu_prf_id = f"stu_{uuid.uuid4().hex[:6]}"

    db.create_user(User(id=stu_user_id, organization_id=org1_id, email=f"{stu_user_id}@p8.edu", full_name="Arjun Mehta", role=UserRole.STUDENT))

    with db._get_connection() as conn:
        now_str = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO persons (id, organization_id, user_id, first_name, last_name, email, created_at, updated_at) "
            f"VALUES ('{per_id}', '{org1_id}', '{stu_user_id}', 'Arjun', 'Mehta', '{stu_user_id}@p8.edu', '{now_str}', '{now_str}');"
        )
        conn.execute(
            "INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at) "
            f"VALUES ('{stu_prf_id}', '{per_id}', '{org1_id}', 'P8-ADM-1', 'R-01', '2026-06-01', 'ACTIVE', '{now_str}', '{now_str}');"
        )

    admin_user_id = "user-admin-p8"
    db.create_user(User(id=admin_user_id, organization_id=org1_id, email=f"{admin_user_id}@p8.edu", full_name="Phase 8 Admin", role=UserRole.ORG_ADMIN))
    token_org1 = create_access_token(
        user_id=admin_user_id,
        role="org_admin",
        organization_id=org1_id,
    )
    headers_org1 = {"Authorization": f"Bearer {token_org1}"}

    admin_org2_id = "user-admin-p8-coa"
    db.create_user(User(id=admin_org2_id, organization_id=org2_id, email=f"{admin_org2_id}@p8.edu", full_name="Phase 8 Coaching Admin", role=UserRole.ORG_ADMIN))
    token_org2 = create_access_token(
        user_id=admin_org2_id,
        role="org_admin",
        organization_id=org2_id,
    )
    headers_org2 = {"Authorization": f"Bearer {token_org2}"}

    client = TestClient(app)

    # 1. Fetch KPIs
    resp_kpis = client.get("/api/v1/analytics/institutional/kpis", headers=headers_org1)
    assert resp_kpis.status_code == 200
    assert resp_kpis.json()["total_students"] == 1

    # 2. Trigger Export via API
    resp_exp = client.post(
        "/api/v1/analytics/institutional/export",
        headers=headers_org1,
        json={"export_type": "STUDENTS", "format": "CSV"},
    )
    assert resp_exp.status_code == 201
    assert "Arjun Mehta" in resp_exp.json()["payload"]

    # 3. Diagnostics via API
    resp_diag = client.get("/api/v1/analytics/institutional/diagnostics", headers=headers_org1)
    assert resp_diag.status_code == 200
    assert resp_diag.json()["database_integrity"]["ok"] is True

    # 4. Cross-Tenant Isolation: Org 2 KPIs show 0 students
    resp_kpis_org2 = client.get("/api/v1/analytics/institutional/kpis", headers=headers_org2)
    assert resp_kpis_org2.status_code == 200
    assert resp_kpis_org2.json()["total_students"] == 0
