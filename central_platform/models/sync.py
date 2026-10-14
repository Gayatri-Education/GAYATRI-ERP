"""Gayatri School OS — Edge Devices & Offline Sync Domain Models (Phase 07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeviceType(str, Enum):
    BIOMETRIC_TERMINAL = "BIOMETRIC_TERMINAL"
    RFID_GATE = "RFID_GATE"
    DESKTOP_CLIENT = "DESKTOP_CLIENT"
    MOBILE_SCANNER = "MOBILE_SCANNER"


class DeviceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    SUSPENDED = "SUSPENDED"


class PunchType(str, Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"
    BREAK_START = "BREAK_START"
    BREAK_END = "BREAK_END"


class VerificationType(str, Enum):
    FINGERPRINT = "FINGERPRINT"
    RFID_CARD = "RFID_CARD"
    FACIAL = "FACIAL"
    PIN = "PIN"


class SyncItemStatus(str, Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"
    CONFLICT = "CONFLICT"
    DUPLICATE = "DUPLICATE"


class ConflictResolutionStrategy(str, Enum):
    AUTO_MERGED = "AUTO_MERGED"
    LAST_WRITE_WINS = "LAST_WRITE_WINS"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass
class EdgeDevice:
    id: str
    organization_id: str
    device_code: str
    device_type: DeviceType
    device_name: str
    secret_hash: str
    status: DeviceStatus = DeviceStatus.ACTIVE
    last_heartbeat_at: Optional[str] = None
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    metadata_json: str = "{}"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass
class EdgePunch:
    id: str
    organization_id: str
    device_id: str
    user_id: str
    punch_type: PunchType
    punch_time: str
    verification_type: VerificationType
    idempotency_key: str
    status: SyncItemStatus = SyncItemStatus.PENDING
    created_at: str = field(default_factory=_now_iso)
    processed_at: Optional[str] = None


@dataclass
class SyncConflictRecord:
    id: str
    organization_id: str
    entity_type: str
    entity_id: str
    conflict_type: str
    client_payload_json: str
    server_payload_json: str
    resolution_strategy: ConflictResolutionStrategy
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)


@dataclass
class DeadLetterItem:
    id: str
    organization_id: str
    device_id: str
    operation_id: str
    entity_type: str
    payload_json: str
    error_category: str
    error_message: str
    retry_count: int = 0
    created_at: str = field(default_factory=_now_iso)


@dataclass
class SyncHealthMetrics:
    organization_id: str
    active_devices_count: int
    pending_outbox_count: int
    dead_letter_count: int
    unresolved_conflicts_count: int
    last_sync_timestamp: Optional[str]
    healthy: bool
