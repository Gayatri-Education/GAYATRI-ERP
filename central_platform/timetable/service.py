"""Timetable and Scheduling Domain Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from central_platform.models.timetable import (
    DayOfWeek,
    TimetablePeriod,
    TimetableSlot,
    TeacherSubstitution,
)


class TimetableService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_period(
        self,
        organization_id: str,
        academic_year_id: str,
        name: str,
        period_number: int,
        start_time: str,
        end_time: str,
        is_break: bool = False,
    ) -> TimetablePeriod:
        now = self._now()
        period_id = f"ttp-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO timetable_periods (
                    id, organization_id, academic_year_id, name, period_number, start_time, end_time, is_break, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (period_id, organization_id, academic_year_id, name, period_number, start_time, end_time, 1 if is_break else 0, now),
            )

        return TimetablePeriod(
            id=period_id,
            organization_id=organization_id,
            academic_year_id=academic_year_id,
            name=name,
            period_number=period_number,
            start_time=start_time,
            end_time=end_time,
            is_break=is_break,
            created_at=now,
        )

    def list_periods(self, organization_id: str, academic_year_id: str) -> List[TimetablePeriod]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM timetable_periods WHERE organization_id = ? AND academic_year_id = ? ORDER BY period_number ASC;",
                (organization_id, academic_year_id),
            )
            rows = cursor.fetchall()
            return [
                TimetablePeriod(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    academic_year_id=r["academic_year_id"],
                    name=r["name"],
                    period_number=r["period_number"],
                    start_time=r["start_time"],
                    end_time=r["end_time"],
                    is_break=bool(r["is_break"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def create_slot(
        self,
        organization_id: str,
        academic_year_id: str,
        class_id: str,
        period_id: str,
        day_of_week: DayOfWeek,
        subject_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        room_name: Optional[str] = None,
    ) -> TimetableSlot:
        now = self._now()
        slot_id = f"tts-{uuid.uuid4().hex[:12]}"
        day_val = day_of_week.value if hasattr(day_of_week, "value") else day_of_week

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Conflict Check: Teacher double-booking
            if teacher_id:
                cursor.execute(
                    """
                    SELECT COUNT(*) as cnt FROM class_timetable_slots
                    WHERE organization_id = ? AND day_of_week = ? AND period_id = ? AND teacher_id = ? AND status = 'ACTIVE';
                    """,
                    (organization_id, day_val, period_id, teacher_id),
                )
                if cursor.fetchone()["cnt"] > 0:
                    raise ValueError(f"Teacher {teacher_id} is already scheduled during this period on {day_val}")

            # 2. Conflict Check: Room double-booking
            if room_name:
                cursor.execute(
                    """
                    SELECT COUNT(*) as cnt FROM class_timetable_slots
                    WHERE organization_id = ? AND day_of_week = ? AND period_id = ? AND room_name = ? AND status = 'ACTIVE';
                    """,
                    (organization_id, day_val, period_id, room_name),
                )
                if cursor.fetchone()["cnt"] > 0:
                    raise ValueError(f"Room {room_name} is already booked during this period on {day_val}")

            # 3. Conflict Check: Class double-booking
            cursor.execute(
                """
                SELECT COUNT(*) as cnt FROM class_timetable_slots
                WHERE organization_id = ? AND day_of_week = ? AND period_id = ? AND class_id = ? AND status = 'ACTIVE';
                """,
                (organization_id, day_val, period_id, class_id),
            )
            if cursor.fetchone()["cnt"] > 0:
                raise ValueError(f"Class {class_id} already has a session scheduled during this period on {day_val}")

            # 4. Insert slot
            conn.execute(
                """
                INSERT INTO class_timetable_slots (
                    id, organization_id, academic_year_id, class_id, period_id, day_of_week, subject_id, teacher_id, room_name, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?);
                """,
                (slot_id, organization_id, academic_year_id, class_id, period_id, day_val, subject_id, teacher_id, room_name, now, now),
            )

        return TimetableSlot(
            id=slot_id,
            organization_id=organization_id,
            academic_year_id=academic_year_id,
            class_id=class_id,
            period_id=period_id,
            day_of_week=DayOfWeek(day_val),
            subject_id=subject_id,
            teacher_id=teacher_id,
            room_name=room_name,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )

    def get_class_slots(self, organization_id: str, class_id: str) -> List[TimetableSlot]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM class_timetable_slots WHERE organization_id = ? AND class_id = ? AND status = 'ACTIVE' ORDER BY day_of_week, period_id;",
                (organization_id, class_id),
            )
            rows = cursor.fetchall()
            return [
                TimetableSlot(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    academic_year_id=r["academic_year_id"],
                    class_id=r["class_id"],
                    period_id=r["period_id"],
                    day_of_week=DayOfWeek(r["day_of_week"]),
                    subject_id=r["subject_id"],
                    teacher_id=r["teacher_id"],
                    room_name=r["room_name"],
                    status=r["status"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def assign_substitution(
        self,
        organization_id: str,
        slot_id: str,
        date: str,
        original_teacher_id: str,
        substitute_teacher_id: str,
        reason: Optional[str] = None,
    ) -> TeacherSubstitution:
        now = self._now()
        sub_id = f"sub-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO teacher_substitutions (
                    id, organization_id, slot_id, date, original_teacher_id, substitute_teacher_id, reason, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'APPROVED', ?)
                ON CONFLICT(slot_id, date) DO UPDATE SET
                    substitute_teacher_id = excluded.substitute_teacher_id,
                    reason = excluded.reason;
                """,
                (sub_id, organization_id, slot_id, date, original_teacher_id, substitute_teacher_id, reason, now),
            )

        return TeacherSubstitution(
            id=sub_id,
            organization_id=organization_id,
            slot_id=slot_id,
            date=date,
            original_teacher_id=original_teacher_id,
            substitute_teacher_id=substitute_teacher_id,
            reason=reason,
            status="APPROVED",
            created_at=now,
        )

    def get_class_schedule_for_date(
        self,
        organization_id: str,
        class_id: str,
        date: str,
        day_of_week: DayOfWeek,
    ) -> List[Dict[str, Any]]:
        day_val = day_of_week.value if hasattr(day_of_week, "value") else day_of_week
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cts.*, p.name as period_name, p.period_number, p.start_time, p.end_time,
                       ts.substitute_teacher_id, ts.reason as substitution_reason
                FROM class_timetable_slots cts
                JOIN timetable_periods p ON cts.period_id = p.id
                LEFT JOIN teacher_substitutions ts ON cts.id = ts.slot_id AND ts.date = ?
                WHERE cts.organization_id = ? AND cts.class_id = ? AND cts.day_of_week = ? AND cts.status = 'ACTIVE'
                ORDER BY p.period_number ASC;
                """,
                (date, organization_id, class_id, day_val),
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["effective_teacher_id"] = item["substitute_teacher_id"] or item["teacher_id"]
                results.append(item)
            return results
