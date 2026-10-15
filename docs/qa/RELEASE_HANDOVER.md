# GAYATRI-ERP Production Release Handover & Operations Guide

**Version:** 3.0.1  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer & Gayatri Core Engineering  
**Canonical Tracker:** [`docs/qa/PROGRESS_TRACKER.yaml`](PROGRESS_TRACKER.yaml)  
**Issue Register:** [`docs/qa/ISSUE_REGISTER.md`](ISSUE_REGISTER.md)  
**Status:** PRODUCTION_READY / APPROVED  

---

## 1. Executive Summary & Release Status
This document constitutes the authoritative release handover for **GAYATRI-ERP**, an offline-first, curriculum-free adaptive AI tutoring and educational ERP platform for CBSE/NCERT Classes 9–12.

Following a rigorous 17-phase engineering and QA remediation program (`PHASE-00` through `PHASE-16`) executed under `GAYATRI_ERP_DEVELOPMENT_GUIDE.md`:
- **100% of the initial QA review seed findings (ERP-001 through ERP-022) are permanently resolved and verified (`FIXED_VERIFIED`)** with zero open P0 or P1 security/data-loss vulnerabilities.
- **Over 1,765 automated non-GUI regression tests** pass cleanly with zero skipped tests, zero weakened assertions, and zero bypassed production gates.
- Complete role-based journeys (Student, Teacher, School Admin, Parent, Auditor) have been verified end-to-end with real SQLite persistence.

---

## 2. Architectural Blueprint & Core Subsystems

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Desktop Shell (PySide6)                         │
│   Student Portal │ Teacher Portal │ Parent Portal │ Fee Admin │ Admin   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ QWebChannel / Bridge
┌───────────────────────────────────▼────────────────────────────────────┐
│                       Central Platform (FastAPI)                       │
│   Auth & RBAC │ Students │ Teachers │ Courses │ Sessions │ RAG         │
│   Assessments │ Analytics │ Notifications │ Sync │ Fees │ Payments     │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
┌──────────────────▼─────────────┐     ┌─────────────▼───────────────────┐
│     SQLite WAL Persistence     │     │      AI Execution Gateway       │
│  50+ tables, 8 DDL migrations  │     │   Local SLM (Qwen2.5-0.5B GGUF) │
│  busy_timeout=30s, timeout=30s │     │   LocalFirstRouter + Fallback   │
└────────────────────────────────┘     └─────────────────────────────────┘
```

### Core Subsystem Responsibilities:
1. **Authentication & Authorization (`central_platform/auth/`)**:
   - Zero-trust JWT tokens with JTI-based revocation stored in `revoked_tokens` table.
   - Strict tenant boundary checking and role-based access control (RBAC).
2. **Database & Data Layer (`central_platform/db.py`, `migrations/`)**:
   - SQLite with Write-Ahead Logging (`PRAGMA journal_mode = WAL;`).
   - Concurrency resilience: `PRAGMA busy_timeout = 30000;` and connection `timeout=30.0`.
   - 8 reversible SQL migrations (`001_initial_schema.sql` through `008_course_versions.sql`).
3. **Tutoring & Adaptation Engine (`central_platform/tutor/`, `core/tutor/`)**:
   - Socratic dialog orchestration with grounded curriculum RAG.
   - Fail-closed deterministic evaluation: offline/degraded states preserve mastery with zero fake-credit inflation.
4. **Finance & Invoicing Engine (`central_platform/finance/`, `central_platform/fees/`)**:
   - Double-entry financial ledger (`financial_ledger_entries`).
   - Constant-time HMAC signature verification for Razorpay/UPI payment webhooks.
   - Atomic database transactions ensuring idempotency and duplicate deduplication.
5. **Observability & Health Probes (`central_platform/health/`)**:
   - Live non-mocked `/healthz`, `/readyz`, and `/livez` probes.
   - `FailureRecoveryManager` providing automated degraded fallback policies and structured diagnostics.

---

## 3. Configuration & Environment Variables

| Variable | Default (Dev) | Production Requirement | Purpose |
|---|---|---|---|
| `GAYATRI_ENV` | `development` | `production` | Enables strict production gates and disables debug defaults. |
| `GAYATRI_DB_PATH` | `gayatri_local.db` | Absolute path (e.g. `/var/data/gayatri.db`) | Path to canonical SQLite database file. |
| `JWT_SECRET_KEY` | None (ephemeral) | Minimum 32-byte cryptographically random string | Signing key for authentication tokens. |
| `PAYMENT_WEBHOOK_SECRET` | `rzp_secret_mock` | Verified merchant secret from payment gateway | HMAC secret for payment webhook signature validation. |
| `GAYATRI_LOCAL_MODEL_PATH` | `models/qwen2.5...` | Path to verified `.gguf` weights | Local SLM model weights for offline inference. |
| `OPENAI_API_KEY` | None | Optional cloud key | Optional upstream cloud model key. |
| `ANTHROPIC_API_KEY` | None | Optional cloud key | Optional upstream cloud model key. |
| `GEMINI_API_KEY` | None | Optional cloud key | Optional upstream cloud model key. |

---

## 4. Deployment, Installation & Startup Guide

### Prerequisites
- Python 3.12+ 64-bit
- Git
- Modern OS: Windows 10/11, Ubuntu 22.04+, or macOS 13+

### Step-by-Step Installation
```bash
# 1. Clone the repository
git clone https://github.com/Gayatri-Education/GAYATRI-ERP.git
cd Gayatri-ERP

# 2. Create virtual environment and install dependencies
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# 3. Apply database migrations
python scripts/migrate_db.py up --db-path gayatri_local.db

# 4. Start the platform
# For API Server only:
python -m uvicorn central_platform.api.server:app --host 0.0.0.0 --port 8000

# For Desktop Application:
python -m app.main
```

---

## 5. Database Migrations & Reversibility
- **Migration Runner:** `scripts/migrate_db.py`
- **Schema Directory:** `migrations/`
- **Applied Versions:** `001` through `008`.
- **Upgrade:** `python scripts/migrate_db.py up --db-path <path>`
- **Rollback:** `python scripts/migrate_db.py down --target 007 --db-path <path>`
- **Integrity Verification:** Tested automatically in `tests/architecture/test_migration_integrity.py`.

---

## 6. Backup, Restore, and Disaster Recovery Procedures

### SQLite Online Backup
Because the database runs in WAL mode, backups can be performed while the application is actively serving requests without locking out readers or writers:
```bash
# Recommended online backup using sqlite3 CLI
sqlite3 gayatri_local.db ".backup backup/gayatri_backup_$(date +%Y%m%d_%H%M%S).db"

# Or using Python SQLite API
python -c "
import sqlite3, shutil, datetime
src = sqlite3.connect('gayatri_local.db')
dst = sqlite3.connect(f'backup/gayatri_{datetime.datetime.now().strftime(\"%Y%m%d_%H%M%S\")}.db')
with dst:
    src.backup(dst)
dst.close()
src.close()
print('Backup complete.')
"
```

### Restore Procedure
1. Stop the application server (`uvicorn` or desktop process).
2. Archive the existing database file: `mv gayatri_local.db gayatri_local.corrupt.db`.
3. Copy the verified backup to the canonical path: `cp backup/gayatri_backup_YYYYMMDD.db gayatri_local.db`.
4. Run migrations check: `python scripts/migrate_db.py up --db-path gayatri_local.db`.
5. Restart application services and verify `/healthz` returns `status: ONLINE`.

---

## 7. Monitoring, Health Probes & Incident Response

### Endpoints
- **Liveness Probe:** `GET /healthz` (returns HTTP 200 with overall platform and component statuses).
- **Readiness Probe:** `GET /readyz` (returns HTTP 200 only when database connectivity and critical storage are verified).

### Incident Response Runbook
1. **Database Lock Contention**:
   - Symptoms: Latency spikes or `database is locked` warnings in logs.
   - Action: Connections configure `busy_timeout = 30000ms`. Verify no long-running transactions hold write locks across external HTTP calls.
2. **Payment Webhook Verification Failures**:
   - Symptoms: Webhook returns HTTP 400 with signature verification failure.
   - Action: Confirm `PAYMENT_WEBHOOK_SECRET` matches merchant portal. Invariant: Unverified webhooks NEVER mutate financial state.
3. **Local AI Model Failure**:
   - Symptoms: SLM process fails to load weights or returns malformed response.
   - Action: `FailureRecoveryManager` automatically routes to fallback deterministic grader or syllabus context; student mastery is preserved without credit inflation.

---

## 8. Resolution Audit of Initial Seed Findings (ERP-001 through ERP-022)

All 22 initial findings from `GAYATRI_ERP_DEVELOPMENT_GUIDE.md` Section 5 have been systematically audited, remediated, verified with targeted tests, and certified across the full non-GUI regression suite:

| ID | Finding Description | Severity | First Phase | Verified Status | Evidence |
|---|---|---|---|---|---|
| **ERP-001** | Payment webhook signature verification trust boundary | P0 | 03 | **FIXED_VERIFIED** | HMAC constant-time verification; unverified calls rejected. |
| **ERP-002** | Payment/order/ledger/event atomicity & idempotency | P0 | 02–03 | **FIXED_VERIFIED** | Atomic transactions, duplicate delivery deduplication. |
| **ERP-003** | Token revocation persistence fail-open risk | P1 | 01 | **FIXED_VERIFIED** | `DatabaseRevocationStore` with strict DB error fail-closed semantics. |
| **ERP-004** | Demo token & synthetic identity production exposure | P1 | 01 | **FIXED_VERIFIED** | Blocked in production; requires verified persistent users. |
| **ERP-005** | Independent DB factories / stale module-global services | P1 | 02 | **FIXED_VERIFIED** | Dependency injection with scoped DB connections. |
| **ERP-006** | Health endpoint reporting fabricated state | P1/P2 | 10 | **FIXED_VERIFIED** | Live DB probe (`SELECT 1`), honest component health reporting. |
| **ERP-007** | Billing generation UI toast-only | P1/P2 | 05 | **FIXED_VERIFIED** | End-to-end fee generation wired to persistent backend. |
| **ERP-008** | Outstanding report export toast-only | P2 | 05 | **FIXED_VERIFIED** | Persistent export service with authorization and row limits. |
| **ERP-009** | Receipt print without persisted receipt verification | P1/P2 | 03, 05 | **FIXED_VERIFIED** | Verified persisted receipt lookup before generation. |
| **ERP-010** | Student review action toast-only | P1/P2 | 06 | **FIXED_VERIFIED** | Spaced review scheduler with durable SLR persistence. |
| **ERP-011** | Teacher Copilot action toast-only | P1/P2 | 05 | **FIXED_VERIFIED** | Real backend endpoint integration and error handling. |
| **ERP-012** | AI provider routes lacking authorization | P1 | 01, 04 | **FIXED_VERIFIED** | Strict RBAC (`ADMIN` / `SUPERADMIN`) and tenant scoping. |
| **ERP-013** | AI failure represented as HTTP 200 | P1/P2 | 04, 11 | **FIXED_VERIFIED** | Structured error responses with truthful HTTP 502/503. |
| **ERP-014** | Unknown provider silently defaulting to mock | P2 | 04 | **FIXED_VERIFIED** | Strict enum validation rejecting unknown providers with 422. |
| **ERP-015** | Legacy API endpoints bypassing auth/persistence | P1 | 01, 09 | **FIXED_VERIFIED** | All routes mounted under canonical security middleware. |
| **ERP-016** | Assessment bank serving sample questions in empty state | P1/P2 | 07 | **FIXED_VERIFIED** | Strict empty-bank handling without fabricated questions. |
| **ERP-017** | Blocked tutor turn looking like successful turn | P2 | 08 | **FIXED_VERIFIED** | Explicit status `BLOCKED` with zero mastery mutation. |
| **ERP-018** | Dynamic innerHTML / inline handler XSS risk | P2 | 05, 12 | **FIXED_VERIFIED** | Contextual HTML escaping and CSP security headers. |
| **ERP-019** | Optional/missing bearer token edge cases | P1 | 01 | **FIXED_VERIFIED** | Missing/malformed headers strictly rejected with 401. |
| **ERP-020** | Broad exception handlers masking failures | P1/P2 | 10–12 | **FIXED_VERIFIED** | Truthful error logs and sanitized user messages. |
| **ERP-021** | Test fixtures mutating developer database | P1/P2 | 00, 02 | **FIXED_VERIFIED** | Isolated `tmp_path` fixtures for all test runs. |
| **ERP-022** | Critical features lack restart/negative/E2E evidence | P1 | 00, 14 | **FIXED_VERIFIED** | Complete multi-step lifecycle journeys with DB restart. |

---

## 9. Phase-by-Phase Execution Summary (PHASE-00 through PHASE-16)

- **PHASE-00:** Repository baseline, reproducibility inventory, and test environment verification.
- **PHASE-01:** Authentication, role authorization, tenant isolation, and token revocation.
- **PHASE-02:** Database lifecycle, transaction boundaries, and foreign key enforcement.
- **PHASE-03:** Financial integrity, double-entry ledger, and payment webhook verification.
- **PHASE-04:** AI gateway contracts, error reporting, and provider enum validation.
- **PHASE-05:** Portal integration, UI bridge wiring, and toast-only elimination.
- **PHASE-06:** Student adaptive learning, spaced review, and durable SLR state.
- **PHASE-07:** Assessment bank integrity, deterministic grading, and honest empty-state handling.
- **PHASE-08:** Tutor orchestration, RAG grounding, and blocked-turn semantics.
- **PHASE-09:** Attendance, academic workflows, notifications, and offline sync outbox.
- **PHASE-10:** Health, readiness, observability probes, and failure reporting.
- **PHASE-11:** API contracts, input validation schemas, rate limits, and idempotency.
- **PHASE-12:** Privacy, secrets containment, XSS neutralization, and security headers.
- **PHASE-13:** Performance budgets, WAL concurrency, lock timeouts, and failure recovery.
- **PHASE-14:** End-to-end product acceptance across role-based journeys and restart durability.
- **PHASE-15:** Repository cleanup, candidate file classification, and documentation consolidation.
- **PHASE-16:** Final audit, operational release handover, and maintenance sign-off.

---

## 10. Maintenance & Rollback Plan
- **Rollback Decision**: In the event of a critical deployment failure, revert database schema to the prior verified baseline using `python scripts/migrate_db.py down` and restore application binary/code to the prior tagged release commit.
- **Release Sign-off**: All functional and non-functional requirements of `GAYATRI_ERP_DEVELOPMENT_GUIDE.md` are satisfied. Platform is certified **PRODUCTION_READY**.
