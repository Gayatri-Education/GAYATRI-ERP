"""Gayatri AI Platform — Classes & Cohorts API Endpoints (Phase 12).

Section 12.12: Real Online API Boundary
- Pure route/service separation connecting to PlatformDatabase
- Class group management (course-bound cohorts)
- Cohort creation and grouping for student rosters
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.api.schemas import (
    ApiResponse,
    ClassGroupCreateRequest,
    ClassGroupResponse,
    CohortCreateRequest,
    CohortResponse,
)
from central_platform.auth.dependencies import (
    get_current_user,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import ClassGroup, Cohort, User, UserRole
from central_platform.rbac.engine import normalize_role

logger = logging.getLogger("gayatri.api.classes")

router = APIRouter(prefix="/classes", tags=["Classes & Cohorts"])


@router.get("", response_model=ApiResponse[List[ClassGroupResponse]])
async def list_classes(
    organization_id: Optional[str] = Query(None, description="Filter by organization ID"),
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    db: PlatformDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List class groups with tenant isolation."""
    user_role = normalize_role(current_user.role)
    if user_role != UserRole.SUPER_ADMIN:
        if organization_id and organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: cross-organization access to '{organization_id}' prohibited",
            )
        effective_org_id = current_user.organization_id
    else:
        effective_org_id = organization_id

    query = "SELECT id, organization_id, course_id, name, section, created_at FROM class_groups WHERE 1=1"
    params = []
    if effective_org_id:
        query += " AND organization_id = ?"
        params.append(effective_org_id)
    if course_id:
        query += " AND course_id = ?"
        params.append(course_id)

    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

    results = [
        ClassGroupResponse(
            id=r[0],
            organization_id=r[1],
            course_id=r[2],
            name=r[3],
            created_at=str(r[5] or ""),
        )
        for r in rows
    ]
    return ApiResponse(ok=True, data=results)


@router.post("", response_model=ApiResponse[ClassGroupResponse], status_code=status.HTTP_201_CREATED)
async def create_class_group(
    req: ClassGroupCreateRequest,
    db: PlatformDatabase = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new class group."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role in (UserRole.STUDENT, UserRole.PARENT):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students and parents are not authorized to create class groups",
            )
        if user_role != UserRole.SUPER_ADMIN:
            if current_user.organization_id and current_user.organization_id != req.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: cross-organization class creation is prohibited ('{req.organization_id}' != '{current_user.organization_id}')",
                )

    # Ensure organization exists in database
    if not db.get_organization(req.organization_id):
        from central_platform.models.schema import Organization
        db.create_organization(Organization(id=req.organization_id, name=req.organization_id, slug=req.organization_id))

    class_id = req.id or f"cls-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    cg = ClassGroup(
        id=class_id,
        organization_id=req.organization_id,
        course_id=req.course_id,
        name=req.name,
        section="A",
        created_at=now,
    )
    created = db.create_class_group(cg)
    return ApiResponse(
        ok=True,
        data=ClassGroupResponse(
            id=created.id,
            name=created.name,
            course_id=created.course_id,
            organization_id=created.organization_id,
            teacher_id=req.teacher_id,
            created_at=now.isoformat(),
        ),
    )


@router.get("/{class_id}", response_model=ApiResponse[ClassGroupResponse])
async def get_class_group(
    class_id: str,
    db: PlatformDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get class group by ID with tenant scoping."""
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, organization_id, course_id, name, section, created_at FROM class_groups WHERE id = ?",
            (class_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class group '{class_id}' not found.",
        )

    user_role = normalize_role(current_user.role)
    if user_role != UserRole.SUPER_ADMIN and row[1] != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: cross-organization access to class group '{class_id}' prohibited",
        )

    return ApiResponse(
        ok=True,
        data=ClassGroupResponse(
            id=row[0],
            organization_id=row[1],
            course_id=row[2],
            name=row[3],
            created_at=str(row[5] or ""),
        ),
    )


@router.post("/{class_id}/cohorts", response_model=ApiResponse[CohortResponse], status_code=status.HTTP_201_CREATED)
async def create_cohort_for_class(
    class_id: str,
    req: CohortCreateRequest,
    db: PlatformDatabase = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a cohort in a class group."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role in (UserRole.STUDENT, UserRole.PARENT):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students and parents are not authorized to create cohorts",
            )
        if req.organization_id and user_role != UserRole.SUPER_ADMIN:
            if current_user.organization_id and current_user.organization_id != req.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: cross-organization cohort creation is prohibited ('{req.organization_id}' != '{current_user.organization_id}')",
                )

    cohort_id = req.id or f"coh-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    cohort = Cohort(
        id=cohort_id,
        class_group_id=class_id,
        name=req.name,
        academic_year="2026-2027",
        created_at=now,
    )
    created = db.create_cohort(cohort)
    return ApiResponse(
        ok=True,
        data=CohortResponse(
            id=created.id,
            name=created.name,
            class_id=created.class_group_id,
            course_id=req.course_id,
            organization_id=req.organization_id,
            created_at=now.isoformat(),
        ),
    )


@router.get("/{class_id}/cohorts", response_model=ApiResponse[List[CohortResponse]])
async def list_cohorts_for_class(
    class_id: str,
    db: PlatformDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List cohorts belonging to a class group with tenant verification."""
    user_role = normalize_role(current_user.role)
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT organization_id FROM class_groups WHERE id = ?",
            (class_id,),
        )
        cg_row = cur.fetchone()
        if not cg_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Class group '{class_id}' not found.",
            )
        if user_role != UserRole.SUPER_ADMIN and cg_row[0] != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: cross-organization access to cohorts of class '{class_id}' prohibited",
            )

        cur.execute(
            "SELECT id, class_group_id, name, academic_year, created_at FROM cohorts WHERE class_group_id = ?",
            (class_id,),
        )
        rows = cur.fetchall()

    results = [
        CohortResponse(
            id=r[0],
            class_id=r[1],
            name=r[2],
            course_id="",
            organization_id="",
            created_at=str(r[4] or ""),
        )
        for r in rows
    ]
    return ApiResponse(ok=True, data=results)
