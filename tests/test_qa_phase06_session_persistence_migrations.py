"""Tests for QA Phase 06: Session Persistence, Write Acknowledgements, Data Integrity & Migrations.

Verifies:
- GQA-011: Async session writer exposes write success/failure, provides WriteAcknowledgement,
  retries transient locks, tracks failed writes, and fails closed during flush/shutdown.
- GQA-007: Safe database migration runner, empty DB bootstrap, checksum validation, and test isolation.
- Idempotency of learning event submissions and state projections.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from core.conversation import Conversation
from core.session import (
    PersistenceFailureError,
    SessionStore,
    WriteAcknowledgement,
    WriteStatus,
)
from central_platform.db import PlatformDatabase
from central_platform.events.models import LearningEventIngest
from central_platform.events.store import LearningEventStore
from central_platform.events.types import LearningEventType
from scripts.migrate_db import (
    MigrationChecksumMismatchError,
    get_applied_migrations,
    run_all_migrations,
)


# ── 1. GQA-011: Write Acknowledgement & Lifecycle ──────────────────────────

def test_write_acknowledgement_lifecycle(tmp_path: Path):
    """Verify WriteAcknowledgement reports PENDING then DURABLE upon background commit."""
    db_file = tmp_path / "test_ack_lifecycle.db"
    store = SessionStore(db_file)
    try:
        conv = Conversation(session_id="sess_ack_1", user_id="student_1")
        conv.add("user", "What is Le Chatelier's principle?")
        conv.add("assistant", "It describes system response to equilibrium disturbance.")

        ack = store.save_session("sess_ack_1", conv, sync=False)
        assert isinstance(ack, WriteAcknowledgement)
        assert ack.operation_id.startswith("op-")
        assert ack.session_id == "sess_ack_1"

        # Wait for durability
        completed = ack.wait(timeout=2.0)
        assert completed is True
        assert ack.is_durable is True
        assert ack.is_pending is False
        assert ack.is_failed is False
        assert ack.status == WriteStatus.DURABLE
        assert ack.exception() is None

        # Confirm data is physically on disk
        loaded = store.load_session("sess_ack_1")
        assert len(loaded) == 2
        assert loaded[0]["content"] == "What is Le Chatelier's principle?"
    finally:
        store.shutdown()


def test_injected_worker_thread_exception_failure_detection(tmp_path: Path):
    """GQA-011: Verify worker-thread exceptions are exposed via ack, fail_count, and flush."""
    db_file = tmp_path / "test_injected_failure.db"
    store = SessionStore(db_file)
    try:
        def failing_write(*args, **kwargs):
            raise sqlite3.OperationalError("Simulated disk I/O / corruption failure")

        # Directly enqueue a failing write task
        ack = store._enqueue_write(failing_write, "sess_fail_1")
        assert ack.is_pending is True

        # Flush must raise PersistenceFailureError rather than quietly swallowing the failure
        with pytest.raises(PersistenceFailureError, match="Asynchronous DB write failed"):
            store.flush(raise_on_failure=True)

        assert ack.is_failed is True
        assert ack.is_durable is False
        assert ack.status == WriteStatus.FAILED
        assert store.failed_write_count >= 1

        # ack.wait() must re-raise the underlying exception
        with pytest.raises(sqlite3.OperationalError, match="Simulated disk I/O"):
            ack.wait(timeout=1.0)
    finally:
        store.shutdown(raise_on_failure=False)


def test_bounded_retry_on_transient_sqlite_lock(tmp_path: Path):
    """Verify writer loop automatically retries transient SQLite lock errors before succeeding."""
    db_file = tmp_path / "test_retry_lock.db"
    store = SessionStore(db_file)
    try:
        attempts = 0

        def flaky_write(session_id, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                # Simulate temporary busy/lock
                raise sqlite3.OperationalError("database is locked")
            # Succeed on 3rd attempt
            store._save_session_internal(session_id, "Flaky Chat", [], None)

        ack = store._enqueue_write(flaky_write, "sess_flaky_1")
        ack.wait(timeout=3.0)

        assert ack.is_durable is True
        assert attempts == 3
        assert store.failed_write_count == 0  # Recovered via retry, not counted as terminal failure
    finally:
        store.shutdown()


def test_enqueue_after_shutdown_rejected(tmp_path: Path):
    """Verify that attempting to enqueue writes after shutdown raises RuntimeError."""
    db_file = tmp_path / "test_shutdown_reject.db"
    store = SessionStore(db_file)
    conv = Conversation(session_id="sess_pre_shut")
    conv.add("user", "Hello")
    store.save_session("sess_pre_shut", conv)
    store.shutdown()

    # Attempting to enqueue write post-shutdown must fail fast
    conv2 = Conversation(session_id="sess_post_shut")
    with pytest.raises(RuntimeError, match="Cannot enqueue writes after SessionStore shutdown has started"):
        store.save_session("sess_post_shut", conv2)


def test_graceful_shutdown_drains_all_queued_writes(tmp_path: Path):
    """Verify shutdown commits all buffered async writes across a clean restart."""
    db_file = tmp_path / "test_graceful_drain.db"
    store = SessionStore(db_file)

    for i in range(8):
        c = Conversation(session_id=f"drain_sess_{i}", user_id="drain_user")
        c.add("user", f"Message {i}")
        store.save_session(f"drain_sess_{i}", c)

    # Immediately trigger shutdown without manual flush
    store.shutdown()
    assert store._db_conn is None

    # Re-open in a fresh store to verify everything on disk was persisted
    store2 = SessionStore(db_file)
    try:
        sessions = store2.list_sessions(user_id="drain_user")
        assert len(sessions) == 8
        for i in range(8):
            msgs = store2.load_session(f"drain_sess_{i}")
            assert len(msgs) == 1
            assert msgs[0]["content"] == f"Message {i}"
    finally:
        store2.shutdown()


# ── 2. Database Migration Suite Verification ──────────────────────────────

def test_database_migrations_empty_db_and_idempotence(tmp_path: Path):
    """GQA-007: Verify migration runner bootstraps empty DB and runs idempotently."""
    db_file = str(tmp_path / "clean_migration.db")
    conn = sqlite3.connect(db_file)
    try:
        # 1. Run migrations on brand new empty database
        applied_initial = run_all_migrations(conn)
        assert len(applied_initial) >= 8

        applied_records = get_applied_migrations(conn)
        assert len(applied_records) == len(applied_initial)

        # 2. Idempotent re-run: 0 new migrations applied
        applied_second = run_all_migrations(conn)
        assert len(applied_second) == 0
    finally:
        conn.close()


def test_database_migration_tamper_detection(tmp_path: Path, monkeypatch):
    """GQA-007: Verify tampered migration scripts trigger MigrationChecksumMismatchError."""
    db_file = str(tmp_path / "tamper_test.db")
    conn = sqlite3.connect(db_file)
    try:
        run_all_migrations(conn)

        # Tamper simulation: record tampered checksum for migration 001
        with conn:
            conn.execute(
                "UPDATE schema_migrations SET checksum = 'tampered_fake_checksum_hex' WHERE version = '001';"
            )

        with pytest.raises(MigrationChecksumMismatchError, match="has been tampered with"):
            run_all_migrations(conn)
    finally:
        conn.close()


# ── 3. Learning Event Idempotency & Deduplication ──────────────────────────

def test_learning_event_idempotency_duplicate_ids(tmp_path: Path):
    """Verify duplicate event IDs are rejected from duplicating records or score effects."""
    db_file = str(tmp_path / "event_idempotency.db")
    db = PlatformDatabase(db_file)
    store = LearningEventStore(db=db)

    ingest_req = LearningEventIngest(
        event_id="ev_idempotency_test_001",
        student_id="student_idempotent_1",
        organization_id="org_idempotency",
        course_id="crs_chem_101",
        session_id="sess_idempotent_1",
        event_type=LearningEventType.ANSWER_SUBMITTED,
        score=0.95,
        concept_id="stoichiometry_mole_ratio",
    )


    # First ingestion must succeed
    ev1, inserted1 = store.ingest_event(ingest_req)
    assert inserted1 is True
    assert ev1.id == "ev_idempotency_test_001"

    # Second ingestion with identical event_id must be deduplicated
    ev2, inserted2 = store.ingest_event(ingest_req)
    assert inserted2 is False
    assert ev2.id == "ev_idempotency_test_001"

    # Verify database contains exactly 1 record for this event
    all_events = db.get_learning_events_for_session("sess_idempotent_1")
    assert len(all_events) == 1
    assert all_events[0].id == "ev_idempotency_test_001"


    db.close()


# ── 4. Concurrency & Multi-Thread Safety ───────────────────────────────────

def test_concurrent_session_writes(tmp_path: Path):
    """Verify thread-safe concurrent saves across multiple sessions and threads."""
    import concurrent.futures

    db_file = tmp_path / "concurrent_sessions.db"
    store = SessionStore(db_file)
    try:
        def worker_save(idx: int):
            c = Conversation(session_id=f"thread_sess_{idx}", user_id=f"user_{idx}")
            c.add("user", f"Thread question {idx}")
            c.add("assistant", f"Thread response {idx}")
            ack = store.save_session(f"thread_sess_{idx}", c)
            return ack.wait(timeout=5.0)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_save, i) for i in range(15)]
            results = [f.result() for f in futures]

        assert all(results)
        assert store.failed_write_count == 0

        # Verify all 15 sessions are intact
        for i in range(15):
            loaded = store.load_session(f"thread_sess_{i}")
            assert len(loaded) == 2
    finally:
        store.shutdown()
