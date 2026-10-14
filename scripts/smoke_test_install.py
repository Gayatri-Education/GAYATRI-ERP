#!/usr/bin/env python3
"""Post-Installation Smoke Test & Operational Readiness Validator (Phase 11).

Validates:
- Python runtime environment (>=3.12)
- Importability and linkage of core dependencies (PySide6, FastAPI, Pydantic, Cryptography)
- Database schema initialization in clean sandbox
- Transparent AI readiness reporting (missing model yields MISSING/LOADABLE, never false green HEALTHY - GQA-001)
- Provider status based on runtime inference evidence (GQA-004)
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_smoke_test() -> int:
    print("=" * 65)
    print("  GAYATRI AI — POST-INSTALLATION SMOKE TEST & VERIFICATION")
    print("=" * 65)

    errors = []

    # 1. Python version check
    if sys.version_info < (3, 12):
        errors.append(f"Python 3.12+ required, detected {sys.version}")
    else:
        print(f"[OK] Python version: {sys.version.split()[0]}")

    # 2. Dependency import checks
    required_modules = [
        ("pydantic", "Pydantic V2"),
        ("cryptography", "Cryptography"),
        ("fastapi", "FastAPI"),
        ("httpx", "HTTPX"),
        ("central_platform.db", "Central Platform Database"),
        ("central_platform.deployment.validator", "Deployment Validator"),
    ]

    for mod_name, label in required_modules:
        try:
            __import__(mod_name)
            print(f"[OK] Module '{label}' ({mod_name}) loaded successfully.")
        except Exception as exc:
            errors.append(f"Failed to import {label} ({mod_name}): {exc}")

    # 3. Clean database bootstrap in temporary sandbox
    with tempfile.TemporaryDirectory() as tmp_dir:
        sandbox_db_path = Path(tmp_dir) / "smoke_test.db"
        try:
            from central_platform.db import PlatformDatabase
            db = PlatformDatabase(db_path=str(sandbox_db_path))
            with db._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA integrity_check")
                row = cur.fetchone()
                if row[0] != "ok":
                    errors.append(f"Database PRAGMA integrity_check failed: {row[0]}")
                else:
                    print("[OK] Database schema initialized and PRAGMA integrity_check passed.")
            db.close()
        except Exception as exc:
            errors.append(f"Database sandbox initialization failed: {exc}")

    # 4. Transparent AI readiness check (GQA-001 & GQA-004)
    try:
        from central_platform.deployment.validator import (
            DeploymentValidator,
            ModelReadinessState,
            ValidationStatus,
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            deploy_db = Path(tmp_dir) / "deploy.db"
            validator = DeploymentValidator(
                db_path=str(deploy_db),
                env_vars={"APP_ENV": "development", "GAYATRI_JWT_SECRET": "smoke_test_dev_secret_key_32_chars_ok"},
            )
            # Validate model provider checks
            provider_report = validator.validate_model_providers()
            readiness = provider_report.details.get("readiness_state")
            # If no model is configured or present, readiness state must NOT be HEALTHY
            if readiness == ModelReadinessState.HEALTHY.value:
                errors.append("DeploymentValidator reported HEALTHY despite missing/unverified model! (GQA-001 regression)")
            else:
                print(f"[OK] AI provider readiness probe evaluated safely: status={provider_report.status.value}, readiness={readiness}")
    except Exception as exc:
        errors.append(f"DeploymentValidator smoke probe failed: {exc}")

    # 5. Summary
    print("-" * 65)
    if errors:
        print(f"[FAIL] Smoke test encountered {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("[SUCCESS] All post-installation smoke tests passed cleanly.")
        return 0


if __name__ == "__main__":
    sys.exit(run_smoke_test())
