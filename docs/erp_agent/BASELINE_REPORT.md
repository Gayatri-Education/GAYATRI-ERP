# Baseline Verification Report — GAYATRI-ERP

**Document:** `docs/erp_agent/BASELINE_REPORT.md`  
**Contract Reference:** [`../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Execution Phase:** Phase 00 — Discovery and Independent Baseline  
**Date of Audit:** 2026-10-15  
**Auditor / Agent:** Local AI Coding Assistant  

---

## 1. Environment & Runtime Baseline

| Parameter | Observed Value | Verification Command / Evidence |
|---|---|---|
| **Repository Remote** | `https://github.com/Gayatri-Education/GAYATRI-ERP` | `git remote -v` |
| **Current Branch** | `main` | `git status --short --branch` |
| **Commit SHA (HEAD)** | `8b24bb716bcfce558acd3dd4253c641774905ac6` | `git rev-parse HEAD` |
| **Working Tree Status** | Clean on tracked files; untracked roadmap & agent documentation files present (`ERP_TRANSFORMATION_DEVELOPMENT.md`, `README_INSERT.md`, `docs/erp_agent/`) | `git status --short` |
| **Host Operating System**| Windows 11 Enterprise (win32) | `python -c "import sys; print(sys.platform)"` |
| **Python Runtime** | `Python 3.12.10` | `python --version` |
| **Pytest Framework** | `pytest 7.4.4` (plugins: anyio, base-url, cov, flask, playwright, qt) | `pytest --version` |
| **Qt / GUI Binding** | `PySide6 6.11.1` (Qt runtime 6.11.1) | `pytest session header` |
| **Database Engine** | SQLite 3 with WAL journal mode (`gayatri_local.db`) | `python scripts/migrate_db.py status` |
| **Applied Migrations** | 16 migrations applied (001–016); Checksum integrity: VERIFIED | `python scripts/migrate_db.py status` |
| **Dependency Lock** | `requirements.lock` reconciled against `requirements.txt` | `python scripts/verify_dependency_lock.py` |

---

## 2. Compilation Hygiene & Preflight Checks

1. **Bytecode Compilation (`compileall`):**
   - Command: `python -m compileall -q app core central_platform tests scripts`
   - Exit Code: `0`
   - Result: 0 syntax or compilation errors across all platform packages.

2. **Dependency Lock Reconciliation:**
   - Command: `python scripts/verify_dependency_lock.py`
   - Exit Code: `0`
   - Result: `[OK] requirements.lock is valid, fully pinned, and reconciled against requirements.txt.`

3. **Database Migration Ledger Integrity:**
   - Command: `python scripts/migrate_db.py status --db-path gayatri_local.db`
   - Exit Code: `0`
   - Total Applied Migrations: 16 (from `001_initial_schema` through `016_analytics_exports_diagnostics`).
   - Checksum Integrity: `VERIFIED`.

---

## 3. Test Execution Baseline

All tests were executed against the authoritative environment without any modifications to production code:

| Test Suite / Scope | Command | Passed | Failed | Errors | Skipped | Runtime | Exit Code |
|---|---|---|---|---|---|---|---|
| **Architecture Guardrails** | `pytest -v tests/architecture` | 13 | 0 | 0 | 0 | 1.08s | 0 |
| **Focused Acceptance Sample** | `pytest tests/test_qa_phase14_e2e_product_acceptance.py tests/test_qa_phase16_final_audit_handover.py tests/test_server_live_sync.py tests/architecture` | 30 | 0 | 0 | 0 | 3.28s | 0 |
| **Full Headless Suite** | `pytest -q -m "not gui"` | **1,775** | **0** | **0** | **0** | **205.11s** | **0** |

---

## 4. Architectural & Scope Findings

1. **Multi-Tenant Foundation & RBAC:**
   - Multi-tenant organization boundaries and role normalizations (`SUPER_ADMIN`, `ORG_ADMIN`, `TEACHER`, `STUDENT`, `PARENT`, `GUEST`) are deeply embedded across the DAL and route dependencies.
   - Server-side scope derivation prevents header spoofing (`X-Branch-ID` cannot elevate privileges).

2. **Domain Service Coverage:**
   - Extensive institutional ERP domains are already instantiated and registered in `central_platform/`:
     - Admissions & CRM (`central_platform/admissions/service.py`)
     - Attendance & Timetable (`central_platform/attendance/service.py`, `central_platform/timetable/service.py`)
     - Examinations & Grading (`central_platform/examinations/service.py`, `central_platform/grading/service.py`)
     - Finance, Payments & Ledger (`central_platform/finance/service.py`, `central_platform/fees/service.py`)
     - HR & Payroll (`central_platform/hr/service.py`)
     - Campus Facilities, Transport & Hostel (`central_platform/campus/`, `central_platform/transport/`, `central_platform/hostel/`)
     - Communications & Public CMS (`central_platform/communications/`, `central_platform/campus/`)
     - Local SLM & Scoped RAG (`central_platform/ai/`, `central_platform/rag/`)

3. **Honest Limitations & Disclosures (Hardware / External Providers):**
   - Physical RFID hardware, biometric fingerprint/iris scanners, and vehicle GPS hardware require physical interfaces; software abstractions and local mock adapters function correctly in tests, but real physical hardware remains marked `BLOCKED`/`DEFER_WITH_REASON` for local environment testing.
   - Cloud messaging providers (WhatsApp Business API, external SMS gateways, live-streaming servers) require live API keys and network egress; offline outbox queuing is verified.

---

## 5. Phase 00 Baseline Sign-Off

The baseline has been independently reproduced and validated. The repository is healthy, consistent, and passes all 1,775 automated tests.
Phase 00 exit criteria are fully satisfied.
