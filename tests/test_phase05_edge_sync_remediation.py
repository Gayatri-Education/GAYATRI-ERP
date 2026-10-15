"""Phase 05 Remediation Test Suite — Edge Devices, Attendance Punches & Invalid Enum Rejection (QA-005).

Mandatory Invariants Tested:
1. Strict Enum Validation: Invalid device_type, punch_type, verification_type, or conflict strategy rejects with HTTP 422.
2. Device Heartbeat Authentication: Unauthenticated heartbeats rejected with 401, wrong secret 401, unknown device 404, revoked device 403.
3. Punch Batch Authentication: Unauthenticated punch batches rejected with 401, wrong secret 401, unknown device 404, revoked device 403.
4. Tenant Mapping Integrity: Tenant is derived from authenticated device; mismatched caller X-Organization-ID rejected with 400.
5. Durable ACKs: Heartbeat returns ACK only when persisted in DB.
6. Batch Idempotency: Duplicate punch keys return DUPLICATE without duplicate rows.
7. Restart Durability: DB restart verifies persisted punches and device states.
8. Truthful Hardware Declarations: Simulated drivers explicitly identify as SIMULATED.
"""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import Organization, User, UserRole
from central_platform.models.sync import (
    ConflictResolutionStrategy,
    DeviceStatus,
    DeviceType,
    PunchType,
    VerificationType,
)
from central_platform.sync.edge_service import EdgeSyncService, _hash_secret
from central_platform.edge.drivers.simulator import SimulatedBiometricDriver


@pytest.fixture
def phase05_env(tmp_path):
    """Provides isolated database, organizations, users, and registered edge devices."""
    db_path = tmp_path / "test_phase05_edge_remediation.db"
    db = PlatformDatabase(db_path)

    # 1. Setup Tenant Organizations
    org_a = Organization(id=f"org-alpha-{uuid.uuid4().hex[:6]}", name="Alpha High School", slug=f"alpha-{uuid.uuid4().hex[:6]}")
    org_b = Organization(id=f"org-beta-{uuid.uuid4().hex[:6]}", name="Beta Collegiate", slug=f"beta-{uuid.uuid4().hex[:6]}")
    db.create_organization(org_a)
    db.create_organization(org_b)

    # 2. Setup Student Users in Org A and Org B
    student_a = User(
        id=f"stu-a-{uuid.uuid4().hex[:6]}",
        organization_id=org_a.id,
        email="student.a@alpha.edu",
        full_name="Student Alpha",
        role=UserRole.STUDENT,
        is_active=True,
    )
    student_b = User(
        id=f"stu-b-{uuid.uuid4().hex[:6]}",
        organization_id=org_b.id,
        email="student.b@beta.edu",
        full_name="Student Beta",
        role=UserRole.STUDENT,
        is_active=True,
    )
    admin_a = User(
        id=f"adm-a-{uuid.uuid4().hex[:6]}",
        organization_id=org_a.id,
        email="admin@alpha.edu",
        full_name="Admin Alpha",
        role=UserRole.ORG_ADMIN,
        is_active=True,
    )
    db.create_user(student_a)
    db.create_user(student_b)
    db.create_user(admin_a)

    # 3. Setup Edge Device in Org A
    edge_svc = EdgeSyncService(db)
    device_secret = f"devsecret_{uuid.uuid4().hex[:12]}"
    device_a = edge_svc.register_device(
        organization_id=org_a.id,
        device_code=f"BIO-GATE-{uuid.uuid4().hex[:6]}",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Main Gate Terminal",
        secret_plaintext=device_secret,
    )

    # 4. Setup Revoked Device in Org A
    revoked_secret = f"revsecret_{uuid.uuid4().hex[:12]}"
    device_revoked = edge_svc.register_device(
        organization_id=org_a.id,
        device_code=f"BIO-OLD-{uuid.uuid4().hex[:6]}",
        device_type=DeviceType.BIOMETRIC_TERMINAL,
        device_name="Old Decommissioned Gate",
        secret_plaintext=revoked_secret,
    )
    edge_svc.revoke_device(org_a.id, device_revoked.id, reason="Broken sensor")

    # Tokens
    token_admin_a = create_access_token(user_id=admin_a.id, role="org_admin", organization_id=org_a.id)

    app.dependency_overrides[get_db] = lambda: db

    yield {
        "db": db,
        "db_path": db_path,
        "org_a": org_a,
        "org_b": org_b,
        "student_a": student_a,
        "student_b": student_b,
        "admin_a": admin_a,
        "token_admin_a": token_admin_a,
        "device_a": device_a,
        "device_secret": device_secret,
        "device_revoked": device_revoked,
        "revoked_secret": revoked_secret,
        "edge_svc": edge_svc,
    }

    app.dependency_overrides.pop(get_db, None)


# ── 1. Enum Validation Rejections (HTTP 422) ──────────────────────────────────

def test_invalid_device_type_rejected_with_422(phase05_env):
    """QA-005: Registering device with invalid device_type rejects with HTTP 422 (never coerced)."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {phase05_env['token_admin_a']}"}

    resp = client.post(
        "/api/v1/edge/devices/register",
        headers=headers,
        json={
            "device_code": "BIO-TEST-001",
            "device_type": "QUANTUM_TELEPORTER",  # Invalid type
            "device_name": "Invalid Device",
            "secret": "secret123",
        },
    )
    assert resp.status_code == 422
    assert "device_type" in resp.text.lower()


def test_invalid_punch_type_rejected_with_422(phase05_env):
    """QA-005: Punch batch with unrecognized punch_type rejects with HTTP 422."""
    client = TestClient(app)
    device = phase05_env["device_a"]
    now_str = datetime.now(timezone.utc).isoformat()

    resp = client.post(
        "/api/v1/edge/punches/batch",
        headers={"X-Device-Secret": phase05_env["device_secret"]},
        json={
            "device_id": device.id,
            "punches": [
                {
                    "user_id": phase05_env["student_a"].id,
                    "punch_type": "COFFEE_BREAK",  # Invalid punch type
                    "punch_time": now_str,
                    "verification_type": "FINGERPRINT",
                    "idempotency_key": "p-invalid-1",
                }
            ],
        },
    )
    assert resp.status_code == 422
    assert "punch_type" in resp.text.lower()


def test_invalid_verification_type_rejected_with_422(phase05_env):
    """QA-005: Punch batch with unrecognized verification_type rejects with HTTP 422."""
    client = TestClient(app)
    device = phase05_env["device_a"]
    now_str = datetime.now(timezone.utc).isoformat()

    resp = client.post(
        "/api/v1/edge/punches/batch",
        headers={"X-Device-Secret": phase05_env["device_secret"]},
        json={
            "device_id": device.id,
            "punches": [
                {
                    "user_id": phase05_env["student_a"].id,
                    "punch_type": "CHECK_IN",
                    "punch_time": now_str,
                    "verification_type": "RETINAL_SCAN",  # Invalid verification type
                    "idempotency_key": "p-invalid-2",
                }
            ],
        },
    )
    assert resp.status_code == 422
    assert "verification_type" in resp.text.lower()


def test_invalid_conflict_strategy_rejected_with_422(phase05_env):
    """QA-005: Resolving conflict with invalid strategy rejects with HTTP 422 (never coerced)."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {phase05_env['token_admin_a']}"}

    resp = client.post(
        "/api/v1/edge/conflicts/cnf-fake-123/resolve",
        headers=headers,
        json={"strategy": "COIN_FLIP"},  # Invalid strategy
    )
    assert resp.status_code == 422
    assert "strategy" in resp.text.lower()


# ── 2. Device Heartbeat Authentication & Lifecycle ───────────────────────────

def test_heartbeat_requires_device_credentials_or_user_auth(phase05_env):
    """QA-005: Unauthenticated heartbeat without credentials is rejected with HTTP 401."""
    client = TestClient(app)
    device = phase05_env["device_a"]

    resp = client.post(
        "/api/v1/edge/devices/heartbeat",
        json={"device_id": device.id},
    )
    assert resp.status_code == 401
    assert "Missing device authentication credentials" in resp.json()["detail"]


def test_heartbeat_rejects_invalid_secret_with_401(phase05_env):
    """QA-005: Heartbeat with wrong secret is rejected with HTTP 401."""
    client = TestClient(app)
    device = phase05_env["device_a"]

    resp = client.post(
        "/api/v1/edge/devices/heartbeat",
        headers={"X-Device-Secret": "wrong_secret_123"},
        json={"device_id": device.id},
    )
    assert resp.status_code == 401
    assert "Invalid device credentials" in resp.json()["detail"]


def test_heartbeat_rejects_unknown_device_with_404(phase05_env):
    """QA-005: Heartbeat for non-existent device is rejected with HTTP 404."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/edge/devices/heartbeat",
        headers={"X-Device-Secret": "any_secret"},
        json={"device_id": "dev-nonexistent-999"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_heartbeat_rejects_revoked_device_with_403(phase05_env):
    """QA-005: Heartbeat for a revoked device is rejected with HTTP 403."""
    client = TestClient(app)
    revoked = phase05_env["device_revoked"]

    resp = client.post(
        "/api/v1/edge/devices/heartbeat",
        headers={"X-Device-Secret": phase05_env["revoked_secret"]},
        json={"device_id": revoked.id},
    )
    assert resp.status_code == 403
    assert "REVOKED" in resp.json()["detail"]


def test_heartbeat_durable_ack_with_valid_secret(phase05_env):
    """QA-005: Verified device heartbeat durably records heartbeat and responds ACK."""
    client = TestClient(app)
    device = phase05_env["device_a"]

    resp = client.post(
        "/api/v1/edge/devices/heartbeat",
        headers={"X-Device-Secret": phase05_env["device_secret"]},
        json={
            "device_id": device.id,
            "ip_address": "192.168.1.50",
            "firmware_version": "v2.4.1",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACK"
    assert data["device_id"] == device.id
    assert data["organization_id"] == phase05_env["org_a"].id

    # Verify Database row updated durably
    with phase05_env["db"]._get_connection() as conn:
        row = conn.execute("SELECT last_heartbeat_at, ip_address, firmware_version FROM edge_devices WHERE id = ?;", (device.id,)).fetchone()
        assert row[0] is not None
        assert row[1] == "192.168.1.50"
        assert row[2] == "v2.4.1"


# ── 3. Punch Batch Authentication & Tenant Mapping ───────────────────────────

def test_punch_batch_requires_device_credentials_or_user_auth(phase05_env):
    """QA-005: Unauthenticated punch batch without credentials is rejected with HTTP 401."""
    client = TestClient(app)
    device = phase05_env["device_a"]
    now_str = datetime.now(timezone.utc).isoformat()

    resp = client.post(
        "/api/v1/edge/punches/batch",
        json={
            "device_id": device.id,
            "punches": [
                {
                    "user_id": phase05_env["student_a"].id,
                    "punch_type": "CHECK_IN",
                    "punch_time": now_str,
                    "verification_type": "FINGERPRINT",
                    "idempotency_key": "p-unauth-1",
                }
            ],
        },
    )
    assert resp.status_code == 401
    assert "Missing device authentication credentials" in resp.json()["detail"]


def test_punch_batch_derives_tenant_from_device_rejects_mismatch(phase05_env):
    """QA-005: Organization is derived from device. Mismatched X-Organization-ID is rejected with HTTP 400."""
    client = TestClient(app)
    device = phase05_env["device_a"]  # Belongs to org_a
    attacker_org = phase05_env["org_b"].id
    now_str = datetime.now(timezone.utc).isoformat()

    resp = client.post(
        "/api/v1/edge/punches/batch",
        headers={
            "X-Device-Secret": phase05_env["device_secret"],
            "X-Organization-ID": attacker_org,  # Spoofed org
        },
        json={
            "device_id": device.id,
            "punches": [
                {
                    "user_id": phase05_env["student_a"].id,
                    "punch_type": "CHECK_IN",
                    "punch_time": now_str,
                    "verification_type": "FINGERPRINT",
                    "idempotency_key": "p-spoof-1",
                }
            ],
        },
    )
    assert resp.status_code == 400
    assert "Organization mismatch" in resp.json()["detail"]


def test_punch_batch_rejects_revoked_device_with_403(phase05_env):
    """QA-005: Punch batch from revoked device is rejected with HTTP 403."""
    client = TestClient(app)
    revoked = phase05_env["device_revoked"]
    now_str = datetime.now(timezone.utc).isoformat()

    resp = client.post(
        "/api/v1/edge/punches/batch",
        headers={"X-Device-Secret": phase05_env["revoked_secret"]},
        json={
            "device_id": revoked.id,
            "punches": [
                {
                    "user_id": phase05_env["student_a"].id,
                    "punch_type": "CHECK_IN",
                    "punch_time": now_str,
                    "verification_type": "FINGERPRINT",
                    "idempotency_key": "p-rev-1",
                }
            ],
        },
    )
    assert resp.status_code == 403
    assert "REVOKED" in resp.json()["detail"]


def test_punch_batch_idempotency_and_dead_letter_isolation(phase05_env):
    """QA-005: Valid punch commits, duplicate punch marked DUPLICATE without duplicate rows, unknown user quarantined."""
    client = TestClient(app)
    device = phase05_env["device_a"]
    student_a = phase05_env["student_a"]
    now_str = datetime.now(timezone.utc).isoformat()

    key1 = f"key-valid-{uuid.uuid4().hex[:8]}"
    key_unknown = f"key-unknown-{uuid.uuid4().hex[:8]}"

    payload = {
        "device_id": device.id,
        "punches": [
            {
                "user_id": student_a.id,
                "punch_type": "CHECK_IN",
                "punch_time": now_str,
                "verification_type": "FINGERPRINT",
                "idempotency_key": key1,
            },
            {
                "user_id": "usr-unknown-ghost-999",
                "punch_type": "CHECK_IN",
                "punch_time": now_str,
                "verification_type": "RFID_CARD",
                "idempotency_key": key_unknown,
            },
        ],
    }

    # First Batch Ingestion
    resp1 = client.post(
        "/api/v1/edge/punches/batch",
        headers={"X-Device-Secret": phase05_env["device_secret"]},
        json=payload,
    )
    assert resp1.status_code == 200
    res1 = resp1.json()
    assert res1["acknowledged"] == 1
    assert res1["failed"] == 1
    assert res1["item_statuses"][key1] == "ACKNOWLEDGED"
    assert res1["item_statuses"][key_unknown] == "FAILED"

    # Second Delivery: Exact same batch
    resp2 = client.post(
        "/api/v1/edge/punches/batch",
        headers={"X-Device-Secret": phase05_env["device_secret"]},
        json=payload,
    )
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["duplicates"] == 2
    assert res2["item_statuses"][key1] == "DUPLICATE"
    assert res2["item_statuses"][key_unknown] == "DUPLICATE"

    # Verify Database state
    with phase05_env["db"]._get_connection() as conn:
        # Exactly 1 row for key1 in edge_punches
        punch_rows = conn.execute("SELECT COUNT(*) FROM edge_punches WHERE idempotency_key = ?;", (key1,)).fetchone()[0]
        assert punch_rows == 1

        # Exactly 1 row in dead letter queue for key_unknown
        dlq_rows = conn.execute("SELECT COUNT(*) FROM sync_dead_letter_queue WHERE operation_id = ?;", (key_unknown,)).fetchone()[0]
        assert dlq_rows == 1


# ── 4. Restart Durability & Truthful Simulation ───────────────────────────────

def test_durable_read_back_across_db_restart(phase05_env):
    """QA-005: Edge punches and device metadata survive process restart and read back accurately."""
    client = TestClient(app)
    device = phase05_env["device_a"]
    student_a = phase05_env["student_a"]
    now_str = datetime.now(timezone.utc).isoformat()
    key_durable = f"key-dur-{uuid.uuid4().hex[:8]}"

    resp = client.post(
        "/api/v1/edge/punches/batch",
        headers={"X-Device-Secret": phase05_env["device_secret"]},
        json={
            "device_id": device.id,
            "punches": [
                {
                    "user_id": student_a.id,
                    "punch_type": "CHECK_OUT",
                    "punch_time": now_str,
                    "verification_type": "FACIAL",
                    "idempotency_key": key_durable,
                }
            ],
        },
    )
    assert resp.status_code == 200

    # Instantiate fresh DB instance
    restarted_db = PlatformDatabase(phase05_env["db_path"])
    restarted_svc = EdgeSyncService(restarted_db)

    # Read back device and punches
    read_device = restarted_svc.get_device(phase05_env["org_a"].id, device.id)
    assert read_device is not None
    assert read_device.device_name == "Main Gate Terminal"

    with restarted_db._get_connection() as conn:
        r = conn.execute(
            "SELECT user_id, punch_type, verification_type, status FROM edge_punches WHERE idempotency_key = ?;",
            (key_durable,),
        ).fetchone()
        assert r is not None
        assert r[0] == student_a.id
        assert r[1] == "CHECK_OUT"
        assert r[2] == "FACIAL"
        assert r[3] == "ACKNOWLEDGED"


def test_hardware_driver_disclosures_truthful_simulation():
    """QA-005: In accordance with audit invariants, simulated drivers are labeled SIMULATED."""
    sim = SimulatedBiometricDriver(device_id="SIM-BIO-001")
    assert sim.is_simulated is True
    assert "simulated" in sim.driver_name.lower()
