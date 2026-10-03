"""Gayatri AI Platform — Synchronization API Endpoints (Phase 08).

Master Plan Section 17:
- Real network synchronization pipeline
- Server-side validation and device authorization
- Idempotency & deduplication filter via LearningEventStore
- Out-of-order event sequence reconciliation
- Permanent storage in central PostgreSQL/SQLite database
- Canonical SLR projection update immediately post-sync
"""
from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger("gayatri.central_platform.api.routes.sync")

from central_platform.api.schemas import (
    ApiResponse,
    BatchSyncEventsRequest,
    BatchSyncEventsResponse,
    DeviceBindRequest,
    DeviceBindResponse,
    DeviceListItem,
    SyncStatusResponse,
)
from central_platform.auth.dependencies import (
    enforce_resource_boundaries,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.models.schema import User
from central_platform.sync.manager import SyncEvent, SyncManager
from central_platform.sync.service import SyncService

router = APIRouter(prefix="/sync", tags=["Sync"])


def get_sync_service() -> SyncService:
    """Resolve SyncService backed by active platform database."""
    db = get_db()
    return SyncService(db=db)


_sync_manager = SyncManager()


def _enforce_sync_access(current_user: Optional[User], target_student_id: Optional[str] = None) -> None:
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for synchronization",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user and target_student_id:
        enforce_resource_boundaries(current_user, target_student_id=target_student_id)


@router.post("/events", response_model=ApiResponse[BatchSyncEventsResponse])
async def sync_events(
    batch: BatchSyncEventsRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Batch synchronize offline/local student events with central platform."""
    _enforce_sync_access(current_user, target_student_id=batch.student_id)

    svc = get_sync_service()
    # Process through authoritative central sync service
    try:
        result = svc.process_sync_batch(
            student_id=batch.student_id,
            events=batch.events,
            course_id=batch.course_id,
            device_id=batch.device_id,
            operation_id=batch.operation_id,
            course_version=batch.course_version,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Keep backward compatibility with legacy in-memory manager
    count = 0
    for ev in batch.events:
        sync_ev = SyncEvent(
            event_id=ev.get("event_id", f"sync-{count}"),
            student_id=batch.student_id,
            device_id=batch.device_id or ev.get("device_id", f"device-{batch.student_id}"),
            event_type=ev.get("event_type", "turn_completed"),
            payload=ev,
            timestamp=ev.get("timestamp", ""),
        )
        try:
            _sync_manager.record_event(sync_ev)
        except Exception as exc:
            logger.warning("Failed to record event %s in legacy sync manager: %s", sync_ev.event_id, exc)
        count += 1

    return ApiResponse(
        ok=result["ok"],
        data=BatchSyncEventsResponse(
            ok=result["ok"],
            operation_id=result.get("operation_id"),
            synced_count=result["synced_count"],
            duplicate_count=result["duplicate_count"],
            failed_count=result["failed_count"],
            acknowledged_ids=result["acknowledged_ids"],
            conflicts_resolved=result.get("conflicts_resolved", 0),
            status=result["status"],
            latest_mastery=result["latest_mastery"],
            server_timestamp=result["server_timestamp"],
            is_replay=result.get("is_replay", False),
            sequence_gaps=result.get("sequence_gaps", []),
        ),
    )


@router.get("/status", response_model=ApiResponse[SyncStatusResponse])
async def get_sync_status(
    student_id: str,
    course_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve telemetry synchronization status and device audit summary for a student."""
    _enforce_sync_access(current_user, target_student_id=student_id)

    svc = get_sync_service()
    status_data = svc.get_sync_status(student_id=student_id, course_id=course_id)
    return ApiResponse(
        ok=True,
        data=SyncStatusResponse(**status_data),
    )


@router.post("/devices/bind", response_model=ApiResponse[DeviceBindResponse])
async def bind_device(
    req: DeviceBindRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Explicitly bind hardware device to authenticated student account."""
    _enforce_sync_access(current_user, target_student_id=req.student_id)

    svc = get_sync_service()
    try:
        svc.bind_device(
            device_id=req.device_id,
            student_id=req.student_id,
            organization_id=req.organization_id,
            device_name=req.device_name,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    binding = svc.db.get_device_binding(req.device_id)
    return ApiResponse(
        ok=True,
        data=DeviceBindResponse(
            device_id=req.device_id,
            student_id=req.student_id,
            device_name=req.device_name,
            status="ACTIVE",
            bound_at=binding.bound_at if binding else "",
        ),
    )


@router.get("/devices", response_model=ApiResponse[List[DeviceListItem]])
async def list_devices(
    student_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve all devices bound to a student account."""
    _enforce_sync_access(current_user, target_student_id=student_id)

    svc = get_sync_service()
    devices = svc.db.get_devices_for_student(student_id)
    return ApiResponse(
        ok=True,
        data=[
            DeviceListItem(
                device_id=d.device_id,
                student_id=d.student_id,
                organization_id=d.organization_id,
                device_name=d.device_name,
                device_type=d.device_type,
                status=d.status,
                bound_at=d.bound_at,
                last_synced_at=d.last_synced_at,
            )
            for d in devices
        ],
    )


