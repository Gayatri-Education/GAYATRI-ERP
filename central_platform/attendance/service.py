"""Attendance Domain Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from central_platform.models.attendance import (
    AttendanceStatus,
    SessionType,
    ExcuseStatus,
    AttendanceSession,
    AttendanceRecord,
    AttendanceCorrection,
    AbsenceExcuseRequest,
)


class AttendanceService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_session(
        self,
        organization_id: str,
        academic_year_id: str,
        class_id: str,
        date: str,
        session_type: SessionType = SessionType.FULL_DAY,
        taken_by: Optional[str] = None,
    ) -> AttendanceSession:
        now = self._now()
        session_id = f"ats-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO attendance_sessions (
                    id, organization_id, academic_year_id, class_id, date, session_type, status, taken_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'SUBMITTED', ?, ?, ?)
                ON CONFLICT(organization_id, class_id, date, session_type) DO UPDATE SET
                    taken_by = excluded.taken_by,
                    updated_at = excluded.updated_at;
                """,
                (
                    session_id,
                    organization_id,
                    academic_year_id,
                    class_id,
                    date,
                    session_type.value if hasattr(session_type, "value") else session_type,
                    taken_by,
                    now,
                    now,
                ),
            )
            # Re-fetch in case of conflict upsert
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM attendance_sessions 
                WHERE organization_id = ? AND class_id = ? AND date = ? AND session_type = ?;
                """,
                (organization_id, class_id, date, session_type.value if hasattr(session_type, "value") else session_type),
            )
            r = cursor.fetchone()

        return AttendanceSession(
            id=r["id"],
            organization_id=r["organization_id"],
            academic_year_id=r["academic_year_id"],
            class_id=r["class_id"],
            date=r["date"],
            session_type=SessionType(r["session_type"]),
            status=r["status"],
            taken_by=r["taken_by"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def get_session(self, organization_id: str, session_id: str) -> Optional[AttendanceSession]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM attendance_sessions WHERE id = ? AND organization_id = ?;",
                (session_id, organization_id),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return AttendanceSession(
                id=r["id"],
                organization_id=r["organization_id"],
                academic_year_id=r["academic_year_id"],
                class_id=r["class_id"],
                date=r["date"],
                session_type=SessionType(r["session_type"]),
                status=r["status"],
                taken_by=r["taken_by"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def list_sessions(
        self,
        organization_id: str,
        class_id: Optional[str] = None,
        date: Optional[str] = None,
    ) -> List[AttendanceSession]:
        query = "SELECT * FROM attendance_sessions WHERE organization_id = ?"
        params: List[Any] = [organization_id]
        if class_id:
            query += " AND class_id = ?"
            params.append(class_id)
        if date:
            query += " AND date = ?"
            params.append(date)
        query += " ORDER BY date DESC, created_at DESC;"

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [
                AttendanceSession(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    academic_year_id=r["academic_year_id"],
                    class_id=r["class_id"],
                    date=r["date"],
                    session_type=SessionType(r["session_type"]),
                    status=r["status"],
                    taken_by=r["taken_by"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def record_roll_call(
        self,
        organization_id: str,
        session_id: str,
        records: List[Dict[str, Any]],
    ) -> List[AttendanceRecord]:
        now = self._now()
        results: List[AttendanceRecord] = []

        with self.db._get_connection() as conn:
            for item in records:
                student_id = item["student_id"]
                stat = item.get("status", AttendanceStatus.PRESENT)
                stat_val = stat.value if hasattr(stat, "value") else stat
                arr_time = item.get("arrival_time")
                remarks = item.get("remarks")
                rec_id = f"atr-{uuid.uuid4().hex[:12]}"

                conn.execute(
                    """
                    INSERT INTO attendance_records (
                        id, organization_id, session_id, student_id, status, arrival_time, remarks, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, student_id) DO UPDATE SET
                        status = excluded.status,
                        arrival_time = excluded.arrival_time,
                        remarks = excluded.remarks,
                        updated_at = excluded.updated_at;
                    """,
                    (rec_id, organization_id, session_id, student_id, stat_val, arr_time, remarks, now, now),
                )
                results.append(
                    AttendanceRecord(
                        id=rec_id,
                        organization_id=organization_id,
                        session_id=session_id,
                        student_id=student_id,
                        status=AttendanceStatus(stat_val),
                        arrival_time=arr_time,
                        remarks=remarks,
                        created_at=now,
                        updated_at=now,
                    )
                )

        return results

    def get_session_records(self, organization_id: str, session_id: str) -> List[AttendanceRecord]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM attendance_records WHERE organization_id = ? AND session_id = ? ORDER BY student_id;",
                (organization_id, session_id),
            )
            rows = cursor.fetchall()
            return [
                AttendanceRecord(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    session_id=r["session_id"],
                    student_id=r["student_id"],
                    status=AttendanceStatus(r["status"]),
                    arrival_time=r["arrival_time"],
                    remarks=r["remarks"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def get_record(self, organization_id: str, record_id: str) -> Optional[AttendanceRecord]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM attendance_records WHERE id = ? AND organization_id = ?;",
                (record_id, organization_id),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return AttendanceRecord(
                id=r["id"],
                organization_id=r["organization_id"],
                session_id=r["session_id"],
                student_id=r["student_id"],
                status=AttendanceStatus(r["status"]),
                arrival_time=r["arrival_time"],
                remarks=r["remarks"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def correct_attendance(
        self,
        organization_id: str,
        record_id: str,
        new_status: AttendanceStatus,
        reason: str,
        corrected_by: str,
    ) -> AttendanceCorrection:
        now = self._now()
        correction_id = f"atc-{uuid.uuid4().hex[:12]}"
        new_stat_val = new_status.value if hasattr(new_status, "value") else new_status

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM attendance_records WHERE id = ? AND organization_id = ?;",
                (record_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Attendance record not found")

            old_status = row["status"]

            # Insert immutable correction record
            conn.execute(
                """
                INSERT INTO attendance_corrections (
                    id, organization_id, record_id, previous_status, new_status, reason, corrected_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (correction_id, organization_id, record_id, old_status, new_stat_val, reason, corrected_by, now),
            )

            # Update live record
            conn.execute(
                "UPDATE attendance_records SET status = ?, updated_at = ? WHERE id = ? AND organization_id = ?;",
                (new_stat_val, now, record_id, organization_id),
            )

        return AttendanceCorrection(
            id=correction_id,
            organization_id=organization_id,
            record_id=record_id,
            previous_status=AttendanceStatus(old_status),
            new_status=AttendanceStatus(new_stat_val),
            reason=reason,
            corrected_by=corrected_by,
            created_at=now,
        )

    def get_correction_history(self, organization_id: str, record_id: str) -> List[AttendanceCorrection]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM attendance_corrections WHERE organization_id = ? AND record_id = ? ORDER BY created_at ASC;",
                (organization_id, record_id),
            )
            rows = cursor.fetchall()
            return [
                AttendanceCorrection(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    record_id=r["record_id"],
                    previous_status=AttendanceStatus(r["previous_status"]),
                    new_status=AttendanceStatus(r["new_status"]),
                    reason=r["reason"],
                    corrected_by=r["corrected_by"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def submit_excuse_request(
        self,
        organization_id: str,
        student_id: str,
        start_date: str,
        end_date: str,
        reason: str,
    ) -> AbsenceExcuseRequest:
        now = self._now()
        req_id = f"aex-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO absence_excuse_requests (
                    id, organization_id, student_id, start_date, end_date, reason, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?);
                """,
                (req_id, organization_id, student_id, start_date, end_date, reason, now, now),
            )

        return AbsenceExcuseRequest(
            id=req_id,
            organization_id=organization_id,
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status=ExcuseStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    def approve_excuse_request(
        self,
        organization_id: str,
        excuse_id: str,
        approved_by: str,
    ) -> AbsenceExcuseRequest:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE absence_excuse_requests
                SET status = 'APPROVED', approved_by = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (approved_by, now, excuse_id, organization_id),
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM absence_excuse_requests WHERE id = ? AND organization_id = ?;",
                (excuse_id, organization_id),
            )
            r = cursor.fetchone()
            if not r:
                raise ValueError("Excuse request not found")

        return AbsenceExcuseRequest(
            id=r["id"],
            organization_id=r["organization_id"],
            student_id=r["student_id"],
            start_date=r["start_date"],
            end_date=r["end_date"],
            reason=r["reason"],
            status=ExcuseStatus(r["status"]),
            approved_by=r["approved_by"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
