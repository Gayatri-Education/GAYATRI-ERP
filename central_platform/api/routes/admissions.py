"""Gayatri School OS — Admissions CRM API Router (Phase 02B)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user
from central_platform.db import PlatformDatabase
from central_platform.admissions.service import AdmissionsService
from central_platform.models.admissions import ApplicationStatus
from central_platform.api.routes.identity import _get_org_id, _get_roles

logger = logging.getLogger("gayatri.api.routes.admissions")

router = APIRouter(prefix="/admissions", tags=["Admissions CRM"])


def get_db() -> PlatformDatabase:
    return PlatformDatabase()


def get_admissions_service(db: PlatformDatabase = Depends(get_db)) -> AdmissionsService:
    return AdmissionsService(db)


class InquirySubmitRequest(BaseModel):
    organization_id: str
    applicant_name: str = Field(..., min_length=2)
    guardian_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    target_grade: Optional[str] = None
    notes: Optional[str] = None


class ApplicationSubmitRequest(BaseModel):
    applicant_name: str = Field(..., min_length=2)
    academic_year_id: Optional[str] = None
    inquiry_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    previous_school: Optional[str] = None
    target_grade: Optional[str] = None


class OfferIssueRequest(BaseModel):
    grade: str
    fee_amount: float = 0.0
    valid_until: str
    conditions: Optional[str] = None


class ApplicationConvertRequest(BaseModel):
    class_id: Optional[str] = None
    roll_number: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_relationship: str = "PARENT"


# ── Public Endpoints ─────────────────────────────────────────────────────────

@router.post("/inquiries", status_code=status.HTTP_201_CREATED)
def submit_public_inquiry(
    req: InquirySubmitRequest,
    service: AdmissionsService = Depends(get_admissions_service),
):
    inquiry = service.submit_inquiry(
        organization_id=req.organization_id,
        applicant_name=req.applicant_name,
        guardian_name=req.guardian_name,
        email=req.email,
        phone=req.phone,
        target_grade=req.target_grade,
        notes=req.notes,
    )
    return inquiry.__dict__


# ── Authenticated Endpoints ──────────────────────────────────────────────────

@router.get("/inquiries")
def list_inquiries(
    current_user: Any = Depends(get_current_user),
    service: AdmissionsService = Depends(get_admissions_service),
):
    org_id = _get_org_id(current_user)
    inquiries = service.list_inquiries(org_id)
    return [i.__dict__ for i in inquiries]


@router.post("/applications", status_code=status.HTTP_201_CREATED)
def submit_application(
    req: ApplicationSubmitRequest,
    current_user: Any = Depends(get_current_user),
    service: AdmissionsService = Depends(get_admissions_service),
):
    org_id = _get_org_id(current_user)
    app = service.submit_application(
        organization_id=org_id,
        applicant_name=req.applicant_name,
        academic_year_id=req.academic_year_id,
        inquiry_id=req.inquiry_id,
        date_of_birth=req.date_of_birth,
        gender=req.gender,
        email=req.email,
        phone=req.phone,
        address=req.address,
        previous_school=req.previous_school,
        target_grade=req.target_grade,
    )
    return app.__dict__


@router.get("/applications")
def list_applications(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: Any = Depends(get_current_user),
    service: AdmissionsService = Depends(get_admissions_service),
):
    org_id = _get_org_id(current_user)
    apps = service.list_applications(org_id, status=status_filter)
    return [a.__dict__ for a in apps]


@router.get("/applications/{app_id}")
def get_application(
    app_id: str,
    current_user: Any = Depends(get_current_user),
    service: AdmissionsService = Depends(get_admissions_service),
):
    org_id = _get_org_id(current_user)
    app = service.get_application(app_id, org_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app.__dict__


@router.post("/applications/{app_id}/offer", status_code=status.HTTP_201_CREATED)
def issue_offer(
    app_id: str,
    req: OfferIssueRequest,
    current_user: Any = Depends(get_current_user),
    service: AdmissionsService = Depends(get_admissions_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required to issue offers")

    org_id = _get_org_id(current_user)
    offer = service.issue_offer(
        organization_id=org_id,
        application_id=app_id,
        grade=req.grade,
        fee_amount=req.fee_amount,
        valid_until=req.valid_until,
        conditions=req.conditions,
    )
    return offer.__dict__


@router.post("/applications/{app_id}/convert")
def convert_to_student(
    app_id: str,
    req: ApplicationConvertRequest,
    current_user: Any = Depends(get_current_user),
    service: AdmissionsService = Depends(get_admissions_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required to convert applications")

    org_id = _get_org_id(current_user)
    try:
        result = service.convert_application_to_student(
            organization_id=org_id,
            application_id=app_id,
            class_id=req.class_id,
            roll_number=req.roll_number,
            guardian_name=req.guardian_name,
            guardian_phone=req.guardian_phone,
            guardian_relationship=req.guardian_relationship,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
