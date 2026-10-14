-- Migration 009 Reversible Down Script (Phase 01)

DROP TABLE IF EXISTS domain_events_outbox;
DROP TABLE IF EXISTS module_entitlements;
DROP TABLE IF EXISTS staff_profiles;
DROP TABLE IF EXISTS student_guardian_links;
DROP TABLE IF EXISTS guardian_profiles;
DROP TABLE IF EXISTS student_profiles;
DROP TABLE IF EXISTS persons;
