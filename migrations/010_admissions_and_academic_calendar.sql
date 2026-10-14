-- ============================================================================
-- Migration 010: Core ERP Foundation (Admissions CRM, Academic Calendar & SIS)
-- ============================================================================

-- 1. Academic Years
CREATE TABLE IF NOT EXISTS academic_years (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS idx_academic_years_org ON academic_years(organization_id);
CREATE INDEX IF NOT EXISTS idx_academic_years_current ON academic_years(organization_id, is_current);

-- 2. Academic Terms
CREATE TABLE IF NOT EXISTS academic_terms (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(academic_year_id, code)
);

CREATE INDEX IF NOT EXISTS idx_academic_terms_year ON academic_terms(academic_year_id);

-- 3. School Calendar Events
CREATE TABLE IF NOT EXISTS school_calendar_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'EVENT',
    description TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    is_holiday INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_org ON school_calendar_events(organization_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_year ON school_calendar_events(academic_year_id);

-- 4. Admissions Inquiries
CREATE TABLE IF NOT EXISTS admission_inquiries (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    inquiry_number TEXT NOT NULL,
    applicant_name TEXT NOT NULL,
    guardian_name TEXT,
    email TEXT,
    phone TEXT,
    target_grade TEXT,
    status TEXT NOT NULL DEFAULT 'NEW',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, inquiry_number)
);

CREATE INDEX IF NOT EXISTS idx_admission_inquiries_org ON admission_inquiries(organization_id);
CREATE INDEX IF NOT EXISTS idx_admission_inquiries_contact ON admission_inquiries(organization_id, email, phone);

-- 5. Admission Applications
CREATE TABLE IF NOT EXISTS admission_applications (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    application_number TEXT NOT NULL,
    inquiry_id TEXT REFERENCES admission_inquiries(id) ON DELETE SET NULL,
    academic_year_id TEXT REFERENCES academic_years(id) ON DELETE SET NULL,
    applicant_name TEXT NOT NULL,
    date_of_birth TEXT,
    gender TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    previous_school TEXT,
    target_grade TEXT,
    status TEXT NOT NULL DEFAULT 'SUBMITTED',
    review_notes TEXT,
    decision_date TEXT,
    decision_by TEXT,
    converted_student_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, application_number)
);

CREATE INDEX IF NOT EXISTS idx_admission_applications_org ON admission_applications(organization_id);
CREATE INDEX IF NOT EXISTS idx_admission_applications_status ON admission_applications(organization_id, status);

-- 6. Admission Documents
CREATE TABLE IF NOT EXISTS admission_documents (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    application_id TEXT NOT NULL REFERENCES admission_applications(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT,
    verification_status TEXT NOT NULL DEFAULT 'PENDING',
    verified_by TEXT,
    verified_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_admission_docs_app ON admission_documents(application_id);

-- 7. Admission Offers
CREATE TABLE IF NOT EXISTS admission_offers (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    application_id TEXT NOT NULL REFERENCES admission_applications(id) ON DELETE CASCADE,
    offer_date TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    grade TEXT NOT NULL,
    fee_amount REAL NOT NULL DEFAULT 0.0,
    conditions TEXT,
    status TEXT NOT NULL DEFAULT 'ISSUED',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_admission_offers_app ON admission_offers(application_id);

-- 8. Student Classes / Sections / Batches
CREATE TABLE IF NOT EXISTS student_classes (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    grade_level TEXT NOT NULL,
    section TEXT,
    capacity INTEGER NOT NULL DEFAULT 40,
    class_teacher_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, academic_year_id, name)
);

CREATE INDEX IF NOT EXISTS idx_student_classes_org ON student_classes(organization_id);
CREATE INDEX IF NOT EXISTS idx_student_classes_year ON student_classes(academic_year_id);

-- 9. Student Class Enrollments
CREATE TABLE IF NOT EXISTS student_class_enrollments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES student_classes(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    roll_number TEXT,
    enrollment_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, academic_year_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_student_enrollments_class ON student_class_enrollments(class_id);
CREATE INDEX IF NOT EXISTS idx_student_enrollments_student ON student_class_enrollments(student_id);
