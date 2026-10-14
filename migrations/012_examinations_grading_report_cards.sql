-- ============================================================================
-- Migration 012: Examinations, Official Grading and Report Cards
-- ============================================================================

-- 1. Exam Series
CREATE TABLE IF NOT EXISTS exam_series (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    academic_term_id TEXT REFERENCES academic_terms(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    series_type TEXT NOT NULL DEFAULT 'MID_TERM',
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'SCHEDULED',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS idx_exam_series_org ON exam_series(organization_id);
CREATE INDEX IF NOT EXISTS idx_exam_series_year ON exam_series(academic_year_id);

-- 2. Exam Schedules
CREATE TABLE IF NOT EXISTS exam_schedules (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    exam_series_id TEXT NOT NULL REFERENCES exam_series(id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES student_classes(id) ON DELETE CASCADE,
    subject_id TEXT NOT NULL,
    exam_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    max_marks REAL NOT NULL DEFAULT 100.0,
    pass_marks REAL NOT NULL DEFAULT 35.0,
    room_name TEXT,
    is_locked INTEGER NOT NULL DEFAULT 0,
    locked_at TEXT,
    locked_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exam_schedules_series ON exam_schedules(exam_series_id);
CREATE INDEX IF NOT EXISTS idx_exam_schedules_class ON exam_schedules(class_id);
CREATE INDEX IF NOT EXISTS idx_exam_schedules_org ON exam_schedules(organization_id);

-- 3. Exam Student Marks
CREATE TABLE IF NOT EXISTS exam_student_marks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    schedule_id TEXT NOT NULL REFERENCES exam_schedules(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    marks_obtained REAL,
    is_absent INTEGER NOT NULL DEFAULT 0,
    is_exempt INTEGER NOT NULL DEFAULT 0,
    remarks TEXT,
    status TEXT NOT NULL DEFAULT 'SUBMITTED',
    entered_by TEXT,
    verified_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(schedule_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_exam_marks_sched ON exam_student_marks(schedule_id);
CREATE INDEX IF NOT EXISTS idx_exam_marks_student ON exam_student_marks(student_id);
CREATE INDEX IF NOT EXISTS idx_exam_marks_org ON exam_student_marks(organization_id);

-- 4. Grading Scales
CREATE TABLE IF NOT EXISTS grading_scales (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    scale_type TEXT NOT NULL DEFAULT 'NINE_POINT',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS idx_grading_scales_org ON grading_scales(organization_id);

-- 5. Grading Scale Tiers
CREATE TABLE IF NOT EXISTS grading_scale_tiers (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    scale_id TEXT NOT NULL REFERENCES grading_scales(id) ON DELETE CASCADE,
    grade_name TEXT NOT NULL,
    grade_point REAL NOT NULL DEFAULT 0.0,
    min_percentage REAL NOT NULL,
    max_percentage REAL NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_grading_tiers_scale ON grading_scale_tiers(scale_id);
CREATE INDEX IF NOT EXISTS idx_grading_tiers_org ON grading_scale_tiers(organization_id);

-- 6. Student Term Results
CREATE TABLE IF NOT EXISTS student_term_results (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    academic_term_id TEXT REFERENCES academic_terms(id) ON DELETE SET NULL,
    total_marks_obtained REAL NOT NULL DEFAULT 0.0,
    total_max_marks REAL NOT NULL DEFAULT 0.0,
    percentage REAL NOT NULL DEFAULT 0.0,
    gpa REAL DEFAULT 0.0,
    final_grade TEXT,
    rank INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(student_id, academic_year_id, academic_term_id)
);

CREATE INDEX IF NOT EXISTS idx_term_results_student ON student_term_results(student_id);
CREATE INDEX IF NOT EXISTS idx_term_results_term ON student_term_results(academic_term_id);
CREATE INDEX IF NOT EXISTS idx_term_results_org ON student_term_results(organization_id);

-- 7. Student Report Cards
CREATE TABLE IF NOT EXISTS student_report_cards (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    academic_term_id TEXT REFERENCES academic_terms(id) ON DELETE SET NULL,
    report_number TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    general_remarks TEXT,
    document_hash TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, report_number)
);

CREATE INDEX IF NOT EXISTS idx_report_cards_student ON student_report_cards(student_id);
CREATE INDEX IF NOT EXISTS idx_report_cards_term ON student_report_cards(academic_term_id);
CREATE INDEX IF NOT EXISTS idx_report_cards_org ON student_report_cards(organization_id);
