"""Gayatri School OS — Edge Synchronization API Router (Phase 07 / Phase 05 QA)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, validator

from central_platform.auth.dependencies import get_current_user, get_current_user_optional, get_db
from central_platform.db import PlatformDatabase
from central_platform.sync.edge_service import EdgeSyncService, _hash_secret
from central_platform.models.sync import (
    ConflictResolutionStrategy,
    DeviceStatus,
    DeviceType,
    PunchType,
    VerificationType,
)
from central_platform.api.routes.identity import _get_org_id

logger = logging.getLogger("gayatri.api.routes.edge_sync")

router = APIRouter(prefix="/edge", tags=["Edge & Hardware Sync"])


def get_edge_service(db: PlatformDatabase = Depends(get_db)) -> EdgeSyncService:
    return EdgeSyncService(db)


# ── Schemas ───────────────────────────────────────────────────────────────────

class DeviceRegisterRequest(BaseModel):
    device_code: str
    device_type: Optional[str] = "BIOMETRIC_TERMINAL"
    device_name: str
    secret: str
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @validator("device_type", pre=True, always=True)
    def validate_device_type(cls, v):
        if v is None:
            return "BIOMETRIC_TERMINAL"
        v_str = str(v).strip().upper()
        allowed = {d.value for d in DeviceType}
        if v_str not in allowed:
            raise ValueError(f"Invalid device_type: '{v}'. Must be one of {sorted(allowed)}")
        return v_str


class DeviceHeartbeatRequest(BaseModel):
    device_id: str
    secret: Optional[str] = None
    ip_address: Optional[str] = None
    firmware_version: Optional[str] = None


class PunchItemSchema(BaseModel):
    user_id: str
    punch_type: str = "CHECK_IN"
    punch_time: str
    verification_type: str = "FINGERPRINT"
    idempotency_key: str

    @validator("punch_type")
    def validate_punch_type(cls, v):
        v_str = str(v).strip().upper()
        allowed = {p.value for p in PunchType}
        if v_str not in allowed:
            raise ValueError(f"Invalid punch_type: '{v}'. Must be one of {sorted(allowed)}")
        return v_str

    @validator("verification_type")
    def validate_verification_type(cls, v):
        v_str = str(v).strip().upper()
        allowed = {vt.value for vt in VerificationType}
        if v_str not in allowed:
            raise ValueError(f"Invalid verification_type: '{v}'. Must be one of {sorted(allowed)}")
        return v_str


class PunchBatchRequest(BaseModel):
    device_id: str
    device_secret: Optional[str] = None
    punches: List[PunchItemSchema]


class ConflictResolveRequest(BaseModel):
    strategy: str = "AUTO_MERGED"
    notes: Optional[str] = ""

    @validator("strategy")
    def validate_strategy(cls, v):
        v_str = str(v).strip().upper()
        allowed = {s.value for s in ConflictResolutionStrategy}
        if v_str not in allowed:
            raise ValueError(f"Invalid strategy: '{v}'. Must be one of {sorted(allowed)}")
        return v_str


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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid device_type: '{req.device_type}'. Must be one of {[d.value for d in DeviceType]}",
        )

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
    current_user: Optional[Any] = Depends(get_current_user_optional),
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
    service: EdgeSyncService = Depends(get_edge_service),
):
    # 1. Retrieve device unscoped to find registered device and tenant
    device = service.get_device_unscoped(req.device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{req.device_id}' not found")

    if device.status == DeviceStatus.REVOKED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Device '{req.device_id}' is REVOKED")

    # 2. Authorize via user session or device secret
    if current_user:
        user_org = _get_org_id(current_user)
        user_role = getattr(current_user, "role", None)
        user_role_str = user_role.value if hasattr(user_role, "value") else str(user_role or "").lower()
        if user_role_str != "super_admin" and user_org != device.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-tenant access forbidden: user in '{user_org}' cannot manage device in '{device.organization_id}'",
            )
    else:
        provided_secret = x_device_secret or req.secret
        if not provided_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing device authentication credentials",
            )
        if _hash_secret(provided_secret) != device.secret_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid device credentials",
            )

    # 3. Durably persist heartbeat
    updated = service.record_heartbeat(device.id, ip_address=req.ip_address, firmware_version=req.firmware_version)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to record heartbeat: device may be inactive or revoked",
        )
    return {
        "status": "ACK",
        "device_id": device.id,
        "organization_id": device.organization_id,
    }


@router.post("/punches/batch")
def ingest_punches(
    req: PunchBatchRequest,
    current_user: Optional[Any] = Depends(get_current_user_optional),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
    service: EdgeSyncService = Depends(get_edge_service),
):
    # 1. Retrieve device unscoped to find registered device and tenant
    device = service.get_device_unscoped(req.device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device '{req.device_id}' not found")

    if device.status == DeviceStatus.REVOKED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Device '{req.device_id}' is REVOKED")

    # 2. Authorize via user session or device secret
    if current_user:
        user_org = _get_org_id(current_user)
        user_role = getattr(current_user, "role", None)
        user_role_str = user_role.value if hasattr(user_role, "value") else str(user_role or "").lower()
        if user_role_str != "super_admin" and user_org != device.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-tenant access forbidden: user in '{user_org}' cannot ingest punches for device in '{device.organization_id}'",
            )
    else:
        provided_secret = x_device_secret or req.device_secret
        if not provided_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing device authentication credentials",
            )
        if _hash_secret(provided_secret) != device.secret_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid device credentials",
            )

    # 3. Derive organization strictly from authenticated device (Requirement 4)
    org_id = device.organization_id

    # 4. If caller provided X-Organization-ID header, verify it matches device tenant
    if x_org_id and x_org_id.strip() and x_org_id.strip() != org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization mismatch: device '{device.id}' belongs to organization '{org_id}', but caller specified '{x_org_id.strip()}'",
        )

    punches_data = [p.dict() for p in req.punches]
    try:
        result = service.ingest_punch_batch(
            organization_id=org_id,
            device_id=device.id,
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid strategy: '{req.strategy}'. Must be one of {[s.value for s in ConflictResolutionStrategy]}",
        )

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
