-- ============================================================================
-- Migration 011: Attendance, Timetable and Communications Foundation
-- ============================================================================

-- 1. Attendance Sessions
CREATE TABLE IF NOT EXISTS attendance_sessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES student_classes(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    session_type TEXT NOT NULL DEFAULT 'FULL_DAY',
    status TEXT NOT NULL DEFAULT 'SUBMITTED',
    taken_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, class_id, date, session_type)
);

CREATE INDEX IF NOT EXISTS idx_att_sessions_class_date ON attendance_sessions(class_id, date);
CREATE INDEX IF NOT EXISTS idx_att_sessions_org ON attendance_sessions(organization_id);

-- 2. Attendance Records
CREATE TABLE IF NOT EXISTS attendance_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PRESENT',
    arrival_time TEXT,
    remarks TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_att_records_student ON attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_att_records_session ON attendance_records(session_id);

-- 3. Attendance Corrections Ledger
CREATE TABLE IF NOT EXISTS attendance_corrections (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    record_id TEXT NOT NULL REFERENCES attendance_records(id) ON DELETE CASCADE,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    corrected_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_att_corrections_rec ON attendance_corrections(record_id);

-- 4. Absence Excuse Requests
CREATE TABLE IF NOT EXISTS absence_excuse_requests (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    approved_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_absence_excuse_student ON absence_excuse_requests(student_id);

-- 5. Timetable Periods
CREATE TABLE IF NOT EXISTS timetable_periods (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    period_number INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    is_break INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(organization_id, academic_year_id, period_number)
);

CREATE INDEX IF NOT EXISTS idx_tt_periods_year ON timetable_periods(academic_year_id);

-- 6. Class Timetable Slots
CREATE TABLE IF NOT EXISTS class_timetable_slots (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    academic_year_id TEXT NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    class_id TEXT NOT NULL REFERENCES student_classes(id) ON DELETE CASCADE,
    period_id TEXT NOT NULL REFERENCES timetable_periods(id) ON DELETE CASCADE,
    day_of_week TEXT NOT NULL,
    subject_id TEXT,
    teacher_id TEXT,
    room_name TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tt_slots_class ON class_timetable_slots(class_id);
CREATE INDEX IF NOT EXISTS idx_tt_slots_teacher ON class_timetable_slots(teacher_id, day_of_week, period_id);
CREATE INDEX IF NOT EXISTS idx_tt_slots_room ON class_timetable_slots(room_name, day_of_week, period_id);

-- 7. Teacher Substitutions
CREATE TABLE IF NOT EXISTS teacher_substitutions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    slot_id TEXT NOT NULL REFERENCES class_timetable_slots(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    original_teacher_id TEXT NOT NULL,
    substitute_teacher_id TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'APPROVED',
    created_at TEXT NOT NULL,
    UNIQUE(slot_id, date)
);

CREATE INDEX IF NOT EXISTS idx_substitutions_date ON teacher_substitutions(date);

-- 8. Notification Templates
CREATE TABLE IF NOT EXISTS notification_templates (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    template_code TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'IN_APP',
    subject_template TEXT,
    body_template TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, template_code)
);

CREATE INDEX IF NOT EXISTS idx_notif_templates_org ON notification_templates(organization_id);

-- 9. Notification Dispatches
CREATE TABLE IF NOT EXISTS notification_dispatches (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    template_code TEXT NOT NULL,
    recipient_user_id TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'IN_APP',
    destination TEXT,
    rendered_subject TEXT,
    rendered_body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    error_details TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    sent_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notif_dispatches_user ON notification_dispatches(recipient_user_id, status);
CREATE INDEX IF NOT EXISTS idx_notif_dispatches_org ON notification_dispatches(organization_id);
