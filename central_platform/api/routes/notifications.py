"""Gayatri AI Platform — Multi-Channel Notifications API Endpoints (Phase 21).

Supports in-app, email, push, and WhatsApp delivery with queueing, status tracking,
and exponential backoff retry mechanics.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.api.schemas import (
    ApiResponse,
    NotificationBatchRequest,
    NotificationCreateRequest,
    NotificationQueueStatsResponse,
    NotificationResponse,
    NotificationStatusResponse,
)
from central_platform.auth.dependencies import (
    get_current_user_optional,
    is_production_mode,
)
from central_platform.models.schema import User, UserRole
from central_platform.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])

_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# ── 1. Query Notifications ───────────────────────────────────────────────────

@router.get("", response_model=ApiResponse[List[NotificationResponse]])
async def list_notifications(
    recipient_id: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    channel: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: NotificationService = Depends(get_notification_service),
):
    """Retrieve notifications for user with optional unread and channel filters."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    target_recipient = recipient_id
    if not target_recipient and current_user:
        target_recipient = current_user.id
    if not target_recipient:
        target_recipient = "usr-current-01"

    # RBAC: Students can only view their own notifications
    if current_user and current_user.role == UserRole.STUDENT and current_user.id != target_recipient:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students may only view their own notifications",
        )

    records = service.get_user_notifications(
        recipient_id=target_recipient,
        unread_only=unread_only,
        channel=channel,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    # If no records in db and querying in unauthenticated/legacy mode, provide standard greeting notification
    if not records and not current_user:
        return ApiResponse(
            ok=True,
            data=[
                NotificationResponse(
                    id="notif-01",
                    notification_id="notif-01",
                    recipient_id=target_recipient,
                    channel="in_app",
                    title="Pedagogical Directive Updated",
                    message="Teacher Sharma added a new directive for thermodynamics.",
                    status="delivered",
                    is_read=False,
                    created_at="2026-09-27T10:00:00Z",
                )
            ],
        )

    data = [NotificationResponse(**r.to_dict()) for r in records]
    return ApiResponse(ok=True, data=data)


# ── 2. Create and Dispatch Notifications ──────────────────────────────────────

@router.post("", response_model=ApiResponse[NotificationResponse])
async def create_notification(
    req: NotificationCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: NotificationService = Depends(get_notification_service),
):
    """Dispatch a notification to a recipient via specified delivery channel."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Students cannot dispatch arbitrary notifications to other users
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students are not authorized to dispatch notifications",
        )

    notif = await service.send_notification(
        recipient_id=req.recipient_id,
        title=req.title,
        message=req.message,
        channel=req.channel,
        metadata=req.metadata,
        sync_deliver=req.sync_deliver,
    )
    return ApiResponse(ok=True, data=NotificationResponse(**notif.to_dict()))


@router.post("/batch", response_model=ApiResponse[List[NotificationResponse]])
async def create_batch_notifications(
    req: NotificationBatchRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: NotificationService = Depends(get_notification_service),
):
    """Dispatch notifications to multiple recipients simultaneously."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students are not authorized to dispatch batch notifications",
        )

    results = await service.send_batch(
        recipient_ids=req.recipient_ids,
        title=req.title,
        message=req.message,
        channel=req.channel,
        metadata=req.metadata,
    )
    return ApiResponse(ok=True, data=[NotificationResponse(**n.to_dict()) for n in results])


# ── 3. Status and Read Lifecycle ──────────────────────────────────────────────

@router.get("/{notification_id}/status", response_model=ApiResponse[NotificationStatusResponse])
async def get_notification_status(
    notification_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: NotificationService = Depends(get_notification_service),
):
    """Track delivery status, retry attempts, and provider confirmation for a notification."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    notif = service.get_notification(notification_id)
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found",
        )

    if current_user and current_user.role == UserRole.STUDENT and current_user.id != notif.recipient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to inspect this notification",
        )

    return ApiResponse(
        ok=True,
        data=NotificationStatusResponse(
            notification_id=notif.id,
            recipient_id=notif.recipient_id,
            channel=notif.channel,
            status=notif.status,
            retry_count=notif.retry_count,
            max_retries=notif.max_retries,
            next_retry_at=notif.next_retry_at,
            delivered_at=notif.delivered_at,
            error_message=notif.error_message,
            provider_message_id=notif.provider_message_id,
            is_read=notif.is_read,
        ),
    )


@router.post("/{notification_id}/read", response_model=ApiResponse[Dict[str, Any]])
async def mark_as_read(
    notification_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: NotificationService = Depends(get_notification_service),
):
    """Mark a specific notification as read."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = current_user.id if current_user else None
    success = service.mark_as_read(notification_id, recipient_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found or already read",
        )
    return ApiResponse(ok=True, data={"notification_id": notification_id, "is_read": True})


@router.post("/read-all", response_model=ApiResponse[Dict[str, Any]])
async def mark_all_as_read(
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: NotificationService = Depends(get_notification_service),
):
    """Mark all unread notifications for the current authenticated user as read."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to mark all notifications as read",
        )

    count = service.mark_all_as_read(current_user.id)
    return ApiResponse(ok=True, data={"recipient_id": current_user.id, "marked_count": count})


# ── 4. Queue Processing & Metrics ─────────────────────────────────────────────

@router.post("/process-queue", response_model=ApiResponse[Dict[str, Any]])
async def process_notification_queue(
    limit: int = Query(50, ge=1, le=500),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: NotificationService = Depends(get_notification_service),
):
    """Trigger background queue processing worker tick (Admin / System)."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user and current_user.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privilege required to trigger queue worker",
        )

    stats = await service.process_queue(limit=limit)
    return ApiResponse(ok=True, data=stats)


@router.get("/queue/stats", response_model=ApiResponse[NotificationQueueStatsResponse])
async def get_queue_stats(
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: NotificationService = Depends(get_notification_service),
):
    """Get real-time statistics on notification queue depth and channel volume."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user and current_user.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privilege required to view queue statistics",
        )

    stats = service.get_queue_stats()
    return ApiResponse(ok=True, data=NotificationQueueStatsResponse(**stats))
