"""Gayatri School OS — Platform Support Diagnostics & Health Auditing (Phase 08).

Collects redacted, safe operational diagnostics:
- Database schema version and applied migrations
- SQL PRAGMA integrity check
- Table row counts
- Sync health & edge hardware connectivity
- Redacts all passwords, API keys, and device secret hashes.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from central_platform.db import PlatformDatabase

logger = logging.getLogger("gayatri.ops.diagnostics")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlatformDiagnosticsService:
    """Produces verified, redacted system health diagnostic packages."""

    def __init__(self, db: PlatformDatabase):
        self.db = db

    def generate_diagnostic_package(
        self,
        organization_id: str,
        requested_by: str = "system",
    ) -> Dict[str, Any]:
        """Generate safe, sanitized platform diagnostic report."""
        snapshot_id = f"diag-{uuid.uuid4().hex[:10]}"
        now = _now_iso()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. PRAGMA integrity_check
            try:
                cursor.execute("PRAGMA integrity_check;")
                check_result = cursor.fetchone()[0]
                integrity_ok = (check_result == "ok")
            except Exception as exc:
                integrity_ok = False
                check_result = str(exc)

            # 2. Applied Migrations
            try:
                cursor.execute("SELECT version, description, applied_at FROM schema_migrations ORDER BY version ASC;")
                migrations = [{"version": r[0], "description": r[1], "applied_at": r[2]} for r in cursor.fetchall()]
            except Exception:
                migrations = []

            # 3. Table counts (Sanitized)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [r[0] for r in cursor.fetchall()]
            table_counts = {}
            for tbl in tables:
                cursor.execute(f"SELECT count(*) FROM {tbl};")
                table_counts[tbl] = cursor.fetchone()[0]

            # 4. Edge devices summary (strictly redacted secret hashes)
            cursor.execute(
                """
                SELECT id, device_code, device_type, device_name, status, last_heartbeat_at, firmware_version
                FROM edge_devices
                WHERE organization_id = ?;
                """,
                (organization_id,),
            )
            devices = [
                {
                    "id": r[0],
                    "device_code": r[1],
                    "device_type": r[2],
                    "device_name": r[3],
                    "status": r[4],
                    "last_heartbeat_at": r[5],
                    "firmware_version": r[6],
                    "secret_hash": "[REDACTED]",
                }
                for r in cursor.fetchall()
            ]

            # 5. Dead letter queue and conflict summary
            cursor.execute(
                "SELECT count(*) FROM sync_dead_letter_queue WHERE organization_id = ?;",
                (organization_id,),
            )
            dlq_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT count(*) FROM sync_conflict_records WHERE organization_id = ? AND resolved_at IS NULL;",
                (organization_id,),
            )
            unresolved_conflicts = cursor.fetchone()[0]

            package = {
                "snapshot_id": snapshot_id,
                "organization_id": organization_id,
                "generated_at": now,
                "requested_by": requested_by,
                "database_integrity": {
                    "ok": integrity_ok,
                    "details": check_result,
                    "total_tables": len(tables),
                },
                "migrations_applied_count": len(migrations),
                "latest_migration": migrations[-1]["version"] if migrations else "none",
                "table_counts": table_counts,
                "edge_devices": devices,
                "sync_health": {
                    "dead_letter_items": dlq_count,
                    "unresolved_conflicts": unresolved_conflicts,
                    "healthy": (integrity_ok and dlq_count == 0 and unresolved_conflicts == 0),
                },
            }

            # Persist snapshot
            conn.execute(
                """
                INSERT INTO diagnostic_snapshots
                (id, organization_id, snapshot_type, payload_json, created_at)
                VALUES (?, ?, 'SYSTEM_HEALTH', ?, ?);
                """,
                (snapshot_id, organization_id, json.dumps(package), now),
            )

        return package
