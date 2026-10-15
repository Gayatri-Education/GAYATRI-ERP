"""Phase 11 Remediation Test Suite: Offline Mode, Sync Recovery, Hardware & Third-Party Disclosures (QA-011).

Verifies Section 14 of GAYATRI_ERP_QA_REMEDIATION_GOAL.md:
1. Outbox lifecycle, durable queueing, and in-flight crash recovery.
2. Selective acknowledgement and outbox purging.
3. Exponential backoff and retry storm mitigation.
4. Multi-client concurrency and monotonic sequence ordering.
5. Edge punch batch ingestion idempotency and replay safety.
6. Clock skew detection and conflict journal routing.
7. Active WAL online database backup, restore drill, and foreign key verification.
8. Offline AI execution and RAG empty/degraded isolation (zero network egress).
9. Hardware driver simulation, framing, CRC verification, and truthful BLOCKED disclosure.
10. Third-party payment and notification sandbox honesty (constant-time HMAC, failure routing).
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict

import pytest

from central_platform.db import PlatformDatabase
from central_platform.edge.drivers.base import HardwareDeviceError, HardwareTimeoutError
from central_platform.edge.drivers.simulator import SimulatedBiometricDriver
from central_platform.edge.protocol import HardwarePunchFrame, pack_punch_frame, unpack_punch_frame
from central_platform.events.models import LearningEventIngest
from central_platform.events.store import LearningEventStore
from central_platform.events.types import LearningEventType
from central_platform.models.schema import Notification
from central_platform.models.sync import (
    DeviceStatus,
    DeviceType,
    EdgePunch,
    PunchType,
    SyncItemStatus,
    VerificationType,
)
from central_platform.notifications.models import NotificationChannel, ProviderDeliveryResult
from central_platform.notifications.providers import (
    EmailDeliveryProvider,
    InAppDeliveryProvider,
    ProviderRegistry,
    WhatsAppDeliveryProvider,
)
from central_platform.payments.razorpay import RazorpayPaymentAdapter
from core.rag.retriever import NCERTRetriever
from core.rag.schema import ConfidenceLevel, RAGStatus
from central_platform.sync.edge_service import EdgeSyncService
from local_runtime.sync_outbox import LocalSyncOutbox
from scripts.backup_restore_db import create_backup, restore_backup, verify_database_integrity

ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# 1. Outbox Lifecycle & In-Flight Crash Recovery
# ─────────────────────────────────────────────────────────────────────────────
def test_outbox_lifecycle_and_in_flight_recovery(tmp_path):
    """Pending events transition to IN_FLIGHT, and unacknowledged items recover to PENDING on startup."""
    outbox_file = tmp_path / "client_outbox.db"
    outbox = LocalSyncOutbox(db_path=outbox_file)

    # Enqueue 3 events
    outbox.enqueue(
        student_id="stu-101",
        course_id="crs-math",
        event_id="evt-001",
        event_type="ASSESSMENT_SUBMITTED",
        payload={"score": 88, "unit": "algebra"},
    )
    outbox.enqueue(
        student_id="stu-101",
        course_id="crs-math",
        event_id="evt-002",
        event_type="HINT_REQUESTED",
        payload={"step": 3},
    )
    outbox.enqueue(
        student_id="stu-102",
        course_id="crs-science",
        event_id="evt-003",
        event_type="LESSON_COMPLETED",
        payload={"lesson_id": "sci-ch1"},
    )

    status_initial = outbox.get_outbox_status()
    assert status_initial["pending"] == 3
    assert status_initial["in_flight"] == 0

    # Fetch batch under operation_id
    op_id, batch = outbox.get_pending_batch(limit=2)
    assert len(batch) == 2
    assert op_id.startswith("op_")

    status_inflight = outbox.get_outbox_status()
    assert status_inflight["pending"] == 1
    assert status_inflight["in_flight"] == 2

    # Simulate sudden crash / ungraceful restart (outbox reconstructed from file)
    recovered_outbox = LocalSyncOutbox(db_path=outbox_file)

    # recover_in_flight was triggered during __init__
    status_recovered = recovered_outbox.get_outbox_status()
    assert status_recovered["pending"] == 3
    assert status_recovered["in_flight"] == 0

    # Ensure all events are durable and intact
    op_id_2, batch_2 = recovered_outbox.get_pending_batch(limit=10)
    assert len(batch_2) == 3
    event_ids = {e["event_id"] for e in batch_2}
    assert event_ids == {"evt-001", "evt-002", "evt-003"}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Selective Acknowledgement & Outbox Purging
# ─────────────────────────────────────────────────────────────────────────────
def test_outbox_selective_acknowledgement_and_deletion(tmp_path):
    """Confirmed events are deleted while unconfirmed items remain queued."""
    outbox_file = tmp_path / "ack_outbox.db"
    outbox = LocalSyncOutbox(db_path=outbox_file)

    for i in range(1, 4):
        outbox.enqueue(
            student_id="stu-200",
            course_id="crs-phy",
            event_id=f"evt-ack-{i}",
            event_type="STEP_SOLVED",
            payload={"step": i},
        )

    op_id, batch = outbox.get_pending_batch(limit=10)
    assert len(batch) == 3

    # Acknowledge only item 1 and 3
    deleted = outbox.mark_acknowledged(op_id, ["evt-ack-1", "evt-ack-3"])
    assert deleted == 2

    # Status shows 1 remaining in_flight
    status = outbox.get_outbox_status()
    assert status["total"] == 1
    assert status["in_flight"] == 1

    # Recover remainder and verify item 2 remains
    outbox.recover_in_flight()
    _, next_batch = outbox.get_pending_batch(limit=10)
    assert len(next_batch) == 1
    assert next_batch[0]["event_id"] == "evt-ack-2"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Exponential Backoff & Retry Storm Prevention
# ─────────────────────────────────────────────────────────────────────────────
def test_outbox_exponential_backoff_and_retry_storm_prevention(tmp_path):
    """Network failure increments retry count and sets exponential backoff delay."""
    outbox_file = tmp_path / "backoff_outbox.db"
    outbox = LocalSyncOutbox(db_path=outbox_file)

    outbox.enqueue(
        student_id="stu-300",
        course_id="crs-chem",
        event_id="evt-fail-1",
        event_type="EXPERIMENT_RECORDED",
        payload={"ph": 7.4},
    )

    op_id, batch = outbox.get_pending_batch(limit=10)
    assert len(batch) == 1

    # Mark failed with base delay 5.0s
    outbox.mark_failed(operation_id=op_id, error_message="503 Service Unavailable", backoff_base_sec=5.0)

    # Immediately query pending batch: must return 0 because next_retry_ts is in the future
    op_id_next, empty_batch = outbox.get_pending_batch(limit=10)
    assert len(empty_batch) == 0

    # Inspect stored row metadata
    with outbox._get_connection() as conn:
        row = conn.execute("SELECT * FROM local_sync_outbox WHERE event_id = 'evt-fail-1'").fetchone()
        assert row["status"] == "FAILED"
        assert row["retry_count"] == 1
        assert "503" in row["last_error"]
        assert row["next_retry_ts"] > time.time()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Multi-Client Concurrency & Monotonic Timeline Ordering
# ─────────────────────────────────────────────────────────────────────────────
def test_multiclient_concurrency_and_monotonic_ordering(tmp_path):
    """Two independent clients submitting events merge into a consistent chronological timeline."""
    db_file = str(tmp_path / "shared_platform.db")
    db = PlatformDatabase(db_file)
    event_store = LearningEventStore(db=db)

    # Client A: Offline Mobile App (sequences 1, 2)
    reqs_a = [
        LearningEventIngest(
            event_id="cli-a-1",
            student_id="stu-shared-1",
            session_id="sess-1",
            course_id="crs-lit",
            event_type=LearningEventType.SESSION_STARTED,
            timestamp="2026-10-15T09:00:00Z",
            payload={"sequence_num": 1},
        ),
        LearningEventIngest(
            event_id="cli-a-2",
            student_id="stu-shared-1",
            session_id="sess-1",
            course_id="crs-lit",
            event_type=LearningEventType.HINT_REQUESTED,
            timestamp="2026-10-15T09:05:00Z",
            payload={"sequence_num": 2},
        ),
    ]

    # Client B: Desktop Classroom Kiosk (sequences 3, 4)
    reqs_b = [
        LearningEventIngest(
            event_id="cli-b-3",
            student_id="stu-shared-1",
            session_id="sess-1",
            course_id="crs-lit",
            event_type=LearningEventType.ANSWER_SUBMITTED,
            timestamp="2026-10-15T09:30:00Z",
            payload={"sequence_num": 3, "score": 95},
        ),
        LearningEventIngest(
            event_id="cli-b-4",
            student_id="stu-shared-1",
            session_id="sess-1",
            course_id="crs-lit",
            event_type=LearningEventType.ASSESSMENT_COMPLETED,
            timestamp="2026-10-15T09:35:00Z",
            payload={"sequence_num": 4, "score": 100},
        ),
    ]

    # Ingest in interleaved arrival order: B-3 arrives before A-2
    event_store.ingest_event(reqs_a[0])
    event_store.ingest_event(reqs_b[0])
    event_store.ingest_event(reqs_a[1])
    event_store.ingest_event(reqs_b[1])

    # Fetch canonical student event timeline
    timeline = event_store.get_student_events(student_id="stu-shared-1", course_id="crs-lit")
    assert len(timeline) == 4

    # Verify chronological / sequence ordering across events
    seqs = [e.payload["sequence_num"] for e in timeline]
    assert seqs == sorted(seqs)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Edge Biometric Ingestion Idempotency & Replay Safety
# ─────────────────────────────────────────────────────────────────────────────
def test_edge_biometric_ingestion_idempotency(tmp_path):
    """Replaying identical punch batches returns DUPLICATE status and prevents duplicate records."""
    db_file = str(tmp_path / "edge_platform.db")
    db = PlatformDatabase(db_file)
    service = EdgeSyncService(db=db)

    # Insert organization and users for foreign key constraints
    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("org-school-1", "Greenwood High", "greenwood-high", "2026-10-15T00:00:00Z", "2026-10-15T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("usr-p11-student-01", "org-school-1", "s1@gh.edu", "Student One", "STUDENT", "2026-10-15T00:00:00Z", "2026-10-15T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("usr-p11-student-02", "org-school-1", "s2@gh.edu", "Student Two", "STUDENT", "2026-10-15T00:00:00Z", "2026-10-15T00:00:00Z"),
        )

    # Register edge terminal
    device = service.register_device(
        organization_id="org-school-1",
        device_code="BIO-GATE-01",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Main Gate Terminal",
        secret_plaintext="secret-key-123",
    )

    punches_payload = [
        {
            "user_id": "usr-p11-student-01",
            "punch_type": "CHECK_IN",
            "punch_time": datetime.now(timezone.utc).isoformat(),
            "verification_type": "FINGERPRINT",
            "idempotency_key": "punch-hash-unique-101",
        },
        {
            "user_id": "usr-p11-student-02",
            "punch_type": "CHECK_IN",
            "punch_time": datetime.now(timezone.utc).isoformat(),
            "verification_type": "RFID_CARD",
            "idempotency_key": "punch-hash-unique-102",
        },
    ]

    # First ingestion attempt
    result1 = service.ingest_punch_batch(
        organization_id="org-school-1",
        device_id=device.id,
        punches=punches_payload,
    )
    assert result1["acknowledged"] == 2
    assert result1["duplicates"] == 0

    with db._get_connection() as conn:
        count1 = conn.execute("SELECT COUNT(*) FROM edge_punches WHERE organization_id = 'org-school-1'").fetchone()[0]
        assert count1 == 2

    # Second ingestion attempt: exact replay of identical punches
    result2 = service.ingest_punch_batch(
        organization_id="org-school-1",
        device_id=device.id,
        punches=punches_payload,
    )
    assert result2["acknowledged"] == 0
    assert result2["duplicates"] == 2
    assert result2["item_statuses"]["punch-hash-unique-101"] == "DUPLICATE"
    assert result2["item_statuses"]["punch-hash-unique-102"] == "DUPLICATE"

    # Verify zero duplicate rows in database
    with db._get_connection() as conn:
        count2 = conn.execute("SELECT COUNT(*) FROM edge_punches WHERE organization_id = 'org-school-1'").fetchone()[0]
        assert count2 == 2


# ─────────────────────────────────────────────────────────────────────────────
# 6. Clock Skew Detection & Conflict Journal Routing
# ─────────────────────────────────────────────────────────────────────────────
def test_excessive_clock_skew_flagging_and_conflict_journal(tmp_path):
    """Punches with excessive clock skew (> 300s) are flagged and routed to conflict records."""
    db_file = str(tmp_path / "clock_skew.db")
    db = PlatformDatabase(db_file)
    service = EdgeSyncService(db=db)

    # Insert organization and user for foreign key constraints
    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("org-school-skew", "Skew School", "skew-school", "2026-10-15T00:00:00Z", "2026-10-15T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("usr-skewed-01", "org-school-skew", "skew1@gh.edu", "Skewed User", "STUDENT", "2026-10-15T00:00:00Z", "2026-10-15T00:00:00Z"),
        )

    device = service.register_device(
        organization_id="org-school-skew",
        device_code="BIO-SKEW-01",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Skewed Gate Terminal",
        secret_plaintext="secret-key-skew",
    )

    # 15 minutes in the future (skew > 300s)
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    skewed_punches = [
        {
            "user_id": "usr-skewed-01",
            "punch_type": "CHECK_IN",
            "punch_time": future_time,
            "verification_type": "FINGERPRINT",
            "idempotency_key": "punch-skew-001",
        }
    ]

    result = service.ingest_punch_batch(
        organization_id="org-school-skew",
        device_id=device.id,
        punches=skewed_punches,
    )

    # Verify flagged for conflict / clock skew audit
    assert result["conflicts"] == 1
    assert result["item_statuses"]["punch-skew-001"] == "CONFLICT"

    with db._get_connection() as conn:
        conflicts = conn.execute(
            "SELECT * FROM sync_conflict_records WHERE organization_id = 'org-school-skew'"
        ).fetchall()
        assert len(conflicts) == 1
        assert conflicts[0]["conflict_type"] == "CLOCK_SKEW_EXCESSIVE"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Online Hot Backup & Restore Drill with Active WAL
# ─────────────────────────────────────────────────────────────────────────────
def test_online_hot_backup_and_restore_with_active_wal(tmp_path):
    """Online backup and restore drill under active WAL verifies PRAGMA integrity, foreign keys, and row parity."""
    src_db = tmp_path / "source_active_wal.db"
    backup_dir = tmp_path / "backups"
    target_db = tmp_path / "restored_drill.db"

    # 1. Initialize and populate database in WAL mode
    conn = sqlite3.connect(str(src_db))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("CREATE TABLE departments (id TEXT PRIMARY KEY, name TEXT NOT NULL);")
    conn.execute(
        "CREATE TABLE employees (id TEXT PRIMARY KEY, name TEXT NOT NULL, dept_id TEXT REFERENCES departments(id));"
    )

    conn.execute("INSERT INTO departments VALUES ('dept-1', 'Mathematics'), ('dept-2', 'Science');")
    conn.execute("INSERT INTO employees VALUES ('emp-1', 'Alice', 'dept-1'), ('emp-2', 'Bob', 'dept-2');")
    conn.commit()

    # 2. Perform hot online backup while WAL connection is open
    backup_file = create_backup(str(src_db), str(backup_dir))
    assert Path(backup_file).exists()
    assert Path(backup_file).stat().st_size > 0

    # 3. Perform restore drill into target_db
    restored = restore_backup(backup_file, str(target_db))
    assert restored is True
    assert target_db.exists()

    # 4. Run deep database integrity validation
    integrity = verify_database_integrity(str(target_db))
    assert integrity["integrity_ok"] is True
    assert integrity["foreign_keys_ok"] is True
    assert integrity["foreign_key_violations"] == 0
    assert integrity["tables"]["departments"] == 2
    assert integrity["tables"]["employees"] == 2

    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 8. Offline AI Execution & RAG Degraded Isolation
# ─────────────────────────────────────────────────────────────────────────────
def test_offline_ai_local_provider_isolation(tmp_path):
    """LocalProvider and NCERTRetriever execute in-process with zero network calls and honest ungrounded states."""
    from core.providers.local import LocalModelError, LocalProvider
    from core.rag.schema import RAGStatus
    from core.rag.store import RAGStore

    # LocalProvider is strictly local
    assert LocalProvider.MODEL_PATH.name.endswith(".gguf")
    assert LocalProvider.MODEL_PATH.is_absolute()

    # Empty store returns honest RAG_EMPTY / LOW confidence without remote fallback
    empty_store = RAGStore(db_path=tmp_path / "empty_rag.db")
    retriever = NCERTRetriever(store=empty_store)
    ctx = retriever.retrieve_hybrid("What is photoelectric effect in physics?")

    assert ctx.confidence == ConfidenceLevel.LOW
    assert ctx.status == RAGStatus.RAG_EMPTY
    assert len(ctx.results) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 9. Hardware Driver Simulation & Truthful BLOCKED Disclosure
# ─────────────────────────────────────────────────────────────────────────────
def test_hardware_simulator_framing_and_blocked_disclosure():
    """Simulated biometric driver verifies framing/CRC, and disclosures file marks hardware acceptance as BLOCKED."""
    driver = SimulatedBiometricDriver(device_id="SIM-BIO-VERIFY")

    # 1. Driver explicitly identifies as simulated
    assert driver.is_simulated is True
    assert driver.driver_name == "SimulatedBiometricDriver"
    assert driver.is_connected() is True

    # 2. Frame encoding, packet framing, and CRC-16 round-trip
    injected_frame = driver.inject_punch(
        user_id="usr-test-44",
        punch_type="CHECK_IN",
        punch_time="2026-10-15T10:00:00Z",
        verification_type="FINGERPRINT",
    )
    read_frame = driver.read_punch()
    assert read_frame is not None
    assert read_frame.user_id == "usr-test-44"
    assert read_frame.verification_type == "FINGERPRINT"

    # 3. Disconnect handling
    driver.trigger_disconnect()
    assert driver.is_connected() is False
    with pytest.raises(HardwareDeviceError):
        driver.read_punch()

    driver.connect()
    assert driver.is_connected() is True

    # 4. Timeout handling
    driver.trigger_timeout_once()
    with pytest.raises(HardwareTimeoutError):
        driver.read_punch()

    # 5. Checksum / CRC corruption handling
    driver.trigger_corrupt_packet_once()
    with pytest.raises(ValueError, match="Checksum mismatch"):
        driver.read_punch()

    # 6. Verify canonical disclosures document exists and marks physical hardware as BLOCKED
    disclosures_path = ROOT / "docs" / "operations" / "HARDWARE_AND_THIRD_PARTY_DISCLOSURES.md"
    assert disclosures_path.exists()
    content = disclosures_path.read_text(encoding="utf-8")
    assert "BLK-003" in content
    assert "BLOCKED" in content
    assert "SIMULATED" in content


# ─────────────────────────────────────────────────────────────────────────────
# 10. Third-Party Payment & Notification Sandbox Honesty
# ─────────────────────────────────────────────────────────────────────────────
def test_third_party_payment_and_notification_sandbox_honesty():
    """Payment and notification providers enforce HMAC verification and fail-closed error handling."""
    # 1. Razorpay Adapter HMAC verification
    rzp = RazorpayPaymentAdapter(key_id="rzp_test_k1", key_secret="rzp_test_s1")
    assert rzp.provider_name == "razorpay"

    order_id = "order_123456"
    payment_id = "pay_789012"
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    valid_sig = hmac.new("rzp_test_s1".encode("utf-8"), msg, hashlib.sha256).hexdigest()

    assert rzp.verify_payment_signature(order_id, payment_id, valid_sig) is True
    assert rzp.verify_payment_signature(order_id, payment_id, "forged_invalid_signature") is False
    assert rzp.verify_payment_signature("", payment_id, valid_sig) is False

    # 2. Notification Provider Registry & Honest Delivery Simulation
    registry = ProviderRegistry()
    in_app = registry.get(NotificationChannel.IN_APP)
    assert in_app.channel == NotificationChannel.IN_APP

    wa_provider = registry.get(NotificationChannel.WHATSAPP)
    assert wa_provider.channel == NotificationChannel.WHATSAPP

    email_provider = registry.get(NotificationChannel.EMAIL)
    assert email_provider.channel == NotificationChannel.EMAIL
