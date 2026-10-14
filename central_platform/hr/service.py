"""HR and Payroll Domain Services."""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from central_platform.models.hr import (
    LeaveType,
    LeaveStatus,
    StaffLeaveRequest,
    StaffAttendanceRecord,
    PayrollPeriod,
    PayrollRun,
    Payslip,
)


class HRService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def apply_leave(
        self,
        organization_id: str,
        staff_id: str,
        leave_type: LeaveType,
        start_date: str,
        end_date: str,
        total_days: float = 1.0,
        reason: str = "",
    ) -> StaffLeaveRequest:
        # Check overlapping leave requests
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM staff_leave_requests
                WHERE organization_id = ? AND staff_id = ?
                  AND status NOT IN ('REJECTED', 'CANCELLED')
                  AND start_date <= ? AND end_date >= ?;
                """,
                (organization_id, staff_id, end_date, start_date),
            )
            overlap = cursor.fetchone()
            if overlap:
                raise ValueError("Overlapping leave request exists")

            now = self._now()
            leave_id = f"slr-{uuid.uuid4().hex[:12]}"
            lt_val = leave_type.value if hasattr(leave_type, "value") else str(leave_type)

            conn.execute(
                """
                INSERT INTO staff_leave_requests (
                    id, organization_id, staff_id, leave_type, start_date, end_date, total_days,
                    reason, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?);
                """,
                (
                    leave_id,
                    organization_id,
                    staff_id,
                    lt_val,
                    start_date,
                    end_date,
                    total_days,
                    reason,
                    now,
                    now,
                ),
            )

        return StaffLeaveRequest(
            id=leave_id,
            organization_id=organization_id,
            staff_id=staff_id,
            leave_type=LeaveType(lt_val) if lt_val in LeaveType._value2member_map_ else LeaveType.CASUAL,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            status=LeaveStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

    def approve_leave(
        self,
        organization_id: str,
        leave_id: str,
        approved_by: str,
        approved: bool = True,
        rejection_reason: Optional[str] = None,
    ) -> StaffLeaveRequest:
        now = self._now()
        new_status = LeaveStatus.APPROVED.value if approved else LeaveStatus.REJECTED.value

        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE staff_leave_requests
                SET status = ?, approved_by = ?, approved_at = ?, rejection_reason = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (new_status, approved_by, now, rejection_reason, now, leave_id, organization_id),
            )

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, staff_id, leave_type, start_date, end_date, total_days,
                       reason, status, approved_by, approved_at, rejection_reason, created_at, updated_at
                FROM staff_leave_requests
                WHERE id = ? AND organization_id = ?;
                """,
                (leave_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Leave request {leave_id} not found in organization {organization_id}")

            return StaffLeaveRequest(
                id=row[0],
                organization_id=row[1],
                staff_id=row[2],
                leave_type=LeaveType(row[3]) if row[3] in LeaveType._value2member_map_ else LeaveType.CASUAL,
                start_date=row[4],
                end_date=row[5],
                total_days=float(row[6]),
                reason=row[7],
                status=LeaveStatus(row[8]) if row[8] in LeaveStatus._value2member_map_ else LeaveStatus.PENDING,
                approved_by=row[9],
                approved_at=row[10],
                rejection_reason=row[11],
                created_at=row[12],
                updated_at=row[13],
            )

    def mark_staff_attendance(
        self,
        organization_id: str,
        staff_id: str,
        date: str,
        status: str = "PRESENT",
        check_in_time: Optional[str] = None,
        check_out_time: Optional[str] = None,
        remarks: Optional[str] = None,
    ) -> StaffAttendanceRecord:
        now = self._now()
        att_id = f"sat-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO staff_attendance_records (
                    id, organization_id, staff_id, date, status, check_in_time, check_out_time,
                    remarks, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(organization_id, staff_id, date) DO UPDATE SET
                    status = excluded.status,
                    check_in_time = excluded.check_in_time,
                    check_out_time = excluded.check_out_time,
                    remarks = excluded.remarks,
                    updated_at = excluded.updated_at;
                """,
                (
                    att_id,
                    organization_id,
                    staff_id,
                    date,
                    status,
                    check_in_time,
                    check_out_time,
                    remarks,
                    now,
                    now,
                ),
            )

            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, staff_id, date, status, check_in_time, check_out_time,
                       remarks, created_at, updated_at
                FROM staff_attendance_records
                WHERE organization_id = ? AND staff_id = ? AND date = ?;
                """,
                (organization_id, staff_id, date),
            )
            row = cursor.fetchone()

        return StaffAttendanceRecord(
            id=row[0],
            organization_id=row[1],
            staff_id=row[2],
            date=row[3],
            status=row[4],
            check_in_time=row[5],
            check_out_time=row[6],
            remarks=row[7],
            created_at=row[8],
            updated_at=row[9],
        )


class PayrollService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_period(
        self,
        organization_id: str,
        name: str,
        year: int,
        month: int,
        start_date: str,
        end_date: str,
    ) -> PayrollPeriod:
        now = self._now()
        period_id = f"prd-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO payroll_periods (
                    id, organization_id, name, year, month, start_date, end_date, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
                ON CONFLICT(organization_id, year, month) DO UPDATE SET
                    name = excluded.name,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    updated_at = excluded.updated_at;
                """,
                (period_id, organization_id, name, year, month, start_date, end_date, now, now),
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, organization_id, name, year, month, start_date, end_date, status, created_at, updated_at "
                "FROM payroll_periods WHERE organization_id = ? AND year = ? AND month = ?;",
                (organization_id, year, month),
            )
            row = cursor.fetchone()

        return PayrollPeriod(
            id=row[0],
            organization_id=row[1],
            name=row[2],
            year=row[3],
            month=row[4],
            start_date=row[5],
            end_date=row[6],
            status=row[7],
            created_at=row[8],
            updated_at=row[9],
        )

    def calculate_payroll_run(
        self,
        organization_id: str,
        period_id: str,
        employee_salary_specs: List[Dict[str, Any]],
        created_by: str,
    ) -> PayrollRun:
        now = self._now()
        run_id = f"prun-{uuid.uuid4().hex[:12]}"

        total_gross = 0.0
        total_deductions = 0.0
        total_net = 0.0
        employee_count = len(employee_salary_specs)

        slips_to_insert = []
        for spec in employee_salary_specs:
            basic = float(spec.get("basic_salary", 0.0))
            allowances = spec.get("allowances", {})
            deductions = spec.get("deductions", {})

            allowance_sum = sum(float(v) for v in allowances.values())
            deduction_sum = sum(float(v) for v in deductions.values())

            gross = round(basic + allowance_sum, 2)
            net = round(gross - deduction_sum, 2)

            total_gross += gross
            total_deductions += deduction_sum
            total_net += net

            slip_id = f"pslp-{uuid.uuid4().hex[:12]}"
            slips_to_insert.append(
                (
                    slip_id,
                    organization_id,
                    run_id,
                    spec["staff_id"],
                    basic,
                    json.dumps(allowances),
                    json.dumps(deductions),
                    gross,
                    net,
                    "PENDING",
                    now,
                    now,
                )
            )

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO payroll_runs (
                    id, organization_id, payroll_period_id, total_gross, total_deductions, total_net,
                    employee_count, status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?);
                """,
                (
                    run_id,
                    organization_id,
                    period_id,
                    total_gross,
                    total_deductions,
                    total_net,
                    employee_count,
                    created_by,
                    now,
                    now,
                ),
            )

            for s in slips_to_insert:
                conn.execute(
                    """
                    INSERT INTO payslips (
                        id, organization_id, payroll_run_id, staff_id, basic_salary, allowances_json,
                        deductions_json, gross_amount, net_amount, payment_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    s,
                )

        return PayrollRun(
            id=run_id,
            organization_id=organization_id,
            payroll_period_id=period_id,
            total_gross=total_gross,
            total_deductions=total_deductions,
            total_net=total_net,
            employee_count=employee_count,
            status="DRAFT",
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )

    def get_payslips_for_run(self, organization_id: str, payroll_run_id: str) -> List[Payslip]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, payroll_run_id, staff_id, basic_salary, allowances_json,
                       deductions_json, gross_amount, net_amount, payment_status, created_at, updated_at
                FROM payslips
                WHERE payroll_run_id = ? AND organization_id = ?;
                """,
                (payroll_run_id, organization_id),
            )
            rows = cursor.fetchall()

        return [
            Payslip(
                id=r[0],
                organization_id=r[1],
                payroll_run_id=r[2],
                staff_id=r[3],
                basic_salary=float(r[4]),
                allowances_json=r[5],
                deductions_json=r[6],
                gross_amount=float(r[7]),
                net_amount=float(r[8]),
                payment_status=r[9],
                created_at=r[10],
                updated_at=r[11],
            )
            for r in rows
        ]
