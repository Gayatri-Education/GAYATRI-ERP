# Phase 05 Plan — Attendance Engine and Hardware Adapters

**Document:** `docs/erp_agent/plans/PHASE_05_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 05 — Attendance Engine and Hardware Adapters  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 05 verifies and hardens the institutional attendance subsystem and hardware ingestion interfaces:
1. **Classroom Registers:** Daily attendance sessions per class/section and date; bulk marking (`PRESENT`, `ABSENT`, `LATE`, `EXCUSED`, `HALF_DAY`); review, undo, and audited corrections (`request_correction`, `approve_correction`).
2. **Kiosk & Adapter Interfaces:** QR kiosk attendance recording, student ID card mapping, simulated RFID serial/Ethernet packet processing, and deduplication.
3. **Leave & Excuse Reconciliation:** Parent/student excuse requests (`AbsenceExcuseRequest`) linked to attendance records.
4. **Summary & Payroll Feeds:** Class/student attendance aggregations feeding teacher briefings, parent portals, and staff payroll calculations.
5. **Hardware Truthfulness Disclosure:** Software adapters and simulated device packets are verified; real physical biometric scanners and RFID hardware are marked `DEFER_WITH_REASON` / `BLOCKED`.

---

## 2. Likely Files & Scope Boundary

- `central_platform/attendance/service.py` (`AttendanceService`)
- `central_platform/models/attendance.py`
- `central_platform/api/routes/attendance.py`
- `central_platform/hr/service.py` (`StaffAttendanceRecord`)
- `tests/test_qa_phase14_e2e_product_acceptance.py`
- `tests/test_phase28_teacher_portal_ui.py`
- `tests/test_qa_phase11_contracts_validation_idempotency.py`

---

## 3. Targeted Test Scenarios

1. Session creation upserts idempotently for identical class, date, and session type.
2. Bulk attendance marks entire rosters accurately without missing records.
3. Attendance corrections require reason, requester ID, and reviewer approval.
4. Excuse requests update status from `PENDING` to `APPROVED` or `REJECTED`.
5. Class attendance summary computes total students, present, absent, and percentage accurately.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Manual classroom register and bulk attendance workflows verified.
- [ ] Correction and excuse request lifecycles verified with audit trails.
- [ ] QR kiosk and simulated adapter ingestion verified.
- [ ] Hardware limitations honestly disclosed in `BLOCKERS.md`.
- [ ] `docs/erp_agent/reports/PHASE_05_REPORT.md` and `docs/erp_agent/regressions/PHASE_05_REGRESSION.md` generated with passing evidence.
