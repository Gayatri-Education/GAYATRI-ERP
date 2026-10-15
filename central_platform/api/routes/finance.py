"""Gayatri School OS — Finance API Router (Phase 05)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user, get_db
from central_platform.db import PlatformDatabase
from central_platform.finance.service import FinanceService
from central_platform.api.routes.identity import _get_org_id

logger = logging.getLogger("gayatri.api.routes.finance")

router = APIRouter(prefix="/finance", tags=["Finance & Payments"])


def get_finance_service(db: PlatformDatabase = Depends(get_db)) -> FinanceService:
    return FinanceService(db)


class OrderCreateRequest(BaseModel):
    invoice_id: str
    student_id: str
    amount: float
    currency: str = "INR"
    provider: str = "razorpay"
    idempotency_key: Optional[str] = None


class WebhookIngestRequest(BaseModel):
    event_id: str
    event_type: str
    payload: Dict[str, Any]
    idempotency_key: Optional[str] = None


class ReconciliationRequest(BaseModel):
    run_date: str
    provider: str
    total_expected: float
    total_settled: float
    notes: Optional[str] = None


class ConcessionRequestInput(BaseModel):
    student_id: str
    fee_structure_id: str
    concession_type: str = "percentage"
    amount_or_percentage: float
    reason: str


class ConcessionApprovalInput(BaseModel):
    approved: bool = True


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def create_order(
    req: OrderCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    org_id = _get_org_id(current_user)
    order = service.create_payment_order(
        organization_id=org_id,
        invoice_id=req.invoice_id,
        student_id=req.student_id,
        amount=req.amount,
        currency=req.currency,
        provider=req.provider,
        idempotency_key=req.idempotency_key,
    )
    return order.__dict__


@router.get("/orders/{order_id}")
def get_order(
    order_id: str,
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    org_id = _get_org_id(current_user)
    order = service.get_payment_order(org_id, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment order not found")
    return order.__dict__


@router.post("/webhooks/{provider}", status_code=status.HTTP_200_OK)
def ingest_webhook(
    provider: str,
    req: WebhookIngestRequest,
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    org_id = _get_org_id(current_user)
    result = service.process_payment_webhook(
        organization_id=org_id,
        provider=provider,
        event_id=req.event_id,
        event_type=req.event_type,
        payload=req.payload,
        idempotency_key=req.idempotency_key,
    )
    return result


@router.get("/ledger/{account_id}")
def get_ledger(
    account_id: str,
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    org_id = _get_org_id(current_user)
    entries = service.get_account_ledger(org_id, account_id)
    balance = service.calculate_ledger_balance(org_id, account_id)
    return {
        "account_id": account_id,
        "balance_due": balance,
        "entries": [e.__dict__ for e in entries],
    }


@router.post("/reconcile", status_code=status.HTTP_200_OK)
def execute_reconciliation(
    req: ReconciliationRequest,
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "bursar")
    record = service.execute_reconciliation(
        organization_id=org_id,
        run_date=req.run_date,
        provider=req.provider,
        total_expected=req.total_expected,
        total_settled=req.total_settled,
        reconciled_by=user_id,
        notes=req.notes,
    )
    return record.__dict__


@router.get("/reconciliation-records")
def list_reconciliation(
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    org_id = _get_org_id(current_user)
    return [r.__dict__ for r in service.list_reconciliation_records(org_id)]


@router.post("/concessions", status_code=status.HTTP_201_CREATED)
def request_concession(
    req: ConcessionRequestInput,
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "officer")
    conc = service.request_concession(
        organization_id=org_id,
        student_id=req.student_id,
        fee_structure_id=req.fee_structure_id,
        concession_type=req.concession_type,
        amount_or_percentage=req.amount_or_percentage,
        reason=req.reason,
        requested_by=user_id,
    )
    return conc.__dict__


@router.post("/concessions/{concession_id}/approve", status_code=status.HTTP_200_OK)
def approve_concession(
    concession_id: str,
    req: ConcessionApprovalInput,
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "admin")
    try:
        conc = service.approve_concession(
            organization_id=org_id,
            concession_id=concession_id,
            approved_by=user_id,
            approved=req.approved,
        )
        return conc.__dict__
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
