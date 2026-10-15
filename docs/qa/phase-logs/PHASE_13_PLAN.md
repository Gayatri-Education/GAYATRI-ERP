# Phase 13 Plan: Performance, Concurrency, Reliability, and Recovery

**Phase:** PHASE-13  
**Status:** IN_PLANNING  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer  

---

## 1. Goal & Scope
Harden system concurrency, performance budgets, transaction atomicity under multithreaded load, duplicate race prevention, and automated failure recovery. Verify that parallel requests across authentication, course retrieval, event synchronization, and payment webhooks execute reliably without database deadlocks, race conditions, or unhandled lock timeouts. Ensure failure recovery policies cleanly classify faults and provide observable, retryable outcomes without duplicating financial state or corrupting learning records.

---

## 2. Invariants & Performance Targets
- **Concurrency & Deadlock Prevention**:
  - SQLite connections in `PlatformDatabase` must configure `timeout=30.0` and `PRAGMA busy_timeout = 30000;` alongside WAL journal mode (`PRAGMA journal_mode = WAL;`) and synchronous normal (`PRAGMA synchronous = NORMAL;`).
  - Concurrent multi-threaded reads and writes must execute without raising unhandled `sqlite3.OperationalError: database is locked`.
- **Payment & Webhook Race Condition Prevention**:
  - Concurrent identical webhook deliveries (`event_id` / `idempotency_key`) must deduplicate atomically. Exactly one payment order transitions to captured, and exactly one receipt is issued.
- **Latency Budgets & SLAs**:
  - Core metadata / health probes (`/healthz`, `/readyz`): p95 < 50ms.
  - Course catalog retrieval (`/api/v1/courses`): p95 < 150ms.
  - Token verification / me (`/api/v1/auth/me`): p95 < 50ms.
- **Reliability & Failure Recovery**:
  - `FailureRecoveryManager`: Structured failure classification across provider timeouts, model failures, network drops, and corrupted inputs.
  - Failures must produce safe user messages, actionable technical diagnostics, and explicit retryability flags without hanging or crashing the server process.

---

## 3. Implementation Plan
1. **Remediate `central_platform/db.py`**:
   - Set `timeout=30.0` in `sqlite3.connect` calls.
   - Execute `PRAGMA busy_timeout = 30000;` on new connections.
2. **Author Verification Suite (`tests/test_qa_phase13_performance_concurrency_recovery.py`)**:
   - Concurrent multithreaded database read/write stress test.
   - Concurrent payment webhook duplicate race prevention.
   - Concurrent user login and session handling.
   - Provider timeout and failure recovery classification in `FailureRecoveryManager`.
   - Latency SLA benchmarks for core endpoints.
3. **Execute targeted test suite, related concurrency/perf suites, and full non-GUI regression suite (`python -m pytest -q -m "not gui"`)**.
4. **Update logs, trackers, and commit**.
