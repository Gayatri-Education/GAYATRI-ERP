"""Gayatri School OS — Communications & Notification Gateway API Router (Phase 03)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user
from central_platform.db import PlatformDatabase
from central_platform.communications.service import CommunicationsService
from central_platform.models.communications import NotificationChannel
from central_platform.api.routes.identity import _get_org_id, _get_roles

logger = logging.getLogger("gayatri.api.routes.communications")

router = APIRouter(prefix="/communications", tags=["Communications Gateway"])


def get_db() -> PlatformDatabase:
    return PlatformDatabase()


def get_communications_service(db: PlatformDatabase = Depends(get_db)) -> CommunicationsService:
    return CommunicationsService(db)


class TemplateCreateRequest(BaseModel):
    template_code: str
    channel: NotificationChannel = NotificationChannel.IN_APP
    subject_template: Optional[str] = None
    body_template: str


class NotificationSendRequest(BaseModel):
    template_code: str
    recipient_user_id: str
    destination: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


@router.post("/templates", status_code=status.HTTP_201_CREATED)
def create_template(
    req: TemplateCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: CommunicationsService = Depends(get_communications_service),
):
    roles = _get_roles(current_user)
    if not any(r in ("admin", "org_admin", "super_admin") for r in roles):
        raise HTTPException(status_code=403, detail="Admin permissions required")

    org_id = _get_org_id(current_user)
    tmpl = service.create_template(
        organization_id=org_id,
        template_code=req.template_code,
        channel=req.channel,
        subject_template=req.subject_template,
        body_template=req.body_template,
    )
    return tmpl.__dict__


@router.post("/send", status_code=status.HTTP_201_CREATED)
def send_notification(
    req: NotificationSendRequest,
    current_user: Any = Depends(get_current_user),
    service: CommunicationsService = Depends(get_communications_service),
):
    org_id = _get_org_id(current_user)
    try:
        dispatch = service.send_notification(
            organization_id=org_id,
            template_code=req.template_code,
            recipient_user_id=req.recipient_user_id,
            destination=req.destination,
            params=req.params,
        )
        return dispatch.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/my-notifications")
def get_my_notifications(
    current_user: Any = Depends(get_current_user),
    service: CommunicationsService = Depends(get_communications_service),
):
    org_id = _get_org_id(current_user)
    user_id = getattr(current_user, "id", None) or getattr(current_user, "user_id", "system")
    notifications = service.get_user_notifications(org_id, user_id)
    return [n.__dict__ for n in notifications]
