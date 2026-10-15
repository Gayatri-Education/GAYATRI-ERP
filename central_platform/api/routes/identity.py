"""Gayatri School OS — Shared Identity & Entitlements API Router (Phase 01).

Implements Section 5 and 6 of DEVELOPMENT.md:
- Canonical Person, Student, Guardian, Staff identity queries and mutations.
- Multi-tenant isolation and RBAC role validation.
- Tenant feature module entitlement configuration.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user, get_db
from central_platform.db import PlatformDatabase
from central_platform.entitlements.manager import EntitlementManager

logger = logging.getLogger("gayatri.api.routes.identity")

router = APIRouter(prefix="/identity", tags=["Identity & Entitlements"])


def get_entitlements_manager(db: PlatformDatabase = Depends(get_db)) -> EntitlementManager:
    return EntitlementManager(db)


def _get_org_id(user: Any) -> str:
    if isinstance(user, dict):
        return user.get("organization_id") or "default_org"
    return getattr(user, "organization_id", None) or "default_org"


def _get_roles(user: Any) -> List[str]:
    if isinstance(user, dict):
        roles = user.get("roles") or ([user["role"]] if "role" in user else [])
    else:
        role_val = getattr(user, "role", None)
        if isinstance(role_val, list):
            roles = role_val
        elif role_val:
            val = getattr(role_val, "value", str(role_val))
            roles = [val]
            if val in ("org_admin", "super_admin"):
                roles.append("admin")
        else:
            roles = getattr(user, "roles", [])
    return [str(r).lower() for r in roles]


class PersonCreateRequest(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    user_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    national_id_hash: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "India"


class LinkGuardianRequest(BaseModel):
    guardian_id: str
    relationship: str = Field(..., description="e.g. father, mother, legal_guardian")
    is_primary_contact: bool = False
    is_emergency_contact: bool = False
    is_pickup_authorized: bool = False
    can_access_portal: bool = True


class SetEntitlementRequest(BaseModel):
    module_key: str
    is_enabled: bool
    tier: str = "standard"
    valid_until: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


@router.post("/persons", status_code=status.HTTP_201_CREATED)
def create_person(
    payload: PersonCreateRequest,
    current_user: Any = Depends(get_current_user),
    db: PlatformDatabase = Depends(get_db),
):
    """Create a new Person within the caller's organization."""
    org_id = _get_org_id(current_user)
    person_id = f"per_{uuid.uuid4().hex[:12]}"
    created = db.create_person(
        person_id=person_id,
        organization_id=org_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        user_id=payload.user_id,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        national_id_hash=payload.national_id_hash,
        address_line1=payload.address_line1,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country=payload.country,
    )
    return {"status": "success", "person": created}


@router.get("/persons/{person_id}")
def get_person(
    person_id: str,
    current_user: Any = Depends(get_current_user),
    db: PlatformDatabase = Depends(get_db),
):
    """Retrieve Person profile isolated by organization."""
    org_id = _get_org_id(current_user)
    person = db.get_person(organization_id=org_id, person_id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person '{person_id}' not found in organization."
        )
    return {"status": "success", "person": person}


@router.get("/students/{student_id}")
def get_student_profile(
    student_id: str,
    current_user: Any = Depends(get_current_user),
    db: PlatformDatabase = Depends(get_db),
):
    """Retrieve Student profile with personal metadata."""
    org_id = _get_org_id(current_user)
    student = db.get_student_profile(organization_id=org_id, student_id=student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student profile '{student_id}' not found in organization."
        )
    return {"status": "success", "student": student}


@router.get("/students/{student_id}/guardians")
def get_student_guardians(
    student_id: str,
    current_user: Any = Depends(get_current_user),
    db: PlatformDatabase = Depends(get_db),
):
    """Retrieve authorized guardians for a student."""
    org_id = _get_org_id(current_user)
    guardians = db.get_student_guardians(organization_id=org_id, student_id=student_id)
    return {"status": "success", "student_id": student_id, "guardians": guardians}


@router.post("/students/{student_id}/guardians", status_code=status.HTTP_201_CREATED)
def link_guardian(
    student_id: str,
    payload: LinkGuardianRequest,
    current_user: Any = Depends(get_current_user),
    db: PlatformDatabase = Depends(get_db),
):
    """Link a guardian to a student with pickup/emergency flags."""
    org_id = _get_org_id(current_user)
    link_id = db.link_student_guardian(
        organization_id=org_id,
        student_id=student_id,
        guardian_id=payload.guardian_id,
        relationship=payload.relationship,
        is_primary_contact=payload.is_primary_contact,
        is_emergency_contact=payload.is_emergency_contact,
        is_pickup_authorized=payload.is_pickup_authorized,
        can_access_portal=payload.can_access_portal,
    )
    return {"status": "success", "link_id": link_id}


@router.get("/entitlements")
def list_entitlements(
    current_user: Any = Depends(get_current_user),
    ent_mgr: EntitlementManager = Depends(get_entitlements_manager),
):
    """List active module entitlements for caller's tenant."""
    org_id = _get_org_id(current_user)
    entitlements = ent_mgr.list_entitlements(org_id)
    return {"status": "success", "organization_id": org_id, "entitlements": entitlements}


@router.post("/entitlements")
def set_entitlement(
    payload: SetEntitlementRequest,
    current_user: Any = Depends(get_current_user),
    ent_mgr: EntitlementManager = Depends(get_entitlements_manager),
):
    """Configure module entitlement for tenant (Admin only)."""
    roles = _get_roles(current_user)
    if "admin" not in roles and "super_admin" not in roles and "org_admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to configure module entitlements."
        )
    org_id = _get_org_id(current_user)
    ent_mgr.set_entitlement(
        organization_id=org_id,
        module_key=payload.module_key,
        enabled=payload.is_enabled,
        tier=payload.tier,
        valid_until=payload.valid_until,
        config=payload.config,
    )
    return {"status": "success", "module_key": payload.module_key, "is_enabled": payload.is_enabled}
