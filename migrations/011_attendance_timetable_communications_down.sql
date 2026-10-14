-- ============================================================================
-- Migration 011 Rollback: Attendance, Timetable and Communications Foundation
-- ============================================================================

DROP TABLE IF EXISTS notification_dispatches;
DROP TABLE IF EXISTS notification_templates;
DROP TABLE IF EXISTS teacher_substitutions;
DROP TABLE IF EXISTS class_timetable_slots;
DROP TABLE IF EXISTS timetable_periods;
DROP TABLE IF EXISTS absence_excuse_requests;
DROP TABLE IF EXISTS attendance_corrections;
DROP TABLE IF EXISTS attendance_records;
DROP TABLE IF EXISTS attendance_sessions;
