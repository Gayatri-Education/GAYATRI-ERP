# Phase 08 Plan: Unified Analytics, Quality, Accessibility and Institution Pilot Verification

## Status
- [ ] NOT_STARTED
- [ ] IN_PROGRESS
- [x] PASSED
- [ ] FAILED
- [ ] BLOCKED

---

## 1. Objective and Architecture

Deliver authoritative, unified cross-module institutional analytics, data export capabilities, support diagnostics, and dual-mode pilot verification:
1. **Unified Data Dictionary:** Formally document every operational KPI (`ANALYTICS_DATA_DICTIONARY.md`), defining canonical SQL source tables, formulas, denominators, and privacy boundaries.
2. **Authoritative SQL Reconciliation:** Ensure all analytics queries reconcile directly against SQL tables (`students`, `invoices`, `student_attendance_records`, `staff_leave_requests`, `exam_marks`, `inventory_items`, `transport_vehicles`, `hostel_rooms`) with verifiable `calculated_at` and `data_freshness_iso` metadata. Zero synthetic or fake numbers.
3. **Parent Privacy Enforcement:** Strict guardian policy levels (`STANDARD`, `RESTRICTED`, `ANONYMIZED`, `BLOCKED`) enforced on analytical and student views.
4. **Dual-Mode Institution Pilot Verification:**
   - K-12 School Tenant: Full grade levels, sections, subject exams, transport routes, and hostel boarding.
   - Coaching/Test-Prep Tenant: Subject batch enrollments, mock test schedules, modular fee installments, without forced school-only mandatory fields.
5. **Data Export & Reporting:** Secure CSV and JSON export engine with bounded pagination, date filters, and multi-tenant leakage protection.
6. **Backup, Restore & Support Diagnostics:** Automated snapshot backup, restoration verification, and redacted support diagnostic packages.
7. **Accessibility & Core Journey Quality:** Verification of key role journeys without dead-ends or unhandled failures.

---

## 2. Schema Specification (Migration 016)

- `export_jobs`: Registry of requested data exports with status (`PENDING`, `COMPLETED`, `FAILED`), row counts, and output references.
- `diagnostic_snapshots`: Persisted system health snapshots capturing schema versions, migration integrity, and hardware connectivity.

---

## 3. Implementation Steps

1. **Data Dictionary:** Complete and published in `docs/development/ANALYTICS_DATA_DICTIONARY.md`.
2. **Migration 016:** Forward (`migrations/016_analytics_exports_diagnostics.sql`) and rollback (`migrations/016_analytics_exports_diagnostics_down.sql`).
3. **Unified Analytics Engine:** `central_platform/analytics/institutional.py` (`UnifiedInstitutionalAnalyticsService`).
4. **Data Export Service:** `central_platform/analytics/exports.py` (`DataExportService`).
5. **Support Diagnostics & Operations:** `central_platform/ops/diagnostics.py` (`PlatformDiagnosticsService`).
6. **API Router:** `central_platform/api/routes/institutional_analytics.py` mounted under `/api/v1/analytics/institutional`.
7. **Focused Test Suite:** `tests/test_phase08_unified_analytics_quality_pilot.py` (10 tests).
8. **Regression & Certification:** Verify all existing 1,621 tests remain 100% green, document evidence and reports.
