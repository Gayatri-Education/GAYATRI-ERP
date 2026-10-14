"""Inventory and Asset Management Domain Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from central_platform.models.inventory import (
    InventoryItem,
    InventoryVendor,
    PurchaseOrder,
    StockMovement,
    MovementType,
)


class InventoryService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_item(
        self,
        organization_id: str,
        name: str,
        sku: str,
        category: str,
        unit: str = "PCS",
        unit_price: float = 0.0,
        reorder_level: int = 10,
    ) -> InventoryItem:
        now = self._now()
        item_id = f"itm-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO inventory_items (
                    id, organization_id, name, sku, category, unit, quantity_on_hand,
                    reorder_level, unit_price, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?);
                """,
                (item_id, organization_id, name, sku, category, unit, reorder_level, unit_price, now, now),
            )

        return InventoryItem(
            id=item_id,
            organization_id=organization_id,
            name=name,
            sku=sku,
            category=category,
            unit=unit,
            quantity_on_hand=0,
            reorder_level=reorder_level,
            unit_price=unit_price,
            created_at=now,
            updated_at=now,
        )

    def get_item(self, organization_id: str, item_id: str) -> Optional[InventoryItem]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, name, sku, category, unit, quantity_on_hand,
                       reorder_level, unit_price, created_at, updated_at
                FROM inventory_items
                WHERE id = ? AND organization_id = ?;
                """,
                (item_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return InventoryItem(
                id=row[0],
                organization_id=row[1],
                name=row[2],
                sku=row[3],
                category=row[4],
                unit=row[5],
                quantity_on_hand=int(row[6]),
                reorder_level=int(row[7]),
                unit_price=float(row[8]),
                created_at=row[9],
                updated_at=row[10],
            )

    def register_vendor(
        self,
        organization_id: str,
        name: str,
        code: str,
        contact_person: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
    ) -> InventoryVendor:
        now = self._now()
        vendor_id = f"vnd-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO inventory_vendors (
                    id, organization_id, name, code, contact_person, phone, email, address, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?);
                """,
                (vendor_id, organization_id, name, code, contact_person, phone, email, address, now, now),
            )

        return InventoryVendor(
            id=vendor_id,
            organization_id=organization_id,
            name=name,
            code=code,
            contact_person=contact_person,
            phone=phone,
            email=email,
            address=address,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def record_movement(
        self,
        organization_id: str,
        item_id: str,
        movement_type: MovementType,
        quantity: int,
        unit_cost: float = 0.0,
        reference_id: Optional[str] = None,
        department_name: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> StockMovement:
        now = self._now()
        mov_id = f"smv-{uuid.uuid4().hex[:12]}"
        mt_val = movement_type.value if hasattr(movement_type, "value") else str(movement_type)

        delta = quantity if mt_val == MovementType.INWARD.value else -quantity

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO inventory_stock_movements (
                    id, organization_id, item_id, movement_type, quantity, unit_cost, reference_id,
                    department_name, remarks, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (mov_id, organization_id, item_id, mt_val, quantity, unit_cost, reference_id, department_name, remarks, now),
            )

            conn.execute(
                """
                UPDATE inventory_items
                SET quantity_on_hand = quantity_on_hand + ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (delta, now, item_id, organization_id),
            )

        return StockMovement(
            id=mov_id,
            organization_id=organization_id,
            item_id=item_id,
            movement_type=MovementType(mt_val) if mt_val in MovementType._value2member_map_ else MovementType.INWARD,
            quantity=quantity,
            unit_cost=unit_cost,
            reference_id=reference_id,
            department_name=department_name,
            remarks=remarks,
            created_at=now,
        )
