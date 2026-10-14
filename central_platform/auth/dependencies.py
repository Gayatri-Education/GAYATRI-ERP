"""FastAPI Authentication and RBAC Guardrail Dependencies (Phase 04).

Master Plan Section 13:
- Token decoding & validation via PyJWT
- Role verification (SUPER_ADMIN, ORG_ADMIN, COURSE_ADMIN, TEACHER, STUDENT)
- Fine-grained permission enforcement
- Organization scoping
- Student self-access & teacher assignment checks
- Negative security boundary enforcement
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Set, Union
from fastapi import Depends, Header, HTTPException, status

from central_platform.auth.tokens import decode_and_verify_token, is_token_revoked
from central_platform.models.schema import User, UserRole
from central_platform.rbac.engine import (
    Permission,
    check_resource_access,
    has_permission,
    normalize_role,
)

# Reference to central database singleton
_DB_INSTANCE = None


def get_db():
    global _DB_INSTANCE
    env_path = os.environ.get("GAYATRI_DB_PATH")
    if _DB_INSTANCE is None or (env_path and str(_DB_INSTANCE.db_path) != str(env_path)):
        from central_platform.db import PlatformDatabase
        _DB_INSTANCE = PlatformDatabase(env_path)
    return _DB_INSTANCE


def is_production_mode() -> bool:
    """Return True if running in production mode (F-001, F-011, F-012, F-025)."""
    from central_platform.config import is_production_mode as _is_prod
    return _is_prod()


def extract_bearer_token(authorization: Optional[str] = Header(None, alias="Authorization")) -> Optional[str]:
    """Extract raw JWT bearer token from Authorization header.

    Rejects:
    - Headers exceeding 8192 characters with HTTP 400 Bad Request
    - Malformed headers containing multiple tokens or ambiguous formats
    """
    if not authorization:
        return None
    if len(authorization) > 8192:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization header exceeds maximum allowed length of 8192 bytes",
        )
    # Check for duplicated or comma-separated authorization headers
    if "," in authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    if len(parts) == 1 and not authorization.lower().startswith("bearer"):
        return parts[0]
    return None



async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> User:
    """Strictly authenticate caller via JWT token and verify account state."""
    raw_token = extract_bearer_token(authorization)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_and_verify_token(raw_token, expected_type="access")
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id") or payload.get("sub")
    role_str = payload.get("role", "student")
    org_id = payload.get("organization_id")

    try:
        norm_role = normalize_role(role_str)
    except Exception:
        norm_role = UserRole.STUDENT

    db = get_db()
    user = db.get_user(user_id, include_deleted=True)
    if user:
        if not user.is_active or user.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive or deleted",
            )
        creds = db.get_user_credentials(user.id)
        if creds and creds.get("is_suspended"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended",
            )
        return user

    # Production gate: Fail closed if account does not exist in the database (F-001, F-004)
    if is_production_mode():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user record not found in platform directory",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In development/test mode: construct User strictly from valid signed claims
    return User(
        id=user_id,
        email=payload.get("email", f"{user_id}@gayatri.ai"),
        full_name=payload.get("full_name", user_id),
        role=norm_role,
        organization_id=org_id or "org-default",
        is_active=True,
    )


async def get_current_user_optional(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[User]:
    """Extract current user if Authorization header is present; return None if omitted."""
    raw_token = extract_bearer_token(authorization)
    if not raw_token:
        return None
    return await get_current_user(authorization=authorization)


def require_roles(*allowed_roles: Union[UserRole, str]) -> Callable:
    """Enforce that current authenticated user holds one of the specified canonical roles."""
    normalized_allowed = {normalize_role(r) for r in allowed_roles}

    async def _role_guard(current_user: User = Depends(get_current_user)) -> User:
        user_role = normalize_role(current_user.role)
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{user_role.value}' is not authorized for this resource",
            )
        return current_user

    return _role_guard


def require_permission(*required_perms: str) -> Callable:
    """Enforce that current authenticated user possesses all specified permissions."""
    async def _perm_guard(current_user: User = Depends(get_current_user)) -> User:
        user_role = normalize_role(current_user.role)
        for perm in required_perms:
            if not has_permission(user_role, perm):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: missing required permission '{perm}'",
                )
        return current_user

    return _perm_guard


def enforce_resource_boundaries(
    current_user: Optional[User],
    target_org_id: Optional[str] = None,
    target_student_id: Optional[str] = None,
    target_session_student_id: Optional[str] = None,
    assigned_student_ids: Optional[Set[str]] = None,
) -> None:
    """Enforce all Section 13 negative security constraints.
    
    Raises HTTPException(403) upon any unauthorized cross-boundary access.
    """
    if not current_user:
        return

    user_role = normalize_role(current_user.role)

    # 1. Super Admin is omniscient
    if user_role == UserRole.SUPER_ADMIN:
        return

    # 2. Org Isolation: Non-super admin cannot access other orgs
    if target_org_id and current_user.organization_id:
        if target_org_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: cross-organization access to '{target_org_id}' prohibited",
            )

    # 3. Student Self-Access Isolation:
    if user_role == UserRole.STUDENT:
        # Student cannot access another student's record
        if target_student_id and target_student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students may only access their own records",
            )
        # Student cannot access another student's session
        if target_session_student_id and target_session_student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: cannot access another student's session",
            )

    # 4. Teacher Scope Isolation:
    if user_role == UserRole.TEACHER:
        if target_student_id and target_student_id != "all":
            if assigned_student_ids is not None and target_student_id not in assigned_student_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: student '{target_student_id}' is not assigned to this teacher",
                )

    # 5. Parent Scope Isolation:
    if user_role == UserRole.PARENT:
        if target_student_id:
            from central_platform.privacy.policies import PrivacyRulesEngine
            if not PrivacyRulesEngine.is_parent_linked(current_user.id, target_student_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: student '{target_student_id}' is not linked to this parent",
                )
