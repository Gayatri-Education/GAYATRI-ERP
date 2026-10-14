"""Examinations Domain Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from central_platform.models.examinations import (
    ExamSeriesType,
    MarksStatus,
    ExamSeries,
    ExamSchedule,
    StudentMarks,
)


class ExaminationService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_exam_series(
        self,
        organization_id: str,
        academic_year_id: str,
        name: str,
        code: str,
        start_date: str,
        end_date: str,
        academic_term_id: Optional[str] = None,
        series_type: ExamSeriesType = ExamSeriesType.MID_TERM,
        status: str = "SCHEDULED",
    ) -> ExamSeries:
        now = self._now()
        series_id = f"exs-{uuid.uuid4().hex[:12]}"
        st_val = series_type.value if hasattr(series_type, "value") else str(series_type)

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO exam_series (
                    id, organization_id, academic_year_id, academic_term_id, name, code, series_type, start_date, end_date, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    series_id,
                    organization_id,
                    academic_year_id,
                    academic_term_id,
                    name,
                    code,
                    st_val,
                    start_date,
                    end_date,
                    status,
                    now,
                    now,
                ),
            )

        return ExamSeries(
            id=series_id,
            organization_id=organization_id,
            academic_year_id=academic_year_id,
            academic_term_id=academic_term_id,
            name=name,
            code=code,
            series_type=ExamSeriesType(st_val) if st_val in ExamSeriesType._value2member_map_ else ExamSeriesType.MID_TERM,
            start_date=start_date,
            end_date=end_date,
            status=status,
            created_at=now,
            updated_at=now,
        )

    def get_exam_series(self, organization_id: str, series_id: str) -> Optional[ExamSeries]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, academic_year_id, academic_term_id, name, code, series_type, start_date, end_date, status, created_at, updated_at
                FROM exam_series
                WHERE id = ? AND organization_id = ?;
                """,
                (series_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return ExamSeries(
                id=row[0],
                organization_id=row[1],
                academic_year_id=row[2],
                academic_term_id=row[3],
                name=row[4],
                code=row[5],
                series_type=ExamSeriesType(row[6]) if row[6] in ExamSeriesType._value2member_map_ else ExamSeriesType.MID_TERM,
                start_date=row[7],
                end_date=row[8],
                status=row[9],
                created_at=row[10],
                updated_at=row[11],
            )

    def list_exam_series(self, organization_id: str, academic_year_id: Optional[str] = None) -> List[ExamSeries]:
        query = """
            SELECT id, organization_id, academic_year_id, academic_term_id, name, code, series_type, start_date, end_date, status, created_at, updated_at
            FROM exam_series
            WHERE organization_id = ?
        """
        params: List[Any] = [organization_id]
        if academic_year_id:
            query += " AND academic_year_id = ?"
            params.append(academic_year_id)
        query += " ORDER BY start_date DESC;"

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [
            ExamSeries(
                id=r[0],
                organization_id=r[1],
                academic_year_id=r[2],
                academic_term_id=r[3],
                name=r[4],
                code=r[5],
                series_type=ExamSeriesType(r[6]) if r[6] in ExamSeriesType._value2member_map_ else ExamSeriesType.MID_TERM,
                start_date=r[7],
                end_date=r[8],
                status=r[9],
                created_at=r[10],
                updated_at=r[11],
            )
            for r in rows
        ]

    def schedule_exam(
        self,
        organization_id: str,
        exam_series_id: str,
        class_id: str,
        subject_id: str,
        exam_date: str,
        start_time: str,
        end_time: str,
        max_marks: float = 100.0,
        pass_marks: float = 35.0,
        room_name: Optional[str] = None,
    ) -> ExamSchedule:
        now = self._now()
        schedule_id = f"exsch-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO exam_schedules (
                    id, organization_id, exam_series_id, class_id, subject_id, exam_date, start_time, end_time,
                    max_marks, pass_marks, room_name, is_locked, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?);
                """,
                (
                    schedule_id,
                    organization_id,
                    exam_series_id,
                    class_id,
                    subject_id,
                    exam_date,
                    start_time,
                    end_time,
                    max_marks,
                    pass_marks,
                    room_name,
                    now,
                    now,
                ),
            )

        return ExamSchedule(
            id=schedule_id,
            organization_id=organization_id,
            exam_series_id=exam_series_id,
            class_id=class_id,
            subject_id=subject_id,
            exam_date=exam_date,
            start_time=start_time,
            end_time=end_time,
            max_marks=max_marks,
            pass_marks=pass_marks,
            room_name=room_name,
            is_locked=False,
            created_at=now,
            updated_at=now,
        )

    def get_exam_schedule(self, organization_id: str, schedule_id: str) -> Optional[ExamSchedule]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, exam_series_id, class_id, subject_id, exam_date, start_time, end_time,
                       max_marks, pass_marks, room_name, is_locked, locked_at, locked_by, created_at, updated_at
                FROM exam_schedules
                WHERE id = ? AND organization_id = ?;
                """,
                (schedule_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return ExamSchedule(
                id=row[0],
                organization_id=row[1],
                exam_series_id=row[2],
                class_id=row[3],
                subject_id=row[4],
                exam_date=row[5],
                start_time=row[6],
                end_time=row[7],
                max_marks=float(row[8]),
                pass_marks=float(row[9]),
                room_name=row[10],
                is_locked=bool(row[11]),
                locked_at=row[12],
                locked_by=row[13],
                created_at=row[14],
                updated_at=row[15],
            )

    def list_schedules_for_series(self, organization_id: str, exam_series_id: str) -> List[ExamSchedule]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, exam_series_id, class_id, subject_id, exam_date, start_time, end_time,
                       max_marks, pass_marks, room_name, is_locked, locked_at, locked_by, created_at, updated_at
                FROM exam_schedules
                WHERE exam_series_id = ? AND organization_id = ?
                ORDER BY exam_date, start_time;
                """,
                (exam_series_id, organization_id),
            )
            rows = cursor.fetchall()

        return [
            ExamSchedule(
                id=r[0],
                organization_id=r[1],
                exam_series_id=r[2],
                class_id=r[3],
                subject_id=r[4],
                exam_date=r[5],
                start_time=r[6],
                end_time=r[7],
                max_marks=float(r[8]),
                pass_marks=float(r[9]),
                room_name=r[10],
                is_locked=bool(r[11]),
                locked_at=r[12],
                locked_by=r[13],
                created_at=r[14],
                updated_at=r[15],
            )
            for r in rows
        ]

    def enter_marks(
        self,
        organization_id: str,
        schedule_id: str,
        student_id: str,
        marks_obtained: Optional[float] = None,
        entered_by: Optional[str] = None,
        is_absent: bool = False,
        is_exempt: bool = False,
        remarks: Optional[str] = None,
    ) -> StudentMarks:
        schedule = self.get_exam_schedule(organization_id, schedule_id)
        if not schedule:
            raise ValueError(f"Exam schedule {schedule_id} not found in organization {organization_id}")

        if schedule.is_locked:
            raise ValueError("Marks are locked")

        if marks_obtained is not None:
            if marks_obtained < 0:
                raise ValueError("Marks cannot be negative")
            if marks_obtained > schedule.max_marks:
                raise ValueError("Marks cannot exceed max marks")

        now = self._now()
        mark_id = f"mk-{uuid.uuid4().hex[:12]}"
        status = MarksStatus.SUBMITTED.value

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO exam_student_marks (
                    id, organization_id, schedule_id, student_id, marks_obtained, is_absent, is_exempt,
                    remarks, status, entered_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(schedule_id, student_id) DO UPDATE SET
                    marks_obtained = excluded.marks_obtained,
                    is_absent = excluded.is_absent,
                    is_exempt = excluded.is_exempt,
                    remarks = excluded.remarks,
                    status = excluded.status,
                    entered_by = excluded.entered_by,
                    updated_at = excluded.updated_at;
                """,
                (
                    mark_id,
                    organization_id,
                    schedule_id,
                    student_id,
                    marks_obtained,
                    1 if is_absent else 0,
                    1 if is_exempt else 0,
                    remarks,
                    status,
                    entered_by,
                    now,
                    now,
                ),
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, schedule_id, student_id, marks_obtained, is_absent, is_exempt,
                       remarks, status, entered_by, verified_by, created_at, updated_at
                FROM exam_student_marks
                WHERE schedule_id = ? AND student_id = ?;
                """,
                (schedule_id, student_id),
            )
            row = cursor.fetchone()

        return StudentMarks(
            id=row[0],
            organization_id=row[1],
            schedule_id=row[2],
            student_id=row[3],
            marks_obtained=float(row[4]) if row[4] is not None else None,
            is_absent=bool(row[5]),
            is_exempt=bool(row[6]),
            remarks=row[7],
            status=MarksStatus(row[8]) if row[8] in MarksStatus._value2member_map_ else MarksStatus.SUBMITTED,
            entered_by=row[9],
            verified_by=row[10],
            created_at=row[11],
            updated_at=row[12],
        )

    def lock_marks(self, organization_id: str, schedule_id: str, verified_by: str) -> ExamSchedule:
        schedule = self.get_exam_schedule(organization_id, schedule_id)
        if not schedule:
            raise ValueError(f"Exam schedule {schedule_id} not found in organization {organization_id}")

        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE exam_schedules
                SET is_locked = 1, locked_at = ?, locked_by = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (now, verified_by, now, schedule_id, organization_id),
            )
            conn.execute(
                """
                UPDATE exam_student_marks
                SET status = 'LOCKED', verified_by = ?, updated_at = ?
                WHERE schedule_id = ? AND organization_id = ?;
                """,
                (verified_by, now, schedule_id, organization_id),
            )

        updated = self.get_exam_schedule(organization_id, schedule_id)
        return updated  # type: ignore

    def get_student_marks(self, organization_id: str, schedule_id: str, student_id: str) -> Optional[StudentMarks]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, schedule_id, student_id, marks_obtained, is_absent, is_exempt,
                       remarks, status, entered_by, verified_by, created_at, updated_at
                FROM exam_student_marks
                WHERE schedule_id = ? AND student_id = ? AND organization_id = ?;
                """,
                (schedule_id, student_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return StudentMarks(
                id=row[0],
                organization_id=row[1],
                schedule_id=row[2],
                student_id=row[3],
                marks_obtained=float(row[4]) if row[4] is not None else None,
                is_absent=bool(row[5]),
                is_exempt=bool(row[6]),
                remarks=row[7],
                status=MarksStatus(row[8]) if row[8] in MarksStatus._value2member_map_ else MarksStatus.SUBMITTED,
                entered_by=row[9],
                verified_by=row[10],
                created_at=row[11],
                updated_at=row[12],
            )

    def list_marks_for_schedule(self, organization_id: str, schedule_id: str) -> List[StudentMarks]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, schedule_id, student_id, marks_obtained, is_absent, is_exempt,
                       remarks, status, entered_by, verified_by, created_at, updated_at
                FROM exam_student_marks
                WHERE schedule_id = ? AND organization_id = ?
                ORDER BY created_at;
                """,
                (schedule_id, organization_id),
            )
            rows = cursor.fetchall()

        return [
            StudentMarks(
                id=r[0],
                organization_id=r[1],
                schedule_id=r[2],
                student_id=r[3],
                marks_obtained=float(r[4]) if r[4] is not None else None,
                is_absent=bool(r[5]),
                is_exempt=bool(r[6]),
                remarks=r[7],
                status=MarksStatus(r[8]) if r[8] in MarksStatus._value2member_map_ else MarksStatus.SUBMITTED,
                entered_by=r[9],
                verified_by=r[10],
                created_at=r[11],
                updated_at=r[12],
            )
            for r in rows
        ]
