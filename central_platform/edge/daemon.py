"""Gayatri School OS — Edge Biometric Daemon (Phase 07).

Standalone edge daemon process managing hardware I/O, local outbox persistence,
and network synchronization with per-item acknowledgement semantics.

Architectural Guarantees:
1. Sandboxed hardware I/O: Sensor errors, disconnects, or timeouts never propagate into UI or AI runtimes.
2. Durable disk outbox: Punches survive process restarts and power cuts.
3. Idempotent punch generation: Unique composite keys prevent replay duplication.
4. Independent restartability: Can be stopped, restarted, and reconnected without loss.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from central_platform.edge.drivers.base import (
    AbstractBiometricDriver,
    HardwareDeviceError,
    HardwareTimeoutError,
)

logger = logging.getLogger("gayatri.edge.daemon")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EdgeDaemon:
    """Manages local edge hardware reading and durable queue synchronization."""

    def __init__(
        self,
        device_id: str,
        device_secret: str,
        organization_id: str,
        driver: AbstractBiometricDriver,
        outbox_db_path: str = ":memory:",
    ):
        self.device_id = device_id
        self.device_secret = device_secret
        self.organization_id = organization_id
        self.driver = driver
        self.outbox_db_path = outbox_db_path

        if self.outbox_db_path != ":memory:":
            Path(self.outbox_db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.outbox_db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_outbox_schema()

        self.hardware_fault_count: int = 0
        self.last_hardware_fault: Optional[str] = None

    def _init_outbox_schema(self) -> None:
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS local_outbox (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    punch_type TEXT NOT NULL,
                    punch_time TEXT NOT NULL,
                    verification_type TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_outbox_status_created
                ON local_outbox (status, created_at);
            """)

    def poll_hardware_once(self) -> Optional[Dict[str, Any]]:
        """Safely poll hardware sensor for one punch.
        
        Catches all hardware exceptions without crashing the daemon or caller.
        """
        try:
            frame = self.driver.read_punch()
            if frame is None:
                return None

            punch_id = f"pch-{uuid.uuid4().hex[:12]}"
            idempotency_key = f"{self.device_id}:{frame.user_id}:{frame.punch_time}:{frame.punch_type}"

            with self._conn:
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO local_outbox
                    (id, user_id, punch_type, punch_time, verification_type, idempotency_key, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?);
                    """,
                    (
                        punch_id,
                        frame.user_id,
                        frame.punch_type,
                        frame.punch_time,
                        frame.verification_type,
                        idempotency_key,
                        _now_iso(),
                    ),
                )

            return {
                "id": punch_id,
                "user_id": frame.user_id,
                "punch_type": frame.punch_type,
                "punch_time": frame.punch_time,
                "verification_type": frame.verification_type,
                "idempotency_key": idempotency_key,
            }

        except (HardwareDeviceError, HardwareTimeoutError, ValueError, Exception) as exc:
            self.hardware_fault_count += 1
            self.last_hardware_fault = str(exc)
            logger.warning("Hardware poll fault on device %s: %s", self.device_id, exc)
            return None

    def get_pending_punches(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch pending punches from local outbox for synchronization."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, punch_type, punch_time, verification_type, idempotency_key, retry_count
            FROM local_outbox
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def record_sync_results(self, item_statuses: Dict[str, str], errors: Optional[Dict[str, str]] = None) -> None:
        """Update outbox items with per-item status from central platform acknowledgement.
        
        item_statuses: dict mapping idempotency_key -> status ('ACKNOWLEDGED', 'DUPLICATE', 'FAILED', 'CONFLICT')
        """
        errors = errors or {}
        with self._conn:
            for key, status_code in item_statuses.items():
                if status_code in ("ACKNOWLEDGED", "DUPLICATE"):
                    self._conn.execute(
                        "UPDATE local_outbox SET status = 'ACKNOWLEDGED' WHERE idempotency_key = ?;",
                        (key,),
                    )
                else:
                    err_msg = errors.get(key, f"Sync rejected with {status_code}")
                    self._conn.execute(
                        """
                        UPDATE local_outbox
                        SET status = 'FAILED', retry_count = retry_count + 1, last_error = ?
                        WHERE idempotency_key = ?;
                        """,
                        (err_msg, key),
                    )

    def get_outbox_stats(self) -> Dict[str, Any]:
        """Return diagnostic metrics of local outbox and hardware status."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT status, count(*) FROM local_outbox GROUP BY status;")
        counts = {r[0]: r[1] for r in cursor.fetchall()}

        return {
            "device_id": self.device_id,
            "organization_id": self.organization_id,
            "pending_count": counts.get("PENDING", 0),
            "acknowledged_count": counts.get("ACKNOWLEDGED", 0),
            "failed_count": counts.get("FAILED", 0),
            "hardware_fault_count": self.hardware_fault_count,
            "last_hardware_fault": self.last_hardware_fault,
            "is_driver_connected": self.driver.is_connected(),
        }

    def close(self) -> None:
        """Gracefully release database and hardware resources."""
        self._conn.close()
