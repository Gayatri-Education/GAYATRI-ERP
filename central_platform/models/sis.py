"""Student Information System (SIS) Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class EnrollmentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TRANSFERRED = "TRANSFERRED"
    WITHDRAWN = "WITHDRAWN"
    PROMOTED = "PROMOTED"
    SUSPENDED = "SUSPENDED"


@dataclass
class StudentClass:
    id: str
    organization_id: str
    academic_year_id: str
    name: str
    grade_level: str
    section: Optional[str] = None
    capacity: int = 40
    class_teacher_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ClassEnrollment:
    id: str
    organization_id: str
    student_id: str
    class_id: str
    academic_year_id: str
    roll_number: Optional[str] = None
    enrollment_date: str = ""
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""
