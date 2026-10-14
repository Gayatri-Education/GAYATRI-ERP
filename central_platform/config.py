"""Gayatri AI Central Platform — Production Configuration & Security Hardening (Phase 1).

Authoritative environment validation, configuration auditing, and fail-fast startup checks.
"""
from __future__ import annotations

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


def get_environment(env_vars: Optional[Dict[str, str]] = None) -> str:
    """Return the active environment name in lowercase ('development', 'test', 'production')."""
    envs = env_vars if env_vars is not None else os.environ
    env = envs.get("GAYATRI_ENV") or envs.get("APP_ENV") or "development"
    return env.lower()


def is_production_mode(env_vars: Optional[Dict[str, str]] = None) -> bool:
    """Return True if running in production mode."""
    return get_environment(env_vars) == "production"


def validate_production_config(env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Validate all security-critical configuration for production deployment.

    Raises RuntimeError immediately if any security invariant is violated.
    Returns a dictionary of validated configuration values.
    """
    envs = env_vars if env_vars is not None else os.environ

    if not is_production_mode(envs):
        return {"mode": get_environment(envs), "production_enforced": False}

    logger.info("Executing authoritative production configuration hardening validation...")

    # 1. JWT Secret Validation
    jwt_secret = envs.get("GAYATRI_JWT_SECRET") or envs.get("JWT_SECRET")
    if not jwt_secret:
        raise RuntimeError(
            "Production startup aborted: Missing required GAYATRI_JWT_SECRET environment variable."
        )
    if jwt_secret.lower() in WEAK_SECRETS or len(jwt_secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"Production startup aborted: GAYATRI_JWT_SECRET is too weak or uses a default value "
            f"(minimum {MIN_SECRET_LENGTH} characters with high entropy required in production)."
        )

    # 2. Encryption Key Validation
    encryption_key = envs.get("ENCRYPTION_KEY") or envs.get("GAYATRI_ENCRYPTION_KEY")
    if not encryption_key and os.name != "nt":
        raise RuntimeError(
            "Production startup aborted: Missing required ENCRYPTION_KEY for at-rest data protection."
        )
    if encryption_key and (encryption_key.lower() in WEAK_SECRETS or len(encryption_key) < 16):
        raise RuntimeError(
            "Production startup aborted: Configured ENCRYPTION_KEY is insecure or too short."
        )

    # 3. CORS Origins Restriction
    allowed_origins_raw = envs.get("GAYATRI_ALLOWED_ORIGINS") or envs.get("ALLOWED_ORIGINS")
    if not allowed_origins_raw:
        raise RuntimeError(
            "Production startup aborted: GAYATRI_ALLOWED_ORIGINS must be explicitly configured in production mode."
        )
    allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
    if not allowed_origins:
        raise RuntimeError(
            "Production startup aborted: GAYATRI_ALLOWED_ORIGINS must not be empty in production mode."
        )
    if "*" in allowed_origins:
        raise RuntimeError(
            "Production startup aborted: Wildcard CORS ('*') is strictly prohibited in production mode."
        )

    # 4. Debug / Reload Mode Prohibition
    debug = envs.get("DEBUG", "false").lower() in ("true", "1", "yes")
    reload_mode = envs.get("RELOAD", "false").lower() in ("true", "1", "yes")
    fastapi_debug = envs.get("FASTAPI_DEBUG", "false").lower() in ("true", "1", "yes")
    if debug or reload_mode or fastapi_debug:
        raise RuntimeError(
            "Production startup aborted: Debug and reload modes are strictly prohibited in production."
        )

    # 5. Database Configuration & Availability
    db_path = envs.get("GAYATRI_DB_PATH") or envs.get("DATABASE_URL")
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

    # 6. Model Verification (if local model override or validation is requested)
    model_file_override = envs.get("GAYATRI_MODEL_FILE")
    model_checksum_override = envs.get("GAYATRI_MODEL_CHECKSUM")
    if model_file_override:
        model_path = Path(model_file_override)
        if not model_path.is_file():
            raise RuntimeError(
                f"Production startup aborted: Configured model file does not exist: {model_file_override}"
            )
        if model_checksum_override:
            import hashlib
            sha = hashlib.sha256()
            with open(model_path, "rb") as f:
                while chunk := f.read(65536):
                    sha.update(chunk)
            computed = sha.hexdigest()
            if computed.lower() != model_checksum_override.lower():
                raise RuntimeError(
                    f"Production startup aborted: Model checksum mismatch for {model_file_override}. "
                    f"Expected: {model_checksum_override}, Got: {computed}"
                )

    logger.info("Authoritative production configuration hardening verified successfully.")
    return {
        "mode": "production",
        "production_enforced": True,
        "jwt_secret_configured": True,
        "cors_origins": allowed_origins,
        "db_path": db_path,
        "docs_enabled": envs.get("GAYATRI_ENABLE_DOCS", "false").lower() in ("true", "1", "yes"),
    }
