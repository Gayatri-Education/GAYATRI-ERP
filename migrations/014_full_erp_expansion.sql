-- ============================================================================
-- Migration 014: Full ERP Expansion (Submodules 6A through 6H)
-- ============================================================================

-- 1. Staff Leave Requests (6A)
CREATE TABLE IF NOT EXISTS staff_leave_requests (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    staff_id TEXT NOT NULL,
    leave_type TEXT NOT NULL DEFAULT 'CASUAL',
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    total_days REAL NOT NULL DEFAULT 1.0,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    approved_by TEXT,
    approved_at TEXT,
    rejection_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_staff_leave_org ON staff_leave_requests(organization_id);
CREATE INDEX IF NOT EXISTS idx_staff_leave_staff ON staff_leave_requests(staff_id);

-- 2. Staff Attendance Records (6A)
CREATE TABLE IF NOT EXISTS staff_attendance_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    staff_id TEXT NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PRESENT',
    check_in_time TEXT,
    check_out_time TEXT,
    remarks TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, staff_id, date)
);

CREATE INDEX IF NOT EXISTS idx_staff_att_org ON staff_attendance_records(organization_id);
CREATE INDEX IF NOT EXISTS idx_staff_att_staff ON staff_attendance_records(staff_id);

-- 3. Payroll Periods (6B)
CREATE TABLE IF NOT EXISTS payroll_periods (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_payroll_periods_org ON payroll_periods(organization_id);

-- 4. Payroll Runs (6B)
CREATE TABLE IF NOT EXISTS payroll_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    payroll_period_id TEXT NOT NULL REFERENCES payroll_periods(id) ON DELETE CASCADE,
    total_gross REAL NOT NULL DEFAULT 0.0,
    total_deductions REAL NOT NULL DEFAULT 0.0,
    total_net REAL NOT NULL DEFAULT 0.0,
    employee_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    created_by TEXT,
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payroll_runs_org ON payroll_runs(organization_id);

-- 5. Payslips (6B)
CREATE TABLE IF NOT EXISTS payslips (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    payroll_run_id TEXT NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    staff_id TEXT NOT NULL,
    basic_salary REAL NOT NULL DEFAULT 0.0,
    allowances_json TEXT NOT NULL DEFAULT '{}',
    deductions_json TEXT NOT NULL DEFAULT '{}',
    gross_amount REAL NOT NULL DEFAULT 0.0,
    net_amount REAL NOT NULL DEFAULT 0.0,
    payment_status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payslips_run ON payslips(payroll_run_id);
CREATE INDEX IF NOT EXISTS idx_payslips_staff ON payslips(staff_id);

-- 6. Transport Routes (6C)
CREATE TABLE IF NOT EXISTS transport_routes (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    start_point TEXT NOT NULL,
    end_point TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS idx_routes_org ON transport_routes(organization_id);

-- 7. Transport Stops (6C)
CREATE TABLE IF NOT EXISTS transport_stops (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    route_id TEXT NOT NULL REFERENCES transport_routes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    stop_order INTEGER NOT NULL DEFAULT 1,
    morning_pickup_time TEXT,
    evening_drop_time TEXT,
    fare_amount REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stops_route ON transport_stops(route_id);

-- 8. Transport Vehicles (6C)
CREATE TABLE IF NOT EXISTS transport_vehicles (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    registration_number TEXT NOT NULL,
    vehicle_type TEXT NOT NULL DEFAULT 'BUS',
    seating_capacity INTEGER NOT NULL DEFAULT 40,
    driver_name TEXT,
    driver_phone TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, registration_number)
);

CREATE INDEX IF NOT EXISTS idx_vehicles_org ON transport_vehicles(organization_id);

-- 9. Student Transport Allocations (6C)
CREATE TABLE IF NOT EXISTS student_transport_allocations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL,
    route_id TEXT NOT NULL REFERENCES transport_routes(id) ON DELETE CASCADE,
    stop_id TEXT NOT NULL REFERENCES transport_stops(id) ON DELETE CASCADE,
    vehicle_id TEXT NOT NULL REFERENCES transport_vehicles(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(student_id, academic_year_id)
);

CREATE INDEX IF NOT EXISTS idx_trans_alloc_vehicle ON student_transport_allocations(vehicle_id);

-- 10. Hostel Buildings (6D)
CREATE TABLE IF NOT EXISTS hostel_buildings (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    gender_type TEXT NOT NULL DEFAULT 'COED',
    warden_name TEXT,
    warden_phone TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS idx_hostel_bld_org ON hostel_buildings(organization_id);

-- 11. Hostel Rooms (6D)
CREATE TABLE IF NOT EXISTS hostel_rooms (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    building_id TEXT NOT NULL REFERENCES hostel_buildings(id) ON DELETE CASCADE,
    room_number TEXT NOT NULL,
    floor_number INTEGER NOT NULL DEFAULT 1,
    bed_capacity INTEGER NOT NULL DEFAULT 2,
    current_occupancy INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(building_id, room_number)
);

CREATE INDEX IF NOT EXISTS idx_hostel_rooms_bld ON hostel_rooms(building_id);

-- 12. Hostel Allocations (6D)
CREATE TABLE IF NOT EXISTS hostel_allocations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL,
    room_id TEXT NOT NULL REFERENCES hostel_rooms(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL,
    bed_identifier TEXT,
    allocation_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(student_id, academic_year_id)
);

CREATE INDEX IF NOT EXISTS idx_hostel_alloc_room ON hostel_allocations(room_id);

-- 13. Hostel Leave Passes (6D)
CREATE TABLE IF NOT EXISTS hostel_leave_passes (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL,
    leave_type TEXT NOT NULL DEFAULT 'WEEKEND_HOME',
    departure_date TEXT NOT NULL,
    expected_return_date TEXT NOT NULL,
    actual_return_date TEXT,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    approved_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hostel_passes_student ON hostel_leave_passes(student_id);

-- 14. Inventory Items (6E)
CREATE TABLE IF NOT EXISTS inventory_items (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sku TEXT NOT NULL,
    category TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT 'PCS',
    quantity_on_hand INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 10,
    unit_price REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, sku)
);

CREATE INDEX IF NOT EXISTS idx_inv_items_org ON inventory_items(organization_id);

-- 15. Inventory Vendors (6E)
CREATE TABLE IF NOT EXISTS inventory_vendors (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS idx_inv_vendors_org ON inventory_vendors(organization_id);

-- 16. Inventory Purchase Orders (6E)
CREATE TABLE IF NOT EXISTS inventory_purchase_orders (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    po_number TEXT NOT NULL,
    vendor_id TEXT NOT NULL REFERENCES inventory_vendors(id) ON DELETE CASCADE,
    total_amount REAL NOT NULL DEFAULT 0.0,
    order_date TEXT NOT NULL,
    expected_date TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    created_by TEXT,
    approved_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, po_number)
);

CREATE INDEX IF NOT EXISTS idx_inv_po_org ON inventory_purchase_orders(organization_id);

-- 17. Inventory Stock Movements (6E)
CREATE TABLE IF NOT EXISTS inventory_stock_movements (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
    movement_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_cost REAL NOT NULL DEFAULT 0.0,
    reference_id TEXT,
    department_name TEXT,
    remarks TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inv_mov_item ON inventory_stock_movements(item_id);

-- 18. Campus Visitors (6F)
CREATE TABLE IF NOT EXISTS campus_visitors (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    id_proof_type TEXT,
    id_proof_number TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_visitors_org ON campus_visitors(organization_id);

-- 19. Visitor Gate Passes (6F)
CREATE TABLE IF NOT EXISTS visitor_gate_passes (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    visitor_id TEXT NOT NULL REFERENCES campus_visitors(id) ON DELETE CASCADE,
    pass_number TEXT NOT NULL,
    purpose TEXT NOT NULL,
    host_staff_id TEXT,
    check_in_time TEXT NOT NULL,
    check_out_time TEXT,
    status TEXT NOT NULL DEFAULT 'CHECKED_IN',
    issued_by TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(organization_id, pass_number)
);

CREATE INDEX IF NOT EXISTS idx_gate_passes_visitor ON visitor_gate_passes(visitor_id);

-- 20. Official Certificates (6G)
CREATE TABLE IF NOT EXISTS official_certificates (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL,
    certificate_type TEXT NOT NULL,
    certificate_number TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    valid_until TEXT,
    status TEXT NOT NULL DEFAULT 'ISSUED',
    document_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    issued_by TEXT,
    revoked_by TEXT,
    revocation_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, certificate_number)
);

CREATE INDEX IF NOT EXISTS idx_certificates_student ON official_certificates(student_id);

-- 21. CMS Pages (6H)
CREATE TABLE IF NOT EXISTS cms_pages (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    content_html TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_cms_pages_slug ON cms_pages(organization_id, slug);

-- 22. CMS Posts (6H)
CREATE TABLE IF NOT EXISTS cms_posts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    excerpt TEXT,
    content_html TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    published_at TEXT,
    author_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_cms_posts_slug ON cms_posts(organization_id, slug);
