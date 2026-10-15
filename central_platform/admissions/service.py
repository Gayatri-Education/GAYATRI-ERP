"""Admissions CRM Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from central_platform.models.admissions import (
    AdmissionInquiry,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionOffer,
    InquiryStatus,
    ApplicationStatus,
    OfferStatus,
    DocumentType,
    VerificationStatus,
)


class AdmissionsService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def submit_inquiry(
        self,
        organization_id: str,
        applicant_name: str,
        guardian_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        target_grade: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> AdmissionInquiry:
        now = self._now()
        inquiry_id = f"inq-{uuid.uuid4().hex[:12]}"
        inquiry_number = f"INQ-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admission_inquiries (
                    id, organization_id, inquiry_number, applicant_name, guardian_name, email, phone, target_grade, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    inquiry_id,
                    organization_id,
                    inquiry_number,
                    applicant_name,
                    guardian_name,
                    email,
                    phone,
                    target_grade,
                    InquiryStatus.NEW.value,
                    notes,
                    now,
                    now,
                ),
            )

        return AdmissionInquiry(
            id=inquiry_id,
            organization_id=organization_id,
            inquiry_number=inquiry_number,
            applicant_name=applicant_name,
            guardian_name=guardian_name,
            email=email,
            phone=phone,
            target_grade=target_grade,
            status=InquiryStatus.NEW,
            notes=notes,
            created_at=now,
            updated_at=now,
        )

    def find_duplicate_inquiries(
        self, organization_id: str, email: Optional[str] = None, phone: Optional[str] = None
    ) -> List[AdmissionInquiry]:
        if not email and not phone:
            return []
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM admission_inquiries 
                WHERE organization_id = ? AND (
                    (email IS NOT NULL AND email = ?) OR 
                    (phone IS NOT NULL AND phone = ?)
                );
                """,
                (organization_id, email or "", phone or ""),
            )
            rows = cursor.fetchall()
            return [
                AdmissionInquiry(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    inquiry_number=r["inquiry_number"],
                    applicant_name=r["applicant_name"],
                    guardian_name=r["guardian_name"],
                    email=r["email"],
                    phone=r["phone"],
                    target_grade=r["target_grade"],
                    status=InquiryStatus(r["status"]),
                    notes=r["notes"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def list_inquiries(self, organization_id: str) -> List[AdmissionInquiry]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM admission_inquiries WHERE organization_id = ? ORDER BY created_at DESC;",
                (organization_id,),
            )
            rows = cursor.fetchall()
            return [
                AdmissionInquiry(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    inquiry_number=r["inquiry_number"],
                    applicant_name=r["applicant_name"],
                    guardian_name=r["guardian_name"],
                    email=r["email"],
                    phone=r["phone"],
                    target_grade=r["target_grade"],
                    status=InquiryStatus(r["status"]),
                    notes=r["notes"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def submit_application(
        self,
        organization_id: str,
        applicant_name: str,
        academic_year_id: Optional[str] = None,
        inquiry_id: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        gender: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        previous_school: Optional[str] = None,
        target_grade: Optional[str] = None,
    ) -> AdmissionApplication:
        now = self._now()
        app_id = f"app-{uuid.uuid4().hex[:12]}"
        app_number = f"APP-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:6].upper()}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admission_applications (
                    id, organization_id, application_number, inquiry_id, academic_year_id,
                    applicant_name, date_of_birth, gender, email, phone, address,
                    previous_school, target_grade, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    app_id,
                    organization_id,
                    app_number,
                    inquiry_id,
                    academic_year_id,
                    applicant_name,
                    date_of_birth,
                    gender,
                    email,
                    phone,
                    address,
                    previous_school,
                    target_grade,
                    ApplicationStatus.SUBMITTED.value,
                    now,
                    now,
                ),
            )

        return AdmissionApplication(
            id=app_id,
            organization_id=organization_id,
            application_number=app_number,
            applicant_name=applicant_name,
            inquiry_id=inquiry_id,
            academic_year_id=academic_year_id,
            date_of_birth=date_of_birth,
            gender=gender,
            email=email,
            phone=phone,
            address=address,
            previous_school=previous_school,
            target_grade=target_grade,
            status=ApplicationStatus.SUBMITTED,
            created_at=now,
            updated_at=now,
        )

    def get_application(self, application_id: str, organization_id: str) -> Optional[AdmissionApplication]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM admission_applications WHERE id = ? AND organization_id = ?;",
                (application_id, organization_id),
            )
            r = cursor.fetchone()
            if not r:
                return None
            return AdmissionApplication(
                id=r["id"],
                organization_id=r["organization_id"],
                application_number=r["application_number"],
                applicant_name=r["applicant_name"],
                inquiry_id=r["inquiry_id"],
                academic_year_id=r["academic_year_id"],
                date_of_birth=r["date_of_birth"],
                gender=r["gender"],
                email=r["email"],
                phone=r["phone"],
                address=r["address"],
                previous_school=r["previous_school"],
                target_grade=r["target_grade"],
                status=ApplicationStatus(r["status"]),
                review_notes=r["review_notes"],
                decision_date=r["decision_date"],
                decision_by=r["decision_by"],
                converted_student_id=r["converted_student_id"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

    def list_applications(
        self, organization_id: str, status: Optional[str] = None
    ) -> List[AdmissionApplication]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM admission_applications WHERE organization_id = ? AND status = ? ORDER BY created_at DESC;",
                    (organization_id, status),
                )
            else:
                cursor.execute(
                    "SELECT * FROM admission_applications WHERE organization_id = ? ORDER BY created_at DESC;",
                    (organization_id,),
                )
            rows = cursor.fetchall()
            return [
                AdmissionApplication(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    application_number=r["application_number"],
                    applicant_name=r["applicant_name"],
                    inquiry_id=r["inquiry_id"],
                    academic_year_id=r["academic_year_id"],
                    date_of_birth=r["date_of_birth"],
                    gender=r["gender"],
                    email=r["email"],
                    phone=r["phone"],
                    address=r["address"],
                    previous_school=r["previous_school"],
                    target_grade=r["target_grade"],
                    status=ApplicationStatus(r["status"]),
                    review_notes=r["review_notes"],
                    decision_date=r["decision_date"],
                    decision_by=r["decision_by"],
                    converted_student_id=r["converted_student_id"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def attach_document(
        self,
        organization_id: str,
        application_id: str,
        document_type: DocumentType,
        file_name: str,
        file_path: str,
        file_hash: Optional[str] = None,
    ) -> AdmissionDocument:
        now = self._now()
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admission_documents (
                    id, organization_id, application_id, document_type, file_name, file_path, file_hash, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?);
                """,
                (
                    doc_id,
                    organization_id,
                    application_id,
                    document_type.value if hasattr(document_type, "value") else document_type,
                    file_name,
                    file_path,
                    file_hash,
                    now,
                ),
            )

        return AdmissionDocument(
            id=doc_id,
            organization_id=organization_id,
            application_id=application_id,
            document_type=document_type,
            file_name=file_name,
            file_path=file_path,
            file_hash=file_hash,
            verification_status=VerificationStatus.PENDING,
            created_at=now,
        )

    def verify_document(
        self,
        organization_id: str,
        document_id: str,
        status: VerificationStatus,
        verified_by: str,
    ) -> bool:
        now = self._now()
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE admission_documents
                SET verification_status = ?, verified_by = ?, verified_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (
                    status.value if hasattr(status, "value") else status,
                    verified_by,
                    now,
                    document_id,
                    organization_id,
                ),
            )
            return cursor.rowcount > 0

    def update_application_status(
        self,
        organization_id: str,
        application_id: str,
        status: ApplicationStatus,
        review_notes: Optional[str] = None,
        decision_by: Optional[str] = None,
    ) -> AdmissionApplication:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE admission_applications
                SET status = ?, review_notes = COALESCE(?, review_notes), decision_by = COALESCE(?, decision_by), decision_date = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (
                    status.value if hasattr(status, "value") else status,
                    review_notes,
                    decision_by,
                    now,
                    now,
                    application_id,
                    organization_id,
                ),
            )
        app = self.get_application(application_id, organization_id)
        if not app:
            raise ValueError("Application not found after update")
        return app

    def issue_offer(
        self,
        organization_id: str,
        application_id: str,
        grade: str,
        fee_amount: float = 0.0,
        valid_until: str = "",
        conditions: Optional[str] = None,
    ) -> AdmissionOffer:
        now = self._now()
        offer_id = f"ofr-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO admission_offers (
                    id, organization_id, application_id, offer_date, valid_until, grade, fee_amount, conditions, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ISSUED', ?, ?);
                """,
                (offer_id, organization_id, application_id, now, valid_until, grade, fee_amount, conditions, now, now),
            )
            conn.execute(
                "UPDATE admission_applications SET status = 'OFFERED', updated_at = ? WHERE id = ? AND organization_id = ?;",
                (now, application_id, organization_id),
            )

        return AdmissionOffer(
            id=offer_id,
            organization_id=organization_id,
            application_id=application_id,
            offer_date=now,
            valid_until=valid_until,
            grade=grade,
            fee_amount=fee_amount,
            conditions=conditions,
            status=OfferStatus.ISSUED,
            created_at=now,
            updated_at=now,
        )

    def accept_offer(self, organization_id: str, application_id: str, offer_id: str) -> AdmissionApplication:
        now = self._now()
        with self.db._get_connection() as conn:
            conn.execute(
                "UPDATE admission_offers SET status = 'ACCEPTED', updated_at = ? WHERE id = ? AND organization_id = ?;",
                (now, offer_id, organization_id),
            )
            conn.execute(
                "UPDATE admission_applications SET status = 'ACCEPTED', updated_at = ? WHERE id = ? AND organization_id = ?;",
                (now, application_id, organization_id),
            )
        app = self.get_application(application_id, organization_id)
        if not app:
            raise ValueError("Application not found")
        return app

    def convert_application_to_student(
        self,
        organization_id: str,
        application_id: str,
        class_id: Optional[str] = None,
        roll_number: Optional[str] = None,
        guardian_name: Optional[str] = None,
        guardian_phone: Optional[str] = None,
        guardian_relationship: str = "PARENT",
    ) -> Dict[str, Any]:
        """Atomically promote an accepted application to a canonical SIS student record.

        Idempotent: If application was already converted, returns existing IDs.
        """
        now = self._now()
        app = self.get_application(application_id, organization_id)
        if not app:
            raise ValueError("Application not found")

        # Idempotency check: already converted
        if app.converted_student_id:
            return {
                "student_id": app.converted_student_id,
                "person_id": None,
                "guardian_id": None,
                "enrollment_id": None,
                "is_idempotent_replay": True,
            }

        person_id = f"per-{uuid.uuid4().hex[:12]}"
        student_id = f"stu-{uuid.uuid4().hex[:12]}"
        guardian_person_id = f"per-g-{uuid.uuid4().hex[:10]}" if guardian_name else None
        guardian_id = f"grd-{uuid.uuid4().hex[:12]}" if guardian_name else None
        enrollment_id = f"enr-{uuid.uuid4().hex[:12]}" if class_id else None

        name_parts = app.applicant_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        with self.db.transaction():
            with self.db._get_connection() as conn:
                # 1. Create Person
                conn.execute(
                    """
                    INSERT INTO persons (
                        id, organization_id, first_name, last_name, email, phone, date_of_birth, gender, address_line1, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (person_id, organization_id, first_name, last_name, app.email, app.phone, app.date_of_birth, app.gender, app.address, now, now),
                )

                # 2. Create Student Profile
                conn.execute(
                    """
                    INSERT INTO student_profiles (
                        id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?);
                    """,
                    (student_id, person_id, organization_id, app.application_number, roll_number, now, now, now),
                )

                # 3. Create Guardian if provided
                if guardian_name and guardian_id and guardian_person_id:
                    g_parts = guardian_name.strip().split(" ", 1)
                    g_first = g_parts[0]
                    g_last = g_parts[1] if len(g_parts) > 1 else ""
                    conn.execute(
                        """
                        INSERT INTO persons (
                            id, organization_id, first_name, last_name, phone, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (guardian_person_id, organization_id, g_first, g_last, guardian_phone, now, now),
                    )
                    conn.execute(
                        """
                        INSERT INTO guardian_profiles (
                            id, person_id, organization_id, is_legal_guardian, created_at, updated_at
                        ) VALUES (?, ?, ?, 1, ?, ?);
                        """,
                        (guardian_id, guardian_person_id, organization_id, now, now),
                    )
                    conn.execute(
                        """
                        INSERT INTO student_guardian_links (
                            id, organization_id, student_id, guardian_id, relationship, is_primary_contact, is_emergency_contact, is_pickup_authorized, can_access_portal, created_at
                        ) VALUES (?, ?, ?, ?, ?, 1, 1, 1, 1, ?);
                        """,
                        (f"sgl-{uuid.uuid4().hex[:12]}", organization_id, student_id, guardian_id, guardian_relationship, now),
                    )

                # 4. Create class enrollment if class provided
                if class_id and enrollment_id and app.academic_year_id:
                    conn.execute(
                        """
                        INSERT INTO student_class_enrollments (
                            id, organization_id, student_id, class_id, academic_year_id, roll_number, enrollment_date, status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?);
                        """,
                        (enrollment_id, organization_id, student_id, class_id, app.academic_year_id, roll_number, now, now, now),
                    )

                # 5. Update application
                conn.execute(
                    """
                    UPDATE admission_applications
                    SET status = 'CONVERTED', converted_student_id = ?, updated_at = ?
                    WHERE id = ? AND organization_id = ?;
                    """,
                    (student_id, now, application_id, organization_id),
                )

                # 6. Enqueue domain event
                conn.execute(
                    """
                    INSERT INTO domain_events_outbox (
                        id, idempotency_key, event_type, aggregate_type, aggregate_id, organization_id, payload_json, created_at
                    ) VALUES (?, ?, 'admission.converted', 'student', ?, ?, ?, ?);
                    """,
                    (
                        f"evt-{uuid.uuid4().hex[:12]}",
                        f"conv-{application_id}",
                        student_id,
                        organization_id,
                        f'{{"application_id": "{application_id}", "student_id": "{student_id}", "person_id": "{person_id}"}}',
                        now,
                    ),
                )

        return {
            "student_id": student_id,
            "person_id": person_id,
            "guardian_id": guardian_id,
            "enrollment_id": enrollment_id,
            "is_idempotent_replay": False,
        }
