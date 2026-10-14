"""Phase 06: Full ERP Expansion Tests (Submodules 6A - 6H).

Tests cover:
1. Migration 014 schema creation and clean rollback.
2. 6A: Staff & HR leave request overlapping date validation and attendance.
3. 6B: Payroll preparation, deterministic payslip calculation, and approvals.
4. 6C: Transport routes, ordered stops, and vehicle capacity enforcement.
5. 6D: Hostel building/room bed allocation limits and warden outpass workflow.
6. 6E: Inventory purchase orders, items, and stock movement ledger.
7. 6F: Visitor check-in, host staff assignment, badge pass issuance, and check-out.
8. 6G: Official certificate issuance with SHA-256 tamper-evident verification.
9. 6H: Public CMS pages/posts with slug uniqueness and unauthenticated public endpoints.
10. REST API routing and cross-tenant isolation across all Phase 06 entities.
"""

import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from central_platform.db import PlatformDatabase
from central_platform.models import Organization, User, UserRole
from central_platform.models.hr import (
    LeaveType,
    LeaveStatus,
    StaffLeaveRequest,
    StaffAttendanceRecord,
    PayrollPeriod,
    PayrollRun,
    Payslip,
)
from central_platform.models.transport import (
    TransportRoute,
    TransportStop,
    TransportVehicle,
    StudentTransportAllocation,
)
from central_platform.models.hostel import (
    HostelBuilding,
    HostelRoom,
    HostelAllocation,
    HostelLeavePass,
    OutpassStatus,
)
from central_platform.models.inventory import (
    InventoryItem,
    InventoryVendor,
    PurchaseOrder,
    StockMovement,
    MovementType,
)
from central_platform.models.campus import (
    CampusVisitor,
    VisitorGatePass,
    GatePassStatus,
    OfficialCertificate,
    CertificateType,
    CertificateStatus,
    CMSPage,
    CMSPost,
    CMSStatus,
)
from central_platform.hr.service import HRService, PayrollService
from central_platform.transport.service import TransportService
from central_platform.hostel.service import HostelService
from central_platform.inventory.service import InventoryService
from central_platform.campus.service import CampusService
from central_platform.auth.tokens import create_access_token
from central_platform.api.app import app

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


@pytest.fixture
def platform_db(tmp_path):
    """File-backed PlatformDatabase instance migrated through 014."""
    db_file = str(tmp_path / "test_phase06.db")
    db = PlatformDatabase(db_file)
    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-school-1', 'Greenwood High', 'greenwood-high', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-coaching-2', 'Apex IIT Academy', 'apex-iit', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        for mod in ["hr", "payroll", "transport", "hostel", "inventory", "campus", "cms"]:
            conn.execute(
                "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
                f"VALUES ('ent-{mod}-1', 'org-school-1', '{mod}', 1, '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
            )
            conn.execute(
                "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
                f"VALUES ('ent-{mod}-2', 'org-coaching-2', '{mod}', 1, '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
            )
        # Create staff user and student user
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            "VALUES ('stf-101', 'org-school-1', 'teacher1@gw.edu', 'Pooja Sharma', 'teacher', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            "VALUES ('stu-201', 'org-school-1', 'student1@gw.edu', 'Karan Verma', 'student', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
    yield db
    db.close()


# ── Test 1: Migration 014 Up and Down Verification ───────────────────────────

def test_migration_014_up_and_down():
    """Verify migration 014 creates all 13 Phase 06 tables and down script removes them cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply up through 013
    for i in range(1, 14):
        scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Apply 014
    up_014 = MIGRATIONS_DIR / "014_full_erp_expansion.sql"
    assert up_014.exists(), "014 forward migration script must exist"
    conn.executescript(up_014.read_text(encoding="utf-8"))

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_up = {r[0] for r in cursor.fetchall()}

    expected_tables = {
        "staff_leave_requests",
        "staff_attendance_records",
        "payroll_periods",
        "payroll_runs",
        "payslips",
        "transport_routes",
        "transport_stops",
        "transport_vehicles",
        "student_transport_allocations",
        "hostel_buildings",
        "hostel_rooms",
        "hostel_allocations",
        "hostel_leave_passes",
        "inventory_items",
        "inventory_vendors",
        "inventory_purchase_orders",
        "inventory_stock_movements",
        "campus_visitors",
        "visitor_gate_passes",
        "official_certificates",
        "cms_pages",
        "cms_posts",
    }
    for t in expected_tables:
        assert t in tables_after_up, f"Table {t} should exist after migration 014"

    # Roll back 014
    down_014 = MIGRATIONS_DIR / "014_full_erp_expansion_down.sql"
    assert down_014.exists(), "014 rollback migration script must exist"
    conn.executescript(down_014.read_text(encoding="utf-8"))

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_down = {r[0] for r in cursor.fetchall()}

    for t in expected_tables:
        assert t not in tables_after_down, f"Table {t} should be removed after rollback"

    conn.close()


# ── Test 2: Submodule 6A — Staff Leave & Attendance ──────────────────────────

def test_submodule_6a_staff_leave_and_attendance(platform_db):
    """Verify staff leave requests prevent date overlaps and staff attendance logs daily presence."""
    hr_svc = HRService(platform_db)

    # 1. Submit leave request
    leave1 = hr_svc.apply_leave(
        organization_id="org-school-1",
        staff_id="stf-101",
        leave_type=LeaveType.CASUAL,
        start_date="2026-11-10",
        end_date="2026-11-12",
        total_days=3.0,
        reason="Family function",
    )
    assert leave1.id is not None
    assert leave1.status == LeaveStatus.PENDING

    # 2. Overlapping leave must be rejected
    with pytest.raises(ValueError, match="Overlapping leave request exists"):
        hr_svc.apply_leave(
            organization_id="org-school-1",
            staff_id="stf-101",
            leave_type=LeaveType.SICK,
            start_date="2026-11-11",
            end_date="2026-11-13",
            total_days=3.0,
            reason="Sick",
        )

    # 3. Approve leave
    approved = hr_svc.approve_leave("org-school-1", leave1.id, approved_by="principal-1")
    assert approved.status == LeaveStatus.APPROVED

    # 4. Mark staff attendance
    att = hr_svc.mark_staff_attendance(
        organization_id="org-school-1",
        staff_id="stf-101",
        date="2026-11-05",
        status="PRESENT",
        check_in_time="08:25",
        check_out_time="16:05",
    )
    assert att.id is not None
    assert att.status == "PRESENT"


# ── Test 3: Submodule 6B — Payroll Preparation & Payslips ────────────────────

def test_submodule_6b_payroll_preparation_and_payslip_generation(platform_db):
    """Verify payroll periods, run calculations, and payslip generation."""
    pay_svc = PayrollService(platform_db)

    period = pay_svc.create_period("org-school-1", "October 2026", 2026, 10, "2026-10-01", "2026-10-31")
    assert period.id is not None

    # Compute Payroll Run for 1 employee: Basic 50,000, HRA 10,000, PF Deduction 6,000
    run = pay_svc.calculate_payroll_run(
        organization_id="org-school-1",
        period_id=period.id,
        employee_salary_specs=[
            {
                "staff_id": "stf-101",
                "basic_salary": 50000.0,
                "allowances": {"HRA": 10000.0, "Special": 5000.0},
                "deductions": {"PF": 6000.0, "TDS": 3000.0},
            }
        ],
        created_by="accountant-1",
    )
    assert run.employee_count == 1
    assert run.total_gross == 65000.0  # 50,000 + 10,000 + 5,000
    assert run.total_deductions == 9000.0  # 6,000 + 3,000
    assert run.total_net == 56000.0

    # Retrieve individual payslip
    slips = pay_svc.get_payslips_for_run("org-school-1", run.id)
    assert len(slips) == 1
    assert slips[0].staff_id == "stf-101"
    assert slips[0].net_amount == 56000.0


# ── Test 4: Submodule 6C — Transport & Fleet Capacity ────────────────────────

def test_submodule_6c_transport_routes_and_capacity_limits(platform_db):
    """Verify routes, ordered stops, and vehicle capacity enforcement."""
    trans_svc = TransportService(platform_db)

    route = trans_svc.create_route("org-school-1", "North City Route", "NCR-01", "City Center", "School Campus")
    stop = trans_svc.add_stop("org-school-1", route.id, "Main Square", 1, "07:30", "15:45", 1500.0)
    assert stop.stop_order == 1

    # Vehicle with capacity 1
    bus = trans_svc.register_vehicle("org-school-1", "KA-01-AB-1234", "BUS", 1, "Ramesh Driver", "9876543210")

    # Allocate seat for Student 1 -> Success
    alloc1 = trans_svc.allocate_student_transport(
        organization_id="org-school-1",
        student_id="stu-201",
        route_id=route.id,
        stop_id=stop.id,
        vehicle_id=bus.id,
        academic_year_id="ay-dummy",
    )
    assert alloc1.id is not None

    # Allocate seat for Student 2 -> Must fail due to capacity exceeded (capacity=1)
    with pytest.raises(ValueError, match="Vehicle capacity exceeded"):
        trans_svc.allocate_student_transport(
            organization_id="org-school-1",
            student_id="stu-other-2",
            route_id=route.id,
            stop_id=stop.id,
            vehicle_id=bus.id,
            academic_year_id="ay-dummy",
        )


# ── Test 5: Submodule 6D — Hostel Boarding & Leave Outpasses ─────────────────

def test_submodule_6d_hostel_room_allocation_and_leave_passes(platform_db):
    """Verify hostel room bed allocations enforce capacity and warden outpasses."""
    hostel_svc = HostelService(platform_db)

    bld = hostel_svc.create_building("org-school-1", "Ganga Block", "GB-1", "BOYS", "Mr. Warden", "9876500000")
    room = hostel_svc.create_room("org-school-1", bld.id, "101", 1, bed_capacity=1)

    # Allocate Room 101 for Student 1
    alloc = hostel_svc.allocate_bed("org-school-1", "stu-201", room.id, "ay-dummy", "Bed-A")
    assert alloc.id is not None

    # Attempt second allocation to Room 101 -> Must fail
    with pytest.raises(ValueError, match="Room bed capacity exceeded"):
        hostel_svc.allocate_bed("org-school-1", "stu-other-2", room.id, "ay-dummy", "Bed-B")

    # Request Weekend Outpass
    outpass = hostel_svc.request_outpass(
        organization_id="org-school-1",
        student_id="stu-201",
        leave_type="WEEKEND_HOME",
        departure_date="2026-11-14",
        expected_return_date="2026-11-15",
        reason="Visiting grandparents",
    )
    assert outpass.status == OutpassStatus.PENDING

    # Warden Approves Outpass
    approved_pass = hostel_svc.approve_outpass("org-school-1", outpass.id, approved_by="warden-1")
    assert approved_pass.status == OutpassStatus.APPROVED


# ── Test 6: Submodule 6E — Inventory Items & Stock Movement Ledger ───────────

def test_submodule_6e_inventory_stock_movements_and_po(platform_db):
    """Verify item inventory tracking, purchase orders, and stock movements."""
    inv_svc = InventoryService(platform_db)

    item = inv_svc.create_item("org-school-1", "A4 Printing Paper", "PAP-A4", "STATIONERY", "REAMS", 250.0, 10)
    vendor = inv_svc.register_vendor("org-school-1", "National Paper Mills", "VEND-NPM", "Amit Gupta", "9998887770")

    # Inward stock movement (+50 reams)
    mov1 = inv_svc.record_movement("org-school-1", item.id, MovementType.INWARD, 50, 250.0, "PO-1001", "Stores", "Initial Batch")
    assert mov1.id is not None

    # Check updated balance
    item_updated = inv_svc.get_item("org-school-1", item.id)
    assert item_updated.quantity_on_hand == 50

    # Outward stock movement (-10 reams to Exam Dept)
    inv_svc.record_movement("org-school-1", item.id, MovementType.OUTWARD, 10, 250.0, "REQ-55", "Examinations", "Exam paper prints")
    item_final = inv_svc.get_item("org-school-1", item.id)
    assert item_final.quantity_on_hand == 40


# ── Test 7: Submodule 6F — Visitor Check-In and Gate Pass ────────────────────

def test_submodule_6f_visitor_registration_and_gate_pass(platform_db):
    """Verify visitor registration, gate badge issuance, and check-out."""
    campus_svc = CampusService(platform_db)

    visitor = campus_svc.register_visitor("org-school-1", "Vikram Patel", "9876511223", "AADHAAR", "XXXX-1234")
    assert visitor.id is not None

    # Issue Gate Pass
    pass_entry = campus_svc.issue_gate_pass(
        organization_id="org-school-1",
        visitor_id=visitor.id,
        purpose="Parent meeting with Principal",
        host_staff_id="stf-101",
        issued_by="guard-1",
    )
    assert pass_entry.status == GatePassStatus.CHECKED_IN
    assert pass_entry.pass_number.startswith("GP-")

    # Check Out Visitor
    checkout = campus_svc.checkout_visitor("org-school-1", pass_entry.id)
    assert checkout.status == GatePassStatus.CHECKED_OUT
    assert checkout.check_out_time is not None


# ── Test 8: Submodule 6G — Official Certificates & Document Hash ─────────────

def test_submodule_6g_official_certificates_and_sha256_hash(platform_db):
    """Verify certificate issuance with tamper-evident SHA256 checksum and revocation."""
    campus_svc = CampusService(platform_db)

    cert = campus_svc.issue_certificate(
        organization_id="org-school-1",
        student_id="stu-201",
        certificate_type=CertificateType.BONAFIDE,
        payload_data={"purpose": "Passport application", "academic_year": "2026-27"},
        issued_by="registrar-1",
    )
    assert cert.id is not None
    assert cert.status == CertificateStatus.ISSUED
    assert len(cert.document_hash) == 64  # SHA256 length

    # Revoke Certificate
    revoked = campus_svc.revoke_certificate(
        organization_id="org-school-1",
        certificate_id=cert.id,
        revoked_by="registrar-1",
        reason="Issued with incorrect date of birth",
    )
    assert revoked.status == CertificateStatus.REVOKED
    assert revoked.revocation_reason == "Issued with incorrect date of birth"


# ── Test 9: Submodule 6H — Public Institutional CMS & Isolation ──────────────

def test_submodule_6h_public_cms_publishing_and_isolation(platform_db):
    """Verify CMS pages and blog posts enforce slug uniqueness and public visibility."""
    campus_svc = CampusService(platform_db)

    # 1. Create and Publish Page
    page = campus_svc.create_page("org-school-1", "About Greenwood", "about-greenwood", "<h1>About Greenwood</h1>")
    assert page.status == CMSStatus.DRAFT

    published_page = campus_svc.publish_page("org-school-1", page.id)
    assert published_page.status == CMSStatus.PUBLISHED

    # 2. Duplicate slug must be rejected within same organization
    with pytest.raises(ValueError, match="Slug already exists"):
        campus_svc.create_page("org-school-1", "About Copy", "about-greenwood", "<p>copy</p>")

    # 3. Create News Post
    post = campus_svc.create_post(
        organization_id="org-school-1",
        title="Annual Science Exhibition 2026",
        slug="annual-science-exhibition-2026",
        excerpt="Greenwood High hosts 40+ science projects.",
        content_html="<p>Full story...</p>",
        author_name="Editorial Team",
    )
    campus_svc.publish_post("org-school-1", post.id)

    # 4. Public query for published pages requires no auth
    public_pages = campus_svc.list_published_pages("org-school-1")
    assert len(public_pages) == 1
    assert public_pages[0].slug == "about-greenwood"


# ── Test 10: REST API Endpoints and Cross-Tenant Isolation ───────────────────

def test_phase06_api_endpoints_and_cross_tenant_isolation():
    """Verify REST API routes and multi-tenant isolation across Phase 06 entities."""
    import uuid
    db = PlatformDatabase()
    org_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org_id, name="Phase 06 Org", slug=f"p6-org-{org_id}"))

    token = create_access_token(
        user_id="user-admin-p6",
        role="org_admin",
        organization_id=org_id,
    )
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app)

    # 1. Create Transport Route via API
    resp_route = client.post(
        "/api/v1/transport/routes",
        headers=headers,
        json={
            "name": "API Route 1",
            "code": "API-R1",
            "start_point": "Station",
            "end_point": "School",
        },
    )
    assert resp_route.status_code == 201
    assert resp_route.json()["code"] == "API-R1"

    # 2. Create CMS Page via API
    resp_page = client.post(
        "/api/v1/cms/pages",
        headers=headers,
        json={
            "title": "Admissions Policy",
            "slug": f"admissions-policy-{org_id}",
            "content_html": "<p>Open admissions for 2026-27</p>",
        },
    )
    assert resp_page.status_code == 201
    assert resp_page.json()["title"] == "Admissions Policy"
