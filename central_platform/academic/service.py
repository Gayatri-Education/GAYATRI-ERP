"""Academic Calendar & Structure Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from central_platform.models.academic import (
    AcademicYear,
    AcademicTerm,
    CalendarEvent,
    AcademicYearStatus,
)


class AcademicService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_academic_year(
        self,
        organization_id: str,
        name: str,
        code: str,
        start_date: str,
        end_date: str,
        is_current: bool = False,
    ) -> AcademicYear:
        now = self._now()
        year_id = f"ay-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            if is_current:
                # Reset any current year for this tenant
                conn.execute(
                    "UPDATE academic_years SET is_current = 0 WHERE organization_id = ?;",
                    (organization_id,),
                )
            conn.execute(
                """
                INSERT INTO academic_years (
                    id, organization_id, name, code, start_date, end_date, is_current, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    year_id,
                    organization_id,
                    name,
                    code,
                    start_date,
                    end_date,
                    1 if is_current else 0,
                    AcademicYearStatus.ACTIVE.value,
                    now,
                    now,
                ),
            )

        return AcademicYear(
            id=year_id,
            organization_id=organization_id,
            name=name,
            code=code,
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
            status=AcademicYearStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

    def get_academic_year(self, year_id: str, organization_id: str) -> Optional[AcademicYear]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM academic_years WHERE id = ? AND organization_id = ?;",
                (year_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return AcademicYear(
                id=row["id"],
                organization_id=row["organization_id"],
                name=row["name"],
                code=row["code"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                is_current=bool(row["is_current"]),
                status=AcademicYearStatus(row["status"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def get_current_academic_year(self, organization_id: str) -> Optional[AcademicYear]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM academic_years WHERE organization_id = ? AND is_current = 1 LIMIT 1;",
                (organization_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return AcademicYear(
                id=row["id"],
                organization_id=row["organization_id"],
                name=row["name"],
                code=row["code"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                is_current=True,
                status=AcademicYearStatus(row["status"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_academic_years(self, organization_id: str) -> List[AcademicYear]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM academic_years WHERE organization_id = ? ORDER BY start_date DESC;",
                (organization_id,),
            )
            rows = cursor.fetchall()
            return [
                AcademicYear(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    name=r["name"],
                    code=r["code"],
                    start_date=r["start_date"],
                    end_date=r["end_date"],
                    is_current=bool(r["is_current"]),
                    status=AcademicYearStatus(r["status"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def create_academic_term(
        self,
        organization_id: str,
        academic_year_id: str,
        name: str,
        code: str,
        start_date: str,
        end_date: str,
    ) -> AcademicTerm:
        now = self._now()
        term_id = f"term-{uuid.uuid4().hex[:12]}"
        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO academic_terms (
                    id, organization_id, academic_year_id, name, code, start_date, end_date, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?);
                """,
                (term_id, organization_id, academic_year_id, name, code, start_date, end_date, now, now),
            )
        return AcademicTerm(
            id=term_id,
            organization_id=organization_id,
            academic_year_id=academic_year_id,
            name=name,
            code=code,
            start_date=start_date,
            end_date=end_date,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )

    def list_academic_terms(self, organization_id: str, academic_year_id: str) -> List[AcademicTerm]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM academic_terms WHERE organization_id = ? AND academic_year_id = ? ORDER BY start_date ASC;",
                (organization_id, academic_year_id),
            )
            rows = cursor.fetchall()
            return [
                AcademicTerm(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    academic_year_id=r["academic_year_id"],
                    name=r["name"],
                    code=r["code"],
                    start_date=r["start_date"],
                    end_date=r["end_date"],
                    status=r["status"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def create_calendar_event(
        self,
        organization_id: str,
        academic_year_id: str,
        title: str,
        event_type: str = "EVENT",
        description: Optional[str] = None,
        start_date: str = "",
        end_date: str = "",
        is_holiday: bool = False,
    ) -> CalendarEvent:
        now = self._now()
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO school_calendar_events (
                    id, organization_id, academic_year_id, title, event_type, description, start_date, end_date, is_holiday, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event_id,
                    organization_id,
                    academic_year_id,
                    title,
                    event_type,
                    description,
                    start_date,
                    end_date,
                    1 if is_holiday else 0,
                    now,
                ),
            )
        return CalendarEvent(
            id=event_id,
            organization_id=organization_id,
            academic_year_id=academic_year_id,
            title=title,
            event_type=event_type,
            description=description,
            start_date=start_date,
            end_date=end_date,
            is_holiday=is_holiday,
            created_at=now,
        )

    def list_calendar_events(self, organization_id: str, academic_year_id: str) -> List[CalendarEvent]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM school_calendar_events WHERE organization_id = ? AND academic_year_id = ? ORDER BY start_date ASC;",
                (organization_id, academic_year_id),
            )
            rows = cursor.fetchall()
            return [
                CalendarEvent(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    academic_year_id=r["academic_year_id"],
                    title=r["title"],
                    event_type=r["event_type"],
                    description=r["description"],
                    start_date=r["start_date"],
                    end_date=r["end_date"],
                    is_holiday=bool(r["is_holiday"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]
