"""Gayatri School OS — Finance API Router (Phase 05)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user, get_current_user_optional, get_db
from central_platform.db import PlatformDatabase
from central_platform.finance.service import FinanceService
from central_platform.api.routes.identity import _get_org_id
from central_platform.portals.fee_admin import FeeAdminController

ALLOWED_WEBHOOK_PROVIDERS = {"razorpay", "mock", "upi", "stripe"}

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
async def ingest_webhook(
    provider: str,
    request: Request,
    current_user: Optional[Any] = Depends(get_current_user_optional),
    service: FinanceService = Depends(get_finance_service),
):
    provider_clean = provider.strip().lower()
    if provider_clean not in ALLOWED_WEBHOOK_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported or unknown payment provider: '{provider}'",
        )

    raw_payload = await request.body()
    if not raw_payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty webhook payload")

    try:
        payload_dict = json.loads(raw_payload.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON in webhook payload")

    # Extract signature from gateway headers
    signature = (
        request.headers.get("x-razorpay-signature")
        or request.headers.get("x-webhook-signature")
        or request.headers.get("stripe-signature")
        or request.headers.get("x-signature")
        or request.headers.get("x-hub-signature-256")
    )
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing payment gateway signature header",
        )

    webhook_secret = (
        request.headers.get("x-webhook-secret")
        or os.environ.get(f"{provider_clean.upper()}_WEBHOOK_SECRET")
        or os.environ.get("PAYMENT_WEBHOOK_SECRET")
        or os.environ.get("WEBHOOK_SECRET")
        or service.get_webhook_secret(provider_clean)
    )

    if not service.verify_webhook_signature(raw_payload, signature, webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid payment gateway webhook signature",
        )

    # Resolve event details
    event_id = payload_dict.get("event_id") or payload_dict.get("id") or f"evt_{uuid.uuid4().hex[:10]}"
    event_type = payload_dict.get("event_type") or payload_dict.get("event") or "payment.captured"
    idempotency_key = payload_dict.get("idempotency_key") or request.headers.get("x-idempotency-key")

    # Resolve organization scoping
    org_id = None
    if current_user:
        org_id = _get_org_id(current_user)
    if not org_id:
        org_id = request.headers.get("x-organization-id") or request.query_params.get("org_id") or payload_dict.get("organization_id")
    if not org_id:
        order_ref = payload_dict.get("order_id") or payload_dict.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id")
        if order_ref:
            with service.db._get_connection() as conn:
                r = conn.execute(
                    "SELECT organization_id FROM payment_orders WHERE provider_order_id = ? OR id = ?;",
                    (order_ref, order_ref),
                ).fetchone()
                if r:
                    org_id = r[0]
    if not org_id:
        inv_ref = payload_dict.get("invoice_id")
        if inv_ref:
            with service.db._get_connection() as conn:
                r = conn.execute("SELECT org_id FROM invoices WHERE id = ?;", (inv_ref,)).fetchone()
                if r:
                    org_id = r[0]
    if not org_id:
        org_id = "org-default"

    try:
        result = service.process_payment_webhook(
            organization_id=org_id,
            provider=provider_clean,
            event_id=event_id,
            event_type=event_type,
            payload=payload_dict,
            idempotency_key=idempotency_key,
            raw_payload=raw_payload,
            signature=signature,
            webhook_secret=webhook_secret,
            signature_verified=True,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/receipts/{receipt_id}")
def get_receipt(
    receipt_id: str,
    current_user: Any = Depends(get_current_user),
    service: FinanceService = Depends(get_finance_service),
):
    caller_org_id = _get_org_id(current_user)
    caller_role = getattr(current_user, "role", None)
    caller_role_str = caller_role.value if hasattr(caller_role, "value") else str(caller_role or "").lower()
    caller_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "")

    scope_org = "" if caller_role_str == "super_admin" else caller_org_id
    receipt = service.get_receipt(scope_org, receipt_id)
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    if caller_role_str != "super_admin" and receipt["organization_id"] != caller_org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    if caller_role_str == "student":
        if receipt["student_id"] != caller_id and receipt["issued_to"] != caller_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Students may only access their own receipts",
            )

    return receipt


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


class GenerateMonthlyBillingRequest(BaseModel):
    month_year: str = Field(..., description="Target month in YYYY-MM format")


@router.post("/billing/generate", status_code=status.HTTP_201_CREATED)
def generate_monthly_billing(
    req: GenerateMonthlyBillingRequest,
    current_user: Any = Depends(get_current_user),
    db: PlatformDatabase = Depends(get_db),
):
    caller_role = getattr(current_user, "role", None)
    caller_role_str = caller_role.value if hasattr(caller_role, "value") else str(caller_role or "").lower()
    if caller_role_str not in {"super_admin", "org_admin", "bursar", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: insufficient permissions to trigger monthly billing",
        )
    org_id = _get_org_id(current_user)
    return FeeAdminController.generate_monthly_billing(org_id=org_id, month_year=req.month_year, db=db)


@router.get("/reports/outstanding")
def get_outstanding_reports(
    current_user: Any = Depends(get_current_user),
):
    caller_role = getattr(current_user, "role", None)
    caller_role_str = caller_role.value if hasattr(caller_role, "value") else str(caller_role or "").lower()
    if caller_role_str not in {"super_admin", "org_admin", "bursar", "admin", "teacher"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: insufficient permissions to view outstanding fee reports",
        )
    org_id = _get_org_id(current_user)
    items = FeeAdminController.get_outstanding_reports(org_id)
    return [item.to_dict() for item in items]


@router.get("/reports/outstanding/export")
def export_outstanding_reports_csv(
    current_user: Any = Depends(get_current_user),
):
    caller_role = getattr(current_user, "role", None)
    caller_role_str = caller_role.value if hasattr(caller_role, "value") else str(caller_role or "").lower()
    if caller_role_str not in {"super_admin", "org_admin", "bursar", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: insufficient permissions to export outstanding fee reports",
        )
    org_id = _get_org_id(current_user)
    csv_content = FeeAdminController.export_outstanding_report_csv(org_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="outstanding_fee_report.csv"'},
    )

