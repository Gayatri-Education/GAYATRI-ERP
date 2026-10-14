"""Grading Scales and Report Card Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ScaleType(str, Enum):
    NINE_POINT = "NINE_POINT"
    PERCENTAGE = "PERCENTAGE"
    FOUR_POINT = "FOUR_POINT"
    TEN_POINT = "TEN_POINT"


class ReportCardStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


@dataclass
class GradingScale:
    id: str
    organization_id: str
    name: str
    code: str
    scale_type: ScaleType = ScaleType.NINE_POINT
    is_default: bool = False
    created_at: str = ""
    updated_at: str = ""


@dataclass
class GradingTier:
    id: str
    organization_id: str
    scale_id: str
    grade_name: str
    grade_point: float = 0.0
    min_percentage: float = 0.0
    max_percentage: float = 100.0
    description: Optional[str] = None
    created_at: str = ""


@dataclass
class StudentTermResult:
    id: str
    organization_id: str
    student_id: str
    academic_year_id: str
    academic_term_id: Optional[str] = None
    total_marks_obtained: float = 0.0
    total_max_marks: float = 0.0
    percentage: float = 0.0
    gpa: Optional[float] = 0.0
    final_grade: Optional[str] = None
    rank: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StudentReportCard:
    id: str
    organization_id: str
    student_id: str
    academic_year_id: str
    report_number: str
    issue_date: str
    academic_term_id: Optional[str] = None
    status: ReportCardStatus = ReportCardStatus.DRAFT
    general_remarks: Optional[str] = None
    document_hash: Optional[str] = None
    published_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
