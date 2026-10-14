"""Timetable and Scheduling Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class DayOfWeek(str, Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


@dataclass
class TimetablePeriod:
    id: str
    organization_id: str
    academic_year_id: str
    name: str
    period_number: int
    start_time: str
    end_time: str
    is_break: bool = False
    created_at: str = ""


@dataclass
class TimetableSlot:
    id: str
    organization_id: str
    academic_year_id: str
    class_id: str
    period_id: str
    day_of_week: DayOfWeek
    subject_id: Optional[str] = None
    teacher_id: Optional[str] = None
    room_name: Optional[str] = None
    status: str = "ACTIVE"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TeacherSubstitution:
    id: str
    organization_id: str
    slot_id: str
    date: str
    original_teacher_id: str
    substitute_teacher_id: str
    reason: Optional[str] = None
    status: str = "APPROVED"
    created_at: str = ""
