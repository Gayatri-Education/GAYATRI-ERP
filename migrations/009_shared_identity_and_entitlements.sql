-- Migration 009: Shared Identity, Module Entitlements, and Transactional Outbox (Phase 01)
-- Provides authoritative shared Person/Student/Guardian/Staff contracts and fail-closed ERP module gating.

CREATE TABLE IF NOT EXISTS persons (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    date_of_birth VARCHAR(20),
    gender VARCHAR(20),
    national_id_hash VARCHAR(128),
    address_line1 TEXT,
    address_line2 TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(50) DEFAULT 'India',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_persons_org ON persons(organization_id);
CREATE INDEX IF NOT EXISTS idx_persons_user ON persons(user_id);
CREATE INDEX IF NOT EXISTS idx_persons_email ON persons(email);

CREATE TABLE IF NOT EXISTS student_profiles (
    id VARCHAR(64) PRIMARY KEY,
    person_id VARCHAR(64) NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    admission_number VARCHAR(100),
    roll_number VARCHAR(50),
    admission_date VARCHAR(20),
    academic_status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, admission_number)
);

CREATE INDEX IF NOT EXISTS idx_student_profiles_org ON student_profiles(organization_id);
CREATE INDEX IF NOT EXISTS idx_student_profiles_person ON student_profiles(person_id);

CREATE TABLE IF NOT EXISTS guardian_profiles (
    id VARCHAR(64) PRIMARY KEY,
    person_id VARCHAR(64) NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    occupation VARCHAR(100),
    annual_income VARCHAR(50),
    is_legal_guardian BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_guardian_profiles_org ON guardian_profiles(organization_id);
CREATE INDEX IF NOT EXISTS idx_guardian_profiles_person ON guardian_profiles(person_id);

CREATE TABLE IF NOT EXISTS student_guardian_links (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id VARCHAR(64) NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    guardian_id VARCHAR(64) NOT NULL REFERENCES guardian_profiles(id) ON DELETE CASCADE,
    relationship VARCHAR(50) NOT NULL,
    is_primary_contact BOOLEAN DEFAULT 0,
    is_emergency_contact BOOLEAN DEFAULT 0,
    is_pickup_authorized BOOLEAN DEFAULT 0,
    can_access_portal BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, guardian_id)
);

CREATE INDEX IF NOT EXISTS idx_student_guardian_org ON student_guardian_links(organization_id);
CREATE INDEX IF NOT EXISTS idx_student_guardian_stu ON student_guardian_links(student_id);
CREATE INDEX IF NOT EXISTS idx_student_guardian_grd ON student_guardian_links(guardian_id);

CREATE TABLE IF NOT EXISTS staff_profiles (
    id VARCHAR(64) PRIMARY KEY,
    person_id VARCHAR(64) NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    employee_id VARCHAR(100),
    department VARCHAR(100),
    designation VARCHAR(100),
    employment_type VARCHAR(50) DEFAULT 'full_time',
    employment_status VARCHAR(50) DEFAULT 'active',
    joining_date VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_staff_profiles_org ON staff_profiles(organization_id);
CREATE INDEX IF NOT EXISTS idx_staff_profiles_person ON staff_profiles(person_id);

CREATE TABLE IF NOT EXISTS module_entitlements (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    module_key VARCHAR(100) NOT NULL,
    is_enabled BOOLEAN DEFAULT 0,
    tier VARCHAR(50) DEFAULT 'standard',
    valid_until TIMESTAMP,
    config_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, module_key)
);

CREATE INDEX IF NOT EXISTS idx_module_entitlements_org ON module_entitlements(organization_id);

CREATE TABLE IF NOT EXISTS domain_events_outbox (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    payload_json TEXT NOT NULL,
    idempotency_key VARCHAR(128) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_domain_events_outbox_status ON domain_events_outbox(status);
CREATE INDEX IF NOT EXISTS idx_domain_events_outbox_org ON domain_events_outbox(organization_id);
