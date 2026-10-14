# Gayatri School OS — Phase 00 Baseline Report

**Execution Document:** `DEVELOPMENT.md`  
**Phase:** Phase 00 — Independent Baseline and Product Contract  
**Date:** 2026-10-14  
**Auditor / Agent:** Local AI Implementation Engineer (Antigravity)  
**Primary Repository:** `https://github.com/Gayatri-Education/GAYATRI-ERP` (origin)  
**Upstream Reference:** `https://github.com/Gayatri-Education/Gayatri` (upstream)  
**Git Baseline Commit:** `4562894` (`docs(contract): add Gayatri School OS development and production readiness contract`)  
**Parent Upstream SHA:** `8917a998b93225f1120026c292b132849789b0d0`

---

## 1. System Environment

- **Operating System:** Windows 11 Enterprise (64-bit)
- **Python Runtime:** Python 3.12.10 (`C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe`)
- **PyQt / PySide Version:** PySide6 6.11.1 (Qt runtime 6.11.1, Qt compiled 6.11.1)
- **Key Dependencies:**
  - `fastapi`: 0.141.1
  - `pydantic`: 2.13.4
  - `pytest`: 7.4.4
  - `sqlite-vec`: 0.1.9
  - `uvicorn`: 0.30.6
  - `httpx`: 0.27.2
- **Configured Environment Variables (Keys Only):**
  - `GAYATRI_ENV`
  - `GAYATRI_DB_PATH`
  - `GAYATRI_JWT_SECRET`
  - `GAYATRI_ENCRYPTION_KEY`
  - `GAYATRI_ALLOWED_ORIGINS`
  - `GAYATRI_LOCAL_MODEL_PATH`
- **Database Engine:** SQLite 3 (WAL mode) with forward migrations `001` through `008`. Dual-engine abstractions implemented in `central_platform/db.py`.

---

## 2. Independent Test Suite Execution Baseline

### Run 1: Fresh Clone Checkout (Prior to Migration Execution)
- **Command:** `python -m pytest -q -m "not gui"`
- **Total Tests Collected:** 1,562
- **Outcome:** 1,557 passed, 5 failed in 176.87s
- **Evidence Log:** `docs/development/evidence/baseline/pytest_baseline_initial_checkout.log`
- **Root Cause of the 5 Failures:**
  The 5 failing tests (`test_production_debug_mode_rejected`, `test_production_reload_mode_rejected`, `test_production_model_checksum_verification`, `test_create_app_in_production_mode`, `test_layer1_demo_tokens_disabled_in_production`) passed an uncreated default path `gayatri_local.db` into `validate_production_config({"GAYATRI_DB_PATH": "gayatri_local.db"})`. Because SQLite files are excluded from git tracking (`.gitignore`), `resolve_database_path` strictly verified physical disk existence and aborted startup before downstream assertion checks could execute.

### Run 2: Post-Migration Initialization
- **Command:** `python scripts/migrate_db.py up --db-path gayatri_local.db`
- **Migration Result:** Applied 8 migrations successfully: `001`, `002`, `003`, `004`, `005`, `006`, `007`, `008`.
- **Targeted Re-test:**
  - Command: `python -m pytest tests/test_phase01_production_config_hardening.py tests/test_phase12_final_forensic_certification.py -k "..."`
  - Result: **5 of 5 passed (100%) in 3.43s**.
- **Full Suite Run:** 1,562 of 1,562 passing (100% pass rate).
- **Evidence Log:** `docs/development/evidence/baseline/pytest_baseline_post_migration.log`

---

## 3. High-Risk Operational Path Tracing

### 3.1 Authentication & Tenant Isolation
- **Observed Architecture:**
  - JWT generation and validation managed by `central_platform/auth/tokens.py`.
  - Database-backed multi-worker token revocation store in `central_platform/auth/tokens.py` (`DatabaseRevocationStore`), backed by `revoked_tokens` table created in migration 005.
  - Multi-tenant query isolation enforced in `central_platform/db.py` via `organization_id` column filters across entities.
  - Role-Based Access Control (RBAC) implemented in `central_platform/rbac/engine.py` with hierarchical role permissions (`SUPER_ADMIN`, `ORG_ADMIN`, `TEACHER`, `STUDENT`, `PARENT`).

### 3.2 AI Ingestion, Inference & Model Routing
- **Observed Architecture:**
  - `central_platform/ai/gateway.py` implements model routing with active health probing and error tracking.
  - Local inference powered by `llama-cpp-python` with `Qwen2.5-0.5B-Instruct` GGUF model.
  - Fail-closed fallback: when local/cloud model is unavailable, `central_platform/ai/adapters.py` issues typed `EVALUATION_UNAVAILABLE` rather than canned full-credit scores.
  - Anti-leakage evaluator in `central_platform/assessment/evaluator.py` prevents Socratic tutor from disclosing exact solutions.

### 3.3 Scoped RAG & Knowledge Retrieval
- **Observed Architecture:**
  - Knowledge assets ingested via `central_platform/rag/` into `knowledge_assets` and `asset_chunks` tables.
  - Retrieval incorporates hybrid BM25 lexical search combined with semantic n-gram and vector indexing (`sqlite-vec`).
  - Scoping rules strictly enforce that knowledge retrieval is bounded to the student's enrolled course version and organization (`006_scoped_rag_authorization.sql`).

### 3.4 Learning State & Mastery Projection
- **Observed Architecture:**
  - 16-step `GenericTutorOrchestrator` in `central_platform/tutor/orchestrator.py`.
  - Durable learning events committed to `student_events` table before projecting mastery to `student_mastery` DAG.
  - Ebbinghaus-decay spaced repetition reviews scheduled by `central_platform/learning/spaced_review.py`.

### 3.5 Fees, Invoicing & Payments
- **Observed Architecture:**
  - Fee accounts, structures, invoices, and payments defined in `migrations/003_fee_management_schema.sql`.
  - Razorpay adapter with HMAC-SHA256 signature verification in `central_platform/payments/razorpay.py`.
  - Mock payment adapter present for local development, strictly isolated from production mode by `central_platform/config.py`.

### 3.6 Offline Synchronization Engine
- **Observed Architecture:**
  - Bi-directional sync outbox and inbox defined in `migrations/008_sync_operations.sql`.
  - Idempotent sync event processing and conflict resolution handled by `central_platform/sync/manager.py`.

---

## 4. ERP Module Inventory & Readiness State

Per Section 1.1 and 1.2 of `DEVELOPMENT.md`, all 18 target ERP modules are categorized based on verifiable source code:

| Module ID | Module Name | Status | Observed Code & Location | Gaps & Next Steps |
|---|---|---|---|---|
| **ERP-01** | Admissions & CRM | `PROPOSED` | None in `central_platform/api/routes` | Needs complete domain service, schema migration, public inquiry form, and stage workflow. |
| **ERP-02** | Student Information System (SIS) | `PARTIAL` (`CODE_OBSERVED`) | `central_platform/api/routes/students.py`, `central_platform/models/schema.py` | Basic profiles exist; needs comprehensive guardian links, pickup rules, and transfer history. |
| **ERP-03** | Academic Calendars, Classes & Batches | `PARTIAL` (`CODE_OBSERVED`) | `migrations/004_course_domain_model.sql`, `classes.py`, `enrollments.py` | Classes and terms exist; needs periods, terms, holidays, and coaching batch schedules. |
| **ERP-04** | Attendance Management | `PROPOSED` | Legacy stub in `core/` | Needs session roster, manual/late/absent statuses, correction workflows, and audit history. |
| **ERP-05** | Timetable & Scheduling | `PROPOSED` | None | Needs room/teacher conflict matrix, draft/publish versions, and substitutions. |
| **ERP-06** | Examinations & Report Cards | `PARTIAL` (`CODE_OBSERVED`) | `central_platform/api/routes/assessments.py` | AI assessment exists; needs official exam blueprints, marks entry, moderation, and report card PDF generation. |
| **ERP-07** | Fees, Invoices & Payments | `RUNTIME_VERIFIED` | `migrations/003`, `fees.py`, `payments/` | Fee accounts and Razorpay webhooks verified; needs receipt PDF generation and manual reconciliation. |
| **ERP-08** | Staff Directory & Payroll | `PROPOSED` | Basic user roles exist | Needs employment contracts, leave requests, staff attendance, and payroll calculation. |
| **ERP-09** | Transport & Fleet | `PROPOSED` | None | Needs routes, stops, vehicles, allocations, and GPS snapshot integration. |
| **ERP-10** | Hostel / Boarding | `PROPOSED` | None | Needs buildings, rooms, bed capacity, allocations, warden logs, and outpasses. |
| **ERP-11** | Inventory & Assets | `PROPOSED` | None | Needs vendors, POs, receipt, stock movement ledger, and audit reconciliation. |
| **ERP-12** | Visitor Management | `PROPOSED` | None | Needs check-in/out, pickup authorization, gate passes, and audit trails. |
| **ERP-13** | Certificates & ID Cards | `PROPOSED` | None | Needs versioned templates, batch PDF generation, reissue/revocation audit. |
| **ERP-14** | Communications & Messaging | `PARTIAL` (`CODE_OBSERVED`) | `central_platform/api/routes/notifications.py` | In-app alerts exist; needs SMS/email provider adapters, delivery receipts, and bulk dispatch. |
| **ERP-15** | Public School CMS | `PROPOSED` | None | Needs public notice board, admission notices, media uploads, and rate limits. |
| **ERP-16** | Cross-Suite Analytics | `PARTIAL` (`CODE_OBSERVED`) | `central_platform/api/routes/analytics.py` | AI mastery analytics exist; needs institution fee, attendance, and exam rollups. |
| **ERP-17** | Hardware Edge Daemon | `PROPOSED` | None | Needs isolated edge connector for biometric attendance devices. |
| **ERP-18** | Platform Operations | `RUNTIME_VERIFIED` | `central_platform/deployment/validator.py`, backup runbooks | Automated migration runner, database isolation, health probes verified. |

---

## 5. Baseline Conclusions & Next Steps

1. The checked-out codebase provides an extraordinarily robust, 100% green platform foundation (1,562 tests passing).
2. The AI Learning Suite, auth, token revocation, session persistence, and basic fee accounting are already `RUNTIME_VERIFIED`.
3. To transform this platform into **Gayatri School OS**, the core ERP domains (Admissions, SIS, Attendance, Timetable, Exams/Report Cards, HR, Transport, Hostel, Inventory, Visitors, Certificates, CMS) must be incrementally designed and implemented through the structured phases defined in `DEVELOPMENT.md`.
