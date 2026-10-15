"""Gayatri AI Platform — Authoritative Enrollments API Endpoints (Phase 12).

Section 12.12: Real Online API Boundary
- Pure route/service separation connecting to PlatformDatabase
- Student course enrollment lifecycle
- Scoped multi-tenant and course authorization checks
- RBAC boundary enforcement (students scoped to self, teachers/admins scoped to org/cohort)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.api.schemas import (
    ApiResponse,
    EnrollmentCreateRequest,
    EnrollmentResponse,
)
from central_platform.auth.dependencies import (
    enforce_resource_boundaries,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    CourseVisibility,
    Enrollment,
    User,
    UserRole,
)
from central_platform.rbac.engine import normalize_role

logger = logging.getLogger("gayatri.api.enrollments")

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


def _to_enrollment_response(e: Enrollment) -> EnrollmentResponse:
    """Map domain Enrollment to EnrollmentResponse schema."""
    enrolled_at_str = (
        e.enrolled_at.isoformat()
        if hasattr(e.enrolled_at, "isoformat")
        else str(e.enrolled_at or datetime.now(timezone.utc).isoformat())
    )
    status_str = "ACTIVE" if e.is_active else "INACTIVE"
    return EnrollmentResponse(
        id=e.id,
        student_id=e.student_id,
        course_id=e.course_id,
        course_offering_id=None,
        class_id=e.cohort_id,
        status=status_str,
        enrolled_at=enrolled_at_str,
    )


@router.get("", response_model=ApiResponse[List[EnrollmentResponse]])
async def list_enrollments(
    student_id: Optional[str] = Query(None, description="Filter enrollments by student ID"),
    course_id: Optional[str] = Query(None, description="Filter enrollments by course ID"),
    db: PlatformDatabase = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List course enrollments with RBAC boundary checks."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    effective_student_id = student_id
    user_role = normalize_role(current_user.role) if current_user else None
    if current_user and user_role:
        if user_role == UserRole.STUDENT:
            # Student can only list their own enrollments
            if student_id and student_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Students can only view their own enrollments.",
                )
            effective_student_id = current_user.id
        elif user_role == UserRole.PARENT:
            if student_id:
                enforce_resource_boundaries(current_user, target_student_id=student_id)
                effective_student_id = student_id
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="student_id query parameter required for parent queries",
                )
        else:
            if student_id:
                enforce_resource_boundaries(current_user, target_student_id=student_id)
                effective_student_id = student_id

    if effective_student_id:
        enrollments = db.get_enrollments_for_student(effective_student_id)
        if course_id:
            enrollments = [e for e in enrollments if e.course_id == course_id]
        return ApiResponse(ok=True, data=[_to_enrollment_response(e) for e in enrollments])

    # For teachers/admins, query by course or return matching tenant enrollments
    with db._get_connection() as conn:
        cur = conn.cursor()
        query = (
            "SELECT e.id, e.student_id, e.course_id, e.cohort_id, e.enrolled_at, e.is_active "
            "FROM enrollments e JOIN users u ON e.student_id = u.id WHERE 1=1"
        )
        params = []
        if current_user and user_role != UserRole.SUPER_ADMIN and current_user.organization_id:
            query += " AND u.organization_id = ?"
            params.append(current_user.organization_id)
        if course_id:
            query += " AND e.course_id = ?"
            params.append(course_id)
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

    results = []
    for r in rows:
        results.append(
            EnrollmentResponse(
                id=r[0],
                student_id=r[1],
                course_id=r[2],
                class_id=r[3],
                status="ACTIVE" if r[5] else "INACTIVE",
                enrolled_at=str(r[4] or ""),
            )
        )
    return ApiResponse(ok=True, data=results)


@router.post("", response_model=ApiResponse[EnrollmentResponse], status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    req: EnrollmentCreateRequest,
    db: PlatformDatabase = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Enroll a student into a course."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Verify course exists
    course = db.get_course(req.course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{req.course_id}' not found.",
        )

    if current_user:
        u_role = normalize_role(current_user.role)
        if u_role == UserRole.STUDENT and req.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only enroll themselves.",
            )
        if u_role != UserRole.SUPER_ADMIN:
            if course.organization_id and current_user.organization_id != course.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: course '{req.course_id}' belongs to another organization",
                )
            enforce_resource_boundaries(current_user, target_student_id=req.student_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{req.course_id}' not found.",
        )

    # 2. Check private course authorization
    is_private = (
        course.visibility == CourseVisibility.PRIVATE
        or str(course.visibility).upper() == "PRIVATE"
    )
    if is_private:
        # Check active course offering or user org
        student_user = db.get_user(req.student_id)
        student_org = student_user.organization_id if student_user else (current_user.organization_id if current_user else None)
        if student_org:
            offering = db.get_course_offering_by_org_and_course(student_org, req.course_id)
            if not offering and course.organization_id != student_org:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Student organization '{student_org}' is not authorized to enroll in private course '{req.course_id}'.",
                )

    # Ensure student user exists in users table (foreign key constraint)
    student_user = db.get_user(req.student_id)
    if not student_user:
        student_user = User(
            id=req.student_id,
            email=f"{req.student_id}@student.platform.local",
            full_name=f"Student {req.student_id}",
            role=UserRole.STUDENT,
            organization_id=course.organization_id or "org-default",
        )
        db.create_user(student_user)

    # Validate cohort exists if provided
    cohort_id = req.class_id
    if cohort_id:
        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM cohorts WHERE id = ?", (cohort_id,))
            if not cur.fetchone():
                cohort_id = None

    enr_id = f"enr-{uuid.uuid4().hex[:8]}"
    enr = Enrollment(
        id=enr_id,
        student_id=req.student_id,
        course_id=req.course_id,
        cohort_id=cohort_id,
        enrolled_at=datetime.now(timezone.utc),
        is_active=True,
    )
    created = db.create_enrollment(enr)
    return ApiResponse(ok=True, data=_to_enrollment_response(created))


@router.get("/{enrollment_id}", response_model=ApiResponse[EnrollmentResponse])
async def get_enrollment(
    enrollment_id: str,
    db: PlatformDatabase = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get enrollment by ID."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, student_id, course_id, cohort_id, enrolled_at, is_active FROM enrollments WHERE id = ?",
            (enrollment_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enrollment '{enrollment_id}' not found.",
        )

    e = EnrollmentResponse(
        id=row[0],
        student_id=row[1],
        course_id=row[2],
        class_id=row[3],
        status="ACTIVE" if row[5] else "INACTIVE",
        enrolled_at=str(row[4] or ""),
    )

    if current_user:
        enforce_resource_boundaries(current_user, target_student_id=e.student_id)

    return ApiResponse(ok=True, data=e)
