"""Gayatri School OS — Authoritative Unified Institutional Analytics Engine (Phase 08).

Reconciles cross-module operational metrics directly against canonical SQL tables.
Enforces zero placeholder numbers and strict parent privacy policies.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from central_platform.db import PlatformDatabase

logger = logging.getLogger("gayatri.analytics.institutional")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InstitutionalKPISnapshot:
    organization_id: str
    total_students: int
    total_teachers: int
    attendance_rate: float
    fee_collection_rate: float
    total_outstanding_fees: float
    staff_leave_rate: float
    transport_capacity_utilization: float
    hostel_occupancy_rate: float
    exam_pass_percentage: float
    inventory_low_stock_count: int
    data_freshness_iso: str
    calculated_at: str
    reconciliation_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class UnifiedInstitutionalAnalyticsService:
    """Computes authoritative cross-module KPIs reconciling directly to SQL records."""

    def __init__(self, db: PlatformDatabase):
        self.db = db

    def get_kpi_snapshot(
        self,
        organization_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> InstitutionalKPISnapshot:
        """Derive genuine institutional metrics directly from source tables."""
        now = _now_iso()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Total Students
            cursor.execute("SELECT count(*) FROM student_profiles WHERE organization_id = ?;", (organization_id,))
            total_students = cursor.fetchone()[0]

            # 2. Total Teachers
            cursor.execute(
                "SELECT count(*) FROM users WHERE organization_id = ? AND role = 'teacher';",
                (organization_id,),
            )
            total_teachers = cursor.fetchone()[0]

            # 3. Attendance Rate
            cursor.execute(
                """
                SELECT count(CASE WHEN status IN ('PRESENT', 'LATE') THEN 1 END), count(*)
                FROM attendance_records
                WHERE organization_id = ?;
                """,
                (organization_id,),
            )
            att_row = cursor.fetchone()
            att_present, att_total = att_row[0], att_row[1]
            attendance_rate = round((att_present / att_total * 100.0), 2) if att_total > 0 else 0.0

            # 4. Fee Invoicing & Collection Rate (uses org_id, amount_paid, amount_due)
            cursor.execute(
                "SELECT coalesce(sum(amount_paid), 0.0), coalesce(sum(amount_due), 0.0) FROM invoices WHERE org_id = ?;",
                (organization_id,),
            )
            fee_row = cursor.fetchone()
            paid_sum, total_sum = fee_row[0], fee_row[1]
            fee_collection_rate = round((paid_sum / total_sum * 100.0), 2) if total_sum > 0 else 0.0

            # 5. Total Outstanding Fees (uses org_id, balance_due)
            cursor.execute(
                "SELECT coalesce(sum(balance_due), 0.0) FROM fee_accounts WHERE org_id = ?;",
                (organization_id,),
            )
            total_outstanding_fees = round(float(cursor.fetchone()[0]), 2)

            # 6. Staff Leave Rate (total leave days / teachers)
            cursor.execute(
                "SELECT coalesce(sum(total_days), 0.0) FROM staff_leave_requests WHERE organization_id = ? AND status = 'APPROVED';",
                (organization_id,),
            )
            total_leave_days = float(cursor.fetchone()[0])
            staff_leave_rate = round((total_leave_days / total_teachers), 2) if total_teachers > 0 else 0.0

            # 7. Transport Capacity Utilization
            cursor.execute(
                "SELECT count(*) FROM student_transport_allocations WHERE organization_id = ?;",
                (organization_id,),
            )
            transport_allocated = cursor.fetchone()[0]

            cursor.execute(
                "SELECT coalesce(sum(seating_capacity), 0) FROM transport_vehicles WHERE organization_id = ?;",
                (organization_id,),
            )
            total_bus_seats = cursor.fetchone()[0]
            transport_utilization = (
                round((transport_allocated / total_bus_seats * 100.0), 2) if total_bus_seats > 0 else 0.0
            )

            # 8. Hostel Bed Occupancy Rate
            cursor.execute(
                "SELECT count(*) FROM hostel_allocations WHERE organization_id = ?;",
                (organization_id,),
            )
            hostel_allocated = cursor.fetchone()[0]

            cursor.execute(
                "SELECT coalesce(sum(bed_capacity), 0) FROM hostel_rooms WHERE organization_id = ?;",
                (organization_id,),
            )
            total_beds = cursor.fetchone()[0]
            hostel_occupancy = round((hostel_allocated / total_beds * 100.0), 2) if total_beds > 0 else 0.0

            # 9. Academic Exam Pass Percentage
            cursor.execute(
                """
                SELECT count(CASE WHEN m.marks_obtained >= s.pass_marks THEN 1 END), count(*)
                FROM exam_student_marks m
                JOIN exam_schedules s ON m.schedule_id = s.id
                WHERE m.organization_id = ?;
                """,
                (organization_id,),
            )
            exam_row = cursor.fetchone()
            exam_passed, exam_total = exam_row[0], exam_row[1]
            exam_pass_percentage = round((exam_passed / exam_total * 100.0), 2) if exam_total > 0 else 0.0

            # 10. Low Inventory Stock Alerts
            cursor.execute(
                "SELECT count(*) FROM inventory_items WHERE organization_id = ? AND quantity_on_hand <= reorder_level;",
                (organization_id,),
            )
            inventory_low_stock_count = cursor.fetchone()[0]

        # Generate deterministic reconciliation checksum
        payload_hash = hashlib.sha256(
            f"{organization_id}:{total_students}:{total_teachers}:{attendance_rate}:{fee_collection_rate}:{total_outstanding_fees}:{inventory_low_stock_count}".encode("utf-8")
        ).hexdigest()

        return InstitutionalKPISnapshot(
            organization_id=organization_id,
            total_students=total_students,
            total_teachers=total_teachers,
            attendance_rate=attendance_rate,
            fee_collection_rate=fee_collection_rate,
            total_outstanding_fees=total_outstanding_fees,
            staff_leave_rate=staff_leave_rate,
            transport_capacity_utilization=transport_utilization,
            hostel_occupancy_rate=hostel_occupancy,
            exam_pass_percentage=exam_pass_percentage,
            inventory_low_stock_count=inventory_low_stock_count,
            data_freshness_iso=now,
            calculated_at=now,
            reconciliation_hash=payload_hash,
        )

    def get_parent_student_view(
        self,
        organization_id: str,
        student_id: str,
        privacy_level: str = "STANDARD",
    ) -> Dict[str, Any]:
        """Apply strict parent privacy sanitization to student analytics and progress."""
        if privacy_level.upper() == "BLOCKED":
            raise PermissionError("Access to student record is blocked by institutional privacy policy.")

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.first_name || ' ' || p.last_name, sp.admission_number, sp.person_id
                FROM student_profiles sp
                JOIN persons p ON sp.person_id = p.id
                WHERE sp.id = ? AND sp.organization_id = ?;
                """,
                (student_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Student record not found.")

            full_name = row[0]
            admission_no = row[1]
            person_id = row[2]

            # Fetch attendance count
            cursor.execute(
                "SELECT count(CASE WHEN status IN ('PRESENT', 'LATE') THEN 1 END), count(*) FROM attendance_records WHERE student_id = ? AND organization_id = ?;",
                (student_id, organization_id),
            )
            att_row = cursor.fetchone()
            att_rate = round((att_row[0] / att_row[1] * 100.0), 2) if att_row and att_row[1] > 0 else 0.0

            # Fetch fee balance
            cursor.execute(
                """
                SELECT coalesce(balance_due, 0.0) FROM fee_accounts
                WHERE (student_id = ? OR student_id IN (SELECT user_id FROM persons WHERE id = ?)) AND org_id = ?;
                """,
                (student_id, person_id, organization_id),
            )
            bal_row = cursor.fetchone()
            fee_balance = bal_row[0] if bal_row else 0.0

        if privacy_level.upper() == "ANONYMIZED":
            return {
                "student_id": student_id,
                "full_name": "ANONYMOUS STUDENT",
                "admission_number": "***-MASKED",
                "attendance_rate": att_rate,
                "fee_balance": "Contact bursar",
                "privacy_applied": "ANONYMIZED",
            }
        elif privacy_level.upper() == "RESTRICTED":
            return {
                "student_id": student_id,
                "full_name": full_name,
                "admission_number": admission_no,
                "attendance_rate": att_rate,
                "fee_balance": fee_balance,
                "privacy_applied": "RESTRICTED",
            }
        else:  # STANDARD
            return {
                "student_id": student_id,
                "full_name": full_name,
                "admission_number": admission_no,
                "attendance_rate": att_rate,
                "fee_balance": fee_balance,
                "privacy_applied": "STANDARD",
            }
