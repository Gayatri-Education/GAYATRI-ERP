"""Gayatri AI Central Platform — Production Configuration & Security Hardening (Phase 1).

Authoritative environment validation, configuration auditing, settings consolidation,
and fail-fast startup checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gayatri.central_platform.config")

DEFAULT_INSECURE_SECRET = "gayatri-platform-production-secret-key-3.0.0-entropy"

WEAK_SECRETS = {
    "secret",
    "change_me",
    "changeme",
    "password",
    "123456",
    "admin",
    "default_key",
    "gayatri_secret_key_12345",
    "dev_default_secret",
    DEFAULT_INSECURE_SECRET.lower(),
}

MIN_SECRET_LENGTH = 32


@dataclass(frozen=True)
class PlatformSettings:
    """Canonical, immutable representation of resolved platform settings."""
    environment: str
    is_production: bool
    jwt_secret: str
    encryption_key: Optional[str]
    allowed_origins: List[str]
    db_path: str
    debug: bool
    reload: bool
    docs_enabled: bool
    model_file: Optional[str] = None
    model_checksum: Optional[str] = None

    def safe_diagnostics(self) -> Dict[str, Any]:
        """Return safe, non-sensitive diagnostic metadata (no secrets logged)."""
        return {
            "environment": self.environment,
            "is_production": self.is_production,
            "jwt_secret_configured": bool(self.jwt_secret and self.jwt_secret != DEFAULT_INSECURE_SECRET),
            "jwt_secret_length": len(self.jwt_secret) if self.jwt_secret else 0,
            "encryption_key_configured": bool(self.encryption_key),
            "allowed_origins_count": len(self.allowed_origins),
            "db_path": self.db_path,
            "debug": self.debug,
            "reload": self.reload,
            "docs_enabled": self.docs_enabled,
            "model_file_configured": bool(self.model_file),
        }


def resolve_environment(envs: Dict[str, str]) -> str:
    """Resolve environment from canonical GAYATRI_ENV with APP_ENV alias support and conflict detection."""
    gayatri_env = envs.get("GAYATRI_ENV")
    app_env = envs.get("APP_ENV")

    if gayatri_env and app_env and gayatri_env.strip().lower() != app_env.strip().lower():
        raise RuntimeError(
            f"Production startup aborted: Conflicting environment configuration detected. "
            f"GAYATRI_ENV='{gayatri_env}' vs APP_ENV='{app_env}'"
        )

    resolved = (gayatri_env or app_env or "development").strip().lower()
    return resolved


def get_environment(env_vars: Optional[Dict[str, str]] = None) -> str:
    """Return the active environment name in lowercase ('development', 'test', 'production')."""
    envs = env_vars if env_vars is not None else dict(os.environ)
    return resolve_environment(envs)


def is_production_mode(env_vars: Optional[Dict[str, str]] = None) -> bool:
    """Return True if running in production mode."""
    return get_environment(env_vars) == "production"


def resolve_jwt_secret(envs: Dict[str, str], is_prod: bool) -> str:
    """Resolve JWT signing secret enforcing canonical precedence, alias conflict checks, and entropy."""
    canonical = envs.get("GAYATRI_JWT_SECRET")
    alias_jwt = envs.get("JWT_SECRET")
    alias_key = envs.get("SECRET_KEY")

    # Conflict detection between configured secrets
    present_secrets = {s for s in (canonical, alias_jwt, alias_key) if s is not None and s.strip() != ""}
    if len(present_secrets) > 1:
        raise RuntimeError(
            "Production startup aborted: Conflicting JWT secret configurations detected between "
            "GAYATRI_JWT_SECRET, JWT_SECRET, and SECRET_KEY."
        )

    secret = canonical or alias_jwt or alias_key or ""

    if is_prod:
        if not secret:
            raise RuntimeError(
                "Production startup aborted: Missing required GAYATRI_JWT_SECRET environment variable "
                "must be explicitly set with high entropy in production mode."
            )
        if secret.lower() in WEAK_SECRETS or len(secret) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"Production startup aborted: GAYATRI_JWT_SECRET is too weak or uses a default value "
                f"(minimum {MIN_SECRET_LENGTH} characters with high entropy required in production)."
            )
        return secret

    return secret or DEFAULT_INSECURE_SECRET


def resolve_encryption_key(envs: Dict[str, str], is_prod: bool) -> Optional[str]:
    """Resolve encryption key enforcing canonical precedence and production entropy requirements.

    On POSIX platforms, GAYATRI_ENCRYPTION_KEY is unconditionally required in production.
    On Windows NT, platform DPAPI is active by default; explicit key is required when
    GAYATRI_ENFORCE_ENCRYPTION_KEY=true. Any supplied key must have sufficient entropy.
    """
    canonical = envs.get("GAYATRI_ENCRYPTION_KEY")
    alias = envs.get("ENCRYPTION_KEY")

    if canonical and alias and canonical.strip() != alias.strip():
        raise RuntimeError(
            "Production startup aborted: Conflicting encryption key configurations detected between "
            "GAYATRI_ENCRYPTION_KEY and ENCRYPTION_KEY."
        )

    key = canonical or alias
    enforce_key = envs.get("GAYATRI_ENFORCE_ENCRYPTION_KEY", "false").lower() in ("true", "1", "yes")

    if is_prod:
        if not key and (os.name != "nt" or enforce_key):
            raise RuntimeError(
                "Production startup aborted: Missing required GAYATRI_ENCRYPTION_KEY for at-rest data protection."
            )
        if key and (key.lower() in WEAK_SECRETS or len(key) < 16):
            raise RuntimeError(
                "Production startup aborted: Configured GAYATRI_ENCRYPTION_KEY is insecure or too short "
                "(minimum 16 characters required)."
            )
    return key


def resolve_cors_origins(envs: Dict[str, str], is_prod: bool) -> List[str]:
    """Resolve allowed CORS origins enforcing production restrictions."""
    canonical = envs.get("GAYATRI_ALLOWED_ORIGINS")
    alias = envs.get("ALLOWED_ORIGINS")

    if canonical and alias and canonical.strip() != alias.strip():
        raise RuntimeError(
            "Production startup aborted: Conflicting CORS origins configurations detected between "
            "GAYATRI_ALLOWED_ORIGINS and ALLOWED_ORIGINS."
        )

    origins_raw = canonical or alias
    if not origins_raw:
        if is_prod:
            raise RuntimeError(
                "Production startup aborted: GAYATRI_ALLOWED_ORIGINS must be explicitly configured in production mode."
            )
        return ["http://localhost:8000", "http://127.0.0.1:8000"]

    allowed_origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    if not allowed_origins:
        raise RuntimeError(
            "Production startup aborted: GAYATRI_ALLOWED_ORIGINS must not be empty in production mode."
        )
    if is_prod and "*" in allowed_origins:
        raise RuntimeError(
            "Production startup aborted: Wildcard CORS ('*') is strictly prohibited in production mode."
        )
    return allowed_origins


def resolve_database_path(envs: Dict[str, str], is_prod: bool) -> str:
    """Resolve database path enforcing existence in production."""
    canonical = envs.get("GAYATRI_DB_PATH")
    alias = envs.get("DATABASE_URL")

    if canonical and alias and canonical.strip() != alias.strip():
        raise RuntimeError(
            "Production startup aborted: Conflicting database configurations detected between "
            "GAYATRI_DB_PATH and DATABASE_URL."
        )

    db_path = canonical or alias

    if is_prod:
        if not db_path:
            raise RuntimeError(
                "Production startup aborted: Missing authoritative database configuration (GAYATRI_DB_PATH or DATABASE_URL)."
            )
        if (db_path.endswith(".db") or db_path.endswith(".sqlite") or "://" not in db_path) and db_path != ":memory:":
            db_file = Path(db_path)
            if not db_file.exists():
                raise RuntimeError(
                    f"Production startup aborted: Configured production database does not exist: {db_path}"
                )
        return db_path

    return db_path or os.environ.get("GAYATRI_DB_PATH", "gayatri_local.db")


def get_authoritative_settings(env_vars: Optional[Dict[str, str]] = None) -> PlatformSettings:
    """Construct and validate authoritative PlatformSettings from environment."""
    envs = env_vars if env_vars is not None else dict(os.environ)
    env = resolve_environment(envs)
    is_prod = env == "production"

    jwt_secret = resolve_jwt_secret(envs, is_prod)
    encryption_key = resolve_encryption_key(envs, is_prod)
    allowed_origins = resolve_cors_origins(envs, is_prod)
    db_path = resolve_database_path(envs, is_prod)

    debug = envs.get("DEBUG", "false").lower() in ("true", "1", "yes")
    reload_mode = envs.get("RELOAD", "false").lower() in ("true", "1", "yes")
    fastapi_debug = envs.get("FASTAPI_DEBUG", "false").lower() in ("true", "1", "yes")

    if is_prod and (debug or reload_mode or fastapi_debug):
        raise RuntimeError(
            "Production startup aborted: Debug and reload modes are strictly prohibited in production."
        )

    model_file = envs.get("GAYATRI_MODEL_FILE")
    model_checksum = envs.get("GAYATRI_MODEL_CHECKSUM")

    if is_prod and model_file:
        model_path = Path(model_file)
        if not model_path.is_file():
            raise RuntimeError(
                f"Production startup aborted: Configured model file does not exist: {model_file}"
            )
        if model_checksum:
            import hashlib
            sha = hashlib.sha256()
            with open(model_path, "rb") as f:
                while chunk := f.read(65536):
                    sha.update(chunk)
            computed = sha.hexdigest()
            if computed.lower() != model_checksum.lower():
                raise RuntimeError(
                    f"Production startup aborted: Model checksum mismatch for {model_file}. "
                    f"Expected: {model_checksum}, Got: {computed}"
                )

    docs_enabled = envs.get("GAYATRI_ENABLE_DOCS", "false").lower() in ("true", "1", "yes")

    return PlatformSettings(
        environment=env,
        is_production=is_prod,
        jwt_secret=jwt_secret,
        encryption_key=encryption_key,
        allowed_origins=allowed_origins,
        db_path=db_path,
        debug=debug,
        reload=reload_mode,
        docs_enabled=docs_enabled,
        model_file=model_file,
        model_checksum=model_checksum,
    )


def validate_production_config(env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Validate all security-critical configuration for production deployment.

    Raises RuntimeError immediately if any security invariant is violated.
    Returns a dictionary of validated configuration values.
    """
    envs = env_vars if env_vars is not None else dict(os.environ)

    if not is_production_mode(envs):
        return {"mode": get_environment(envs), "production_enforced": False}

    logger.info("Executing authoritative production configuration hardening validation...")
    settings = get_authoritative_settings(envs)
    logger.info("Authoritative production configuration hardening verified successfully.")

    return {
        "mode": "production",
        "production_enforced": True,
        "jwt_secret_configured": True,
        "cors_origins": settings.allowed_origins,
        "db_path": settings.db_path,
        "docs_enabled": settings.docs_enabled,
    }
