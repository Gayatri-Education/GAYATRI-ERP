"""Student Information System (SIS) Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from central_platform.models.sis import (
    StudentClass,
    ClassEnrollment,
    EnrollmentStatus,
)
from central_platform.models.identity import (
    StudentProfile,
)


class SISService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_class(
        self,
        organization_id: str,
        academic_year_id: str,
        name: str,
        grade_level: str,
        section: Optional[str] = None,
        capacity: int = 40,
        class_teacher_id: Optional[str] = None,
    ) -> StudentClass:
        now = self._now()
        class_id = f"cls-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO student_classes (
                    id, organization_id, academic_year_id, name, grade_level, section, capacity, class_teacher_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    class_id,
                    organization_id,
                    academic_year_id,
                    name,
                    grade_level,
                    section,
                    capacity,
                    class_teacher_id,
                    now,
                    now,
                ),
            )

        return StudentClass(
            id=class_id,
            organization_id=organization_id,
            academic_year_id=academic_year_id,
            name=name,
            grade_level=grade_level,
            section=section,
            capacity=capacity,
            class_teacher_id=class_teacher_id,
            created_at=now,
            updated_at=now,
        )

    def get_class(self, class_id: str, organization_id: str) -> Optional[StudentClass]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM student_classes WHERE id = ? AND organization_id = ?;",
                (class_id, organization_id),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return StudentClass(
                id=r["id"],
                organization_id=r["organization_id"],
                academic_year_id=r["academic_year_id"],
                name=r["name"],
                grade_level=r["grade_level"],
                section=r["section"],
                capacity=r["capacity"],
                class_teacher_id=r["class_teacher_id"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def list_classes(
        self, organization_id: str, academic_year_id: Optional[str] = None
    ) -> List[StudentClass]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            if academic_year_id:
                cursor.execute(
                    "SELECT * FROM student_classes WHERE organization_id = ? AND academic_year_id = ? ORDER BY grade_level, section;",
                    (organization_id, academic_year_id),
                )
            else:
                cursor.execute(
                    "SELECT * FROM student_classes WHERE organization_id = ? ORDER BY grade_level, section;",
                    (organization_id,),
                )
            rows = cursor.fetchall()
            return [
                StudentClass(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    academic_year_id=r["academic_year_id"],
                    name=r["name"],
                    grade_level=r["grade_level"],
                    section=r["section"],
                    capacity=r["capacity"],
                    class_teacher_id=r["class_teacher_id"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def create_student_direct(
        self,
        organization_id: str,
        first_name: str,
        last_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        gender: Optional[str] = None,
        admission_number: Optional[str] = None,
    ) -> StudentProfile:
        now = self._now()
        person_id = f"per-{uuid.uuid4().hex[:12]}"
        student_id = f"stu-{uuid.uuid4().hex[:12]}"
        if not admission_number:
            admission_number = f"ADM-{uuid.uuid4().hex[:8].upper()}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO persons (
                    id, organization_id, first_name, last_name, email, phone, date_of_birth, gender, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (person_id, organization_id, first_name, last_name, email, phone, date_of_birth, gender, now, now),
            )
            conn.execute(
                """
                INSERT INTO student_profiles (
                    id, person_id, organization_id, admission_number, admission_date, academic_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?);
                """,
                (student_id, person_id, organization_id, admission_number, now, now, now),
            )

        return StudentProfile(
            id=student_id,
            person_id=person_id,
            organization_id=organization_id,
            admission_number=admission_number,
            academic_status="active",
            created_at=now,
            updated_at=now,
        )

    def get_student(self, student_id: str, organization_id: str) -> Optional[StudentProfile]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM student_profiles WHERE id = ? AND organization_id = ?;",
                (student_id, organization_id),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return StudentProfile(
                id=r["id"],
                person_id=r["person_id"],
                organization_id=r["organization_id"],
                admission_number=r["admission_number"],
                roll_number=r["roll_number"],
                admission_date=r["admission_date"],
                academic_status=r["academic_status"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def enroll_student_in_class(
        self,
        organization_id: str,
        student_id: str,
        class_id: str,
        academic_year_id: str,
        roll_number: Optional[str] = None,
    ) -> ClassEnrollment:
        now = self._now()
        enrollment_id = f"enr-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Check class exists and verify capacity
            cursor.execute(
                "SELECT capacity FROM student_classes WHERE id = ? AND organization_id = ?;",
                (class_id, organization_id),
            )
            class_row = cursor.fetchone()
            if not class_row:
                raise ValueError("Class not found")
            capacity = class_row["capacity"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM student_class_enrollments WHERE class_id = ? AND status = 'ACTIVE';",
                (class_id,),
            )
            active_count = cursor.fetchone()["count"]

            if active_count >= capacity:
                raise ValueError(f"Class enrollment exceeds capacity of {capacity}")

            # 2. Insert enrollment
            conn.execute(
                """
                INSERT INTO student_class_enrollments (
                    id, organization_id, student_id, class_id, academic_year_id, roll_number, enrollment_date, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?);
                """,
                (enrollment_id, organization_id, student_id, class_id, academic_year_id, roll_number, now, now, now),
            )

        return ClassEnrollment(
            id=enrollment_id,
            organization_id=organization_id,
            student_id=student_id,
            class_id=class_id,
            academic_year_id=academic_year_id,
            roll_number=roll_number,
            enrollment_date=now,
            status=EnrollmentStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

    def get_class_roster(self, organization_id: str, class_id: str) -> List[Dict[str, Any]]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT sce.id as enrollment_id, sce.roll_number, sce.enrollment_date, sce.status,
                       sp.id as student_id, sp.admission_number,
                       p.first_name, p.last_name, p.email, p.phone, p.gender, p.date_of_birth
                FROM student_class_enrollments sce
                JOIN student_profiles sp ON sce.student_id = sp.id
                JOIN persons p ON sp.person_id = p.id
                WHERE sce.organization_id = ? AND sce.class_id = ? AND sce.status = 'ACTIVE'
                ORDER BY sce.roll_number ASC, p.last_name ASC;
                """,
                (organization_id, class_id),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
