"""Transport and Fleet Operations Domain Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from central_platform.models.transport import (
    TransportRoute,
    TransportStop,
    TransportVehicle,
    StudentTransportAllocation,
)


class TransportService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_route(
        self,
        organization_id: str,
        name: str,
        code: str,
        start_point: str,
        end_point: str,
    ) -> TransportRoute:
        now = self._now()
        route_id = f"trt-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO transport_routes (
                    id, organization_id, name, code, start_point, end_point, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?);
                """,
                (route_id, organization_id, name, code, start_point, end_point, now, now),
            )

        return TransportRoute(
            id=route_id,
            organization_id=organization_id,
            name=name,
            code=code,
            start_point=start_point,
            end_point=end_point,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def add_stop(
        self,
        organization_id: str,
        route_id: str,
        name: str,
        stop_order: int,
        morning_pickup_time: Optional[str] = None,
        evening_drop_time: Optional[str] = None,
        fare_amount: float = 0.0,
    ) -> TransportStop:
        now = self._now()
        stop_id = f"tst-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO transport_stops (
                    id, organization_id, route_id, name, stop_order, morning_pickup_time, evening_drop_time, fare_amount, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (stop_id, organization_id, route_id, name, stop_order, morning_pickup_time, evening_drop_time, fare_amount, now),
            )

        return TransportStop(
            id=stop_id,
            organization_id=organization_id,
            route_id=route_id,
            name=name,
            stop_order=stop_order,
            morning_pickup_time=morning_pickup_time,
            evening_drop_time=evening_drop_time,
            fare_amount=fare_amount,
            created_at=now,
        )

    def register_vehicle(
        self,
        organization_id: str,
        registration_number: str,
        vehicle_type: str = "BUS",
        seating_capacity: int = 40,
        driver_name: Optional[str] = None,
        driver_phone: Optional[str] = None,
    ) -> TransportVehicle:
        now = self._now()
        vehicle_id = f"tvh-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO transport_vehicles (
                    id, organization_id, registration_number, vehicle_type, seating_capacity,
                    driver_name, driver_phone, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?);
                """,
                (vehicle_id, organization_id, registration_number, vehicle_type, seating_capacity, driver_name, driver_phone, now, now),
            )

        return TransportVehicle(
            id=vehicle_id,
            organization_id=organization_id,
            registration_number=registration_number,
            vehicle_type=vehicle_type,
            seating_capacity=seating_capacity,
            driver_name=driver_name,
            driver_phone=driver_phone,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def allocate_student_transport(
        self,
        organization_id: str,
        student_id: str,
        route_id: str,
        stop_id: str,
        vehicle_id: str,
        academic_year_id: str,
    ) -> StudentTransportAllocation:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Fetch vehicle capacity
            cursor.execute(
                "SELECT seating_capacity FROM transport_vehicles WHERE id = ? AND organization_id = ?;",
                (vehicle_id, organization_id),
            )
            v_row = cursor.fetchone()
            if not v_row:
                raise ValueError(f"Vehicle {vehicle_id} not found in organization {organization_id}")
            capacity = int(v_row[0])

            # 2. Count active allocations for vehicle
            cursor.execute(
                """
                SELECT COUNT(*) FROM student_transport_allocations
                WHERE vehicle_id = ? AND academic_year_id = ? AND status = 'ACTIVE' AND student_id != ?;
                """,
                (vehicle_id, academic_year_id, student_id),
            )
            current_count = int(cursor.fetchone()[0])
            if current_count >= capacity:
                raise ValueError("Vehicle capacity exceeded")

            now = self._now()
            alloc_id = f"sta-{uuid.uuid4().hex[:12]}"

            conn.execute(
                """
                INSERT INTO student_transport_allocations (
                    id, organization_id, student_id, route_id, stop_id, vehicle_id, academic_year_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
                ON CONFLICT(student_id, academic_year_id) DO UPDATE SET
                    route_id = excluded.route_id,
                    stop_id = excluded.stop_id,
                    vehicle_id = excluded.vehicle_id,
                    status = 'ACTIVE',
                    updated_at = excluded.updated_at;
                """,
                (alloc_id, organization_id, student_id, route_id, stop_id, vehicle_id, academic_year_id, now, now),
            )

        return StudentTransportAllocation(
            id=alloc_id,
            organization_id=organization_id,
            student_id=student_id,
            route_id=route_id,
            stop_id=stop_id,
            vehicle_id=vehicle_id,
            academic_year_id=academic_year_id,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )

    def get_route(self, organization_id: str, route_id: str) -> Optional[TransportRoute]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, organization_id, name, code, start_point, end_point, is_active, created_at, updated_at "
                "FROM transport_routes WHERE id = ? AND organization_id = ?;",
                (route_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return TransportRoute(
                id=row[0],
                organization_id=row[1],
                name=row[2],
                code=row[3],
                start_point=row[4],
                end_point=row[5],
                is_active=bool(row[6]),
                created_at=row[7],
                updated_at=row[8],
            )
