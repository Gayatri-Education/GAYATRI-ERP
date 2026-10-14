"""Transport and Fleet Operations Domain Models."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TransportRoute:
    id: str
    organization_id: str
    name: str
    code: str
    start_point: str
    end_point: str
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TransportStop:
    id: str
    organization_id: str
    route_id: str
    name: str
    stop_order: int
    morning_pickup_time: Optional[str] = None
    evening_drop_time: Optional[str] = None
    fare_amount: float = 0.0
    created_at: str = ""


@dataclass
class TransportVehicle:
    id: str
    organization_id: str
    registration_number: str
    vehicle_type: str = "BUS"
    seating_capacity: int = 40
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StudentTransportAllocation:
    id: str
    organization_id: str
    student_id: str
    route_id: str
    stop_id: str
    vehicle_id: str
    academic_year_id: str
    status: str = "ACTIVE"
    created_at: str = ""
    updated_at: str = ""
