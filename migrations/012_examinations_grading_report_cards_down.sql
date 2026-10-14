-- ============================================================================
-- Rollback Migration 012: Examinations, Official Grading and Report Cards
-- ============================================================================

DROP TABLE IF EXISTS student_report_cards;
DROP TABLE IF EXISTS student_term_results;
DROP TABLE IF EXISTS grading_scale_tiers;
DROP TABLE IF EXISTS grading_scales;
DROP TABLE IF EXISTS exam_student_marks;
DROP TABLE IF EXISTS exam_schedules;
DROP TABLE IF EXISTS exam_series;
