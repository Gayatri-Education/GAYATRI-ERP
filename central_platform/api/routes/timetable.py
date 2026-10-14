"""Gayatri School OS — Timetable & Scheduling API Router (Phase 03)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user
from central_platform.db import PlatformDatabase
from central_platform.timetable.service import TimetableService
from central_platform.models.timetable import DayOfWeek
from central_platform.api.routes.identity import _get_org_id, _get_roles

logger = logging.getLogger("gayatri.api.routes.timetable")

router = APIRouter(prefix="/timetable", tags=["Timetable & Scheduling"])


def get_db() -> PlatformDatabase:
    return PlatformDatabase()


def get_timetable_service(db: PlatformDatabase = Depends(get_db)) -> TimetableService:
    return TimetableService(db)


class PeriodCreateRequest(BaseModel):
    academic_year_id: str
    name: str
    period_number: int
    start_time: str
    end_time: str
    is_break: bool = False


class SlotCreateRequest(BaseModel):
    academic_year_id: str
    class_id: str
    period_id: str
    day_of_week: DayOfWeek
    subject_id: Optional[str] = None
    teacher_id: Optional[str] = None
    room_name: Optional[str] = None


class SubstitutionCreateRequest(BaseModel):
    slot_id: str
    date: str
    original_teacher_id: str
    substitute_teacher_id: str
    reason: Optional[str] = None


@router.post("/periods", status_code=status.HTTP_201_CREATED)
def create_period(
    req: PeriodCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: TimetableService = Depends(get_timetable_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    period = service.create_period(
        organization_id=org_id,
        academic_year_id=req.academic_year_id,
        name=req.name,
        period_number=req.period_number,
        start_time=req.start_time,
        end_time=req.end_time,
        is_break=req.is_break,
    )
    return period.__dict__


@router.get("/periods")
def list_periods(
    academic_year_id: str = Query(...),
    current_user: Any = Depends(get_current_user),
    service: TimetableService = Depends(get_timetable_service),
):
    org_id = _get_org_id(current_user)
    periods = service.list_periods(org_id, academic_year_id)
    return [p.__dict__ for p in periods]


@router.post("/slots", status_code=status.HTTP_201_CREATED)
def create_slot(
    req: SlotCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: TimetableService = Depends(get_timetable_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    try:
        slot = service.create_slot(
            organization_id=org_id,
            academic_year_id=req.academic_year_id,
            class_id=req.class_id,
            period_id=req.period_id,
            day_of_week=req.day_of_week,
            subject_id=req.subject_id,
            teacher_id=req.teacher_id,
            room_name=req.room_name,
        )
        return slot.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/classes/{class_id}")
def get_class_slots(
    class_id: str,
    current_user: Any = Depends(get_current_user),
    service: TimetableService = Depends(get_timetable_service),
):
    org_id = _get_org_id(current_user)
    slots = service.get_class_slots(org_id, class_id)
    return [s.__dict__ for s in slots]


@router.post("/substitutions", status_code=status.HTTP_201_CREATED)
def assign_substitution(
    req: SubstitutionCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: TimetableService = Depends(get_timetable_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    sub = service.assign_substitution(
        organization_id=org_id,
        slot_id=req.slot_id,
        date=req.date,
        original_teacher_id=req.original_teacher_id,
        substitute_teacher_id=req.substitute_teacher_id,
        reason=req.reason,
    )
    return sub.__dict__
