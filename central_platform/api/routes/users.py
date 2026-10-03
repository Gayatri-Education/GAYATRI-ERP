"""Gayatri AI Platform — Users API Endpoints (Phase 04).

Master Plan Section 13:
- User provisioning and lookup
- Role-based permissions (only admins can create users)
- Tenant scope enforcement (org admin cannot provision for another organization)
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from central_platform.api.schemas import ApiResponse, UserCreateRequest, UserResponse
from central_platform.auth.dependencies import (
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.models.schema import User, UserRole

logger = logging.getLogger("gayatri.central_platform.api.routes.users")

router = APIRouter(prefix="/users", tags=["Users"])

_USERS_STORE = [
    UserResponse(
        user_id="usr-admin-01",
        username="admin",
        email="admin@gayatri.ai",
        role="SUPER_ADMIN",
        organization_id="org-central",
        is_active=True,
    ),
    UserResponse(
        user_id="usr-teacher-01",
        username="teacher_sharma",
        email="sharma@gayatri.ai",
        role="TEACHER",
        organization_id="org-central",
        is_active=True,
    ),
    UserResponse(
        user_id="usr-student-01",
        username="student_001",
        email="student01@gayatri.ai",
        role="STUDENT",
        organization_id="org-central",
        is_active=True,
    ),
]


@router.get("", response_model=ApiResponse[List[UserResponse]])
async def list_users(
    role: Optional[str] = Query(default=None),
    organization_id: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List platform users with optional role or org filtering."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students cannot list users",
            )
        if current_user.role == UserRole.ORG_ADMIN and organization_id:
            if organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: cross-org user query for '{organization_id}' prohibited",
                )

    results = _USERS_STORE
    if role:
        results = [u for u in results if u.role.upper() == role.upper()]
    if organization_id:
        results = [u for u in results if u.organization_id == organization_id]
    return ApiResponse(ok=True, data=results)


@router.post("", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(
    req: UserCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new platform user."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        if current_user.role in (UserRole.STUDENT, UserRole.TEACHER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: only administrators can create users",
            )
        if current_user.role == UserRole.ORG_ADMIN:
            # Org admin cannot create users for another organization (modified organization_id)
            if req.organization_id and req.organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: cannot create user in organization '{req.organization_id}' outside your tenant",
                )
            if req.role.upper() in ("SUPER_ADMIN", "ORG_ADMIN"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: org admin cannot provision super admin or org admin accounts",
                )

    new_user = UserResponse(
        user_id=f"usr-{uuid.uuid4().hex[:8]}",
        username=req.username,
        email=req.email,
        role=req.role.upper(),
        organization_id=req.organization_id,
        is_active=True,
    )
    _USERS_STORE.append(new_user)

    # Also persist to DB if DB is active
    try:
        db = get_db()
        db_user = User(
            id=new_user.user_id,
            email=new_user.email,
            full_name=new_user.username,
            role=UserRole(new_user.role),
            organization_id=new_user.organization_id,
            is_active=True,
        )
        db.create_user(db_user)
        if req.password:
            db.set_user_password(db_user.id, req.password)
    except Exception as exc:
        logger.warning("Failed to persist user %s into database: %s", new_user.user_id, exc)

    return ApiResponse(ok=True, data=new_user)


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user_by_id(
    user_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get user by unique ID."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        if current_user.role == UserRole.STUDENT and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students can only access their own profile",
            )

    for u in _USERS_STORE:
        if u.user_id == user_id:
            return ApiResponse(ok=True, data=u)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
