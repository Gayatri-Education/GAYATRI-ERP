"""Hostel and Boarding Operations Domain Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from central_platform.models.hostel import (
    HostelBuilding,
    HostelRoom,
    HostelAllocation,
    HostelLeavePass,
    OutpassStatus,
)


class HostelService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_building(
        self,
        organization_id: str,
        name: str,
        code: str,
        gender_type: str = "COED",
        warden_name: Optional[str] = None,
        warden_phone: Optional[str] = None,
    ) -> HostelBuilding:
        now = self._now()
        bld_id = f"hbd-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO hostel_buildings (
                    id, organization_id, name, code, gender_type, warden_name, warden_phone, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (bld_id, organization_id, name, code, gender_type, warden_name, warden_phone, now, now),
            )

        return HostelBuilding(
            id=bld_id,
            organization_id=organization_id,
            name=name,
            code=code,
            gender_type=gender_type,
            warden_name=warden_name,
            warden_phone=warden_phone,
            created_at=now,
            updated_at=now,
        )

    def create_room(
        self,
        organization_id: str,
        building_id: str,
        room_number: str,
        floor_number: int = 1,
        bed_capacity: int = 2,
    ) -> HostelRoom:
        now = self._now()
        room_id = f"hrm-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO hostel_rooms (
                    id, organization_id, building_id, room_number, floor_number, bed_capacity, current_occupancy, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?);
                """,
                (room_id, organization_id, building_id, room_number, floor_number, bed_capacity, now, now),
            )

        return HostelRoom(
            id=room_id,
            organization_id=organization_id,
            building_id=building_id,
            room_number=room_number,
            floor_number=floor_number,
            bed_capacity=bed_capacity,
            current_occupancy=0,
            created_at=now,
            updated_at=now,
        )

    def allocate_bed(
        self,
        organization_id: str,
        student_id: str,
        room_id: str,
        academic_year_id: str,
        bed_identifier: Optional[str] = None,
    ) -> HostelAllocation:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT bed_capacity FROM hostel_rooms WHERE id = ? AND organization_id = ?;",
                (room_id, organization_id),
            )
            r_row = cursor.fetchone()
            if not r_row:
                raise ValueError(f"Room {room_id} not found in organization {organization_id}")
            capacity = int(r_row[0])

            # Count current active allocations for room
            cursor.execute(
                """
                SELECT COUNT(*) FROM hostel_allocations
                WHERE room_id = ? AND academic_year_id = ? AND status = 'ACTIVE' AND student_id != ?;
                """,
                (room_id, academic_year_id, student_id),
            )
            current_count = int(cursor.fetchone()[0])
            if current_count >= capacity:
                raise ValueError("Room bed capacity exceeded")

            now = self._now()
            alloc_id = f"hla-{uuid.uuid4().hex[:12]}"

            conn.execute(
                """
                INSERT INTO hostel_allocations (
                    id, organization_id, student_id, room_id, academic_year_id, bed_identifier,
                    allocation_date, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
                ON CONFLICT(student_id, academic_year_id) DO UPDATE SET
                    room_id = excluded.room_id,
                    bed_identifier = excluded.bed_identifier,
                    status = 'ACTIVE',
                    updated_at = excluded.updated_at;
                """,
                (alloc_id, organization_id, student_id, room_id, academic_year_id, bed_identifier, now[:10], now, now),
            )

            # Update room occupancy
            conn.execute(
                """
                UPDATE hostel_rooms
                SET current_occupancy = (
                    SELECT COUNT(*) FROM hostel_allocations WHERE room_id = ? AND status = 'ACTIVE'
                )
                WHERE id = ?;
                """,
                (room_id, room_id),
            )

        return HostelAllocation(
            id=alloc_id,
            organization_id=organization_id,
            student_id=student_id,
            room_id=room_id,
            academic_year_id=academic_year_id,
            bed_identifier=bed_identifier,
            allocation_date=now[:10],
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )

    def request_outpass(
        self,
        organization_id: str,
        student_id: str,
        leave_type: str,
        departure_date: str,
        expected_return_date: str,
        reason: str = "",
    ) -> HostelLeavePass:
        now = self._now()
        pass_id = f"hlp-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO hostel_leave_passes (
                    id, organization_id, student_id, leave_type, departure_date, expected_return_date,
                    reason, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?);
                """,
                (pass_id, organization_id, student_id, leave_type, departure_date, expected_return_date, reason, now, now),
            )

        return HostelLeavePass(
            id=pass_id,
            organization_id=organization_id,
            student_id=student_id,
            leave_type=leave_type,
            departure_date=departure_date,
            expected_return_date=expected_return_date,
            reason=reason,
            status=OutpassStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    def approve_outpass(
        self,
        organization_id: str,
        pass_id: str,
        approved_by: str,
    ) -> HostelLeavePass:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE hostel_leave_passes
                SET status = 'APPROVED', approved_by = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (approved_by, now, pass_id, organization_id),
            )

            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, student_id, leave_type, departure_date, expected_return_date,
                       actual_return_date, reason, status, approved_by, created_at, updated_at
                FROM hostel_leave_passes
                WHERE id = ? AND organization_id = ?;
                """,
                (pass_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Outpass {pass_id} not found in organization {organization_id}")

            return HostelLeavePass(
                id=row[0],
                organization_id=row[1],
                student_id=row[2],
                leave_type=row[3],
                departure_date=row[4],
                expected_return_date=row[5],
                actual_return_date=row[6],
                reason=row[7],
                status=OutpassStatus(row[8]) if row[8] in OutpassStatus._value2member_map_ else OutpassStatus.APPROVED,
                approved_by=row[9],
                created_at=row[10],
                updated_at=row[11],
            )
