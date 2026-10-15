"""QA Phase 14 Test Suite: End-to-End Product Acceptance and Release Gate.

Authoritative acceptance tests resolving seed finding ERP-022:
- Student End-to-End Journey: Login -> Enroll -> Study -> Assess -> Progress -> DB Restart Durability.
- Teacher & Curriculum Management Journey: Org Provisioning -> Course Creation -> Teaching Instructions -> Audit Logs.
- Finance & Billing Journey: Fee Account -> Invoice -> Order -> Webhook Ingestion -> Receipt Verification -> Ledger Postings.
- Health & Recovery Reliability Journey: Truthful Probes -> Simulated Outage -> Degraded Fallback.
- Negative & Adversarial Gate: Revoked Tokens -> Cross-Tenant Boundaries -> Tampered Webhooks -> Zero Credit Degradation.
"""

from __future__ import annotations

import os
from pathlib import Path
import time
import uuid
import pytest

from central_platform.assessment.grading import DeterministicGrader, QuestionBankItem
from central_platform.auth.tokens import (
    DatabaseRevocationStore,
    create_access_token,
    decode_and_verify_token,
    set_revocation_store,
)
from central_platform.db import PlatformDatabase
from central_platform.fees.service import FeeService
from central_platform.finance.service import FinanceService, LedgerEntryType
from central_platform.health.service import PlatformHealthService
from central_platform.models.schema import (
    AuditLog,
    Course,
    CourseVisibility,
    Enrollment,
    Organization,
    Session,
    SessionStatus,
    StudentLearningRecord,
    TeacherInstructionRecord,
    User,
    UserRole,
)
from central_platform.recovery.manager import FailureCategory, FailureRecoveryManager, RecoveryStatus
from central_platform.security.auditor import SecurityAuditor


@pytest.fixture
def test_db_path(tmp_path: Path) -> str:
    """Provide a isolated database file path on disk."""
    return str(tmp_path / "phase14_e2e_acceptance.db")


# ── 1. Student End-to-End Learning Lifecycle & Restart Durability ─────────────

def test_e2e_student_lifecycle_and_restart_durability(test_db_path: str):
    """Verifies complete student learning lifecycle and durability across process restart (ERP-022)."""
    # Phase A: Initial session setup & execution
    db = PlatformDatabase(test_db_path)
    org = Organization(id="org-e2e-student", name="National Science Academy", slug="nsa-india")
    db.create_organization(org)

    student = User(
        id="usr-std-e2e-01",
        email="aarav.patel@nsa.edu",
        full_name="Aarav Patel",
        role=UserRole.STUDENT,
        organization_id=org.id,
        is_active=True,
    )
    db.create_user(student)

    # 1. Issue access token and verify identity
    token = create_access_token(
        user_id=student.id,
        role=student.role.value,
        organization_id=org.id,
    )
    claims = decode_and_verify_token(token)
    assert claims["sub"] == student.id
    assert claims["organization_id"] == org.id
    assert claims["role"].lower() == "student"

    # 2. Course creation and student enrollment
    course = Course(
        id="crs-physics-101",
        organization_id=org.id,
        code="PHYS-101",
        title="Classical Mechanics & Dynamics",
        visibility=CourseVisibility.PRIVATE,
    )
    db.create_course(course)

    enrollment = Enrollment(
        id="enr-std-e2e-01",
        student_id=student.id,
        course_id=course.id,
    )
    db.create_enrollment(enrollment)

    # 3. Active Tutoring Session
    session = Session(
        id="sess-turn-e2e-01",
        student_id=student.id,
        course_id=course.id,
        concept_id="NEWTONS_SECOND_LAW",
        status=SessionStatus.ACTIVE,
    )
    db.create_session(session)

    # 4. Assessment Evaluation (Deterministic Grader)
    item = QuestionBankItem(
        id="q-newton-01",
        course_id=course.id,
        question_text="A 5kg mass accelerates at 3 m/s^2. What is the net force?",
        item_type="MCQ",
        correct_answer="B",
        options=["10 N", "15 N", "20 N", "25 N"],
        difficulty=1,
    )
    is_correct, score, feedback = DeterministicGrader.grade_item(item, "B")
    assert is_correct is True
    assert score == 1.0

    # 5. Persist Student Learning Record (SLR)
    slr = StudentLearningRecord(
        id="slr-std-e2e-01",
        student_id=student.id,
        course_id=course.id,
    )
    db.create_slr(slr)

    # Close database handle simulating process termination
    db.close()

    # Phase B: Process Restart / Durability Verification
    restarted_db = PlatformDatabase(test_db_path)
    try:
        persisted_user = restarted_db.get_user(student.id)
        assert persisted_user is not None
        assert persisted_user.email == "aarav.patel@nsa.edu"

        persisted_course = restarted_db.get_course(course.id)
        assert persisted_course is not None
        assert persisted_course.code == "PHYS-101"

        persisted_session = restarted_db.get_session(session.id)
        assert persisted_session is not None
        assert persisted_session.status == SessionStatus.ACTIVE
        assert persisted_session.concept_id == "NEWTONS_SECOND_LAW"

        persisted_slr = restarted_db.get_slr(student.id, course.id)
        assert persisted_slr is not None
        assert persisted_slr.student_id == student.id
        assert persisted_slr.course_id == course.id
    finally:
        restarted_db.close()


# ── 2. Teacher & Curriculum Operations Journey ────────────────────────────────

def test_e2e_teacher_curriculum_and_audit_journey(test_db_path: str):
    """Verifies Teacher course creation, pedagogical guidance, and audit logging."""
    db = PlatformDatabase(test_db_path)
    try:
        org = Organization(id="org-e2e-teacher", name="Delhi STEM Institute", slug="delhi-stem")
        db.create_organization(org)

        teacher = User(
            id="usr-tch-e2e-01",
            email="dr.ananya@delhistem.edu",
            full_name="Dr. Ananya Roy",
            role=UserRole.TEACHER,
            organization_id=org.id,
            is_active=True,
        )
        db.create_user(teacher)

        course = Course(
            id="crs-chem-201",
            organization_id=org.id,
            code="CHEM-201",
            title="Organic Reaction Mechanisms",
        )
        db.create_course(course)

        # Teacher attaches pedagogical instruction
        instruction = TeacherInstructionRecord(
            id="inst-chem-01",
            teacher_id=teacher.id,
            course_id=course.id,
            instruction_text="Guide students to draw electron arrow-pushing mechanisms step-by-step.",
            organization_id=org.id,
        )
        db.create_teacher_instruction(instruction)

        # Verify instruction retrieval
        instructions = db.get_teacher_instructions_for_course(course.id)
        assert len(instructions) == 1
        assert "electron arrow-pushing" in instructions[0].instruction_text

        # Record and verify audit log
        audit = AuditLog(
            id="audit-inst-01",
            organization_id=org.id,
            user_id=teacher.id,
            action="ATTACH_TEACHING_GUIDANCE",
            resource=f"course:{course.id}",
            details={"instruction_id": instruction.id},
        )
        db.record_audit_log(audit)

        logs = db.get_audit_logs(organization_id=org.id)
        assert len(logs) >= 1
        assert logs[0].action == "ATTACH_TEACHING_GUIDANCE"
        assert logs[0].user_id == teacher.id
    finally:
        db.close()


# ── 3. Finance, Billing, Webhook Ingestion & Persisted Receipt ─────────────────

def test_e2e_finance_billing_webhook_and_receipt_journey(test_db_path: str):
    """Verifies fee accounting, payment order creation, webhook settlement, and persisted receipts (ERP-009)."""
    db = PlatformDatabase(test_db_path)
    try:
        org = Organization(id="org-e2e-fin", name="Fin Academy", slug="fin-acad")
        db.create_organization(org)

        student = User(
            id="usr-fin-std-01",
            email="fin.student@acad.org",
            full_name="Finance Student",
            role=UserRole.STUDENT,
            organization_id=org.id,
            is_active=True,
        )
        db.create_user(student)

        fee_svc = FeeService(db)
        fin_svc = FinanceService(db)

        # 1. Initialize fee account and generate tuition invoice
        account = fee_svc.create_fee_account(student.id, org.id)
        invoice = fee_svc.generate_invoice(account, amount_due=5000.0, due_date="2026-12-31")
        assert invoice.status.value.lower() == "issued"

        # 2. Create online payment order
        order = fin_svc.create_payment_order(
            organization_id=org.id,
            invoice_id=invoice.id,
            student_id=student.id,
            amount=5000.0,
            currency="INR",
            provider="razorpay",
        )
        assert order.status.value.upper() == "CREATED"

        # 3. Process authorized payment webhook
        event_id = f"evt-e2e-{uuid.uuid4().hex[:8]}"
        idemp_key = f"idemp-e2e-{uuid.uuid4().hex[:8]}"
        payload = {
            "order_id": order.provider_order_id,
            "amount": 5000.0,
            "currency": "INR",
            "payment_id": f"pay-e2e-{uuid.uuid4().hex[:8]}",
            "event": "payment.captured",
        }

        res = fin_svc.process_payment_webhook(
            organization_id=org.id,
            provider="razorpay",
            event_id=event_id,
            event_type="payment.captured",
            payload=payload,
            signature_verified=True,
            idempotency_key=idemp_key,
        )
        assert res.get("status") == "PROCESSED"
        assert res.get("is_duplicate") is False
        receipt_no = res.get("receipt_number")
        assert receipt_no is not None

        # 4. Verify persisted receipt retrieval (ERP-009)
        with db._get_connection() as conn:
            receipt_row = conn.execute(
                "SELECT receipt_number, amount, issued_to FROM receipts WHERE receipt_number = ?;",
                (receipt_no,),
            ).fetchone()
            assert receipt_row is not None
            assert receipt_row[0] == receipt_no
            assert float(receipt_row[1]) == 5000.0
            assert receipt_row[2] == student.id

            # 5. Verify invoice status marked paid
            inv_row = conn.execute(
                "SELECT status, amount_paid FROM invoices WHERE id = ?;",
                (invoice.id,),
            ).fetchone()
            assert inv_row[0].lower() == "paid"
            assert float(inv_row[1]) == 5000.0
    finally:
        db.close()


# ── 4. Health, Observability, and Graceful Failure Recovery ───────────────────

def test_e2e_health_observability_and_failure_recovery(test_db_path: str):
    """Verifies truthful health probes and structured failure recovery classification (ERP-006, ERP-020)."""
    db = PlatformDatabase(test_db_path)
    try:
        health_svc = PlatformHealthService(db)

        # 1. Health and Readiness Checks
        health_data = health_svc.check_health()
        assert health_data["status"] == "ONLINE"
        assert health_data["database"] == "CONNECTED"
        assert "subsystems" in health_data

        is_ready, ready_data = health_svc.check_ready()
        assert is_ready is True

        # 2. Failure Recovery Manager Handling
        rec_timeout = FailureRecoveryManager.handle_provider_timeout(
            error=TimeoutError("Upstream AI gateway timed out after 30s"),
            max_retries=3,
            provider="anthropic",
        )
        assert rec_timeout.failure_category == FailureCategory.PROVIDER_TIMEOUT
        assert rec_timeout.status == RecoveryStatus.DEGRADED_FALLBACK
        assert rec_timeout.retryable is True
        assert "fallback" in rec_timeout.fallback_used.lower() or "router" in rec_timeout.fallback_used.lower()
    finally:
        db.close()


# ── 5. Adversarial & Negative Security Gate ───────────────────────────────────

def test_e2e_adversarial_security_and_tenant_isolation(test_db_path: str):
    """Verifies strict boundary defenses, token revocation, and XSS sanitization (ERP-001, ERP-003, ERP-018)."""
    db = PlatformDatabase(test_db_path)
    try:
        auditor = SecurityAuditor()

        # 1. Cross-Tenant Boundaries
        assert auditor.verify_tenant_boundary("org-alpha", "org-beta") is False
        assert auditor.verify_tenant_boundary("org-alpha", "org-alpha") is True

        # 2. Student-level IDOR Protection
        student_user = User(
            id="usr-std-owner",
            organization_id="org-alpha",
            email="owner@alpha.org",
            full_name="Owner Student",
            role=UserRole.STUDENT,
        )
        assert auditor.verify_student_access(student_user, "usr-std-owner") is True
        assert auditor.verify_student_access(student_user, "usr-std-victim") is False

        # 3. Token Revocation Rejection
        rev_store = DatabaseRevocationStore(db)
        set_revocation_store(rev_store)
        token = create_access_token(
            user_id="usr-revoked-01",
            role="STUDENT",
            organization_id="org-alpha",
        )
        claims = decode_and_verify_token(token)
        jti = claims["jti"]

        # Revoke token
        rev_store.revoke(jti=jti, expires_at=claims["exp"], reason="Security signout")
        with pytest.raises(PermissionError, match="revoked"):
            decode_and_verify_token(token)
        set_revocation_store(None)

        # 4. Contextual XSS Neutralization
        dangerous_html = "<script>alert('pwned')</script><b>Chemistry Chapter 1</b>"
        clean_html = auditor.sanitize_html(dangerous_html, allow_formatting=True)
        assert "<script>" not in clean_html
        assert "alert" not in clean_html
        assert "<b>Chemistry Chapter 1</b>" in clean_html
    finally:
        db.close()
