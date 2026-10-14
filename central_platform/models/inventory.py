"""Inventory and Asset Management Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class MovementType(str, Enum):
    INWARD = "INWARD"
    OUTWARD = "OUTWARD"
    ADJUSTMENT = "ADJUSTMENT"


@dataclass
class InventoryItem:
    id: str
    organization_id: str
    name: str
    sku: str
    category: str
    unit: str = "PCS"
    quantity_on_hand: int = 0
    reorder_level: int = 10
    unit_price: float = 0.0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class InventoryVendor:
    id: str
    organization_id: str
    name: str
    code: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""


@dataclass
class PurchaseOrder:
    id: str
    organization_id: str
    po_number: str
    vendor_id: str
    total_amount: float
    order_date: str
    expected_date: Optional[str] = None
    status: str = "DRAFT"
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StockMovement:
    id: str
    organization_id: str
    item_id: str
    movement_type: MovementType
    quantity: int
    unit_cost: float = 0.0
    reference_id: Optional[str] = None
    department_name: Optional[str] = None
    remarks: Optional[str] = None
    created_at: str = ""
