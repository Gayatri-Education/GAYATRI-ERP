"""Finance, Payment Orders, Ledger, and Reconciliation Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"


class WebhookEventStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"


class LedgerEntryType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class ReconciliationStatus(str, Enum):
    RESOLVED = "RESOLVED"
    DISCREPANCY_FLAGGED = "DISCREPANCY_FLAGGED"


class ConcessionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class PaymentOrder:
    id: str
    organization_id: str
    invoice_id: str
    student_id: str
    amount: float
    currency: str = "INR"
    provider: str = "razorpay"
    provider_order_id: str = ""
    status: OrderStatus = OrderStatus.CREATED
    idempotency_key: Optional[str] = None
    created_at: str = ""
    expires_at: Optional[str] = None


@dataclass
class FinancialLedgerEntry:
    id: str
    organization_id: str
    account_id: str
    entry_type: LedgerEntryType
    amount: float
    description: str
    invoice_id: Optional[str] = None
    payment_id: Optional[str] = None
    balance_after: Optional[float] = None
    created_at: str = ""


@dataclass
class ReconciliationRecord:
    id: str
    organization_id: str
    run_date: str
    provider: str
    total_expected: float = 0.0
    total_settled: float = 0.0
    discrepancy_amount: float = 0.0
    status: ReconciliationStatus = ReconciliationStatus.RESOLVED
    notes: Optional[str] = None
    reconciled_by: Optional[str] = None
    created_at: str = ""


@dataclass
class FeeConcession:
    id: str
    organization_id: str
    student_id: str
    fee_structure_id: str
    concession_type: str = "percentage"
    amount_or_percentage: float = 0.0
    reason: str = ""
    status: ConcessionStatus = ConcessionStatus.PENDING
    requested_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
