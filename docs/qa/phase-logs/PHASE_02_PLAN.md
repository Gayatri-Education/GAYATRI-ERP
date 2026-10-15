# Phase 02 Plan: Database Lifecycle, Dependency Injection, Transactions, and Durable State

**Phase:** PHASE-02  
**Status:** IN_PROGRESS  
**Date:** 2026-10-15  
**Target Findings:** ERP-002, ERP-005, ERP-021  

---

## 1. Problem Analysis & Objectives

### 1.1 ERP-005: Fragmented Database Dependency Injection & Lifecycle
- **Finding:** 15 API route modules (`academic.py`, `admissions.py`, `attendance.py`, `cms.py`, `communications.py`, `edge_sync.py`, `examinations.py`, `finance.py`, `grading.py`, `identity.py`, `institutional_analytics.py`, `reports.py`, `sis.py`, `timetable.py`, `transport.py`) each redefine their own independent `def get_db() -> PlatformDatabase: return PlatformDatabase()`.
- **Consequence:** 
  1. FastAPI dependency injection overrides (`app.dependency_overrides[get_db]`) fail to intercept these routes because FastAPI matches dependencies by function object identity.
  2. Each HTTP request instantiates a new `PlatformDatabase` instance and re-runs `_init_db()`.
  3. Tests using `:memory:` or temporary database paths cannot share state with these routes.
- **Remediation:** Harmonize all route modules to import and use the canonical `get_db` from `central_platform.auth.dependencies`. In `central_platform/api/routes/students.py`, replace module-global static `PlatformDatabase()` instantiation with dynamic delegation to canonical `get_db()`.

### 1.2 ERP-002: Financial Mutation Atomicity & Transaction Integrity
- **Finding:** In `central_platform/finance/service.py`, `process_payment_webhook` performs multi-table mutations across several independent connection contexts:
  - Step 1: Inserts `payments` and `receipts`, updates `invoices`, updates `payment_orders`.
  - Step 2: Calls `post_ledger_entry` in a separate connection.
  - Step 3: Inserts `payment_webhook_events` in another separate connection.
- **Consequence:** A failure in ledger entry posting or webhook deduplication leaves orphan payments and receipts committed while the financial ledger and webhook deduplication records are missing.
- **Remediation:** Wrap the entire mutation block in `with self.db.transaction():` using `PlatformDatabase`'s transactional context manager so that any exception triggers an immediate rollback of all database writes, ensuring 100% atomicity.

### 1.3 ERP-021: Developer Database Isolation
- **Finding:** Ensure that developer/production databases (`gayatri_local.db`) are strictly protected from mutation during automated test execution.
- **Remediation:** Confirm and verify that all test suites execute against temporary/isolated databases (`tmp_path`) and that root `gayatri_local.db` remains pristine.

---

## 2. Implementation Steps
1. **Targeted Reproduction Suite:**
   - Create `tests/test_qa_phase02_db_lifecycle_transactions.py` asserting:
     - FastAPI `app.dependency_overrides[get_db]` successfully overrides the database for routes across the platform (`/finance`, `/identity`, `/academic`, etc.).
     - Webhook payment processing rolls back completely on ledger/connection failure, leaving zero partial payment or receipt state.
     - Webhook deduplication idempotency operates correctly.
     - Root `gayatri_local.db` is not modified by test operations.
2. **Harmonize `get_db` Across All Route Modules:**
   - Update `academic.py`, `admissions.py`, `attendance.py`, `cms.py`, `communications.py`, `edge_sync.py`, `examinations.py`, `finance.py`, `grading.py`, `identity.py`, `institutional_analytics.py`, `reports.py`, `sis.py`, `timetable.py`, `transport.py` to import `get_db` from `central_platform.auth.dependencies`.
   - Update `students.py` to use `get_db()` rather than static module-level `PlatformDatabase()`.
3. **Wrap Financial Operations in Explicit Transactions:**
   - In `central_platform/finance/service.py`, wrap `process_payment_webhook` inside `with self.db.transaction():`.
4. **Run Tests & Verify:**
   - Run `tests/test_qa_phase02_db_lifecycle_transactions.py`.
   - Run all finance and academic regression suites.
   - Run full regression test suite (`pytest -q -m "not gui"`).
5. **Update Canonical Logs & Tracker:**
   - Write `docs/qa/phase-logs/PHASE_02_LOG.md`.
   - Update `docs/qa/PROGRESS_TRACKER.yaml` and mirror to root.
   - Update `docs/qa/ISSUE_REGISTER.md` and mirror to root.
