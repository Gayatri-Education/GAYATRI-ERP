"""HR and Payroll Domain Models."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class LeaveType(str, Enum):
    CASUAL = "CASUAL"
    SICK = "SICK"
    EARNED = "EARNED"
    MATERNITY = "MATERNITY"
    PATERNITY = "PATERNITY"
    UNPAID = "UNPAID"


class LeaveStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class StaffLeaveRequest:
    id: str
    organization_id: str
    staff_id: str
    leave_type: LeaveType
    start_date: str
    end_date: str
    total_days: float = 1.0
    reason: str = ""
    status: LeaveStatus = LeaveStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class StaffAttendanceRecord:
    id: str
    organization_id: str
    staff_id: str
    date: str
    status: str = "PRESENT"
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    remarks: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class PayrollPeriod:
    id: str
    organization_id: str
    name: str
    year: int
    month: int
    start_date: str
    end_date: str
    status: str = "OPEN"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class PayrollRun:
    id: str
    organization_id: str
    payroll_period_id: str
    total_gross: float = 0.0
    total_deductions: float = 0.0
    total_net: float = 0.0
    employee_count: int = 0
    status: str = "DRAFT"
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Payslip:
    id: str
    organization_id: str
    payroll_run_id: str
    staff_id: str
    basic_salary: float
    allowances_json: str
    deductions_json: str
    gross_amount: float
    net_amount: float
    payment_status: str = "PENDING"
    created_at: str = ""
    updated_at: str = ""
