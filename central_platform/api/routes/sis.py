"""Gayatri School OS — Student Information System (SIS) API Router (Phase 02B)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user
from central_platform.db import PlatformDatabase
from central_platform.sis.service import SISService
from central_platform.api.routes.identity import _get_org_id, _get_roles

logger = logging.getLogger("gayatri.api.routes.sis")

router = APIRouter(prefix="/sis", tags=["Student Information System"])


def get_db() -> PlatformDatabase:
    return PlatformDatabase()


def get_sis_service(db: PlatformDatabase = Depends(get_db)) -> SISService:
    return SISService(db)


class ClassCreateRequest(BaseModel):
    academic_year_id: str
    name: str = Field(..., min_length=1)
    grade_level: str
    section: Optional[str] = None
    capacity: int = 40
    class_teacher_id: Optional[str] = None


class StudentEnrollRequest(BaseModel):
    student_id: str
    academic_year_id: str
    roll_number: Optional[str] = None


@router.post("/classes", status_code=status.HTTP_201_CREATED)
def create_class(
    req: ClassCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: SISService = Depends(get_sis_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    cls = service.create_class(
        organization_id=org_id,
        academic_year_id=req.academic_year_id,
        name=req.name,
        grade_level=req.grade_level,
        section=req.section,
        capacity=req.capacity,
        class_teacher_id=req.class_teacher_id,
    )
    return cls.__dict__


@router.get("/classes")
def list_classes(
    academic_year_id: Optional[str] = Query(None),
    current_user: Any = Depends(get_current_user),
    service: SISService = Depends(get_sis_service),
):
    org_id = _get_org_id(current_user)
    classes = service.list_classes(org_id, academic_year_id=academic_year_id)
    return [c.__dict__ for c in classes]


@router.get("/classes/{class_id}")
def get_class(
    class_id: str,
    current_user: Any = Depends(get_current_user),
    service: SISService = Depends(get_sis_service),
):
    org_id = _get_org_id(current_user)
    cls = service.get_class(class_id, org_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls.__dict__


@router.get("/classes/{class_id}/roster")
def get_class_roster(
    class_id: str,
    current_user: Any = Depends(get_current_user),
    service: SISService = Depends(get_sis_service),
):
    org_id = _get_org_id(current_user)
    roster = service.get_class_roster(org_id, class_id)
    return roster


@router.post("/classes/{class_id}/enroll", status_code=status.HTTP_201_CREATED)
def enroll_student(
    class_id: str,
    req: StudentEnrollRequest,
    current_user: Any = Depends(get_current_user),
    service: SISService = Depends(get_sis_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    try:
        enrollment = service.enroll_student_in_class(
            organization_id=org_id,
            student_id=req.student_id,
            class_id=class_id,
            academic_year_id=req.academic_year_id,
            roll_number=req.roll_number,
        )
        return enrollment.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
