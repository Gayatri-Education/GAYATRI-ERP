"""Gayatri School OS — Examinations API Router (Phase 04)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user, get_db
from central_platform.db import PlatformDatabase
from central_platform.examinations.service import ExaminationService
from central_platform.models.examinations import ExamSeriesType, MarksStatus
from central_platform.api.routes.identity import _get_org_id, _get_roles

logger = logging.getLogger("gayatri.api.routes.examinations")

router = APIRouter(prefix="/examinations", tags=["Examinations"])


def get_examination_service(db: PlatformDatabase = Depends(get_db)) -> ExaminationService:
    return ExaminationService(db)


class ExamSeriesCreateRequest(BaseModel):
    academic_year_id: str
    name: str
    code: str
    start_date: str
    end_date: str
    academic_term_id: Optional[str] = None
    series_type: ExamSeriesType = ExamSeriesType.MID_TERM
    status: str = "SCHEDULED"


class ExamScheduleCreateRequest(BaseModel):
    exam_series_id: str
    class_id: str
    subject_id: str
    exam_date: str
    start_time: str
    end_time: str
    max_marks: float = 100.0
    pass_marks: float = 35.0
    room_name: Optional[str] = None


class MarksEntryRequest(BaseModel):
    student_id: str
    marks_obtained: Optional[float] = None
    is_absent: bool = False
    is_exempt: bool = False
    remarks: Optional[str] = None


@router.post("/series", status_code=status.HTTP_201_CREATED)
def create_series(
    req: ExamSeriesCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: ExaminationService = Depends(get_examination_service),
):
    org_id = _get_org_id(current_user)
    series = service.create_exam_series(
        organization_id=org_id,
        academic_year_id=req.academic_year_id,
        name=req.name,
        code=req.code,
        start_date=req.start_date,
        end_date=req.end_date,
        academic_term_id=req.academic_term_id,
        series_type=req.series_type,
        status=req.status,
    )
    return series.__dict__


@router.get("/series")
def list_series(
    academic_year_id: Optional[str] = Query(None),
    current_user: Any = Depends(get_current_user),
    service: ExaminationService = Depends(get_examination_service),
):
    org_id = _get_org_id(current_user)
    return [s.__dict__ for s in service.list_exam_series(org_id, academic_year_id)]


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(
    req: ExamScheduleCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: ExaminationService = Depends(get_examination_service),
):
    org_id = _get_org_id(current_user)
    sched = service.schedule_exam(
        organization_id=org_id,
        exam_series_id=req.exam_series_id,
        class_id=req.class_id,
        subject_id=req.subject_id,
        exam_date=req.exam_date,
        start_time=req.start_time,
        end_time=req.end_time,
        max_marks=req.max_marks,
        pass_marks=req.pass_marks,
        room_name=req.room_name,
    )
    return sched.__dict__


@router.get("/schedules")
def list_schedules(
    exam_series_id: str = Query(...),
    current_user: Any = Depends(get_current_user),
    service: ExaminationService = Depends(get_examination_service),
):
    org_id = _get_org_id(current_user)
    return [s.__dict__ for s in service.list_schedules_for_series(org_id, exam_series_id)]


@router.post("/schedules/{schedule_id}/marks", status_code=status.HTTP_200_OK)
def enter_student_marks(
    schedule_id: str,
    req: MarksEntryRequest,
    current_user: Any = Depends(get_current_user),
    service: ExaminationService = Depends(get_examination_service),
):
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "teacher")
    try:
        entry = service.enter_marks(
            organization_id=org_id,
            schedule_id=schedule_id,
            student_id=req.student_id,
            marks_obtained=req.marks_obtained,
            entered_by=user_id,
            is_absent=req.is_absent,
            is_exempt=req.is_exempt,
            remarks=req.remarks,
        )
        return entry.__dict__
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/schedules/{schedule_id}/marks")
def list_marks(
    schedule_id: str,
    current_user: Any = Depends(get_current_user),
    service: ExaminationService = Depends(get_examination_service),
):
    org_id = _get_org_id(current_user)
    return [m.__dict__ for m in service.list_marks_for_schedule(org_id, schedule_id)]


@router.post("/schedules/{schedule_id}/lock", status_code=status.HTTP_200_OK)
def lock_schedule_marks(
    schedule_id: str,
    current_user: Any = Depends(get_current_user),
    service: ExaminationService = Depends(get_examination_service),
):
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "controller")
    try:
        sched = service.lock_marks(org_id, schedule_id, verified_by=user_id)
        return sched.__dict__
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
