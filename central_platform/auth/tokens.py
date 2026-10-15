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
    get_authoritative_settings,
    is_production_mode,
    resolve_jwt_secret,
)

JWT_ALGORITHM = "HS256"
JWT_SECRET_KEY = os.environ.get("GAYATRI_JWT_SECRET", DEFAULT_INSECURE_SECRET)


def get_jwt_secret_key() -> str:
    """Retrieve verified JWT secret key via authoritative settings."""
    return resolve_jwt_secret(dict(os.environ), is_prod=is_production_mode())


# ── Revocation Store Abstraction (QA-005) ──────────────────────────────────

class RevocationStore:
    """Abstract contract for token revocation across deployment tiers."""

    def is_revoked(self, jti: str) -> bool:
        raise NotImplementedError

    def revoke(
        self,
        jti: str,
        user_id: Optional[str] = None,
        expires_at: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        raise NotImplementedError

    def clear(self) -> None:
        """Clear store state (for testing)."""
        pass


class InMemoryRevocationStore(RevocationStore):
    """In-memory revocation registry for single-process / isolated test environments."""

    def __init__(self):
        self._jtis: Set[str] = set()

    def is_revoked(self, jti: str) -> bool:
        return jti in self._jtis

    def revoke(
        self,
        jti: str,
        user_id: Optional[str] = None,
        expires_at: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        self._jtis.add(jti)
        return True

    def clear(self) -> None:
        self._jtis.clear()


class DatabaseRevocationStore(RevocationStore):
    """Authoritative durable revocation store backed by PlatformDatabase (GQA-005).
    
    Guarantees:
    - Durable persistence across process restarts.
    - Synchronized revocation across multi-worker server pools.
    - Write-through local caching for microsecond-level query hits.
    """

    def __init__(self, db_path: Optional[Any] = None):
        if hasattr(db_path, "is_token_revoked"):
            self._db = db_path
            self.db_path = getattr(db_path, "db_path", None)
        else:
            self._db = None
            self.db_path = db_path
        self._local_cache: Set[str] = set()

    def _get_db(self):
        if self._db is not None:
            return self._db
        from central_platform.db import PlatformDatabase
        path = self.db_path or os.environ.get("GAYATRI_DB_PATH")
        return PlatformDatabase(path)

    def is_revoked(self, jti: str) -> bool:
        if jti in self._local_cache:
            return True
        try:
            db = self._get_db()
            if db.is_token_revoked(jti):
                self._local_cache.add(jti)
                return True
        except Exception as exc:
            raise PermissionError(f"Revocation store verification failed: database unavailable ({exc})") from exc
        return False

    def revoke(
        self,
        jti: str,
        user_id: Optional[str] = None,
        expires_at: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        self._local_cache.add(jti)
        try:
            db = self._get_db()
            return db.revoke_token(jti, user_id=user_id, expires_at=expires_at, reason=reason)
        except Exception:
            return False

    def clear(self) -> None:
        self._local_cache.clear()


# Default singleton registry
_REVOKED_JTIS: Set[str] = set()
_ACTIVE_REVOCATION_STORE: Optional[RevocationStore] = None


def get_revocation_store() -> RevocationStore:
    """Retrieve active token revocation store."""
    global _ACTIVE_REVOCATION_STORE
    if _ACTIVE_REVOCATION_STORE is not None:
        return _ACTIVE_REVOCATION_STORE
    _ACTIVE_REVOCATION_STORE = DatabaseRevocationStore()
    return _ACTIVE_REVOCATION_STORE


def set_revocation_store(store: Optional[RevocationStore]) -> None:
    """Override active token revocation store."""
    global _ACTIVE_REVOCATION_STORE
    _ACTIVE_REVOCATION_STORE = store


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
    if jti and is_token_revoked(jti):
        raise PermissionError("Token has been revoked")

    token_type = payload.get("type", "access")
    if token_type != expected_type:
        raise PermissionError(f"Expected token type '{expected_type}', got '{token_type}'")

    return payload


def revoke_token(
    token_or_jti: str,
    user_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> bool:
    """Revoke a token by its jti or by parsing the token."""
    jti = token_or_jti
    exp = None
    sub = user_id

    if not (token_or_jti.startswith("jwt-") or token_or_jti.startswith("ref-")):
        try:
            payload = jwt.decode(
                token_or_jti,
                get_jwt_secret_key(),
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti", token_or_jti)
            exp = payload.get("exp")
            sub = sub or payload.get("sub") or payload.get("user_id")
        except Exception:
            pass

    _REVOKED_JTIS.add(jti)
    store = get_revocation_store()
    return store.revoke(jti, user_id=sub, expires_at=exp, reason=reason)


def is_token_revoked(token_or_jti: str) -> bool:
    """Check if token or jti is in revocation store or local blacklist."""
    jti = token_or_jti
    if not (token_or_jti.startswith("jwt-") or token_or_jti.startswith("ref-")):
        try:
            payload = jwt.decode(
                token_or_jti,
                get_jwt_secret_key(),
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            jti = payload.get("jti", token_or_jti)
        except Exception:
            pass

    if jti in _REVOKED_JTIS:
        return True
    return get_revocation_store().is_revoked(jti)

