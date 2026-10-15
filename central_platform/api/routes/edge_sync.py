"""Gayatri School OS — Edge Synchronization API Router (Phase 07)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user, get_current_user_optional, get_db
from central_platform.db import PlatformDatabase
from central_platform.sync.edge_service import EdgeSyncService
from central_platform.models.sync import (
    ConflictResolutionStrategy,
    DeviceType,
)
from central_platform.api.routes.identity import _get_org_id

logger = logging.getLogger("gayatri.api.routes.edge_sync")

router = APIRouter(prefix="/edge", tags=["Edge & Hardware Sync"])


def get_edge_service(db: PlatformDatabase = Depends(get_db)) -> EdgeSyncService:
    return EdgeSyncService(db)


# ── Schemas ───────────────────────────────────────────────────────────────────

class DeviceRegisterRequest(BaseModel):
    device_code: str
    device_type: str = "BIOMETRIC_TERMINAL"
    device_name: str
    secret: str
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DeviceHeartbeatRequest(BaseModel):
    device_id: str
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None


class PunchItemSchema(BaseModel):
    user_id: str
    punch_type: str = "CHECK_IN"
    punch_time: str
    verification_type: str = "FINGERPRINT"
    idempotency_key: str


class PunchBatchRequest(BaseModel):
    device_id: str
    punches: List[PunchItemSchema]


class ConflictResolveRequest(BaseModel):
    strategy: str = "AUTO_MERGED"
    notes: Optional[str] = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/devices/register", status_code=status.HTTP_201_CREATED)
def register_device(
    req: DeviceRegisterRequest,
    current_user: Any = Depends(get_current_user),
    service: EdgeSyncService = Depends(get_edge_service),
):
    org_id = _get_org_id(current_user)
    try:
        dtype = DeviceType(req.device_type)
    except ValueError:
        dtype = DeviceType.BIOMETRIC_TERMINAL

    device = service.register_device(
        organization_id=org_id,
        device_code=req.device_code,
        device_type=dtype,
        device_name=req.device_name,
        secret_plaintext=req.secret,
        ip_address=req.ip_address,
        firmware_version=req.firmware_version,
        metadata=req.metadata,
    )
    return device.__dict__


@router.post("/devices/{device_id}/revoke")
def revoke_device(
    device_id: str,
    reason: str = Query("Decommissioned"),
    current_user: Any = Depends(get_current_user),
    service: EdgeSyncService = Depends(get_edge_service),
):
    org_id = _get_org_id(current_user)
    try:
        device = service.revoke_device(org_id, device_id, reason=reason)
        return device.__dict__
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/devices/heartbeat")
def heartbeat(
    req: DeviceHeartbeatRequest,
    service: EdgeSyncService = Depends(get_edge_service),
):
    service.record_heartbeat(req.device_id, ip_address=req.ip_address, firmware_version=req.firmware_version)
    return {"status": "ACK"}


@router.post("/punches/batch")
def ingest_punches(
    req: PunchBatchRequest,
    current_user: Any = Depends(get_current_user_optional),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    service: EdgeSyncService = Depends(get_edge_service),
):
    org_id = _get_org_id(current_user) if current_user else x_org_id
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing organization identity")

    punches_data = [p.dict() for p in req.punches]
    try:
        result = service.ingest_punch_batch(
            organization_id=org_id,
            device_id=req.device_id,
            punches=punches_data,
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/health")
def get_sync_health(
    current_user: Any = Depends(get_current_user),
    service: EdgeSyncService = Depends(get_edge_service),
):
    org_id = _get_org_id(current_user)
    metrics = service.get_sync_health_metrics(org_id)
    return metrics.__dict__


@router.get("/conflicts")
def list_conflicts(
    unresolved_only: bool = Query(True),
    current_user: Any = Depends(get_current_user),
    service: EdgeSyncService = Depends(get_edge_service),
):
    org_id = _get_org_id(current_user)
    conflicts = service.list_conflicts(org_id, unresolved_only=unresolved_only)
    return [c.__dict__ for c in conflicts]


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(
    conflict_id: str,
    req: ConflictResolveRequest,
    current_user: Any = Depends(get_current_user),
    service: EdgeSyncService = Depends(get_edge_service),
):
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", "admin")
    try:
        strat = ConflictResolutionStrategy(req.strategy)
    except ValueError:
        strat = ConflictResolutionStrategy.MANUAL_REVIEW

    try:
        resolved = service.resolve_conflict(
            organization_id=org_id,
            conflict_id=conflict_id,
            strategy=strat,
            resolved_by=user_id,
            notes=req.notes or "",
        )
        return resolved.__dict__
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
