# GAYATRI-ERP — Comprehensive Repository & Architecture Map

**Document:** `docs/erp_agent/REPOSITORY_MAP.md`  
**Contract Reference:** [`../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Execution Phase:** Phase 00 — Discovery and Independent Baseline  
**Generated Date:** 2026-10-15  
**Baseline SHA:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Package Structure & Entrypoints

The Gayatri-ERP repository is structured into distinct, decoupled platform layers:

```text
c:\Users\user\Desktop\gayatri\Gayatri-ERP
├── app/                        # PySide6 desktop application shell and QWebChannel bridges
│   ├── bridge/                 # IPC bridge facades for WebEngine/JS communication
│   ├── portals/                # Desktop portal window controllers (admin, teacher, student, parent)
│   ├── ui/                     # WebEngine HTML, CSS tokens, and JS component assets
│   └── windows/                # Main application window and splash screen
├── central_platform/           # Core backend services, FastAPI routers, database, and models
│   ├── academic/               # Academic sessions, classes, sections, subjects
│   ├── admissions/             # Inquiries, intake CRM, document verification, enrollments
│   ├── ai/                     # AI gateway, policy router, providers, and audit logging
│   ├── ai_governance/          # AI safety, explainability, kill-switch, content moderation
│   ├── analytics/              # Institutional cohorts, mastery distribution, telemetry
│   ├── api/                    # FastAPI app factory, middleware, routes (38+ routers)
│   ├── assessment/             # Question banks, assessments, auto-evaluators, attempts
│   ├── attendance/             # Daily registers, bulk attendance, excuse workflows, corrections
│   ├── auth/                   # JWT creation, bcrypt hashing, DB-backed revocation, dependencies
│   ├── campus/                 # Visitors, gate passes, certificates, and CMS pages/posts
│   ├── communications/         # Announcements, notices, channels, and outbox messages
│   ├── courses/                # Subject-agnostic course definitions and versioning
│   ├── curriculum/             # Board curricula, modules, topics, concept DAGs, prerequisites
│   ├── deployment/             # Preflight deployment validator and health probes
│   ├── e2e/                    # End-to-end integration and smoke test harnesses
│   ├── examinations/           # Exam series, schedules, and student mark entry
│   ├── fees/                   # Fee structures, plans, accounts, and student billing
│   ├── finance/                # Orders, webhook verification, double-entry ledger, reconciliation
│   ├── grading/                # Grading scales, 9-point rubrics, term results, report cards
│   ├── health/                 # Multi-subsystem deep health and readiness probes
│   ├── hostel/                 # Hostel blocks, rooms, bed allocations, fees
│   ├── hr/                     # Staff directory, leave requests, attendance, payroll runs, payslips
│   ├── inventory/              # Items, categories, stock ledger, vendor purchase orders
│   ├── models/                 # Canonical Pydantic/dataclass schema definitions (18 modules)
│   ├── notifications/          # Multi-channel notification engine (Email, SMS, Push, WhatsApp)
│   ├── portals/                # Web portal services (FeeAdmin, Parent, Student, Teacher)
│   ├── privacy/                # 4-tier parent visibility rules, PII masking
│   ├── rag/                    # Scoped vector search, BM25, parser, chunker, golden tests
│   ├── rbac/                   # RBAC matrix, permission checking, role normalization
│   ├── recovery/               # Standardized failure classification and commit rollback
│   ├── security/               # Security auditor, prompt injection, path traversal, CSRF/XSS
│   ├── sis/                    # Student Information System profiles, emergency contacts, guardians
│   ├── slr/                    # Student Learning Records and concept mastery snapshots
│   ├── sync/                   # Bi-directional sync engine, outbox, conflict management
│   ├── timetable/              # Period slots, teacher/room conflict detection, substitutions
│   ├── tools/                  # Dynamic pedagogical tools (math, chemistry, code sandboxes)
│   ├── transport/              # Vehicle fleet, bus routes, pickup stops, transport fees
│   └── tutor/                  # 16-step GenericTutorOrchestrator turn execution engine
├── core/                       # Shared platform logic, inference abstractions, agent SDK
├── data/                       # Seed curricula, RAG documents, and sample assets
├── docs/                       # Architectural specifications, QA logs, and phase documentation
│   ├── erp_agent/              # Active transformation contract workspace (Phases 00–18)
│   ├── qa/                     # Historical QA logs and progressive evidence
│   └── release/                # Release baseline and readiness registers
├── migrations/                 # 16 SQL DDL migrations with reversible down-scripts (001–016)
├── packaging/                  # PyInstaller specifications and packaging assets
├── scripts/                    # Database migrations, seed scripts, ops utilities
├── tests/                      # Automated test suite (1,775+ tests collected)
└── training/                   # SLM fine-tuning and pedagogical evaluator scripts
```

### Primary Entrypoints & Commands
- **FastAPI Platform Server:** `python server.py` or `uvicorn central_platform.api.app:create_app --factory --port 8000`
- **Desktop Application:** `python -m app.main` or `run_gayatri.bat` / `launch.bat`
- **Database Migration CLI:** `python scripts/migrate_db.py [status|up|down] --db-path gayatri_local.db`
- **Deployment Validator CLI:** `python -c "from central_platform.deployment.validator import DeploymentValidator; print(DeploymentValidator().run_full_validation().summary)"`
- **Automated Regression Suite:** `pytest -v -m "not gui"`

---

## 2. API Route Registry & Endpoints

All modern endpoints are mounted under `/api/v1/*` within `central_platform/api/app.py`, alongside backward-compatible legacy `/api/*` endpoints and HTML portal dashboards:

| Prefix | Router Module | Tags / Domain | Primary Responsibilities |
|---|---|---|---|
| `/api/v1/auth` | `central_platform.api.routes.auth` | Authentication | Login, token issuance, refresh, DB-backed revocation, logout |
| `/api/v1/users` | `central_platform.api.routes.users` | Users & RBAC | User lifecycle, role assignments, profile retrieval |
| `/api/v1/organizations`| `central_platform.api.routes.organizations`| Multi-Tenant | Institution registration, settings, branch metadata |
| `/api/v1/admissions` | `central_platform.api.routes.admissions` | Admissions CRM | Inquiries, duplicate search, intake applications, offers |
| `/api/v1/sis` | `central_platform.api.routes.sis` | Student SIS | Legal student profiles, enrollments, guardian linkages |
| `/api/v1/academic` | `central_platform.api.routes.academic` | Academic Mgmt | Academic years, terms, classes, sections, subject offerings |
| `/api/v1/attendance` | `central_platform.api.routes.attendance` | Attendance | Daily registers, bulk marking, excuses, audited corrections |
| `/api/v1/timetable` | `central_platform.api.routes.timetable` | Timetable | Periods, slots, clash prevention, teacher substitutions |
| `/api/v1/examinations`| `central_platform.api.routes.examinations` | Exams | Exam series, schedules, marks entry, status lock |
| `/api/v1/grading` | `central_platform.api.routes.grading` | Grading & Cards | Grading scales, term results, report card generation |
| `/api/v1/finance` | `central_platform.api.routes.finance` | Finance Core | Orders, webhook capture, append-only ledger, reconciliation |
| `/api/v1/fees` | `central_platform.api.routes.fees` | Fee Billing | Fee structures, student accounts, invoices, concessions |
| `/api/v1/hr` | `central_platform.api.routes.admin` / `hr` | HR & Payroll | Staff directory, leave requests, attendance, payroll runs |
| `/api/v1/transport` | `central_platform.api.routes.transport` | Facilities | Fleet vehicles, route stops, student assignments, fees |
| `/api/v1/hostel` | `central_platform.api.routes.campus` | Facilities | Hostel blocks, rooms, bed allocations |
| `/api/v1/inventory` | `central_platform.api.routes.campus` | Facilities | Item catalog, stock movements, vendor purchase orders |
| `/api/v1/campus` | `central_platform.api.routes.campus` | Facilities | Visitor check-in, time-bound gate passes, certificates |
| `/api/v1/cms` | `central_platform.api.routes.cms` | Public CMS | Public pages, news/announcements, draft-publish lifecycle |
| `/api/v1/communications`| `central_platform.api.routes.communications`| Messaging | Broadcast announcements, targeting, message outbox |
| `/api/v1/courses` | `central_platform.api.routes.courses` | LMS & Courses | Course definitions, versions, offerings, enrollments |
| `/api/v1/curricula` | `central_platform.api.routes.curricula` | Curriculum | Board trees, concept DAGs, prerequisite graphs |
| `/api/v1/rag` | `central_platform.api.routes.rag` | Scoped RAG | Document upload, chunking, vector/lexical retrieval |
| `/api/v1/assessments` | `central_platform.api.routes.assessments` | Assessment Engine| Question bank, quiz generation, automated scoring |
| `/api/v1/tutor` | `central_platform.api.routes.tutor` | Adaptive AI Tutor| 16-step pedagogical turn execution, state commits |
| `/api/v1/sync` | `central_platform.api.routes.sync` | Offline Sync | Client sync push/pull, idempotency operations |
| `/api/v1/edge-sync` | `central_platform.api.routes.edge_sync` | Edge Daemon | Edge node heartbeat, chunk sync, telemetry |
| `/api/v1/analytics` | `central_platform.api.routes.analytics` | Analytics | Student mastery, session history, cohort heatmaps |
| `/api/v1/health` | `central_platform.api.routes.ops_gate` | Ops & Health | `/healthz`, `/livez`, `/readyz`, `/deep` health probes |

---

## 3. Identity, Auth & RBAC Architecture

1. **Authentication:**
   - Stateless JWT tokens signed with high-entropy HMAC-SHA256 (`JWT_SECRET`).
   - Token revocation is enforced using a durable database table `revoked_tokens` (`token_hash`, `revoked_at`, `expires_at`), verified across multiple worker threads and processes via `TokenRevocationService`.
2. **Role Hierarchy:**
   - Normalized 6 roles: `SUPER_ADMIN` > `ORG_ADMIN` > `TEACHER` > `STUDENT` > `PARENT` > `GUEST`.
   - Granular permissions mapped in `central_platform/rbac/engine.py`.
3. **Tenant & Branch Scoping:**
   - Every request is resolved against the authenticated caller (`current_user.org_id`).
   - Headers like `X-Branch-ID` or `organization_id` queries are never trusted blindly; they are strictly validated server-side to guarantee the principal has administrative or member grants in that scope. Cross-tenant access fails closed with `403 Forbidden`.

---

## 4. Database Lifecycle & Schema Architecture

1. **Engine:** SQLite 3 in WAL (`Write-Ahead Logging`) mode, synchronous=NORMAL, foreign_keys=ON, busy_timeout=5000ms.
2. **Isolation & Concurrency:** Readers do not block writers, writers do not block readers. DAL utilizes connection pooling and explicit transaction context managers (`with db.transaction():`).
3. **Migrations:** Managed via `scripts/migrate_db.py` and recorded in `schema_migrations`:
   - `001_initial_schema.sql`: Core users, curricula, learning records.
   - `002_curriculum_abstraction.sql`: Curriculum board abstractions and metadata.
   - `003_fee_management_schema.sql`: Fee structures, plans, accounts, invoices, payments, receipts, discounts.
   - `004_course_domain_model.sql`: Subject-agnostic courses, versions, offerings, enrollments.
   - `005_knowledge_assets.sql`: RAG sources and chunks.
   - `006_scoped_rag_authorization.sql`: RAG tenant scoping and access rules.
   - `007_teacher_instruction_hierarchy.sql`: 5-tier teacher instruction cascade.
   - `008_sync_operations.sql`: Bi-directional client sync idempotency ledger.
   - `009_shared_identity_and_entitlements.sql`: Extended RBAC and entitlements.
   - `010_admissions_and_academic_calendar.sql`: Inquiries, admissions, calendar sessions.
   - `011_attendance_timetable_communications.sql`: Attendance registers, timetable periods/slots, substitutions, notices.
   - `012_examinations_grading_report_cards.sql`: Exam series, marks, grading scales, report cards.
   - `013_finance_payments_reconciliation.sql`: Orders, webhook logs, append-only financial ledger, reconciliation.
   - `014_full_erp_expansion.sql`: Campus visitors, gate passes, transport, hostel, inventory, certificates, CMS.
   - `015_offline_sync_edge_daemon.sql`: Edge node registration, sync outbox, telemetry.
   - `016_analytics_exports_diagnostics.sql`: Deep analytics, data export tracking, diagnostic logs.

---

## 5. Domain Ownership & Call Graphs

```text
[HTTP Client / Desktop WebEngine]
       │
       ▼
[FastAPI Middleware Pipeline] (RequestID -> SecurityHeaders -> StructuredLogging)
       │
       ▼
[API Route Handler] (e.g. central_platform/api/routes/finance.py)
       │
       ├─► [Auth & RBAC Dependency] (central_platform/auth/dependencies.py)
       │         └─► [Token Revocation Check] (central_platform/auth/tokens.py)
       │
       ├─► [Domain Service Layer] (e.g. central_platform/finance/service.py)
       │         │
       │         ├─► [Input Validation & Pydantic Models] (central_platform/models/finance.py)
       │         ├─► [Transactional Database DAL] (central_platform/db.py)
       │         └─► [Audit & Security Auditor] (central_platform/security/auditor.py)
       │
       └─► [Standardized Response / Error Envelope] (central_platform/api/middleware.py)
```

---

## 6. AI & RAG Subsystem Integration

1. **AI Gateway (`central_platform/ai/`):**
   - Routing modes: `LOCAL_ONLY` (default in air-gapped setups), `LOCAL_FIRST`, `CLOUD_PREFERRED`.
   - Local inference via `llama-cpp-python` loading quantized GGUF (`Qwen2.5-0.5B-Instruct`).
   - Hard kill-switch: `AI_KILL_SWITCH=true` immediately terminates neural calls and returns safe pedagogical explanations.
2. **Pedagogical Orchestration (`central_platform/tutor/orchestrator.py`):**
   - 16-step transactional turn pipeline. State mutation is staged in a scratchpad and committed atomically only upon validation success.
3. **Course-Scoped RAG (`central_platform/rag/`):**
   - Ingests documents per course version.
   - Hybrid retrieval combines dense vector embeddings and lexical BM25 matching.
   - Tenant-scoped query isolation prevents cross-course and cross-tenant knowledge leaks.
