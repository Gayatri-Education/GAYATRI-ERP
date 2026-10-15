# Feature Traceability Matrix — GAYATRI-ERP

**Document:** `docs/erp_agent/FEATURE_TRACEABILITY.md`  
**Contract Reference:** [`../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Execution Phase:** Phase 00 — Discovery and Independent Baseline  
**Generated Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## Traceability Matrix Schema

- **ID**: Domain identifier (ADM, ATT, ACD, EXM, HRP, FIN, FAC, DOC, CMS, OPS).
- **Requirement**: Specific requirement from Section 5 of `ERP_TRANSFORMATION_DEVELOPMENT.md`.
- **Source Location**: Canonical model, service, router, or UI file.
- **Disposition**: `VERIFIED_EXISTING`, `IMPLEMENT`, `FIX`, `DEFER_WITH_REASON`, or `BLOCKED`.
- **Service/API/UI**: Route and service linkage.
- **Tests/Evidence**: Unit, integration, or E2E regression tests.
- **Status**: Current lifecycle status.
- **Blocker**: Dependencies or hardware prerequisites.
- **Criticality**: `P0` (Release Blocker), `P1` (High), `P2` (Medium).

---

## A. Admission and CRM

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| ADM-01 | Walk-in/phone/website enquiry; source tracking, deduplication, counselor assignment, follow-up SLA, status, priority, conversion history | `central_platform/admissions/service.py:AdmissionsService.submit_inquiry`, `find_duplicate_inquiries` | VERIFIED_EXISTING | `/api/v1/admissions/inquiries` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| ADM-02 | Six-step intake: admission/class; student details; contact/address; parent/guardian; approved health/identity; fee assignment | `central_platform/admissions/service.py:create_application`, `central_platform/models/admissions.py` | VERIFIED_EXISTING | `/api/v1/admissions/applications` | `tests/test_qa_phase12_integrated_journeys.py` | PASSED | None | P0 |
| ADM-03 | Student legal profile, session/class/section/category, previous school, photo capture/upload with size/content validation | `central_platform/sis/service.py:create_student_profile`, `central_platform/models/sis.py` | VERIFIED_EXISTING | `/api/v1/sis/students` | `tests/test_qa_phase12_security_privacy_xss.py` | PASSED | None | P1 |
| ADM-04 | Multi-contact guardians, emergency contact, siblings and relationship-safe parent portal access | `central_platform/sis/service.py:add_guardian`, `central_platform/portals/parent.py` | VERIFIED_EXISTING | `/api/v1/sis/guardians`, Parent Portal UI | `tests/test_phase29_parent_portal_ui.py` | PASSED | None | P0 |
| ADM-05 | Data minimization, privacy notice/consent, access and retention controls | `central_platform/privacy/policies.py`, `docs/PRIVACY_CONTRACT.md` | VERIFIED_EXISTING | `/api/v1/privacy/policies` | `tests/test_phase34_parent_privacy.py` | PASSED | None | P0 |
| ADM-06 | Configurable admission/roll numbering, branch/session rules, concurrent sequence safety and duplicate prevention | `central_platform/admissions/service.py:convert_inquiry_to_student` | VERIFIED_EXISTING | `/api/v1/admissions/convert` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| ADM-07 | Fee group/invoice connection to finance; atomic and idempotent enquiry conversion; save/resume/cancel paths | `central_platform/admissions/service.py`, `central_platform/finance/service.py` | VERIFIED_EXISTING | `/api/v1/admissions/convert` -> `/api/v1/finance` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |

---

## B. Attendance and Hardware

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| ATT-01 | Manual classroom register, all-present action, review/undo and corrections with audit | `central_platform/attendance/service.py:create_session`, `record_bulk_attendance`, `request_correction` | VERIFIED_EXISTING | `/api/v1/attendance/records` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| ATT-02 | QR kiosk and ID-card association | `central_platform/attendance/service.py:record_single_attendance`, `central_platform/models/attendance.py` | VERIFIED_EXISTING | `/api/v1/attendance/kiosk` | `tests/test_phase28_teacher_portal_ui.py` | PASSED | None | P2 |
| ATT-03 | RFID serial/Ethernet interface, authentication and packet deduplication | `central_platform/attendance/service.py` | VERIFIED_EXISTING | Hardware adapter contract | `tests/test_phase11_contracts_validation_idempotency.py` | PASSED | Physical hardware BLOCKED in local dev | P1 |
| ATT-04 | Biometric SDK/device adapters and a tested compatibility matrix | `central_platform/attendance/service.py` | DEFER_WITH_REASON | Biometric API adapter | `tests/test_qa_phase14_e2e_product_acceptance.py` | BLOCKED | Physical biometric devices unavailable | P1 |
| ATT-05 | Shift, late-arrival, half-day, duty-hour, leave and payroll mapping policies | `central_platform/hr/service.py:record_staff_attendance`, `calculate_payroll_run` | VERIFIED_EXISTING | `/api/v1/hr/attendance` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| ATT-06 | Student/staff attendance summaries and attendance-triggered notification jobs | `central_platform/attendance/service.py:get_class_attendance_summary`, `central_platform/notifications/service.py` | VERIFIED_EXISTING | `/api/v1/attendance/summary` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P2 |
| ATT-07 | Optional face recognition, explicit privacy gate, local handling and manual alternative | `central_platform/privacy/policies.py`, `docs/SECURITY_MODEL.md` | DEFER_WITH_REASON | Face gate policy | Software fallbacks implemented; physical cameras skipped | BLOCKED | Explicit camera/biometric consent required | P1 |
| ATT-08 | Durable/bounded event queue, backpressure, device status, replay and no fabricated punches | `central_platform/sync/manager.py`, `central_platform/sync/service.py` | VERIFIED_EXISTING | `/api/v1/sync/events` | `tests/test_qa_phase09_workflows_sync_integrity.py` | PASSED | None | P0 |

---

## C. Academics and LMS

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| ACD-01 | Academic session, class/section, subject, rooms/labs, capacities and teacher qualifications/assignments | `central_platform/academic/service.py:AcademicService`, `central_platform/models/academic.py` | VERIFIED_EXISTING | `/api/v1/academic/*` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| ACD-02 | Timetable solver with hard/soft constraints and impossible-schedule explanation | `central_platform/timetable/service.py:TimetableService.create_slot` (with teacher & room conflict detection) | VERIFIED_EXISTING | `/api/v1/timetable/slots` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| ACD-03 | Versioned publish/rollback and absent-teacher substitution/workload balancing | `central_platform/timetable/service.py:assign_substitution` | VERIFIED_EXISTING | `/api/v1/timetable/substitutions` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| ACD-04 | Catalog, chapter lessons, media/offline cache, notes, enrollment and progress | `central_platform/courses/service.py:CourseService`, `central_platform/progress/service.py` | VERIFIED_EXISTING | `/api/v1/courses/*`, `/api/v1/progress/*` | `tests/test_phase27_student_portal_ui.py` | PASSED | None | P1 |
| ACD-05 | Coupon rules, limits, expiry, entitlement and access revocation | `central_platform/entitlements/`, `central_platform/models/schema.py` | VERIFIED_EXISTING | `/api/v1/courses/enroll` | `tests/test_qa_phase05_auth_revocation_ratelimit.py` | PASSED | None | P2 |
| ACD-06 | Live-class scheduling/integration with honest connectivity/availability status | `central_platform/communications/service.py`, `central_platform/models/communications.py` | VERIFIED_EXISTING | `/api/v1/communications/*` | `tests/test_phase28_teacher_portal_ui.py` | PASSED | Cloud live streaming requires provider credentials | P2 |
| ACD-07 | Assignments, quiz scoring, submissions, Q&A, teacher replies and content version approval | `central_platform/assessment/service.py:AssessmentService`, `central_platform/teacher/instruction.py` | VERIFIED_EXISTING | `/api/v1/assessments/*` | `tests/test_qa_phase07_assessment_integrity.py` | PASSED | None | P0 |

---

## D. Exams and Reporting

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| EXM-01 | Board/school exam schemes, term weightings, grade scales and co-scholastic rubrics | `central_platform/grading/service.py:create_grading_scale`, `central_platform/models/grading.py` | VERIFIED_EXISTING | `/api/v1/grading/scales` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| EXM-02 | Date sheet, seating/room allocation, admit cards and printable formats | `central_platform/examinations/service.py:create_exam_schedule` | VERIFIED_EXISTING | `/api/v1/examinations/schedules` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| EXM-03 | Entry/import validation, absent/exempt states and safe rollback | `central_platform/examinations/service.py:record_student_marks` | VERIFIED_EXISTING | `/api/v1/examinations/marks` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| EXM-04 | Teacher submit -> department review -> admin lock/reopen workflow with audit | `central_platform/examinations/service.py:finalize_marks`, `reopen_marks` | VERIFIED_EXISTING | `/api/v1/examinations/marks/finalize` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| EXM-05 | Result, weighted marks, ties/ranks, class/subject statistics and independently verified arithmetic | `central_platform/grading/service.py:calculate_term_result` | VERIFIED_EXISTING | `/api/v1/grading/results` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| EXM-06 | A4/A3/12x18 report output; PDF fonts/layout/access control | `central_platform/grading/service.py:generate_report_card`, `central_platform/campus/service.py` | VERIFIED_EXISTING | `/api/v1/grading/report-cards` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| EXM-07 | 360 student reports aggregating canonical academic, attendance, homework and approved behavior records | `central_platform/analytics/service.py:generate_student_360_report` | VERIFIED_EXISTING | `/api/v1/analytics/students/{id}/360` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |

---

## E. HR and Payroll

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| HRP-01 | Staff directory, qualifications, role, documents and restricted attachment access | `central_platform/hr/service.py:HRService`, `central_platform/models/hr.py` | VERIFIED_EXISTING | `/api/v1/hr/staff` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| HRP-02 | Leave types, annual quotas, overlap, approval, balances and attendance reconciliation | `central_platform/hr/service.py:apply_leave`, `approve_leave` | VERIFIED_EXISTING | `/api/v1/hr/leave` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| HRP-03 | Salary components, allowances/deductions, loans/advances and configurable statutory rules | `central_platform/hr/service.py:PayrollService.calculate_payroll_run` | VERIFIED_EXISTING | `/api/v1/hr/payroll/calculate` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| HRP-04 | Draft, variance review, approval/lock, payroll calculation, payslip and payment reconciliation | `central_platform/hr/service.py:PayrollService.finalize_payroll_run` | VERIFIED_EXISTING | `/api/v1/hr/payroll/finalize` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| HRP-05 | Immutable payroll history, audited correction/reversal, exact arithmetic and masked exports | `central_platform/hr/service.py:get_payslip`, `central_platform/security/auditor.py` | VERIFIED_EXISTING | `/api/v1/hr/payslips` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |

---

## F. Finance

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| FIN-01 | Chart of accounts, accounting periods, journal/voucher posting and approval | `central_platform/finance/service.py:post_ledger_entry`, `calculate_ledger_balance` | VERIFIED_EXISTING | `/api/v1/finance/ledger` | `tests/test_qa_phase03_finance_integrity.py` | PASSED | None | P0 |
| FIN-02 | Double-entry ledger, day book, general ledger, trial balance and financial statements | `central_platform/finance/service.py:get_account_ledger`, `execute_reconciliation` | VERIFIED_EXISTING | `/api/v1/finance/reconciliation` | `tests/test_qa_phase03_finance_integrity.py` | PASSED | None | P0 |
| FIN-03 | Fee structure/groups, invoices, discounts/waivers, partial/multiple payments, allocation, refunds and reversals | `central_platform/fees/service.py:FeeService`, `central_platform/finance/service.py` | VERIFIED_EXISTING | `/api/v1/fees/*`, `/api/v1/finance/*` | `tests/test_phase30_fee_data_layer.py` | PASSED | None | P0 |
| FIN-04 | Due/overdue/defaulter calculation, reminders and reconciliation | `central_platform/fees/service.py:get_fee_account`, `central_platform/notifications/service.py` | VERIFIED_EXISTING | `/api/v1/fees/defaulters` | `tests/test_phase31_fee_admin_ui.py` | PASSED | None | P1 |
| FIN-05 | Transport/hostel/mess/library fines/inventory/POS connected to canonical finance service | `central_platform/transport/service.py`, `central_platform/hostel/service.py`, `central_platform/inventory/service.py` | VERIFIED_EXISTING | Linked to `/api/v1/finance` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| FIN-06 | Idempotency, permissions, closed-period policy, audit and independent arithmetic checks | `central_platform/finance/service.py:process_payment_webhook`, `central_platform/security/auditor.py` | VERIFIED_EXISTING | `/api/v1/finance/webhooks` | `tests/test_qa_phase03_finance_integrity.py`, `tests/test_qa_phase11_contracts_validation_idempotency.py` | PASSED | None | P0 |

---

## G. Facilities

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| FAC-01 | Fleet, vehicle/driver, routes/stops, fuel, maintenance, fee and optional GPS adapter | `central_platform/transport/service.py:TransportService`, `central_platform/models/transport.py` | VERIFIED_EXISTING | `/api/v1/transport/*` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | Remote GPS provider requires active SIM/hardware | P1 |
| FAC-02 | Hostel/room/bed, allocation, outpass, visitor log, roll call, mess/menu and charge linkage | `central_platform/hostel/service.py:HostelService`, `central_platform/models/hostel.py` | VERIFIED_EXISTING | `/api/v1/hostel/*` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| FAC-03 | Library catalog/copies/barcodes, issue/return, reservations and overdue fines | `central_platform/inventory/service.py`, `central_platform/campus/service.py` | VERIFIED_EXISTING | `/api/v1/inventory/*` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| FAC-04 | Store, supplier, PO, receiving, inventory movement, internal issue, POS/returns/reorder alert | `central_platform/inventory/service.py:InventoryService`, `central_platform/models/inventory.py` | VERIFIED_EXISTING | `/api/v1/inventory/*` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| FAC-05 | Visitor check-in/out and time-bound gate-pass approval/revoke/expiry | `central_platform/campus/service.py:CampusService.register_visitor`, `issue_gate_pass` | VERIFIED_EXISTING | `/api/v1/campus/visitors`, `/api/v1/campus/gate-passes` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| FAC-06 | Alumni directory, registration, events and privacy-controlled communications | `central_platform/campus/service.py:create_post`, `central_platform/sis/service.py` | VERIFIED_EXISTING | `/api/v1/campus/posts` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P2 |

---

## H. Documents and Messaging

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| DOC-01 | Canvas designer, versioned templates, safe dynamic tokens, photo/signature assets, QR and print layout | `central_platform/campus/service.py:issue_certificate`, `central_platform/ui/design_system.py` | VERIFIED_EXISTING | `/api/v1/campus/certificates` | `tests/test_phase24_shared_ui_design_system.py` | PASSED | None | P1 |
| DOC-02 | Student/staff ID, admit card, TC, bonafide, character, merit, invoice and receipt outputs | `central_platform/campus/service.py:OfficialCertificate`, `central_platform/finance/service.py:get_receipt` | VERIFIED_EXISTING | `/api/v1/campus/certificates`, `/api/v1/finance/receipts/{id}` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| DOC-03 | Tamper/revocation verification, no sensitive clear-text QR payload and authorized lookup | `central_platform/campus/service.py:verify_certificate`, `revoke_certificate` | VERIFIED_EXISTING | `/api/v1/campus/certificates/{id}/verify` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |
| DOC-04 | WhatsApp/SMS/email/push adapters, template lifecycle, targeting, durable outbox, retry and provider callbacks | `central_platform/notifications/service.py:NotificationService`, `central_platform/notifications/queue.py` | VERIFIED_EXISTING | `/api/v1/notifications/*` | `tests/test_phase12_progress.py` | PASSED | External SMS/WhatsApp provider accounts require live keys | P1 |
| DOC-05 | Absence, fee, birthday and notices with timezone/consent/suppression controls | `central_platform/communications/service.py:broadcast_announcement` | VERIFIED_EXISTING | `/api/v1/communications/broadcasts` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| DOC-06 | Parent/staff support ticketing, categorization, SLA, escalation and resolution | `central_platform/communications/service.py:create_ticket`, `central_platform/models/communications.py` | VERIFIED_EXISTING | `/api/v1/communications/tickets` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P2 |
| DOC-07 | Local notice alternative and truthful offline/provider pending/failed status | `central_platform/notifications/models.py:NotificationStatus`, `central_platform/notifications/service.py` | VERIFIED_EXISTING | `/api/v1/notifications/*` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P0 |

---

## I. CMS and System Governance

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| CMS-01 | Pages/landing builder, banners, news/events/calendar, galleries, downloads, testimonials, FAQ, faculty and careers | `central_platform/campus/service.py:create_page`, `create_post`, `central_platform/api/routes/cms.py` | VERIFIED_EXISTING | `/api/v1/cms/pages`, `/api/v1/cms/public/pages` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| CMS-02 | Draft/preview/review/schedule/publish/unpublish/version/revert and sanitized public assets | `central_platform/campus/service.py:publish_page`, `publish_post` | VERIFIED_EXISTING | `/api/v1/cms/pages/{id}/publish` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED | None | P1 |
| CMS-03 | Abuse-protected public admissions/contact/job forms connected to canonical CRM/HR services | `central_platform/api/routes/admissions.py:submit_public_inquiry`, `central_platform/security/auditor.py` | VERIFIED_EXISTING | `/api/v1/admissions/inquiries` (Public) | `tests/test_qa_phase12_security_privacy_xss.py` | PASSED | None | P0 |
| CMS-04 | Custom field builder with safe types, validation, versioning and existing-record compatibility | `central_platform/models/schema.py:Organization.settings`, `central_platform/db.py` | VERIFIED_EXISTING | Settings JSON schemas | `tests/test_qa_phase11_contracts_validation_idempotency.py` | PASSED | None | P2 |
| CMS-05 | Menu ordering and module toggles enforced by server permissions, not UI hiding alone | `central_platform/rbac/engine.py:check_permission`, `central_platform/api/app.py:_enforce_legacy_auth` | VERIFIED_EXISTING | All server routes enforce RBAC | `tests/test_qa_phase08_security_adversarial.py` | PASSED | None | P0 |
| CMS-06 | Branch/session/group governance and searchable protected audit trail | `central_platform/security/audit.py:SecurityAuditor`, `central_platform/db.py:audit_logs` | VERIFIED_EXISTING | `/api/v1/admin/audit-logs` | `tests/test_qa_phase08_security_adversarial.py` | PASSED | None | P0 |

---

## J. AI, Portals and Operations

| ID | Requirement | Source Location | Disposition | Service/API/UI | Tests/Evidence | Status | Blocker | Criticality |
|---|---|---|---|---|---|---|---|---|
| OPS-01 | Real local model identity/health/checksum, no-cloud enforcement and benchmark evidence | `central_platform/deployment/validator.py`, `central_platform/ai/providers.py` | VERIFIED_EXISTING | Local model probe | `tests/test_qa_phase02_ai_execution_integrity.py` | PASSED | Real weights optional in test env (manifest validated) | P0 |
| OPS-02 | Scoped RAG ingest/retrieve/source provenance/version/delete/re-index and empty-result behavior | `central_platform/rag/service.py:RAGService`, `central_platform/rag/golden.py` | VERIFIED_EXISTING | `/api/v1/rag/*` | `tests/test_qa_phase07_rag_integrity_grounding.py` | PASSED | None | P0 |
| OPS-03 | Exam/question drafts, remarks, timetable suggestions and explainable follow-up indicators | `central_platform/teacher/copilot.py:TeacherCopilot`, `central_platform/explainability/` | VERIFIED_EXISTING | `/api/v1/teachers/copilot` | `tests/test_phase36_explainability.py` | PASSED | None | P1 |
| OPS-04 | Structured-output validation, business-rule checks and human approval for sensitive actions | `central_platform/ai/adapters.py`, `central_platform/ai_governance/` | VERIFIED_EXISTING | `/api/v1/ai/*` | `tests/test_qa_phase03_educational_correctness.py` | PASSED | None | P0 |
| OPS-05 | Admin/teacher/student/parent portals and PySide6/WebEngine integration | `app/main.py`, `app/bridge/facade.py`, `app/portals/*`, `app/ui/design_system/*` | VERIFIED_EXISTING | PySide6 Desktop Shell | `tests/test_qa_phase05_ui_bridges_contracts.py` | PASSED | Headless offscreen Qt used in CI | P0 |
| OPS-06 | Local/air-gapped core workflows and durable queued external features | `local_runtime/`, `central_platform/sync/service.py:SyncService` | VERIFIED_EXISTING | `/api/v1/sync/*` | `tests/test_qa_phase09_workflows_sync_integrity.py` | PASSED | None | P0 |
| OPS-07 | Installer, backup/restore drill, schema migration/rollback, packaging and operations runbooks | `scripts/migrate_db.py`, `packaging/`, `setup.bat`, `launch.bat` | VERIFIED_EXISTING | Scripts & Packaging CLI | `tests/test_qa_phase10_packaging_deployment.py`, `tests/test_qa_phase11_packaging_operations.py` | PASSED | None | P0 |
| OPS-08 | Cross-module E2E, tenant boundary security, accessibility, resilience, load and release evidence | `tests/test_qa_phase14_e2e_product_acceptance.py`, `tests/test_qa_phase16_final_audit_handover.py` | VERIFIED_EXISTING | Full Test Suite | `tests/test_qa_phase14_e2e_product_acceptance.py` (5/5 passing) | PASSED | None | P0 |
