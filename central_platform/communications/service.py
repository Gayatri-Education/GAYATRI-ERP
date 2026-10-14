"""Communications and Notification Gateway Domain Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from central_platform.models.communications import (
    NotificationChannel,
    DispatchStatus,
    NotificationTemplate,
    NotificationDispatch,
)


class CommunicationsService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_template(
        self,
        organization_id: str,
        template_code: str,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        subject_template: Optional[str] = None,
        body_template: str = "",
    ) -> NotificationTemplate:
        now = self._now()
        tmpl_id = f"tpl-{uuid.uuid4().hex[:12]}"
        channel_val = channel.value if hasattr(channel, "value") else channel

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notification_templates (
                    id, organization_id, template_code, channel, subject_template, body_template, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(organization_id, template_code) DO UPDATE SET
                    channel = excluded.channel,
                    subject_template = excluded.subject_template,
                    body_template = excluded.body_template,
                    updated_at = excluded.updated_at;
                """,
                (tmpl_id, organization_id, template_code, channel_val, subject_template, body_template, now, now),
            )

        return NotificationTemplate(
            id=tmpl_id,
            organization_id=organization_id,
            template_code=template_code,
            channel=NotificationChannel(channel_val),
            subject_template=subject_template,
            body_template=body_template,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def get_template(self, organization_id: str, template_code: str) -> Optional[NotificationTemplate]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM notification_templates WHERE organization_id = ? AND template_code = ?;",
                (organization_id, template_code),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return NotificationTemplate(
                id=r["id"],
                organization_id=r["organization_id"],
                template_code=r["template_code"],
                channel=NotificationChannel(r["channel"]),
                subject_template=r["subject_template"],
                body_template=r["body_template"],
                is_active=bool(r["is_active"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def send_notification(
        self,
        organization_id: str,
        template_code: str,
        recipient_user_id: str,
        destination: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> NotificationDispatch:
        now = self._now()
        params = params or {}
        tmpl = self.get_template(organization_id, template_code)
        if not tmpl:
            raise ValueError(f"Notification template {template_code} not found")

        # Render parametric templates safely
        rendered_subject = tmpl.subject_template
        if rendered_subject:
            for k, v in params.items():
                rendered_subject = rendered_subject.replace(f"{{{k}}}", str(v))

        rendered_body = tmpl.body_template
        for k, v in params.items():
            rendered_body = rendered_body.replace(f"{{{k}}}", str(v))

        dispatch_id = f"dsp-{uuid.uuid4().hex[:12]}"
        channel_val = tmpl.channel.value if hasattr(tmpl.channel, "value") else tmpl.channel

        # For IN_APP channel or local simulation, status transitions immediately to DELIVERED
        final_status = DispatchStatus.DELIVERED.value

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notification_dispatches (
                    id, organization_id, template_code, recipient_user_id, channel, destination,
                    rendered_subject, rendered_body, status, attempts, sent_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?);
                """,
                (
                    dispatch_id,
                    organization_id,
                    template_code,
                    recipient_user_id,
                    channel_val,
                    destination,
                    rendered_subject,
                    rendered_body,
                    final_status,
                    now,
                    now,
                ),
            )

        return NotificationDispatch(
            id=dispatch_id,
            organization_id=organization_id,
            template_code=template_code,
            recipient_user_id=recipient_user_id,
            channel=NotificationChannel(channel_val),
            destination=destination,
            rendered_subject=rendered_subject,
            rendered_body=rendered_body,
            status=DispatchStatus(final_status),
            attempts=1,
            sent_at=now,
            created_at=now,
        )

    def get_user_notifications(
        self, organization_id: str, recipient_user_id: str
    ) -> List[NotificationDispatch]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM notification_dispatches 
                WHERE organization_id = ? AND recipient_user_id = ? 
                ORDER BY created_at DESC;
                """,
                (organization_id, recipient_user_id),
            )
            rows = cursor.fetchall()
            return [
                NotificationDispatch(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    template_code=r["template_code"],
                    recipient_user_id=r["recipient_user_id"],
                    channel=NotificationChannel(r["channel"]),
                    destination=r["destination"],
                    rendered_subject=r["rendered_subject"],
                    rendered_body=r["rendered_body"],
                    status=DispatchStatus(r["status"]),
                    attempts=r["attempts"],
                    sent_at=r["sent_at"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
