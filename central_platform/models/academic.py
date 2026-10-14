"""Academic Calendar and Institutional Structure Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class AcademicYearStatus(str, Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class EventType(str, Enum):
    HOLIDAY = "HOLIDAY"
    EXAM = "EXAM"
    SPORTS = "SPORTS"
    CULTURAL = "CULTURAL"
    MEETING = "MEETING"
    EVENT = "EVENT"


@dataclass
class AcademicYear:
    id: str
    organization_id: str
    name: str
    code: str
    start_date: str
    end_date: str
    is_current: bool = False
    status: AcademicYearStatus = AcademicYearStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AcademicTerm:
    id: str
    organization_id: str
    academic_year_id: str
    name: str
    code: str
    start_date: str
    end_date: str
    status: str = "ACTIVE"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class CalendarEvent:
    id: str
    organization_id: str
    academic_year_id: str
    title: str
    event_type: str = "EVENT"
    description: Optional[str] = None
    start_date: str = ""
    end_date: str = ""
    is_holiday: bool = False
    created_at: str = ""
