-- ============================================================================
-- Migration 010 Rollback: Core ERP Foundation (Admissions CRM, Academic Calendar & SIS)
-- ============================================================================

DROP TABLE IF EXISTS student_class_enrollments;
DROP TABLE IF EXISTS student_classes;
DROP TABLE IF EXISTS admission_offers;
DROP TABLE IF EXISTS admission_documents;
DROP TABLE IF EXISTS admission_applications;
DROP TABLE IF EXISTS admission_inquiries;
DROP TABLE IF EXISTS school_calendar_events;
DROP TABLE IF EXISTS academic_terms;
DROP TABLE IF EXISTS academic_years;
