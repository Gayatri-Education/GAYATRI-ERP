"""Gayatri AI Platform — Tutoring Sessions API Endpoints (Phase 04).

Master Plan Section 13:
- Session initiation and lifecycle management
- Student session isolation (modified session_id -> 403 Forbidden)
- Payload identity spoofing defense (modified student_id -> 403 Forbidden)
"""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from central_platform.api.schemas import ApiResponse, SessionResponse, SessionStartRequest
from datetime import datetime, timezone
import logging
from central_platform.auth.dependencies import (
    enforce_resource_boundaries,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import Session as DbSession, SessionStatus, User, UserRole

logger = logging.getLogger("gayatri.api.routes.sessions")

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", response_model=ApiResponse[SessionResponse], status_code=status.HTTP_201_CREATED)
@router.post("/start", response_model=ApiResponse[SessionResponse], status_code=status.HTTP_201_CREATED)
async def start_session(
    req: SessionStartRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: PlatformDatabase = Depends(get_db),
):
    """Start an interactive adaptive tutoring session for a student."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to start a session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user and current_user.role == UserRole.STUDENT:
        if req.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: student_id in request body does not match authenticated student",
            )

    sess_id = f"sess-{uuid.uuid4().hex[:8]}"
    db_sess = DbSession(
        id=sess_id,
        student_id=req.student_id,
        course_id=req.course_id,
        concept_id=req.initial_concept or "chem_thermo_first_law",
        status=SessionStatus.ACTIVE,
        started_at=datetime.now(timezone.utc),
    )
    if not is_production_mode():
        try:
            with db.transaction():
                if not db.get_organization("org-central"):
                    from central_platform.models.schema import Organization
                    db.create_organization(Organization(id="org-central", name="Gayatri Central Platform", slug="org-central"))
                if not db.get_course(req.course_id):
                    from central_platform.models.schema import Course
                    db.create_course(Course(id=req.course_id, organization_id="org-central", code=req.course_id, title=req.course_id))
                if not db.get_user(req.student_id):
                    db.create_user(User(id=req.student_id, email=f"{req.student_id}@platform.local", full_name=req.student_id, role=UserRole.STUDENT, organization_id="org-central"))
        except Exception:
            pass

    with db.transaction():
        db.create_session(db_sess)

    resp = SessionResponse(
        session_id=db_sess.id,
        student_id=db_sess.student_id,
        course_id=db_sess.course_id,
        active_concept=db_sess.concept_id or "foundations",
        status="ACTIVE",
    )
    return ApiResponse(ok=True, data=resp)


@router.get("/{session_id}", response_model=ApiResponse[SessionResponse])
async def get_session(
    session_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: PlatformDatabase = Depends(get_db),
):
    """Get active session details."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db_sess = db.get_session(session_id)
    if not db_sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if current_user:
        enforce_resource_boundaries(current_user, target_session_student_id=db_sess.student_id)

    status_str = db_sess.status.value if hasattr(db_sess.status, "value") else str(db_sess.status)
    resp = SessionResponse(
        session_id=db_sess.id,
        student_id=db_sess.student_id,
        course_id=db_sess.course_id,
        active_concept=db_sess.concept_id or "foundations",
        status=status_str.upper(),
    )
    return ApiResponse(ok=True, data=resp)

