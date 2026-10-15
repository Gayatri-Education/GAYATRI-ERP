"""Gayatri School OS — Institutional Analytics & Exports Router (Phase 08)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user, get_db
from central_platform.db import PlatformDatabase
from central_platform.analytics.institutional import UnifiedInstitutionalAnalyticsService
from central_platform.analytics.exports import DataExportService
from central_platform.ops.diagnostics import PlatformDiagnosticsService
from central_platform.api.routes.identity import _get_org_id

logger = logging.getLogger("gayatri.api.routes.institutional_analytics")

router = APIRouter(prefix="/analytics/institutional", tags=["Institutional Analytics & Ops"])


def get_analytics_service(db: PlatformDatabase = Depends(get_db)) -> UnifiedInstitutionalAnalyticsService:
    return UnifiedInstitutionalAnalyticsService(db)


def get_export_service(db: PlatformDatabase = Depends(get_db)) -> DataExportService:
    return DataExportService(db)


def get_diagnostics_service(db: PlatformDatabase = Depends(get_db)) -> PlatformDiagnosticsService:
    return PlatformDiagnosticsService(db)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ExportCreateRequest(BaseModel):
    export_type: str = "STUDENTS"
    format: str = "CSV"
    filters: Optional[Dict[str, Any]] = None
    limit: int = 1000


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/kpis")
def get_kpis(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: Any = Depends(get_current_user),
    service: UnifiedInstitutionalAnalyticsService = Depends(get_analytics_service),
):
    """Retrieve authoritative cross-module institutional KPIs."""
    org_id = _get_org_id(current_user)
    snapshot = service.get_kpi_snapshot(org_id, start_date=start_date, end_date=end_date)
    return snapshot.to_dict()


@router.get("/student/{student_id}")
def get_student_view(
    student_id: str,
    privacy_level: str = Query("STANDARD"),
    current_user: Any = Depends(get_current_user),
    service: UnifiedInstitutionalAnalyticsService = Depends(get_analytics_service),
):
    """Retrieve student analytics sanitized by parent privacy policy."""
    org_id = _get_org_id(current_user)
    try:
        view = service.get_parent_student_view(org_id, student_id, privacy_level=privacy_level)
        return view
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/export", status_code=status.HTTP_201_CREATED)
def trigger_export(
    req: ExportCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: DataExportService = Depends(get_export_service),
):
    """Trigger bounded, multi-tenant isolated CSV or JSON export."""
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", "admin")
    job_summary, payload_str = service.create_export(
        organization_id=org_id,
        requested_by=user_id,
        export_type=req.export_type,
        format_type=req.format,
        filters=req.filters,
        limit=req.limit,
    )
    return {
        "job": job_summary,
        "payload": payload_str,
    }


@router.get("/diagnostics")
def get_diagnostics(
    current_user: Any = Depends(get_current_user),
    service: PlatformDiagnosticsService = Depends(get_diagnostics_service),
):
    """Generate safe, sanitized platform diagnostic package."""
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", "admin")
    package = service.generate_diagnostic_package(org_id, requested_by=user_id)
    return package
