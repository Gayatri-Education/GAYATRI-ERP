"""Gayatri AI Platform — Auth API Endpoints (Phase 04).

Master Plan Section 13:
- Cryptographic JWT session generation & verification
- Short-lived access tokens & long-lived refresh tokens
- Revocation on logout
- PBKDF2 credential verification
- Account suspension enforcement
"""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status

from central_platform.api.schemas import (
    ApiResponse,
    LoginRequest,
    LoginResponse,
    PasswordResetRequest,
    TokenRefreshRequest,
    UserResponse,
)
from central_platform.auth.dependencies import (
    extract_bearer_token,
    get_current_user,
    get_db,
    is_production_mode,
)
from central_platform.auth.tokens import (
    create_access_token,
    create_refresh_token,
    decode_and_verify_token,
    revoke_token,
)
from central_platform.models.schema import User, UserRole
from central_platform.db import PlatformDatabase

router = APIRouter(prefix="/auth", tags=["Authentication"])

MOCK_USERS = {
    "admin": {"user_id": "usr-admin-01", "role": "SUPER_ADMIN", "org": "org-central"},
    "teacher_1": {"user_id": "usr-teacher-01", "role": "TEACHER", "org": "org-central"},
    "student_001": {"user_id": "usr-student-01", "role": "STUDENT", "org": "org-central"},
}


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(req: LoginRequest, db: PlatformDatabase = Depends(get_db)):
    """Authenticate user with PBKDF2 credentials and issue cryptographically signed JWT tokens."""
    username_clean = req.username.strip().lower() if "@" in req.username else req.username.strip()
    db_user = db.get_user_by_email(username_clean) or db.get_user(req.username) or db.get_user_by_email(req.username)

    if db_user:
        # Check deleted status
        if getattr(db_user, "is_deleted", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deleted or disabled",
            )
        # Check active status
        if hasattr(db_user, "is_active") and not db_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive or disabled",
            )
        # Check suspended status
        creds = db.get_user_credentials(db_user.id)
        if creds and creds.get("is_suspended"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended",
            )
        # Attempt DB authentication
        auth_user = db.authenticate_user(req.username, req.password) or db.authenticate_user(username_clean, req.password)
        if not auth_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        user_id = auth_user.id
        role_str = auth_user.role.value if isinstance(auth_user.role, UserRole) else str(auth_user.role)
        role = role_str.upper()
        org_id = auth_user.organization_id or "org-default"
    else:
        # In production mode: STRICTLY PROHIBIT mock or synthetic identity fallback (P0-01)
        if is_production_mode():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        # Mock or integration user fallback (development/test mode only)
        user = MOCK_USERS.get(req.username)
        if not user:
            if req.password != "password":
                if len(req.password) < 4:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid credentials",
                    )
            user = {"user_id": f"usr-{req.username}", "role": "STUDENT", "org": "org-default"}
        elif req.password != "password" and len(req.password) < 4:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        user_id = user["user_id"]
        role = str(user["role"]).upper()
        org_id = user["org"]

    access_token = create_access_token(
        user_id=user_id,
        role=role.lower(),
        organization_id=org_id,
        expires_minutes=60,
    )
    refresh_token = create_refresh_token(
        user_id=user_id,
        organization_id=org_id,
        expires_days=7,
    )

    data = LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=3600,
        user_id=user_id,
        username=req.username,
        role=role,
        organization_id=org_id,
    )
    return ApiResponse(ok=True, data=data)


@router.post("/logout", response_model=ApiResponse[dict])
async def logout(
    body: Optional[dict] = None,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """Log out current user and invalidate active session tokens."""
    raw_token = extract_bearer_token(authorization)
    ref_tok = body.get("refresh_token") if (body and isinstance(body, dict)) else None

    if not raw_token and not ref_tok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No token provided for logout",
        )

    success = True
    if raw_token:
        if not revoke_token(raw_token, reason="user_logout"):
            success = False
    if ref_tok:
        if not revoke_token(ref_tok, reason="user_logout_refresh"):
            success = False

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist token revocation; logout unsuccessful",
        )

    return ApiResponse(ok=True, data={"logged_out": True})


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user profile using validated JWT Bearer token."""
    role_str = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role)
    data = UserResponse(
        user_id=current_user.id,
        username=current_user.email.split("@")[0] if "@" in current_user.email else current_user.id,
        email=current_user.email,
        role=role_str.upper(),
        organization_id=current_user.organization_id or "org-central",
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
    return ApiResponse(ok=True, data=data)


@router.post("/refresh", response_model=ApiResponse[dict])
async def refresh_access_token(
    body: Optional[TokenRefreshRequest] = None,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: PlatformDatabase = Depends(get_db),
):
    """Exchange a valid refresh token for a newly issued short-lived access token with rotation."""
    token = None
    if body and body.refresh_token:
        token = body.refresh_token
    else:
        token = extract_bearer_token(authorization)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token required in body or Authorization header",
        )

    try:
        payload = decode_and_verify_token(token, expected_type="refresh")
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    user_id = payload["user_id"]
    org_id = payload.get("organization_id", "org-default")
    user = db.get_user(user_id)
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
        role_str = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    else:
        if is_production_mode():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user record not found in platform directory",
            )
        role_str = "student"

    # Refresh token rotation (GQA-005): revoke used refresh token to prevent replay
    revoke_token(token, user_id=user_id, reason="refresh_token_rotated")

    new_access_token = create_access_token(
        user_id=user_id,
        role=role_str,
        organization_id=org_id,
        expires_minutes=60,
    )
    new_refresh_token = create_refresh_token(
        user_id=user_id,
        organization_id=org_id,
        expires_days=7,
    )
    return ApiResponse(
        ok=True,
        data={
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
        },
    )



@router.post("/password-reset", response_model=ApiResponse[dict])
async def reset_password(req: PasswordResetRequest, db: PlatformDatabase = Depends(get_db)):
    """Reset password using email or one-time token."""
    if req.token:
        ok = db.reset_password_with_token(req.token, req.new_password)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token",
            )
    else:
        # In production mode: Unverified email-only reset is strictly prohibited (P0-06)
        if is_production_mode():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token is required in production mode.",
            )
        user = db.get_user_by_email(req.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        db.set_user_password(user.id, req.new_password)

    return ApiResponse(ok=True, data={"reset": True})


@router.get("/demo-tokens", response_model=ApiResponse[dict])
async def get_demo_tokens():
    """Return pre-generated JWT tokens for all local testing personas.
    
    Disabled in production mode to prevent false-green backdoors.
    """
    if is_production_mode():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo tokens are disabled in production environment.",
        )
    personas = {
        "superadmin": {
            "id": "usr_superadmin",
            "name": "Dr. Gayatri Admin",
            "email": "superadmin@gayatri.edu",
            "role": "SUPER_ADMIN",
            "organization_id": "org_global",
            "token": create_access_token("usr_superadmin", "SUPER_ADMIN", "org_global", expires_minutes=1440),
        },
        "org_admin": {
            "id": "usr_dps_admin",
            "name": "Principal Ramesh Gupta",
            "email": "admin@dps.edu",
            "role": "ORG_ADMIN",
            "organization_id": "org_dps",
            "token": create_access_token("usr_dps_admin", "ORG_ADMIN", "org_dps", expires_minutes=1440),
        },
        "teacher": {
            "id": "usr_teacher_sharma",
            "name": "Prof. Anita Sharma",
            "email": "teacher.sharma@dps.edu",
            "role": "TEACHER",
            "organization_id": "org_dps",
            "token": create_access_token("usr_teacher_sharma", "TEACHER", "org_dps", expires_minutes=1440),
        },
        "student_arjun": {
            "id": "usr_student_arjun",
            "name": "Arjun Patel",
            "email": "student.arjun@dps.edu",
            "role": "STUDENT",
            "organization_id": "org_dps",
            "token": create_access_token("usr_student_arjun", "STUDENT", "org_dps", expires_minutes=1440),
        },
        "student_priya": {
            "id": "usr_student_priya",
            "name": "Priya Sen",
            "email": "student.priya@dps.edu",
            "role": "STUDENT",
            "organization_id": "org_dps",
            "token": create_access_token("usr_student_priya", "STUDENT", "org_dps", expires_minutes=1440),
        },
    }
    return ApiResponse(ok=True, data=personas)

