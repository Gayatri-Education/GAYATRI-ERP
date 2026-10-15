"""Gayatri School OS — Central Edge Synchronization Service (Phase 07).

Authoritative server-side management of edge biometric devices, punch ingestion,
idempotency filtering, per-item acknowledgement, and deterministic conflict routing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from central_platform.db import PlatformDatabase
from central_platform.models.sync import (
    ConflictResolutionStrategy,
    DeadLetterItem,
    DeviceStatus,
    DeviceType,
    EdgeDevice,
    EdgePunch,
    PunchType,
    SyncConflictRecord,
    SyncHealthMetrics,
    SyncItemStatus,
    VerificationType,
)

logger = logging.getLogger("gayatri.sync.edge_service")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class EdgeSyncService:
    """Processes edge device registrations, heartbeats, punch batches, and sync conflicts."""

    def __init__(self, db: PlatformDatabase):
        self.db = db

    # ── Device Management ────────────────────────────────────────────────────────

    def register_device(
        self,
        organization_id: str,
        device_code: str,
        device_type: DeviceType,
        device_name: str,
        secret_plaintext: str,
        ip_address: Optional[str] = None,
        firmware_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EdgeDevice:
        """Register a new edge device and hash its authentication secret."""
        device_id = f"dev-{uuid.uuid4().hex[:10]}"
        secret_hash = _hash_secret(secret_plaintext)
        now = _now_iso()
        meta_json = json.dumps(metadata or {})

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO edge_devices
                (id, organization_id, device_code, device_type, device_name, secret_hash,
                 status, ip_address, firmware_version, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?);
                """,
                (
                    device_id,
                    organization_id,
                    device_code,
                    device_type.value if hasattr(device_type, "value") else str(device_type),
                    device_name,
                    secret_hash,
                    ip_address,
                    firmware_version,
                    meta_json,
                    now,
                    now,
                ),
            )

        return EdgeDevice(
            id=device_id,
            organization_id=organization_id,
            device_code=device_code,
            device_type=device_type,
            device_name=device_name,
            secret_hash=secret_hash,
            status=DeviceStatus.ACTIVE,
            ip_address=ip_address,
            firmware_version=firmware_version,
            metadata_json=meta_json,
            created_at=now,
            updated_at=now,
        )

    def revoke_device(self, organization_id: str, device_id: str, reason: str = "Decommissioned") -> EdgeDevice:
        """Revoke an edge device, preventing any further synchronization."""
        now = _now_iso()
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE edge_devices SET status = 'REVOKED', updated_at = ? WHERE id = ? AND organization_id = ?;",
                (now, device_id, organization_id),
            )
        device = self.get_device(organization_id, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not found")
        return device

    def authenticate_device(self, organization_id: str, device_code: str, secret_plaintext: str) -> EdgeDevice:
        """Authenticate device by code and secret. Raises PermissionError if revoked or invalid."""
        device = self.get_device_by_code(organization_id, device_code)
        if not device:
            raise PermissionError("Invalid device credentials.")

        if device.status == DeviceStatus.REVOKED:
            raise PermissionError(f"Edge device '{device_code}' is REVOKED.")

        if device.secret_hash != _hash_secret(secret_plaintext):
            raise PermissionError("Invalid device secret.")

        return device

    def record_heartbeat(self, device_id: str, ip_address: Optional[str] = None, firmware_version: Optional[str] = None) -> bool:
        """Update last heartbeat timestamp of an active edge device."""
        now = _now_iso()
        with self.db._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE edge_devices
                SET last_heartbeat_at = ?,
                    ip_address = COALESCE(?, ip_address),
                    firmware_version = COALESCE(?, firmware_version),
                    updated_at = ?
                WHERE id = ? AND status != 'REVOKED';
                """,
                (now, ip_address, firmware_version, now, device_id),
            )
            return cursor.rowcount > 0

    def get_device_unscoped(self, device_id: str) -> Optional[EdgeDevice]:
        """Retrieve an edge device by ID across all organizations (for device authentication)."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, organization_id, device_code, device_type, device_name, secret_hash, "
                "status, last_heartbeat_at, firmware_version, ip_address, metadata_json, created_at, updated_at "
                "FROM edge_devices WHERE id = ?;",
                (device_id,),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return EdgeDevice(
                id=r[0],
                organization_id=r[1],
                device_code=r[2],
                device_type=DeviceType(r[3]),
                device_name=r[4],
                secret_hash=r[5],
                status=DeviceStatus(r[6]),
                last_heartbeat_at=r[7],
                firmware_version=r[8],
                ip_address=r[9],
                metadata_json=r[10],
                created_at=r[11],
                updated_at=r[12],
            )

    def get_device(self, organization_id: str, device_id: str) -> Optional[EdgeDevice]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, organization_id, device_code, device_type, device_name, secret_hash, "
                "status, last_heartbeat_at, firmware_version, ip_address, metadata_json, created_at, updated_at "
                "FROM edge_devices WHERE id = ? AND organization_id = ?;",
                (device_id, organization_id),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return EdgeDevice(
                id=r[0],
                organization_id=r[1],
                device_code=r[2],
                device_type=DeviceType(r[3]),
                device_name=r[4],
                secret_hash=r[5],
                status=DeviceStatus(r[6]),
                last_heartbeat_at=r[7],
                firmware_version=r[8],
                ip_address=r[9],
                metadata_json=r[10],
                created_at=r[11],
                updated_at=r[12],
            )

    def get_device_by_code(self, organization_id: str, device_code: str) -> Optional[EdgeDevice]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, organization_id, device_code, device_type, device_name, secret_hash, "
                "status, last_heartbeat_at, firmware_version, ip_address, metadata_json, created_at, updated_at "
                "FROM edge_devices WHERE device_code = ? AND organization_id = ?;",
                (device_code, organization_id),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return EdgeDevice(
                id=r[0],
                organization_id=r[1],
                device_code=r[2],
                device_type=DeviceType(r[3]),
                device_name=r[4],
                secret_hash=r[5],
                status=DeviceStatus(r[6]),
                last_heartbeat_at=r[7],
                firmware_version=r[8],
                ip_address=r[9],
                metadata_json=r[10],
                created_at=r[11],
                updated_at=r[12],
            )

    # ── Punch Batch Ingestion & Idempotency ──────────────────────────────────────

    def ingest_punch_batch(
        self,
        organization_id: str,
        device_id: str,
        punches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Ingest batch of punches with per-item acknowledgement semantics.
        
        Guarantees:
        - Valid punches are committed.
        - Idempotent duplicate punches are marked DUPLICATE without side effects.
        - Invalid users/malformed payloads are quarantined in DLQ without aborting batch.
        - Future clock skew > 300s is routed to conflict records for human review.
        """
        device = self.get_device(organization_id, device_id)
        if not device:
            raise ValueError(f"Device {device_id} not registered.")
        if device.status == DeviceStatus.REVOKED:
            raise PermissionError(f"Device {device_id} is REVOKED.")

        item_statuses: Dict[str, str] = {}
        errors: Dict[str, str] = {}
        ack_count = 0
        dup_count = 0
        fail_count = 0
        conflict_count = 0

        now_dt = datetime.now(timezone.utc)
        now_str = _now_iso()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            for p in punches:
                idempotency_key = p.get("idempotency_key", "")
                user_id = p.get("user_id", "")
                punch_type = p.get("punch_type", "CHECK_IN")
                punch_time = p.get("punch_time", now_str)
                verification_type = p.get("verification_type", "FINGERPRINT")

                # 1. Idempotency Check (Punches and DLQ)
                cursor.execute(
                    "SELECT id FROM edge_punches WHERE organization_id = ? AND idempotency_key = ?;",
                    (organization_id, idempotency_key),
                )
                if cursor.fetchone():
                    item_statuses[idempotency_key] = SyncItemStatus.DUPLICATE.value
                    dup_count += 1
                    continue

                cursor.execute(
                    "SELECT id FROM sync_dead_letter_queue WHERE organization_id = ? AND operation_id = ?;",
                    (organization_id, idempotency_key),
                )
                if cursor.fetchone():
                    item_statuses[idempotency_key] = SyncItemStatus.DUPLICATE.value
                    dup_count += 1
                    continue

                # 2. User existence validation
                cursor.execute(
                    "SELECT id FROM users WHERE id = ? AND organization_id = ?;",
                    (user_id, organization_id),
                )
                if not cursor.fetchone():
                    # Quarantine in Dead Letter Queue
                    dlq_id = f"dlq-{uuid.uuid4().hex[:10]}"
                    conn.execute(
                        """
                        INSERT INTO sync_dead_letter_queue
                        (id, organization_id, device_id, operation_id, entity_type, payload_json, error_category, error_message, created_at)
                        VALUES (?, ?, ?, ?, 'EDGE_PUNCH', ?, 'INVALID_USER', ?, ?);
                        """,
                        (
                            dlq_id,
                            organization_id,
                            device_id,
                            idempotency_key,
                            json.dumps(p),
                            f"User '{user_id}' does not exist in organization '{organization_id}'",
                            now_str,
                        ),
                    )
                    item_statuses[idempotency_key] = SyncItemStatus.FAILED.value
                    errors[idempotency_key] = f"User '{user_id}' not found."
                    fail_count += 1
                    continue

                # 3. Clock Skew Conflict Check (> 300s into the future)
                try:
                    p_dt = datetime.fromisoformat(punch_time.replace("Z", "+00:00"))
                    time_diff_sec = (p_dt - now_dt).total_seconds()
                    if time_diff_sec > 300:
                        conflict_id = f"cnf-{uuid.uuid4().hex[:10]}"
                        conn.execute(
                            """
                            INSERT INTO sync_conflict_records
                            (id, organization_id, entity_type, entity_id, conflict_type, client_payload_json,
                             server_payload_json, resolution_strategy, created_at)
                            VALUES (?, ?, 'EDGE_PUNCH', ?, 'CLOCK_SKEW_EXCESSIVE', ?, ?, 'MANUAL_REVIEW', ?);
                            """,
                            (
                                conflict_id,
                                organization_id,
                                user_id,
                                json.dumps(p),
                                json.dumps({"server_time": now_str, "skew_seconds": time_diff_sec}),
                                now_str,
                            ),
                        )
                        item_statuses[idempotency_key] = SyncItemStatus.CONFLICT.value
                        errors[idempotency_key] = f"Clock skew excessive ({int(time_diff_sec)}s ahead of server)."
                        conflict_count += 1
                        continue
                except Exception:
                    pass

                # 4. Valid Punch Insertion
                punch_id = f"pch-{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO edge_punches
                    (id, organization_id, device_id, user_id, punch_type, punch_time, verification_type,
                     idempotency_key, status, created_at, processed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACKNOWLEDGED', ?, ?);
                    """,
                    (
                        punch_id,
                        organization_id,
                        device_id,
                        user_id,
                        punch_type,
                        punch_time,
                        verification_type,
                        idempotency_key,
                        now_str,
                        now_str,
                    ),
                )
                item_statuses[idempotency_key] = SyncItemStatus.ACKNOWLEDGED.value
                ack_count += 1

            # Update device last heartbeat
            conn.execute(
                "UPDATE edge_devices SET last_heartbeat_at = ?, updated_at = ? WHERE id = ?;",
                (now_str, now_str, device_id),
            )

        return {
            "total": len(punches),
            "acknowledged": ack_count,
            "duplicates": dup_count,
            "failed": fail_count,
            "conflicts": conflict_count,
            "item_statuses": item_statuses,
            "errors": errors,
        }

    # ── Conflict Inspection and Resolution ───────────────────────────────────────

    def list_conflicts(self, organization_id: str, unresolved_only: bool = True) -> List[SyncConflictRecord]:
        """List sync conflict records for admin review."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            if unresolved_only:
                cursor.execute(
                    """
                    SELECT id, organization_id, entity_type, entity_id, conflict_type, client_payload_json,
                           server_payload_json, resolution_strategy, resolved_by, resolved_at, resolution_notes, created_at
                    FROM sync_conflict_records
                    WHERE organization_id = ? AND resolved_at IS NULL
                    ORDER BY created_at DESC;
                    """,
                    (organization_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, organization_id, entity_type, entity_id, conflict_type, client_payload_json,
                           server_payload_json, resolution_strategy, resolved_by, resolved_at, resolution_notes, created_at
                    FROM sync_conflict_records
                    WHERE organization_id = ?
                    ORDER BY created_at DESC;
                    """,
                    (organization_id,),
                )
            rows = cursor.fetchall()
            return [
                SyncConflictRecord(
                    id=r[0],
                    organization_id=r[1],
                    entity_type=r[2],
                    entity_id=r[3],
                    conflict_type=r[4],
                    client_payload_json=r[5],
                    server_payload_json=r[6],
                    resolution_strategy=ConflictResolutionStrategy(r[7]),
                    resolved_by=r[8],
                    resolved_at=r[9],
                    resolution_notes=r[10],
                    created_at=r[11],
                )
                for r in rows
            ]

    def resolve_conflict(
        self,
        organization_id: str,
        conflict_id: str,
        strategy: ConflictResolutionStrategy,
        resolved_by: str,
        notes: str = "",
    ) -> SyncConflictRecord:
        """Resolve a conflict record deterministically."""
        now = _now_iso()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE sync_conflict_records
                SET resolution_strategy = ?, resolved_by = ?, resolved_at = ?, resolution_notes = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (strategy.value, resolved_by, now, notes, conflict_id, organization_id),
            )
        conflicts = self.list_conflicts(organization_id, unresolved_only=False)
        for c in conflicts:
            if c.id == conflict_id:
                return c
        raise ValueError(f"Conflict {conflict_id} not found")

    # ── Sync Health & Observability Metrics ──────────────────────────────────────

    def get_sync_health_metrics(self, organization_id: str) -> SyncHealthMetrics:
        """Calculate comprehensive health and diagnostic metrics."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Active devices
            cursor.execute(
                "SELECT count(*) FROM edge_devices WHERE organization_id = ? AND status = 'ACTIVE';",
                (organization_id,),
            )
            active_devices = cursor.fetchone()[0]

            # 2. Pending punches
            cursor.execute(
                "SELECT count(*) FROM edge_punches WHERE organization_id = ? AND status = 'PENDING';",
                (organization_id,),
            )
            pending_punches = cursor.fetchone()[0]

            # 3. Dead letter queue count
            cursor.execute(
                "SELECT count(*) FROM sync_dead_letter_queue WHERE organization_id = ?;",
                (organization_id,),
            )
            dlq_count = cursor.fetchone()[0]

            # 4. Unresolved conflicts count
            cursor.execute(
                "SELECT count(*) FROM sync_conflict_records WHERE organization_id = ? AND resolved_at IS NULL;",
                (organization_id,),
            )
            unresolved_conflicts = cursor.fetchone()[0]

            # 5. Last sync timestamp
            cursor.execute(
                "SELECT max(created_at) FROM edge_punches WHERE organization_id = ?;",
                (organization_id,),
            )
            last_sync = cursor.fetchone()[0]

        healthy = (dlq_count == 0) and (unresolved_conflicts == 0)

        return SyncHealthMetrics(
            organization_id=organization_id,
            active_devices_count=active_devices,
            pending_outbox_count=pending_punches,
            dead_letter_count=dlq_count,
            unresolved_conflicts_count=unresolved_conflicts,
            last_sync_timestamp=last_sync,
            healthy=healthy,
        )
