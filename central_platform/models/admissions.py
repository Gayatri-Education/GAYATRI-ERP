"""Admissions CRM Domain Models."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class InquiryStatus(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    CONVERTED = "CONVERTED"
    CLOSED = "CLOSED"


class ApplicationStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    CONVERTED = "CONVERTED"


class DocumentType(str, Enum):
    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE"
    PREVIOUS_MARKSHEET = "PREVIOUS_MARKSHEET"
    TRANSFER_CERTIFICATE = "TRANSFER_CERTIFICATE"
    PHOTO = "PHOTO"
    ID_PROOF = "ID_PROOF"
    MEDICAL_RECORD = "MEDICAL_RECORD"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class OfferStatus(str, Enum):
    ISSUED = "ISSUED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


@dataclass
class AdmissionInquiry:
    id: str
    organization_id: str
    inquiry_number: str
    applicant_name: str
    guardian_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    target_grade: Optional[str] = None
    status: InquiryStatus = InquiryStatus.NEW
    notes: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AdmissionApplication:
    id: str
    organization_id: str
    application_number: str
    applicant_name: str
    inquiry_id: Optional[str] = None
    academic_year_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    previous_school: Optional[str] = None
    target_grade: Optional[str] = None
    status: ApplicationStatus = ApplicationStatus.SUBMITTED
    review_notes: Optional[str] = None
    decision_date: Optional[str] = None
    decision_by: Optional[str] = None
    converted_student_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AdmissionDocument:
    id: str
    organization_id: str
    application_id: str
    document_type: DocumentType
    file_name: str
    file_path: str
    file_hash: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None
    created_at: str = ""


@dataclass
class AdmissionOffer:
    id: str
    organization_id: str
    application_id: str
    offer_date: str
    valid_until: str
    grade: str
    fee_amount: float = 0.0
    conditions: Optional[str] = None
    status: OfferStatus = OfferStatus.ISSUED
    created_at: str = ""
    updated_at: str = ""
