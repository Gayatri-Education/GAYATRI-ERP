"""Cryptographic JWT token lifecycle, signature verification, and revocation manager (Phase 04).

Master Plan Section 13:
- Short-lived signed access tokens
- Long-lived refresh tokens
- Revocation blacklist tracking
- Payload tampering and expiration detection
"""

from __future__ import annotations

import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

import jwt

from central_platform.config import (
    DEFAULT_INSECURE_SECRET,
    MIN_SECRET_LENGTH,
    WEAK_SECRETS,
    is_production_mode,
)

JWT_SECRET_KEY = os.environ.get("GAYATRI_JWT_SECRET", DEFAULT_INSECURE_SECRET)
JWT_ALGORITHM = "HS256"


def get_jwt_secret_key() -> str:
    """Retrieve verified JWT secret key, strictly refusing insecure defaults in production."""
    secret = os.environ.get("GAYATRI_JWT_SECRET") or os.environ.get("JWT_SECRET")
    if is_production_mode():
        if not secret:
            raise RuntimeError(
                "Production startup aborted: GAYATRI_JWT_SECRET environment variable "
                "must be explicitly set with high entropy in production mode."
            )
        if secret.lower() in WEAK_SECRETS or len(secret) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"Production startup aborted: GAYATRI_JWT_SECRET is too weak or uses a default value "
                f"(minimum {MIN_SECRET_LENGTH} characters required in production mode)."
            )
        return secret
    return secret or DEFAULT_INSECURE_SECRET


# In-memory revocation registry (production can back with Redis / PostgreSQL)
_REVOKED_JTIS: Set[str] = set()


def create_access_token(
    user_id: str,
    role: str,
    organization_id: Optional[str] = None,
    expires_minutes: int = 60,
    custom_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a signed JWT access token."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)
    jti = f"jwt-{uuid.uuid4().hex}"

    payload: Dict[str, Any] = {
        "sub": user_id,
        "user_id": user_id,
        "role": role,
        "organization_id": organization_id,
        "type": "access",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if custom_claims:
        payload.update(custom_claims)

    return jwt.encode(payload, get_jwt_secret_key(), algorithm=JWT_ALGORITHM)


def create_refresh_token(
    user_id: str,
    organization_id: Optional[str] = None,
    expires_days: int = 7,
) -> str:
    """Generate a signed JWT refresh token."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=expires_days)
    jti = f"ref-{uuid.uuid4().hex}"

    payload = {
        "sub": user_id,
        "user_id": user_id,
        "organization_id": organization_id,
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, get_jwt_secret_key(), algorithm=JWT_ALGORITHM)


def decode_and_verify_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """Decode, verify signature, check expiration, and ensure token is not revoked."""
    try:
        payload = jwt.decode(token, get_jwt_secret_key(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise PermissionError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise PermissionError("Invalid token signature or payload") from exc

    jti = payload.get("jti")
    if jti and jti in _REVOKED_JTIS:
        raise PermissionError("Token has been revoked")

    token_type = payload.get("type", "access")
    if token_type != expected_type:
        raise PermissionError(f"Expected token type '{expected_type}', got '{token_type}'")

    return payload


def revoke_token(token_or_jti: str) -> bool:
    """Revoke a token by its jti or by parsing the token."""
    if token_or_jti.startswith("jwt-") or token_or_jti.startswith("ref-"):
        _REVOKED_JTIS.add(token_or_jti)
        return True
    try:
        payload = jwt.decode(token_or_jti, get_jwt_secret_key(), algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        jti = payload.get("jti")
        if jti:
            _REVOKED_JTIS.add(jti)
            return True
    except Exception:
        pass
    _REVOKED_JTIS.add(token_or_jti)
    return True


def is_token_revoked(token_or_jti: str) -> bool:
    """Check if token is in revocation list."""
    if token_or_jti in _REVOKED_JTIS:
        return True
    try:
        payload = jwt.decode(token_or_jti, get_jwt_secret_key(), algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        return payload.get("jti") in _REVOKED_JTIS
    except Exception:
        return False
