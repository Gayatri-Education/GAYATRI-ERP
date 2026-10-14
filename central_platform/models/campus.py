"""Campus Operations Domain Models: Visitors, Certificates, and CMS."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class GatePassStatus(str, Enum):
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class CertificateType(str, Enum):
    TRANSFER_CERTIFICATE = "TRANSFER_CERTIFICATE"
    BONAFIDE = "BONAFIDE"
    CHARACTER = "CHARACTER"
    MERIT = "MERIT"


class CertificateStatus(str, Enum):
    ISSUED = "ISSUED"
    REVOKED = "REVOKED"


class CMSStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


@dataclass
class CampusVisitor:
    id: str
    organization_id: str
    full_name: str
    phone: str
    id_proof_type: Optional[str] = None
    id_proof_number: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class VisitorGatePass:
    id: str
    organization_id: str
    visitor_id: str
    pass_number: str
    purpose: str
    host_staff_id: Optional[str] = None
    check_in_time: str = ""
    check_out_time: Optional[str] = None
    status: GatePassStatus = GatePassStatus.CHECKED_IN
    issued_by: Optional[str] = None
    created_at: str = ""


@dataclass
class OfficialCertificate:
    id: str
    organization_id: str
    student_id: str
    certificate_type: CertificateType
    certificate_number: str
    issue_date: str
    valid_until: Optional[str] = None
    status: CertificateStatus = CertificateStatus.ISSUED
    document_hash: str = ""
    payload_json: str = "{}"
    issued_by: Optional[str] = None
    revoked_by: Optional[str] = None
    revocation_reason: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class CMSPage:
    id: str
    organization_id: str
    title: str
    slug: str
    content_html: str
    status: CMSStatus = CMSStatus.DRAFT
    published_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class CMSPost:
    id: str
    organization_id: str
    title: str
    slug: str
    excerpt: Optional[str] = None
    content_html: str = ""
    status: CMSStatus = CMSStatus.DRAFT
    published_at: Optional[str] = None
    author_name: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
