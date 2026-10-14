"""Gayatri School OS — Report Cards API Router (Phase 04)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user
from central_platform.db import PlatformDatabase
from central_platform.grading.service import GradingService
from central_platform.api.routes.identity import _get_org_id

logger = logging.getLogger("gayatri.api.routes.reports")

router = APIRouter(prefix="/reports", tags=["Report Cards & Transcripts"])


def get_db() -> PlatformDatabase:
    return PlatformDatabase()


def get_grading_service(db: PlatformDatabase = Depends(get_db)) -> GradingService:
    return GradingService(db)


class ReportCardGenerateRequest(BaseModel):
    student_id: str
    academic_year_id: str
    academic_term_id: Optional[str] = None
    general_remarks: Optional[str] = None


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_report(
    req: ReportCardGenerateRequest,
    current_user: Any = Depends(get_current_user),
    service: GradingService = Depends(get_grading_service),
):
    org_id = _get_org_id(current_user)
    card = service.generate_report_card(
        organization_id=org_id,
        student_id=req.student_id,
        academic_year_id=req.academic_year_id,
        academic_term_id=req.academic_term_id,
        general_remarks=req.general_remarks,
    )
    return card.__dict__


@router.post("/{report_id}/publish", status_code=status.HTTP_200_OK)
def publish_report(
    report_id: str,
    current_user: Any = Depends(get_current_user),
    service: GradingService = Depends(get_grading_service),
):
    org_id = _get_org_id(current_user)
    try:
        card = service.publish_report_card(org_id, report_id)
        return card.__dict__
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/student/{student_id}")
def list_student_reports(
    student_id: str,
    current_user: Any = Depends(get_current_user),
    service: GradingService = Depends(get_grading_service),
):
    org_id = _get_org_id(current_user)
    return [c.__dict__ for c in service.list_report_cards_for_student(org_id, student_id)]


@router.get("/{report_id}")
def get_report(
    report_id: str,
    current_user: Any = Depends(get_current_user),
    service: GradingService = Depends(get_grading_service),
):
    org_id = _get_org_id(current_user)
    card = service.get_report_card(org_id, report_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report card not found")
    return card.__dict__
