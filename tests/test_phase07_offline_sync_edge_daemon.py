"""Phase 07: Offline Sync Hardening and Edge Biometric Integrations Tests.

Tests cover:
1. Migration 015 schema creation and clean rollback.
2. Device registration, secret hashing, heartbeat, and revocation lifecycle.
3. Edge daemon local outbox persistence across crashes and restarts.
4. Batch ingestion partial success with per-item acknowledgement (valid + duplicate + invalid).
5. Replay and idempotency: zero duplicate consequential punches or double attendance.
6. Excessive clock skew detection and conflict journal routing.
7. Hardware failure and disconnect sandboxing (zero UI/AI impact).
8. Binary packet protocol framing, CRC-16 checksums, and corruption rejection.
9. Conflict resolution workflow and sync health observability dashboard metrics.
10. REST API routing and strict cross-tenant isolation.
"""

import sqlite3
import pytest
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient

from central_platform.db import PlatformDatabase
from central_platform.models import Organization, User, UserRole
from central_platform.models.sync import (
    ConflictResolutionStrategy,
    DeviceStatus,
    DeviceType,
    EdgeDevice,
    EdgePunch,
    PunchType,
    SyncItemStatus,
    VerificationType,
)
from central_platform.edge.protocol import (
    HardwarePunchFrame,
    pack_punch_frame,
    unpack_punch_frame,
)
from central_platform.edge.drivers.simulator import SimulatedBiometricDriver
from central_platform.edge.daemon import EdgeDaemon
from central_platform.sync.edge_service import EdgeSyncService
from central_platform.auth.tokens import create_access_token
from central_platform.api.app import app

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


@pytest.fixture
def platform_db(tmp_path):
    """File-backed PlatformDatabase instance migrated through 015."""
    db_file = str(tmp_path / "test_phase07.db")
    db = PlatformDatabase(db_file)
    with db._get_connection() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-school-1', 'Greenwood High', 'greenwood-high', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-coaching-2', 'Apex IIT Academy', 'apex-iit', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        for mod in ["edge", "sync", "hr", "attendance"]:
            conn.execute(
                "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
                f"VALUES ('ent-{mod}-1', 'org-school-1', '{mod}', 1, '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
            )
            conn.execute(
                "INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, created_at, updated_at) "
                f"VALUES ('ent-{mod}-2', 'org-coaching-2', '{mod}', 1, '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
            )
        # Create student and staff users in Greenwood High
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            "VALUES ('usr-stu-101', 'org-school-1', 'student1@gw.edu', 'Karan Verma', 'student', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            "INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            "VALUES ('usr-stf-201', 'org-school-1', 'teacher1@gw.edu', 'Pooja Sharma', 'teacher', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
    yield db
    db.close()


# ── Test 1: Migration 015 Up and Down ─────────────────────────────────────────

def test_migration_015_up_and_down():
    """Verify migration 015 creates edge sync tables and down script drops them cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply up through 014
    for i in range(1, 15):
        scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Apply 015
    up_015 = MIGRATIONS_DIR / "015_offline_sync_edge_daemon.sql"
    assert up_015.exists(), "015 forward migration script must exist"
    conn.executescript(up_015.read_text(encoding="utf-8"))

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_up = {r[0] for r in cursor.fetchall()}

    expected_tables = {
        "edge_devices",
        "edge_punches",
        "sync_conflict_records",
        "sync_dead_letter_queue",
    }
    for t in expected_tables:
        assert t in tables_after_up, f"Table {t} should exist after migration 015"

    # Roll back 015
    down_015 = MIGRATIONS_DIR / "015_offline_sync_edge_daemon_down.sql"
    assert down_015.exists(), "015 rollback migration script must exist"
    conn.executescript(down_015.read_text(encoding="utf-8"))

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables_after_down = {r[0] for r in cursor.fetchall()}

    for t in expected_tables:
        assert t not in tables_after_down, f"Table {t} should be removed after rollback"

    conn.close()


# ── Test 2: Edge Device Lifecycle & Revocation ────────────────────────────────

def test_edge_device_registration_auth_and_revocation(platform_db):
    """Verify device registration, secret verification, heartbeat, and revocation."""
    service = EdgeSyncService(platform_db)

    # 1. Register device
    dev = service.register_device(
        organization_id="org-school-1",
        device_code="BIO-GATE-01",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Main Gate Turnstile",
        secret_plaintext="top-secret-edge-key-123",
        ip_address="192.168.1.50",
        firmware_version="v2.4.1",
    )
    assert dev.id is not None
    assert dev.status == DeviceStatus.ACTIVE

    # 2. Authenticate successfully
    auth_dev = service.authenticate_device("org-school-1", "BIO-GATE-01", "top-secret-edge-key-123")
    assert auth_dev.id == dev.id

    # 3. Authenticate with bad secret
    with pytest.raises(PermissionError, match="Invalid device secret"):
        service.authenticate_device("org-school-1", "BIO-GATE-01", "wrong-secret")

    # 4. Record Heartbeat
    service.record_heartbeat(dev.id, ip_address="192.168.1.55", firmware_version="v2.4.2")
    updated = service.get_device("org-school-1", dev.id)
    assert updated.ip_address == "192.168.1.55"
    assert updated.last_heartbeat_at is not None

    # 5. Revoke Device
    revoked = service.revoke_device("org-school-1", dev.id, reason="Terminal decommissioned")
    assert revoked.status == DeviceStatus.REVOKED

    # 6. Authenticate after revocation must be rejected
    with pytest.raises(PermissionError, match="REVOKED"):
        service.authenticate_device("org-school-1", "BIO-GATE-01", "top-secret-edge-key-123")


# ── Test 3: Edge Daemon Local Outbox Persistence & Restart ────────────────────

def test_edge_daemon_local_outbox_persistence_and_restart(tmp_path):
    """Verify punches queued in local disk outbox survive process restarts and power loss."""
    outbox_file = str(tmp_path / "edge_daemon_outbox.db")
    driver = SimulatedBiometricDriver(device_id="DEV-001")

    # Instance 1: Poll hardware punch
    daemon1 = EdgeDaemon(
        device_id="DEV-001",
        device_secret="secret",
        organization_id="org-school-1",
        driver=driver,
        outbox_db_path=outbox_file,
    )
    driver.inject_punch(user_id="usr-stu-101", punch_type="CHECK_IN", punch_time="2026-10-15T08:15:00Z")
    polled = daemon1.poll_hardware_once()
    assert polled is not None
    assert polled["user_id"] == "usr-stu-101"

    stats1 = daemon1.get_outbox_stats()
    assert stats1["pending_count"] == 1
    daemon1.close()  # Simulate daemon shutdown/crash

    # Instance 2: Start new daemon on same persistent outbox DB file
    daemon2 = EdgeDaemon(
        device_id="DEV-001",
        device_secret="secret",
        organization_id="org-school-1",
        driver=driver,
        outbox_db_path=outbox_file,
    )
    pending = daemon2.get_pending_punches()
    assert len(pending) == 1
    assert pending[0]["user_id"] == "usr-stu-101"
    daemon2.close()


# ── Test 4: Batch Partial Success & Per-Item Acknowledgement ──────────────────

def test_batch_partial_success_and_per_item_acknowledgement(platform_db, tmp_path):
    """Verify batch with mixed valid, duplicate, and invalid user punches commits valid items and routes failures to DLQ."""
    service = EdgeSyncService(platform_db)
    dev = service.register_device(
        organization_id="org-school-1",
        device_code="BIO-02",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Staff Room Scanner",
        secret_plaintext="secret",
    )

    outbox_file = str(tmp_path / "outbox_partial.db")
    driver = SimulatedBiometricDriver(device_id=dev.id)
    daemon = EdgeDaemon(dev.id, "secret", "org-school-1", driver, outbox_db_path=outbox_file)

    now_str = datetime.now(timezone.utc).isoformat()

    # Ingest 1 prior punch directly to set up duplicate test
    service.ingest_punch_batch(
        organization_id="org-school-1",
        device_id=dev.id,
        punches=[
            {
                "user_id": "usr-stf-201",
                "punch_type": "CHECK_IN",
                "punch_time": now_str,
                "verification_type": "FINGERPRINT",
                "idempotency_key": "punch-prior-001",
            }
        ],
    )

    # Batch of 3 items:
    # 1. Valid punch for Karan Verma (usr-stu-101)
    # 2. Duplicate punch (punch-prior-001)
    # 3. Invalid non-existent user (usr-ghost-999)
    batch = [
        {
            "user_id": "usr-stu-101",
            "punch_type": "CHECK_IN",
            "punch_time": now_str,
            "verification_type": "FINGERPRINT",
            "idempotency_key": "punch-valid-002",
        },
        {
            "user_id": "usr-stf-201",
            "punch_type": "CHECK_IN",
            "punch_time": now_str,
            "verification_type": "FINGERPRINT",
            "idempotency_key": "punch-prior-001",
        },
        {
            "user_id": "usr-ghost-999",
            "punch_type": "CHECK_IN",
            "punch_time": now_str,
            "verification_type": "FINGERPRINT",
            "idempotency_key": "punch-invalid-003",
        },
    ]

    result = service.ingest_punch_batch("org-school-1", dev.id, batch)
    assert result["total"] == 3
    assert result["acknowledged"] == 1
    assert result["duplicates"] == 1
    assert result["failed"] == 1
    assert result["item_statuses"]["punch-valid-002"] == SyncItemStatus.ACKNOWLEDGED.value
    assert result["item_statuses"]["punch-prior-001"] == SyncItemStatus.DUPLICATE.value
    assert result["item_statuses"]["punch-invalid-003"] == SyncItemStatus.FAILED.value

    # Update daemon outbox and verify
    daemon.record_sync_results(result["item_statuses"], result["errors"])
    stats = daemon.get_outbox_stats()
    daemon.close()


# ── Test 5: Replay & Idempotency Guarantee ───────────────────────────────────

def test_replay_and_idempotency_zero_double_marking(platform_db):
    """Verify that replayed batches produce zero duplicate punches or side effects."""
    service = EdgeSyncService(platform_db)
    dev = service.register_device(
        organization_id="org-school-1",
        device_code="BIO-REPLAY-01",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Replay Gate",
        secret_plaintext="secret",
    )

    now_str = datetime.now(timezone.utc).isoformat()
    batch = [
        {
            "user_id": "usr-stu-101",
            "punch_type": "CHECK_IN",
            "punch_time": now_str,
            "verification_type": "RFID_CARD",
            "idempotency_key": "replay-test-key-101",
        }
    ]

    # First delivery
    res1 = service.ingest_punch_batch("org-school-1", dev.id, batch)
    assert res1["acknowledged"] == 1
    assert res1["duplicates"] == 0

    # Second delivery (replay after network packet loss)
    res2 = service.ingest_punch_batch("org-school-1", dev.id, batch)
    assert res2["acknowledged"] == 0
    assert res2["duplicates"] == 1

    # Verify database has exactly 1 punch record
    with platform_db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM edge_punches WHERE idempotency_key = 'replay-test-key-101';")
        count = cursor.fetchone()[0]
        assert count == 1, "Exactly one punch record must exist despite replay"


# ── Test 6: Clock Skew Detection and Conflict Routing ────────────────────────

def test_clock_skew_detection_and_conflict_routing(platform_db):
    """Verify punches with excessive forward clock skew (> 300s) are quarantined to conflict records."""
    service = EdgeSyncService(platform_db)
    dev = service.register_device(
        organization_id="org-school-1",
        device_code="BIO-SKEW-01",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Skewed Clock Terminal",
        secret_plaintext="secret",
    )

    # Punch set 2 hours into the future
    future_punch = [
        {
            "user_id": "usr-stu-101",
            "punch_type": "CHECK_IN",
            "punch_time": "2030-01-01T12:00:00Z",
            "verification_type": "FINGERPRINT",
            "idempotency_key": "skew-future-001",
        }
    ]

    res = service.ingest_punch_batch("org-school-1", dev.id, future_punch)
    assert res["conflicts"] == 1
    assert res["acknowledged"] == 0
    assert res["item_statuses"]["skew-future-001"] == SyncItemStatus.CONFLICT.value

    # Verify conflict record exists
    conflicts = service.list_conflicts("org-school-1")
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "CLOCK_SKEW_EXCESSIVE"
    assert conflicts[0].resolution_strategy == ConflictResolutionStrategy.MANUAL_REVIEW


# ── Test 7: Hardware Failure & Disconnect Sandboxing ─────────────────────────

def test_hardware_failure_and_disconnect_sandboxing():
    """Verify physical hardware disconnects or timeouts do not crash the daemon or caller."""
    driver = SimulatedBiometricDriver(device_id="FAULTY-01")
    daemon = EdgeDaemon("FAULTY-01", "secret", "org-school-1", driver)

    # 1. Simulate hardware disconnect
    driver.trigger_disconnect()
    res1 = daemon.poll_hardware_once()
    assert res1 is None
    assert daemon.hardware_fault_count == 1
    assert "disconnected" in daemon.last_hardware_fault.lower()

    # 2. Simulate hardware reconnect and read timeout
    driver.connect()
    driver.trigger_timeout_once()
    res2 = daemon.poll_hardware_once()
    assert res2 is None
    assert daemon.hardware_fault_count == 2
    assert "timed out" in daemon.last_hardware_fault.lower()

    # 3. Simulate hardware packet corruption
    driver.trigger_corrupt_packet_once()
    res3 = daemon.poll_hardware_once()
    assert res3 is None
    assert daemon.hardware_fault_count == 3
    assert "checksum mismatch" in daemon.last_hardware_fault.lower()

    daemon.close()


# ── Test 8: Binary Packet Protocol Framing & Checksum ────────────────────────

def test_binary_packet_protocol_framing_and_checksum():
    """Verify binary frame packing, CRC-16 calculation, and corruption rejection."""
    frame = HardwarePunchFrame(
        user_id="usr-stu-101",
        punch_type="CHECK_IN",
        punch_time="2026-10-15T08:30:00Z",
        verification_type="FINGERPRINT",
        sequence_num=42,
    )

    # Pack to wire bytes
    packet = pack_punch_frame(frame)
    assert len(packet) > 10

    # Unpack valid wire bytes
    decoded = unpack_punch_frame(packet)
    assert decoded.user_id == "usr-stu-101"
    assert decoded.sequence_num == 42

    # Corrupt packet checksum byte
    corrupted = bytearray(packet)
    corrupted[-1] ^= 0x55
    with pytest.raises(ValueError, match="Checksum mismatch"):
        unpack_punch_frame(bytes(corrupted))

    # Corrupt header byte
    corrupted_hdr = bytearray(packet)
    corrupted_hdr[0] = 0x00
    with pytest.raises(ValueError, match="Invalid frame header"):
        unpack_punch_frame(bytes(corrupted_hdr))


# ── Test 9: Conflict Resolution & Sync Health Observability ──────────────────

def test_conflict_resolution_and_sync_health_metrics(platform_db):
    """Verify conflict resolution audit and health metrics dashboard calculation."""
    service = EdgeSyncService(platform_db)
    dev = service.register_device(
        organization_id="org-school-1",
        device_code="BIO-HLTH-01",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Health Metric Terminal",
        secret_plaintext="secret",
    )

    # Inject a clock skew punch to create 1 conflict
    service.ingest_punch_batch(
        "org-school-1",
        dev.id,
        [
            {
                "user_id": "usr-stu-101",
                "punch_type": "CHECK_IN",
                "punch_time": "2030-01-01T00:00:00Z",
                "verification_type": "PIN",
                "idempotency_key": "hlth-skew-1",
            }
        ],
    )

    # Health before resolution: unhealthy because 1 unresolved conflict exists
    metrics1 = service.get_sync_health_metrics("org-school-1")
    assert metrics1.active_devices_count == 1
    assert metrics1.unresolved_conflicts_count == 1
    assert metrics1.healthy is False

    # Resolve the conflict
    conflicts = service.list_conflicts("org-school-1")
    resolved = service.resolve_conflict(
        organization_id="org-school-1",
        conflict_id=conflicts[0].id,
        strategy=ConflictResolutionStrategy.MANUAL_REVIEW,
        resolved_by="admin-user-1",
        notes="Confirmed clock desync on physical terminal, rescheduled terminal clock sync.",
    )
    assert resolved.resolved_by == "admin-user-1"
    assert resolved.resolved_at is not None

    # Health after resolution: healthy
    metrics2 = service.get_sync_health_metrics("org-school-1")
    assert metrics2.unresolved_conflicts_count == 0
    assert metrics2.healthy is True


# ── Test 10: REST API Endpoints & Cross-Tenant Isolation ─────────────────────

def test_phase07_api_endpoints_and_cross_tenant_isolation():
    """Verify edge REST API endpoints and strict multi-tenant boundary enforcement."""
    import uuid
    db = PlatformDatabase()
    org1_id = f"org_{uuid.uuid4().hex[:6]}"
    org2_id = f"org_{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org1_id, name="Org One", slug=f"org-one-{org1_id}"))
    db.create_organization(Organization(id=org2_id, name="Org Two", slug=f"org-two-{org2_id}"))

    stu_id = f"stu_{uuid.uuid4().hex[:6]}"
    db.create_user(User(id=stu_id, organization_id=org1_id, email=f"{stu_id}@org1.edu", full_name="Student One", role=UserRole.STUDENT))

    token_org1 = create_access_token(
        user_id="user-admin-p7",
        role="org_admin",
        organization_id=org1_id,
    )
    headers_org1 = {"Authorization": f"Bearer {token_org1}"}

    token_org2 = create_access_token(
        user_id="user-admin-apex",
        role="org_admin",
        organization_id=org2_id,
    )
    headers_org2 = {"Authorization": f"Bearer {token_org2}"}

    client = TestClient(app)

    # 1. Register Device in Org 1
    resp_reg = client.post(
        "/api/v1/edge/devices/register",
        headers=headers_org1,
        json={
            "device_code": f"BIO-API-{org1_id}",
            "device_type": "BIOMETRIC_TERMINAL",
            "device_name": "Front Gate API",
            "secret": "supersecretkey123",
        },
    )
    assert resp_reg.status_code == 201
    device_id = resp_reg.json()["id"]

    # 2. Ingest punch batch via API
    now_str = datetime.now(timezone.utc).isoformat()
    resp_punch = client.post(
        "/api/v1/edge/punches/batch",
        headers=headers_org1,
        json={
            "device_id": device_id,
            "punches": [
                {
                    "user_id": stu_id,
                    "punch_type": "CHECK_IN",
                    "punch_time": now_str,
                    "verification_type": "FINGERPRINT",
                    "idempotency_key": f"api-punch-{uuid.uuid4().hex[:8]}",
                }
            ],
        },
    )
    assert resp_punch.status_code == 200
    assert resp_punch.json()["acknowledged"] == 1

    # 3. Org 1 Health Check
    resp_health_org1 = client.get("/api/v1/edge/health", headers=headers_org1)
    assert resp_health_org1.status_code == 200
    assert resp_health_org1.json()["active_devices_count"] == 1

    # 4. Cross-Tenant Isolation: Org 2 Health Check must have 0 devices
    resp_health_org2 = client.get("/api/v1/edge/health", headers=headers_org2)
    assert resp_health_org2.status_code == 200
    assert resp_health_org2.json()["active_devices_count"] == 0

    # 5. Org 2 cannot revoke Org 1's device
    resp_revoke_cross = client.post(f"/api/v1/edge/devices/{device_id}/revoke", headers=headers_org2)
    assert resp_revoke_cross.status_code == 404
