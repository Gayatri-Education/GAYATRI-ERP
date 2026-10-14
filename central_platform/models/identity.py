"""Gayatri School OS — Shared Platform Identity and Entitlement Domain Models (Phase 01).

Implements Section 6 of DEVELOPMENT.md:
- Canonical Person individual representation.
- Role-specific profiles (Student, Guardian, Staff).
- Student-Guardian authorization linkages.
- Module entitlement records preventing synthetic mock fallbacks in production.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Person:
    id: str
    organization_id: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    user_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    national_id_hash: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "India"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StudentProfile:
    id: str
    person_id: str
    organization_id: str
    admission_number: Optional[str] = None
    roll_number: Optional[str] = None
    admission_date: Optional[str] = None
    academic_status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GuardianProfile:
    id: str
    person_id: str
    organization_id: str
    occupation: Optional[str] = None
    annual_income: Optional[str] = None
    is_legal_guardian: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StudentGuardianLink:
    id: str
    organization_id: str
    student_id: str
    guardian_id: str
    relationship: str
    is_primary_contact: bool = False
    is_emergency_contact: bool = False
    is_pickup_authorized: bool = False
    can_access_portal: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StaffProfile:
    id: str
    person_id: str
    organization_id: str
    employee_id: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    employment_type: str = "full_time"
    employment_status: str = "active"
    joining_date: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModuleEntitlement:
    id: str
    organization_id: str
    module_key: str
    is_enabled: bool = False
    tier: str = "standard"
    valid_until: Optional[str] = None
    config_json: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DomainEvent:
    id: str
    organization_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload_json: str
    idempotency_key: Optional[str] = None
    status: str = "pending"
    retry_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    published_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
