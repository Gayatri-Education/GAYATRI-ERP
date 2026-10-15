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
    enforce_resource_boundaries,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import User, UserRole
from central_platform.rbac.engine import normalize_role

logger = logging.getLogger("gayatri.central_platform.api.routes.users")

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=ApiResponse[List[UserResponse]])
async def list_users(
    role: Optional[str] = Query(default=None),
    organization_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500, description="Max users to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: PlatformDatabase = Depends(get_db),
):
    """List platform users with optional role or org filtering."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: administrative privileges required to list users",
            )
        if user_role == UserRole.ORG_ADMIN:
            if organization_id and organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: cross-org user query for '{organization_id}' prohibited",
                )
            organization_id = current_user.organization_id

    db_users = db.list_users(organization_id=organization_id, role=role, limit=limit, offset=offset)
    results = [
        UserResponse(
            user_id=u.id,
            username=u.full_name,
            email=u.email,
            role=(u.role.name if hasattr(u.role, "name") else str(u.role)).upper(),
            organization_id=u.organization_id or "",
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in db_users
    ]
    return ApiResponse(ok=True, data=results)


@router.post("", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(
    req: UserCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: PlatformDatabase = Depends(get_db),
):
    """Create a new platform user."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: only administrators can create users",
            )
        if user_role == UserRole.ORG_ADMIN:
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

    new_id = f"usr-{uuid.uuid4().hex[:8]}"
    db_user = User(
        id=new_id,
        email=req.email,
        full_name=req.username,
        role=normalize_role(req.role),
        organization_id=req.organization_id,
        is_active=True,
    )
    if not is_production_mode() and req.organization_id:
        if not db.get_organization(req.organization_id):
            from central_platform.models.schema import Organization
            db.create_organization(Organization(id=req.organization_id, name=req.organization_id, slug=req.organization_id.lower()))

    with db.transaction():
        db.create_user(db_user)
        if req.password:
            db.set_user_password(db_user.id, req.password)

    resp_user = UserResponse(
        user_id=db_user.id,
        username=db_user.full_name,
        email=db_user.email,
        role=(db_user.role.name if hasattr(db_user.role, "name") else str(db_user.role)).upper(),
        organization_id=db_user.organization_id or "",
        is_active=db_user.is_active,
        created_at=db_user.created_at,
    )
    return ApiResponse(ok=True, data=resp_user)


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user_by_id(
    user_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: PlatformDatabase = Depends(get_db),
):
    """Get user by unique ID."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role == UserRole.STUDENT and current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students can only access their own profile",
            )
        enforce_resource_boundaries(current_user, target_student_id=user_id)

    u = db.get_user(user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")

    resp_user = UserResponse(
        user_id=u.id,
        username=u.full_name,
        email=u.email,
        role=(u.role.name if hasattr(u.role, "name") else str(u.role)).upper(),
        organization_id=u.organization_id or "",
        is_active=u.is_active,
        created_at=u.created_at,
    )
    return ApiResponse(ok=True, data=resp_user)
