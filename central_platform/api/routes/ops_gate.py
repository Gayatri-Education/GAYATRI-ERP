"""FastAPI Router for Production Release Gate & Release Candidate Verification (Phase 09)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from central_platform.auth.dependencies import get_current_user
from central_platform.models import User
from central_platform.models.schema import UserRole
from central_platform.ops.release_gate import ProductionReleaseGateValidator
from central_platform.rbac.engine import normalize_role

router = APIRouter(prefix="/ops", tags=["Production Operations & Release Gate"])


@router.get("/release-gate")
def get_release_gate_status(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Audit the platform for production readiness and evaluate GO / NO-GO release gate."""
    user_role = normalize_role(current_user.role)
    if user_role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin credentials required to inspect release gate.",
        )

    validator = ProductionReleaseGateValidator()
    result = validator.evaluate_release_gate()
    return {
        "decision": result.decision,
        "passed": result.passed,
        "summary": result.summary,
        "reasons": result.reasons,
        "checks": result.checks,
        "checksum": result.checksum,
    }


@router.get("/release-manifest")
def get_release_manifest(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Retrieve the authoritative release candidate manifest and artifact digest."""
    user_role = normalize_role(current_user.role)
    if user_role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin credentials required to inspect release manifest.",
        )

    manifest_path = Path(__file__).resolve().parent.parent.parent.parent / "RELEASE_MANIFEST.json"
    if not manifest_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Release manifest not generated yet.",
        )

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return data
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read release manifest: {exc}",
        )
