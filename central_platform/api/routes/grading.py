"""Gayatri School OS — Grading API Router (Phase 04)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user
from central_platform.db import PlatformDatabase
from central_platform.grading.service import GradingService
from central_platform.models.grading import ScaleType
from central_platform.api.routes.identity import _get_org_id

logger = logging.getLogger("gayatri.api.routes.grading")

router = APIRouter(prefix="/grading", tags=["Grading Engine"])


def get_db() -> PlatformDatabase:
    return PlatformDatabase()


def get_grading_service(db: PlatformDatabase = Depends(get_db)) -> GradingService:
    return GradingService(db)


class GradingTierInput(BaseModel):
    grade_name: str
    grade_point: float = 0.0
    min_percentage: float
    max_percentage: float
    description: Optional[str] = None


class GradingScaleCreateRequest(BaseModel):
    name: str
    code: str
    scale_type: ScaleType = ScaleType.NINE_POINT
    tiers: Optional[List[GradingTierInput]] = None
    is_default: bool = False


class CalculateTermRequest(BaseModel):
    student_id: str
    academic_year_id: str
    academic_term_id: Optional[str] = None
    scale_id: Optional[str] = None


@router.post("/scales", status_code=status.HTTP_201_CREATED)
def create_scale(
    req: GradingScaleCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: GradingService = Depends(get_grading_service),
):
    org_id = _get_org_id(current_user)
    tiers_data = [t.dict() for t in req.tiers] if req.tiers else None
    scale = service.create_grading_scale(
        organization_id=org_id,
        name=req.name,
        code=req.code,
        scale_type=req.scale_type,
        tiers=tiers_data,
        is_default=req.is_default,
    )
    return scale.__dict__


@router.get("/scales")
def list_scales(
    current_user: Any = Depends(get_current_user),
    service: GradingService = Depends(get_grading_service),
):
    org_id = _get_org_id(current_user)
    return [s.__dict__ for s in service.list_grading_scales(org_id)]


@router.get("/scales/{scale_id}/tiers")
def list_scale_tiers(
    scale_id: str,
    current_user: Any = Depends(get_current_user),
    service: GradingService = Depends(get_grading_service),
):
    org_id = _get_org_id(current_user)
    return [t.__dict__ for t in service.get_grading_tiers(org_id, scale_id)]


@router.post("/calculate-term", status_code=status.HTTP_200_OK)
def calculate_term(
    req: CalculateTermRequest,
    current_user: Any = Depends(get_current_user),
    service: GradingService = Depends(get_grading_service),
):
    org_id = _get_org_id(current_user)
    result = service.calculate_term_result(
        organization_id=org_id,
        student_id=req.student_id,
        academic_year_id=req.academic_year_id,
        academic_term_id=req.academic_term_id,
        scale_id=req.scale_id,
    )
    return result.__dict__
