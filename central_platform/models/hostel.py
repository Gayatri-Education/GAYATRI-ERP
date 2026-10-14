"""Hostel and Boarding Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class OutpassStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CHECKED_OUT = "CHECKED_OUT"
    CHECKED_IN = "CHECKED_IN"
    REJECTED = "REJECTED"


@dataclass
class HostelBuilding:
    id: str
    organization_id: str
    name: str
    code: str
    gender_type: str = "COED"
    warden_name: Optional[str] = None
    warden_phone: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class HostelRoom:
    id: str
    organization_id: str
    building_id: str
    room_number: str
    floor_number: int = 1
    bed_capacity: int = 2
    current_occupancy: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class HostelAllocation:
    id: str
    organization_id: str
    student_id: str
    room_id: str
    academic_year_id: str
    bed_identifier: Optional[str] = None
    allocation_date: str = ""
    status: str = "ACTIVE"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class HostelLeavePass:
    id: str
    organization_id: str
    student_id: str
    leave_type: str
    departure_date: str
    expected_return_date: str
    actual_return_date: Optional[str] = None
    reason: str = ""
    status: OutpassStatus = OutpassStatus.PENDING
    approved_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
