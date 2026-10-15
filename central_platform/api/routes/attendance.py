"""Gayatri School OS — Attendance API Router (Phase 03)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user, get_db
from central_platform.db import PlatformDatabase
from central_platform.attendance.service import AttendanceService
from central_platform.models.attendance import AttendanceStatus, SessionType
from central_platform.api.routes.identity import _get_org_id, _get_roles

logger = logging.getLogger("gayatri.api.routes.attendance")

router = APIRouter(prefix="/attendance", tags=["Attendance Tracking"])


def get_attendance_service(db: PlatformDatabase = Depends(get_db)) -> AttendanceService:
    return AttendanceService(db)


class SessionCreateRequest(BaseModel):
    academic_year_id: str
    class_id: str
    date: str
    session_type: SessionType = SessionType.FULL_DAY


class RollCallSubmissionRequest(BaseModel):
    records: List[Dict[str, Any]]


class CorrectionRequest(BaseModel):
    new_status: AttendanceStatus
    reason: str


class ExcuseSubmitRequest(BaseModel):
    student_id: str
    start_date: str
    end_date: str
    reason: str


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    req: SessionCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "system")
    sess = service.create_session(
        organization_id=org_id,
        academic_year_id=req.academic_year_id,
        class_id=req.class_id,
        date=req.date,
        session_type=req.session_type,
        taken_by=user_id,
    )
    return sess.__dict__


@router.get("/sessions")
def list_sessions(
    class_id: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    current_user: Any = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    org_id = _get_org_id(current_user)
    sessions = service.list_sessions(org_id, class_id=class_id, date=date)
    return [s.__dict__ for s in sessions]


@router.post("/sessions/{session_id}/records", status_code=status.HTTP_200_OK)
def submit_roll_call(
    session_id: str,
    req: RollCallSubmissionRequest,
    current_user: Any = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    org_id = _get_org_id(current_user)
    records = service.record_roll_call(org_id, session_id, req.records)
    return [r.__dict__ for r in records]


@router.get("/sessions/{session_id}/records")
def get_session_records(
    session_id: str,
    current_user: Any = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    org_id = _get_org_id(current_user)
    records = service.get_session_records(org_id, session_id)
    return [r.__dict__ for r in records]


@router.post("/records/{record_id}/correct")
def correct_attendance(
    record_id: str,
    req: CorrectionRequest,
    current_user: Any = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin", "teacher") for r in roles):
        raise HTTPException(status_code=403, detail="Permission required to correct attendance")

    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "admin")
    try:
        corr = service.correct_attendance(
            organization_id=org_id,
            record_id=record_id,
            new_status=req.new_status,
            reason=req.reason,
            corrected_by=user_id,
        )
        return corr.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/excuses", status_code=status.HTTP_201_CREATED)
def submit_excuse(
    req: ExcuseSubmitRequest,
    current_user: Any = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    org_id = _get_org_id(current_user)
    excuse = service.submit_excuse_request(
        organization_id=org_id,
        student_id=req.student_id,
        start_date=req.start_date,
        end_date=req.end_date,
        reason=req.reason,
    )
    return excuse.__dict__


@router.post("/excuses/{excuse_id}/approve")
def approve_excuse(
    excuse_id: str,
    current_user: Any = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required to approve excuse")

    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "admin")
    try:
        excuse = service.approve_excuse_request(org_id, excuse_id, approved_by=user_id)
        return excuse.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
