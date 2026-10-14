# Phase 06 Plan: Session Persistence, Write Acknowledgements, Data Integrity & Migrations

**Phase Goal:** Remediate audit findings `GQA-007` (test isolation/data protection) and `GQA-011` (async session writer swallowed worker exceptions) by establishing reliable write acknowledgements, durable queue guarantees, bounded retry for transient locks, graceful shutdown with failure exposure, connection threading safety, and robust schema migration validation.

---

## 1. Architectural Scope & Target Findings

### GQA-011: Async Session Writer Swallows Worker Exceptions
- **Problem:** `core/session.py:_writer_loop()` caught all exceptions from write operations and called `self._write_queue.task_done()` after logging. Calling `store.flush()` (`self._write_queue.join()`) returned without error even when writes failed and data was lost. Furthermore, `save_session` provided no acknowledgement token, future, or error reporting mechanism.
- **Remediation:**
  1. Introduce `WriteAcknowledgement` and `WriteStatus` (`PENDING`, `DURABLE`, `FAILED`).
  2. `save_session(..., sync=False)` returns a `WriteAcknowledgement` holding a `concurrent.futures.Future`.
  3. The background writer executes write operations with bounded retry (up to 3 attempts with exponential backoff on `sqlite3.OperationalError` with `busy` or `locked`).
  4. Terminal exceptions increment `store.failed_write_count`, record structured error metadata (operation ID, session ID, error class without private conversation content), and set the future exception.
  5. `store.flush(raise_on_failure=True)` raises a `PersistenceFailureError` if any write failed during the flush cycle.
  6. Shutdown lifecycle: `store.shutdown()` marks the store as terminating (`_is_shutting_down = True`), rejects subsequent enqueue attempts with `RuntimeError`, drains pending queue items, checks for terminal errors, joins the writer thread, and closes the connection cleanly.
  7. Threading safety: protect all connection operations with the store's re-entrant lock (`_lock`), ensuring the background writer thread and caller read/write threads never create C-level concurrency collisions.

### GQA-007 / Authoritative Database Scoping & Migration Verification
- **Problem:** Ensure services write to the authoritative database for their mode, prevent divergent SQLite databases, and ensure schema migrations handle initial/clean states, forward migrations, and checksum verification.
- **Remediation:**
  1. Authoritative store resolution: Desktop/offline uses `core.config.DB_PATH` or `GAYATRI_DB_PATH`; Platform services use `central_platform.db.PlatformDatabase`.
  2. Verify migration suite in `scripts/migrate_db.py`: clean database initialization, forward migration idempotency, checksum tampering detection, and rollback support.
  3. Verify idempotency in learning event ingestion and mastery state projection: duplicate learning-event IDs never inflate scores or mastery.

---

## 2. Implementation Steps

1. **Write Acknowledgement & Safe Writer Loop (`core/session.py`):**
   - Define `WriteStatus` (`PENDING`, `DURABLE`, `FAILED`) and `WriteAcknowledgement`.
   - Update `SessionStore.__init__`:
     - Add `self.failed_write_count: int = 0`
     - Add `self._last_exception: Optional[Exception] = None`
     - Add `self._is_shutting_down: bool = False`
   - Update `SessionStore._enqueue_write`:
     - Raise `RuntimeError` if store is shutting down.
     - Return `WriteAcknowledgement` with attached `concurrent.futures.Future`.
   - Update `SessionStore._writer_loop`:
     - Implement bounded retry (up to 3 retries with backoff) for transient SQLite busy/locked errors.
     - On success: set `future.set_result(True)`.
     - On failure: set `future.set_exception(err)`, increment `self.failed_write_count`, store `self._last_exception`, log structured error metadata without sensitive student text.
   - Update `SessionStore.flush(raise_on_failure: bool = True)`:
     - Join queue; if `raise_on_failure` and `self._last_exception` is set, raise `PersistenceFailureError`.
   - Update `SessionStore.shutdown()`:
     - Reject new writes, drain queue, raise/log if terminal failures, join writer thread, close connection.

2. **Fault Injection & Edge Case Testing (`tests/test_qa_phase06_session_persistence_migrations.py`):**
   - Test async queue write acknowledgement (`is_pending`, `is_durable`, `wait()`).
   - Test fault injection: injected writer exception triggers `is_durable == False`, `ack.wait()` raises exception, and `flush(raise_on_failure=True)` raises `PersistenceFailureError`.
   - Test transient lock retry: locked DB retries and recovers when lock is released.
   - Test rejection of enqueue writes after `store.shutdown()` begins.
   - Test graceful shutdown persists all queued writes cleanly across restarts.
   - Test database migration runner: empty DB setup, incremental migrations, checksum mismatch detection, and rollback.
   - Test event ingestion idempotency: duplicate event IDs do not duplicate records or mutate mastery twice.

3. **Verification & Master Regression:**
   - Run focused Phase 06 test suite.
   - Run full repository regression (`pytest -q --tb=short`).
   - Record decisions in `docs/qa_agent/decisions/DECISION_LOG.md` (DEC-018).
   - Produce `docs/qa_agent/reports/PHASE_06_REPORT.md`.
   - Update `docs/qa_agent/MASTER_PROGRESS.md` marking Phase 06 PASSED.
