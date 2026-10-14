# Gayatri School OS — Requirements Traceability Matrix

**Contract:** `DEVELOPMENT.md`  
**Status:** Living Traceability Matrix  
**Last Updated:** 2026-10-14  

---

## Phase Requirements Matrix (Phases 00 to 09)

| Req ID | Phase | Business Domain | Description & Contract Requirement | Architecture / Design Reference | Target Code / Files | Test IDs | Status |
|---|---|---|---|---|---|---|---|
| **REQ-P00-01** | Phase 00 | Governance | Confirm repository SHA, git remotes, and baseline test suite. | `DEVELOPMENT.md` §7 | `docs/development/` | Non-GUI suite (1,562 tests) | **PASSED** |
| **REQ-P00-02** | Phase 00 | Architecture | Create living Repository Map covering entrypoints, routes, tables, and services. | `REPOSITORY_MAP.md` | `central_platform/` | Architecture tests | **PASSED** |
| **REQ-P00-03** | Phase 00 | Inventory | Classify all 18 target ERP modules with explicit evidence status. | `BASELINE_REPORT.md` | `central_platform/models/` | Baseline audit | **PASSED** |
| **REQ-P00-04** | Phase 00 | Quality | Record all baseline test failures and open defect ledger. | `DEFECT_LEDGER.md` | `DEFECT_LEDGER.md` | `DEF-P00-01` | **PASSED** |
| **REQ-P01-01** | Phase 01 | Foundation | Consolidate configuration; enforce strict fail-fast production secrets. | `central_platform/config.py` | `central_platform/config.py` | `test_qa_phase01_authoritative_config.py` | **IN_PROGRESS** |
| **REQ-P01-02** | Phase 01 | Identity | Define canonical shared Person, Student, Guardian, and Staff identity models. | `central_platform/models/` | `central_platform/models/identity.py` | `test_phase01_shared_identity.py` | **NOT_STARTED** |
| **REQ-P01-03** | Phase 01 | Multi-Tenant | Enforce object-level tenant boundaries and RBAC policy across all routes. | `central_platform/auth/` | `central_platform/rbac/` | `test_phase08_security_adversarial.py` | **NOT_STARTED** |
| **REQ-P01-04** | Phase 01 | Data Layer | Deterministic migration runner, transaction boundaries, and isolation. | `central_platform/db.py` | `migrations/` | `test_phase01_db_lifecycle.py` | **NOT_STARTED** |
| **REQ-P02A-01**| Phase 02A| AI Suite | Real local model resolution, GGUF checksums, fail-closed educational fallback. | `central_platform/ai/` | `central_platform/ai/gateway.py` | `test_qa_phase02_ai_execution_integrity.py` | **NOT_STARTED** |
| **REQ-P02A-02**| Phase 02A| RAG Suite | Scoped RAG retrieval, anti-leakage defense, golden query benchmark. | `central_platform/rag/` | `central_platform/rag/` | `test_qa_phase07_rag_integrity_grounding.py` | **NOT_STARTED** |
| **REQ-P02B-01**| Phase 02B| Core ERP | Student Information System (SIS), guardian linkages, student profiles. | `central_platform/students/` | `central_platform/models/students.py` | `test_phase02b_sis_foundation.py` | **NOT_STARTED** |
| **REQ-P02B-02**| Phase 02B| Core ERP | Admissions & Inquiry CRM, public form validation, stage workflow. | `central_platform/admissions/` | `central_platform/models/admissions.py` | `test_phase02b_admissions_crm.py` | **NOT_STARTED** |
| **REQ-P03-01** | Phase 03 | Operations | Attendance management (daily roster, statuses, audit corrections). | `central_platform/attendance/`| `central_platform/models/attendance.py` | `test_phase03_attendance_roster.py` | **NOT_STARTED** |
| **REQ-P03-02** | Phase 03 | Operations | Timetable & scheduling, period conflict matrices, substitutions. | `central_platform/timetable/` | `central_platform/models/timetable.py` | `test_phase03_timetable_matrix.py` | **NOT_STARTED** |
| **REQ-P03-03** | Phase 03 | Operations | Communications engine, notification queues, delivery receipts. | `central_platform/comms/` | `central_platform/notifications/` | `test_phase03_communications.py` | **NOT_STARTED** |
| **REQ-P04-01** | Phase 04 | Academics | Official examinations, assessment blueprints, mark entry & moderation. | `central_platform/exams/` | `central_platform/models/exams.py` | `test_phase04_examinations.py` | **NOT_STARTED** |
| **REQ-P04-02** | Phase 04 | Academics | Report cards and transcripts, PDF generation, versioned grading schemes. | `central_platform/reports/` | `central_platform/models/report_cards.py` | `test_phase04_report_cards.py` | **NOT_STARTED** |
| **REQ-P05-01** | Phase 05 | Finance | Fee structures, invoicing, manual payment reconciliation, financial ledger. | `central_platform/fees/` | `central_platform/models/fees.py` | `test_phase05_finance_ledger.py` | **NOT_STARTED** |
| **REQ-P05-02** | Phase 05 | Finance | Live payment gateway integration (Razorpay/UPI), HMAC webhooks. | `central_platform/payments/` | `central_platform/payments/razorpay.py`| `test_phase05_payment_gateways.py` | **NOT_STARTED** |
| **REQ-P06-01** | Phase 06 | Operations | Staff directory, leave requests, staff attendance, payroll preparation. | `central_platform/hr/` | `central_platform/models/hr.py` | `test_phase06_staff_payroll.py` | **NOT_STARTED** |
| **REQ-P06-02** | Phase 06 | Operations | Transport routes, stops, vehicle & driver assignments, allocations. | `central_platform/transport/` | `central_platform/models/transport.py` | `test_phase06_transport.py` | **NOT_STARTED** |
| **REQ-P06-03** | Phase 06 | Operations | Hostel / boarding rooms, bed capacity, allocations, warden outpasses. | `central_platform/hostel/` | `central_platform/models/hostel.py` | `test_phase06_hostel.py` | **NOT_STARTED** |
| **REQ-P06-04** | Phase 06 | Operations | Inventory / assets, POs, receipt, stock movement ledger, audits. | `central_platform/inventory/` | `central_platform/models/inventory.py` | `test_phase06_inventory.py` | **NOT_STARTED** |
| **REQ-P06-05** | Phase 06 | Operations | Visitor management, gate passes, pickup authorizations. | `central_platform/visitors/` | `central_platform/models/visitors.py` | `test_phase06_visitors.py` | **NOT_STARTED** |
| **REQ-P06-06** | Phase 06 | Operations | Certificates & ID cards, versioned templates, batch PDF generation. | `central_platform/certs/` | `central_platform/models/certificates.py`| `test_phase06_certificates.py` | **NOT_STARTED** |
| **REQ-P06-07** | Phase 06 | Operations | Public School CMS, public announcements, admission notices, media. | `central_platform/cms/` | `central_platform/models/cms.py` | `test_phase06_public_cms.py` | **NOT_STARTED** |
| **REQ-P07-01** | Phase 07 | Sync & Edge | Offline sync hardening, conflict resolution, outbox queue. | `central_platform/sync/` | `central_platform/sync/manager.py` | `test_phase07_sync_hardening.py` | **NOT_STARTED** |
| **REQ-P07-02** | Phase 07 | Sync & Edge | Hardware edge daemon, biometric attendance device connector. | `edge/daemon.py` | `edge/` | `test_phase07_edge_connector.py` | **NOT_STARTED** |
| **REQ-P08-01** | Phase 08 | Quality | Cross-suite analytics, institutional pilot verification, WCAG accessibility.| `central_platform/analytics/`| `central_platform/` | `test_phase08_pilot_readiness.py` | **NOT_STARTED** |
| **REQ-P09-01** | Phase 09 | Release | Production release gate, controlled rollout, operational runbooks. | `docs/operations/` | `packaging/` | `test_phase09_release_gate.py` | **NOT_STARTED** |
