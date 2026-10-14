"""Gayatri School OS — Academic Calendar & Structure API Router (Phase 02B)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user
from central_platform.db import PlatformDatabase
from central_platform.academic.service import AcademicService
from central_platform.api.routes.identity import _get_org_id, _get_roles

logger = logging.getLogger("gayatri.api.routes.academic")

router = APIRouter(prefix="/academic", tags=["Academic Calendar"])


def get_db() -> PlatformDatabase:
    return PlatformDatabase()


def get_academic_service(db: PlatformDatabase = Depends(get_db)) -> AcademicService:
    return AcademicService(db)


class AcademicYearCreateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    code: str = Field(..., min_length=2)
    start_date: str
    end_date: str
    is_current: bool = False


class AcademicTermCreateRequest(BaseModel):
    academic_year_id: str
    name: str
    code: str
    start_date: str
    end_date: str


class CalendarEventCreateRequest(BaseModel):
    academic_year_id: str
    title: str
    event_type: str = "EVENT"
    description: Optional[str] = None
    start_date: str
    end_date: str
    is_holiday: bool = False


@router.post("/years", status_code=status.HTTP_201_CREATED)
def create_academic_year(
    req: AcademicYearCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    year = service.create_academic_year(
        organization_id=org_id,
        name=req.name,
        code=req.code,
        start_date=req.start_date,
        end_date=req.end_date,
        is_current=req.is_current,
    )
    return year.__dict__


@router.get("/years")
def list_academic_years(
    current_user: Any = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
):
    org_id = _get_org_id(current_user)
    years = service.list_academic_years(org_id)
    return [y.__dict__ for y in years]


@router.get("/years/current")
def get_current_year(
    current_user: Any = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
):
    org_id = _get_org_id(current_user)
    year = service.get_current_academic_year(org_id)
    if not year:
        raise HTTPException(status_code=404, detail="No active academic year configured")
    return year.__dict__


@router.post("/terms", status_code=status.HTTP_201_CREATED)
def create_academic_term(
    req: AcademicTermCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    term = service.create_academic_term(
        organization_id=org_id,
        academic_year_id=req.academic_year_id,
        name=req.name,
        code=req.code,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    return term.__dict__


@router.get("/terms")
def list_academic_terms(
    academic_year_id: str = Query(...),
    current_user: Any = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
):
    org_id = _get_org_id(current_user)
    terms = service.list_academic_terms(org_id, academic_year_id)
    return [t.__dict__ for t in terms]


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_calendar_event(
    req: CalendarEventCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    event = service.create_calendar_event(
        organization_id=org_id,
        academic_year_id=req.academic_year_id,
        title=req.title,
        event_type=req.event_type,
        description=req.description,
        start_date=req.start_date,
        end_date=req.end_date,
        is_holiday=req.is_holiday,
    )
    return event.__dict__


@router.get("/events")
def list_calendar_events(
    academic_year_id: str = Query(...),
    current_user: Any = Depends(get_current_user),
    service: AcademicService = Depends(get_academic_service),
):
    org_id = _get_org_id(current_user)
    events = service.list_calendar_events(org_id, academic_year_id)
    return [e.__dict__ for e in events]
