"""Attendance Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class AttendanceStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    HALF_DAY = "HALF_DAY"
    EXCUSED = "EXCUSED"
    MEDICAL_LEAVE = "MEDICAL_LEAVE"


class SessionType(str, Enum):
    FULL_DAY = "FULL_DAY"
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    PERIOD_WISE = "PERIOD_WISE"


class ExcuseStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class AttendanceSession:
    id: str
    organization_id: str
    academic_year_id: str
    class_id: str
    date: str
    session_type: SessionType = SessionType.FULL_DAY
    status: str = "SUBMITTED"
    taken_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AttendanceRecord:
    id: str
    organization_id: str
    session_id: str
    student_id: str
    status: AttendanceStatus = AttendanceStatus.PRESENT
    arrival_time: Optional[str] = None
    remarks: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AttendanceCorrection:
    id: str
    organization_id: str
    record_id: str
    previous_status: AttendanceStatus
    new_status: AttendanceStatus
    reason: str
    corrected_by: str
    created_at: str = ""


@dataclass
class AbsenceExcuseRequest:
    id: str
    organization_id: str
    student_id: str
    start_date: str
    end_date: str
    reason: str
    status: ExcuseStatus = ExcuseStatus.PENDING
    approved_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
