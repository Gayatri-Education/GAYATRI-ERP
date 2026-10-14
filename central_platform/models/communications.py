"""Communications and Notifications Domain Models."""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class NotificationChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    PUSH = "PUSH"


class DispatchStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_FINAL = "FAILED_FINAL"


@dataclass
class NotificationTemplate:
    id: str
    organization_id: str
    template_code: str
    channel: NotificationChannel = NotificationChannel.IN_APP
    subject_template: Optional[str] = None
    body_template: str = ""
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""


@dataclass
class NotificationDispatch:
    id: str
    organization_id: str
    template_code: str
    recipient_user_id: str
    channel: NotificationChannel = NotificationChannel.IN_APP
    destination: Optional[str] = None
    rendered_subject: Optional[str] = None
    rendered_body: str = ""
    status: DispatchStatus = DispatchStatus.PENDING
    error_details: Optional[str] = None
    attempts: int = 0
    sent_at: Optional[str] = None
    created_at: str = ""
