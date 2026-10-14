"""Campus Operations Domain Service: Visitors, Certificates, and CMS."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from central_platform.models.campus import (
    GatePassStatus,
    CampusVisitor,
    VisitorGatePass,
    CertificateType,
    CertificateStatus,
    OfficialCertificate,
    CMSStatus,
    CMSPage,
    CMSPost,
)


class CampusService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Visitor Management ────────────────────────────────────────────────────

    def register_visitor(
        self,
        organization_id: str,
        full_name: str,
        phone: str,
        id_proof_type: Optional[str] = None,
        id_proof_number: Optional[str] = None,
    ) -> CampusVisitor:
        now = self._now()
        vis_id = f"vis-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO campus_visitors (
                    id, organization_id, full_name, phone, id_proof_type, id_proof_number, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (vis_id, organization_id, full_name, phone, id_proof_type, id_proof_number, now, now),
            )

        return CampusVisitor(
            id=vis_id,
            organization_id=organization_id,
            full_name=full_name,
            phone=phone,
            id_proof_type=id_proof_type,
            id_proof_number=id_proof_number,
            created_at=now,
            updated_at=now,
        )

    def issue_gate_pass(
        self,
        organization_id: str,
        visitor_id: str,
        purpose: str,
        host_staff_id: Optional[str] = None,
        issued_by: Optional[str] = None,
    ) -> VisitorGatePass:
        now = self._now()
        pass_id = f"vgp-{uuid.uuid4().hex[:12]}"
        pass_number = f"GP-{uuid.uuid4().hex[:6].upper()}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO visitor_gate_passes (
                    id, organization_id, visitor_id, pass_number, purpose, host_staff_id,
                    check_in_time, check_out_time, status, issued_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'CHECKED_IN', ?, ?);
                """,
                (pass_id, organization_id, visitor_id, pass_number, purpose, host_staff_id, now, issued_by, now),
            )

        return VisitorGatePass(
            id=pass_id,
            organization_id=organization_id,
            visitor_id=visitor_id,
            pass_number=pass_number,
            purpose=purpose,
            host_staff_id=host_staff_id,
            check_in_time=now,
            check_out_time=None,
            status=GatePassStatus.CHECKED_IN,
            issued_by=issued_by,
            created_at=now,
        )

    def checkout_visitor(self, organization_id: str, pass_id: str) -> VisitorGatePass:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE visitor_gate_passes
                SET status = 'CHECKED_OUT', check_out_time = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (now, pass_id, organization_id),
            )

            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, visitor_id, pass_number, purpose, host_staff_id,
                       check_in_time, check_out_time, status, issued_by, created_at
                FROM visitor_gate_passes
                WHERE id = ? AND organization_id = ?;
                """,
                (pass_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Gate pass {pass_id} not found in organization {organization_id}")

            return VisitorGatePass(
                id=row[0],
                organization_id=row[1],
                visitor_id=row[2],
                pass_number=row[3],
                purpose=row[4],
                host_staff_id=row[5],
                check_in_time=row[6],
                check_out_time=row[7],
                status=GatePassStatus(row[8]) if row[8] in GatePassStatus._value2member_map_ else GatePassStatus.CHECKED_OUT,
                issued_by=row[9],
                created_at=row[10],
            )

    # ── Official Certificates ─────────────────────────────────────────────────

    def issue_certificate(
        self,
        organization_id: str,
        student_id: str,
        certificate_type: CertificateType,
        payload_data: Dict[str, Any],
        issued_by: Optional[str] = None,
        valid_until: Optional[str] = None,
    ) -> OfficialCertificate:
        now = self._now()
        cert_id = f"crt-{uuid.uuid4().hex[:12]}"
        cert_number = f"CERT-{certificate_type.value[:4]}-{uuid.uuid4().hex[:6].upper()}"
        payload_json = json.dumps(payload_data)

        raw = f"{organization_id}:{student_id}:{certificate_type.value}:{cert_number}:{payload_json}:{now}"
        doc_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO official_certificates (
                    id, organization_id, student_id, certificate_type, certificate_number, issue_date,
                    valid_until, status, document_hash, payload_json, issued_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ISSUED', ?, ?, ?, ?, ?);
                """,
                (
                    cert_id,
                    organization_id,
                    student_id,
                    certificate_type.value,
                    cert_number,
                    now[:10],
                    valid_until,
                    doc_hash,
                    payload_json,
                    issued_by,
                    now,
                    now,
                ),
            )

        return OfficialCertificate(
            id=cert_id,
            organization_id=organization_id,
            student_id=student_id,
            certificate_type=certificate_type,
            certificate_number=cert_number,
            issue_date=now[:10],
            valid_until=valid_until,
            status=CertificateStatus.ISSUED,
            document_hash=doc_hash,
            payload_json=payload_json,
            issued_by=issued_by,
            created_at=now,
            updated_at=now,
        )

    def revoke_certificate(
        self,
        organization_id: str,
        certificate_id: str,
        revoked_by: str,
        reason: str,
    ) -> OfficialCertificate:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE official_certificates
                SET status = 'REVOKED', revoked_by = ?, revocation_reason = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (revoked_by, reason, now, certificate_id, organization_id),
            )

            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, student_id, certificate_type, certificate_number,
                       issue_date, valid_until, status, document_hash, payload_json, issued_by,
                       revoked_by, revocation_reason, created_at, updated_at
                FROM official_certificates
                WHERE id = ? AND organization_id = ?;
                """,
                (certificate_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Certificate {certificate_id} not found in organization {organization_id}")

            return OfficialCertificate(
                id=row[0],
                organization_id=row[1],
                student_id=row[2],
                certificate_type=CertificateType(row[3]) if row[3] in CertificateType._value2member_map_ else CertificateType.BONAFIDE,
                certificate_number=row[4],
                issue_date=row[5],
                valid_until=row[6],
                status=CertificateStatus(row[7]) if row[7] in CertificateStatus._value2member_map_ else CertificateStatus.REVOKED,
                document_hash=row[8],
                payload_json=row[9],
                issued_by=row[10],
                revoked_by=row[11],
                revocation_reason=row[12],
                created_at=row[13],
                updated_at=row[14],
            )

    # ── Public CMS ────────────────────────────────────────────────────────────

    def create_page(
        self,
        organization_id: str,
        title: str,
        slug: str,
        content_html: str,
    ) -> CMSPage:
        # Check slug uniqueness within organization
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM cms_pages WHERE organization_id = ? AND slug = ?;",
                (organization_id, slug),
            )
            if cursor.fetchone():
                raise ValueError("Slug already exists")

            now = self._now()
            page_id = f"cmp-{uuid.uuid4().hex[:12]}"

            conn.execute(
                """
                INSERT INTO cms_pages (
                    id, organization_id, title, slug, content_html, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'DRAFT', ?, ?);
                """,
                (page_id, organization_id, title, slug, content_html, now, now),
            )

        return CMSPage(
            id=page_id,
            organization_id=organization_id,
            title=title,
            slug=slug,
            content_html=content_html,
            status=CMSStatus.DRAFT,
            published_at=None,
            created_at=now,
            updated_at=now,
        )

    def publish_page(self, organization_id: str, page_id: str) -> CMSPage:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE cms_pages
                SET status = 'PUBLISHED', published_at = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (now, now, page_id, organization_id),
            )

            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, organization_id, title, slug, content_html, status, published_at, created_at, updated_at "
                "FROM cms_pages WHERE id = ? AND organization_id = ?;",
                (page_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"CMS Page {page_id} not found in organization {organization_id}")

            return CMSPage(
                id=row[0],
                organization_id=row[1],
                title=row[2],
                slug=row[3],
                content_html=row[4],
                status=CMSStatus(row[5]) if row[5] in CMSStatus._value2member_map_ else CMSStatus.PUBLISHED,
                published_at=row[6],
                created_at=row[7],
                updated_at=row[8],
            )

    def create_post(
        self,
        organization_id: str,
        title: str,
        slug: str,
        excerpt: Optional[str] = None,
        content_html: str = "",
        author_name: Optional[str] = None,
    ) -> CMSPost:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM cms_posts WHERE organization_id = ? AND slug = ?;",
                (organization_id, slug),
            )
            if cursor.fetchone():
                raise ValueError("Slug already exists")

            now = self._now()
            post_id = f"cpt-{uuid.uuid4().hex[:12]}"

            conn.execute(
                """
                INSERT INTO cms_posts (
                    id, organization_id, title, slug, excerpt, content_html, status, author_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?);
                """,
                (post_id, organization_id, title, slug, excerpt, content_html, author_name, now, now),
            )

        return CMSPost(
            id=post_id,
            organization_id=organization_id,
            title=title,
            slug=slug,
            excerpt=excerpt,
            content_html=content_html,
            status=CMSStatus.DRAFT,
            published_at=None,
            author_name=author_name,
            created_at=now,
            updated_at=now,
        )

    def publish_post(self, organization_id: str, post_id: str) -> CMSPost:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE cms_posts
                SET status = 'PUBLISHED', published_at = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (now, now, post_id, organization_id),
            )

            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, organization_id, title, slug, excerpt, content_html, status, published_at, author_name, created_at, updated_at "
                "FROM cms_posts WHERE id = ? AND organization_id = ?;",
                (post_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"CMS Post {post_id} not found in organization {organization_id}")

            return CMSPost(
                id=row[0],
                organization_id=row[1],
                title=row[2],
                slug=row[3],
                excerpt=row[4],
                content_html=row[5],
                status=CMSStatus(row[6]) if row[6] in CMSStatus._value2member_map_ else CMSStatus.PUBLISHED,
                published_at=row[7],
                author_name=row[8],
                created_at=row[9],
                updated_at=row[10],
            )

    def list_published_pages(self, organization_id: str) -> List[CMSPage]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, organization_id, title, slug, content_html, status, published_at, created_at, updated_at "
                "FROM cms_pages WHERE organization_id = ? AND status = 'PUBLISHED' ORDER BY title;",
                (organization_id,),
            )
            rows = cursor.fetchall()

        return [
            CMSPage(
                id=r[0],
                organization_id=r[1],
                title=r[2],
                slug=r[3],
                content_html=r[4],
                status=CMSStatus(r[5]) if r[5] in CMSStatus._value2member_map_ else CMSStatus.PUBLISHED,
                published_at=r[6],
                created_at=r[7],
                updated_at=r[8],
            )
            for r in rows
        ]
