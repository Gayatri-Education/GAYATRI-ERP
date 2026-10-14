"""Gayatri School OS — Module Entitlements Engine (Phase 01).

Prevents synthetic mock success for unentitled or unconfigured ERP modules.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gayatri.entitlements")


class EntitlementManager:
    """Manages tenant-level feature licenses and module access."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def is_entitled(self, organization_id: str, module_key: str) -> bool:
        """Check if an organization is entitled to a specific module."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT is_enabled FROM module_entitlements
                WHERE organization_id = ? AND module_key = ?;
                """,
                (organization_id, module_key),
            )
            row = cursor.fetchone()
            if not row:
                return False
            return bool(row[0])

    def assert_entitled(self, organization_id: str, module_key: str) -> None:
        """Fail closed if an organization is not entitled to a specific module."""
        if not self.is_entitled(organization_id, module_key):
            raise PermissionError(
                f"Feature module '{module_key}' is not entitled for organization '{organization_id}'. "
                f"Contact institution administration to enable this capability."
            )

    def set_entitlement(
        self,
        organization_id: str,
        module_key: str,
        enabled: bool = True,
        tier: str = "standard",
        valid_until: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Enable or update an entitlement for an organization."""
        ent_id = f"ent_{uuid.uuid4().hex[:12]}"
        config_str = json.dumps(config or {})
        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO module_entitlements (id, organization_id, module_key, is_enabled, tier, valid_until, config_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(organization_id, module_key) DO UPDATE SET
                    is_enabled = excluded.is_enabled,
                    tier = excluded.tier,
                    valid_until = excluded.valid_until,
                    config_json = excluded.config_json,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (ent_id, organization_id, module_key, 1 if enabled else 0, tier, valid_until, config_str),
            )
            conn.commit()

    def list_entitlements(self, organization_id: str) -> List[Dict[str, Any]]:
        """List all configured module entitlements for an organization."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, module_key, is_enabled, tier, valid_until, config_json
                FROM module_entitlements
                WHERE organization_id = ?;
                """,
                (organization_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "module_key": r[1],
                    "is_enabled": bool(r[2]),
                    "tier": r[3],
                    "valid_until": r[4],
                    "config": json.loads(r[5] or "{}"),
                }
                for r in rows
            ]
