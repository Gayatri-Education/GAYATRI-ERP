"""Gayatri AI Platform — Organizations API Endpoints (Phase 12).

Section 12.12: Real Online API Boundary
- Pure route/service separation connecting to PlatformDatabase
- Multi-tenant organization tenant retrieval and provisioning
- SUPER_ADMIN authorization gate for tenant mutation
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from central_platform.api.schemas import (
    ApiResponse,
    OrganizationCreateRequest,
    OrganizationResponse,
)
from central_platform.auth.dependencies import (
    get_current_user,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import Organization, User, UserRole
from central_platform.rbac.engine import normalize_role

logger = logging.getLogger("gayatri.api.organizations")

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _to_org_response(org: Organization) -> OrganizationResponse:
    """Map domain Organization to OrganizationResponse schema."""
    created_at_str = (
        org.created_at.isoformat()
        if hasattr(org.created_at, "isoformat")
        else str(org.created_at or datetime.now(timezone.utc).isoformat())
    )
    is_active_val = getattr(org, "is_active", not getattr(org, "is_deleted", False))
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=is_active_val,
        created_at=created_at_str,
    )


@router.get("", response_model=ApiResponse[List[OrganizationResponse]])
async def list_organizations(
    db: PlatformDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List organizations with tenant isolation. Super admins view all; Org admins view own."""
    user_role = normalize_role(current_user.role)
    if user_role == UserRole.SUPER_ADMIN:
        orgs = db.list_organizations()
    elif user_role == UserRole.ORG_ADMIN:
        orgs = [o for o in db.list_organizations() if o.id == current_user.organization_id]
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: role not authorized to list organizations",
        )
    return ApiResponse(ok=True, data=[_to_org_response(o) for o in orgs])


@router.get("/{org_id}", response_model=ApiResponse[OrganizationResponse])
async def get_organization(
    org_id: str,
    db: PlatformDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve organization details by ID with tenant boundary validation."""
    user_role = normalize_role(current_user.role)
    if user_role != UserRole.SUPER_ADMIN and org_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: cross-organization query for '{org_id}' prohibited",
        )

    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found.",
        )
    return ApiResponse(ok=True, data=_to_org_response(org))


@router.post("", response_model=ApiResponse[OrganizationResponse], status_code=status.HTTP_201_CREATED)
async def create_organization(
    req: OrganizationCreateRequest,
    db: PlatformDatabase = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new tenant organization. Requires SUPER_ADMIN role."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to create organizations",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only SUPER_ADMIN can create organizations.",
            )

    org_id = req.id or f"org-{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    org = Organization(
        id=org_id,
        name=req.name,
        slug=req.slug,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )
    created = db.create_organization(org)
    return ApiResponse(ok=True, data=_to_org_response(created))
