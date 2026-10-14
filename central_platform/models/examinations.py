"""Examination Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ExamSeriesType(str, Enum):
    MID_TERM = "MID_TERM"
    FINAL = "FINAL"
    UNIT_TEST = "UNIT_TEST"
    MOCK_ENTRANCE = "MOCK_ENTRANCE"
    PRACTICE = "PRACTICE"


class MarksStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    LOCKED = "LOCKED"


@dataclass
class ExamSeries:
    id: str
    organization_id: str
    academic_year_id: str
    name: str
    code: str
    start_date: str
    end_date: str
    academic_term_id: Optional[str] = None
    series_type: ExamSeriesType = ExamSeriesType.MID_TERM
    status: str = "SCHEDULED"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ExamSchedule:
    id: str
    organization_id: str
    exam_series_id: str
    class_id: str
    subject_id: str
    exam_date: str
    start_time: str
    end_time: str
    max_marks: float = 100.0
    pass_marks: float = 35.0
    room_name: Optional[str] = None
    is_locked: bool = False
    locked_at: Optional[str] = None
    locked_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StudentMarks:
    id: str
    organization_id: str
    schedule_id: str
    student_id: str
    marks_obtained: Optional[float] = None
    is_absent: bool = False
    is_exempt: bool = False
    remarks: Optional[str] = None
    status: MarksStatus = MarksStatus.SUBMITTED
    entered_by: Optional[str] = None
    verified_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
