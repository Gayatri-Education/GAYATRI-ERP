"""Tests for QA Phase 04: Session, Database & Persistence Integrity.

Verifies:
- QA-010: Database write durability on shutdown, flush completion, synchronous save.
- QA-011: Configurable user identity, dynamic tenant isolation, backward compatibility for legacy local_user_1.
- Context manager support and clean resource release.
- Bridge user identity slots and filtering.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from core.conversation import Conversation
from core.session import SessionStore, DEFAULT_LOCAL_USER_ID


def test_async_queue_flush_durability(tmp_path: Path):
    """Verify that asynchronous write queue guarantees durability upon calling flush()."""
    db_file = tmp_path / "test_sessions.db"
    store = SessionStore(db_file)
    try:
        conv1 = Conversation(session_id="sess_async_1", mode="tutor", user_id="user_test_1")
        conv1.add("user", "Hello async world")
        conv1.add("assistant", "Hi there! How can I help?")

        store.save_session("sess_async_1", conv1)
        store.flush()

        # Verify immediate durability
        loaded = store.load_session("sess_async_1")
        assert len(loaded) == 2
        assert loaded[0]["content"] == "Hello async world"
        assert loaded[1]["content"] == "Hi there! How can I help?"
    finally:
        store.shutdown()


def test_shutdown_persistence_and_cleanup(tmp_path: Path):
    """Verify that shutdown() blocks until all queued writes are complete and cleanly closes DB."""
    db_file = tmp_path / "test_shutdown.db"
    store = SessionStore(db_file)

    for i in range(5):
        conv = Conversation(session_id=f"sess_shut_{i}", user_id="user_shut")
        conv.add("user", f"Question {i}")
        conv.add("assistant", f"Answer {i}")
        store.save_session(f"sess_shut_{i}", conv)

    # Shutdown should commit all writes and close
    store.shutdown()
    assert store._db_conn is None
    assert store._write_queue.empty()

    # Re-open in a fresh store to verify everything on disk was persisted
    store2 = SessionStore(db_file)
    try:
        sessions = store2.list_sessions(user_id="user_shut")
        assert len(sessions) == 5
    finally:
        store2.shutdown()


def test_save_session_sync(tmp_path: Path):
    """Verify that save_session_sync immediately persists data synchronously."""
    db_file = tmp_path / "test_sync.db"
    with SessionStore(db_file) as store:
        conv = Conversation(session_id="sess_sync_1", user_id="user_sync")
        conv.add("user", "Sync prompt")
        conv.add("assistant", "Sync answer")

        store.save_session_sync("sess_sync_1", conv)
        # Without calling flush(), should already be in DB
        loaded = store.load_session("sess_sync_1")
        assert len(loaded) == 2
        assert loaded[0]["content"] == "Sync prompt"


def test_session_store_context_manager(tmp_path: Path):
    """Verify SessionStore operates cleanly as a context manager."""
    db_file = tmp_path / "test_ctx.db"
    with SessionStore(db_file) as store:
        conv = Conversation(session_id="sess_ctx_1")
        conv.add("user", "Context test")
        store.save_session("sess_ctx_1", conv)

    # Post-context: shutdown must have been executed
    assert store._shutdown_event.is_set()
    assert store._db_conn is None


def test_user_identity_dynamic_isolation(tmp_path: Path):
    """Verify multi-user session isolation: User A cannot see User B's sessions."""
    db_file = tmp_path / "test_isolation.db"
    with SessionStore(db_file) as store:
        conv_a = Conversation(session_id="sess_user_a", user_id="student_alice")
        conv_a.add("user", "Alice question")
        store.save_session_sync("sess_user_a", conv_a)

        conv_b = Conversation(session_id="sess_user_b", user_id="student_bob")
        conv_b.add("user", "Bob question")
        store.save_session_sync("sess_user_b", conv_b)

        sessions_a = store.list_sessions(user_id="student_alice")
        assert len(sessions_a) == 1
        assert sessions_a[0]["id"] == "sess_user_a"

        sessions_b = store.list_sessions(user_id="student_bob")
        assert len(sessions_b) == 1
        assert sessions_b[0]["id"] == "sess_user_b"


def test_legacy_user_identity_compatibility(tmp_path: Path):
    """Verify that queries for default user retrieve both local_learner and legacy local_user_1 records."""
    db_file = tmp_path / "test_legacy.db"
    with SessionStore(db_file) as store:
        conv_legacy = Conversation(session_id="sess_legacy", user_id="local_user_1")
        conv_legacy.add("user", "Legacy message")
        store.save_session_sync("sess_legacy", conv_legacy)

        conv_new = Conversation(session_id="sess_new", user_id="local_learner")
        conv_new.add("user", "New message")
        store.save_session_sync("sess_new", conv_new)

        # Querying either local_learner or local_user_1 returns both
        sessions_query1 = store.list_sessions(user_id="local_learner")
        ids1 = {s["id"] for s in sessions_query1}
        assert "sess_legacy" in ids1
        assert "sess_new" in ids1

        sessions_query2 = store.list_sessions(user_id="local_user_1")
        ids2 = {s["id"] for s in sessions_query2}
        assert "sess_legacy" in ids2
        assert "sess_new" in ids2


def test_bridge_user_id_slots(tmp_path: Path, monkeypatch):
    """Verify Bridge slots for set_user_id, get_user_id, and dynamic get_sessions filtering."""
    from app.bridge.facade import Bridge
    from core.session import get_session_store

    db_file = tmp_path / "bridge_test.db"
    store = SessionStore(db_file)
    monkeypatch.setattr("core.session.get_session_store", lambda: store)

    bridge = Bridge()
    assert bridge.get_user_id() in ("local_learner", "local_user_1")

    bridge.set_user_id("custom_student_42")
    assert bridge.get_user_id() == "custom_student_42"

    # Add sessions for custom student and another user
    conv_target = Conversation(session_id="sess_custom_42", user_id="custom_student_42")
    conv_target.add("user", "Target question")
    store.save_session_sync("sess_custom_42", conv_target)

    conv_other = Conversation(session_id="sess_other_99", user_id="other_student_99")
    conv_other.add("user", "Other question")
    store.save_session_sync("sess_other_99", conv_other)

    sessions_raw = bridge.get_sessions()
    sessions_data = json.loads(sessions_raw)
    assert sessions_data["ok"] is True
    session_ids = [s["id"] for s in sessions_data["sessions"]]
    assert session_ids == ["sess_custom_42"]

    store.shutdown()
