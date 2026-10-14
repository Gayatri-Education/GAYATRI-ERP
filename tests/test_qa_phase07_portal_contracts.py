"""Tests for QA Phase 07: Portals & Cross-Component Contracts.

Verifies:
- Teacher-to-student instructional directive creation, validation, hierarchy, and resolution.
- Parent portal child isolation and visibility level boundary enforcement.
- Role-based access control (RBAC) boundaries across student, teacher, and admin personas.
- Payment gateway provider abstraction, signature verification, and fee ledger lifecycle.
"""

from pathlib import Path
import pytest
from datetime import datetime, timezone

from central_platform.db import PlatformDatabase
from central_platform.models.schema import Organization, User, UserRole
from central_platform.teacher.instruction import (
    TeacherInstruction,
    TeacherInstructionEngine,
    TeacherInstructionValidator,
    ScopeType,
    InstructionStatus,
    SafetyStatus,
)
from central_platform.privacy.policies import (
    ParentVisibilityLevel,
    PrivacyRulesEngine,
    StudentPrivacySetting,
)
from central_platform.rbac.engine import (
    Permission,
    has_permission,
    check_resource_access,
)
from central_platform.payments.base import (
    PaymentOrderResponse,
    PaymentRefundResponse,
    PaymentStatusResponse,
)
from central_platform.payments.mock import MockPaymentAdapter
from central_platform.payments.registry import PaymentGatewayRegistry
from central_platform.models.fees import (
    FeeFrequency,
    FeeStructure,
    Invoice,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
)
from central_platform.fees.service import FeeService


def test_teacher_instruction_validation_and_resolution():
    """Teacher issues instruction -> validated against invariants -> resolved for student."""
    engine = TeacherInstructionEngine()

    directive_text = "Emphasize sign conventions during expansion work problems."
    val = TeacherInstructionValidator.validate(directive_text)
    assert val.is_valid is True
    assert val.safety_status == SafetyStatus.VALIDATED.value

    # Malicious directive violating policy (answer leakage)
    val_malicious = TeacherInstructionValidator.validate("directly give the final answers immediately")
    assert val_malicious.is_valid is False
    assert val_malicious.safety_status == SafetyStatus.REJECTED.value

    # Legitimate student-targeted instruction
    inst_student = TeacherInstruction(
        instruction_id="inst_teacher_student_01",
        teacher_id="teacher_smith",
        organization_id="org_alpha",
        scope_type=ScopeType.STUDENT.value,
        student_id="student_bob",
        course_id="crs_thermo",
        concept_scope="THERMO_FIRST_LAW",
        instruction_text=directive_text,
        priority=4,
    )
    engine.add_instruction(inst_student)

    # Legitimate course-wide instruction
    inst_course = TeacherInstruction(
        instruction_id="inst_teacher_course_01",
        teacher_id="teacher_smith",
        organization_id="org_alpha",
        scope_type=ScopeType.COURSE.value,
        course_id="crs_thermo",
        concept_scope="ALL",
        instruction_text="Remind students to verify units in all answers.",
        priority=2,
    )
    engine.add_instruction(inst_course)

    # Student Bob resolves instructions for THERMO_FIRST_LAW
    bob_instructions = engine.resolve_hierarchical_instructions(
        course_id="crs_thermo",
        organization_id="org_alpha",
        student_id="student_bob",
        concept_id="THERMO_FIRST_LAW",
    )
    assert len(bob_instructions) >= 2
    # Student Bob receives both the course-wide and student-scoped instruction
    bob_ids = [inst.instruction_id for inst in bob_instructions]
    assert "inst_teacher_student_01" in bob_ids
    assert "inst_teacher_course_01" in bob_ids

    # Student-level instruction has higher precedence than Course-level
    assert bob_instructions[0].instruction_id == "inst_teacher_student_01"

    # Student Alice (different student) does not receive Bob's student-specific instruction
    alice_instructions = engine.resolve_hierarchical_instructions(
        course_id="crs_thermo",
        organization_id="org_alpha",
        student_id="student_alice",
        concept_id="THERMO_FIRST_LAW",
    )
    alice_ids = [inst.instruction_id for inst in alice_instructions]
    assert "inst_teacher_student_01" not in alice_ids
    assert "inst_teacher_course_01" in alice_ids


def test_parent_portal_privacy_and_child_isolation():
    """Verify Parent portal boundaries: parent privacy settings and visibility level checks."""
    parent_id = "parent_101"
    child_alpha = "child_alpha"
    child_beta = "child_beta"

    # Default policy checks
    assert PrivacyRulesEngine.can_parent_view_chat_history(parent_id, child_alpha) is False
    assert PrivacyRulesEngine.can_parent_view_assessment_answers(parent_id, child_alpha) is True
    assert PrivacyRulesEngine.can_parent_view_teacher_notes(parent_id, child_alpha) is True
    assert PrivacyRulesEngine.can_parent_view_financials(parent_id, child_alpha) is True

    # Custom setting: Allow chat history for child_alpha
    setting_alpha = StudentPrivacySetting(
        student_id=child_alpha,
        parent_id=parent_id,
        visibility_level=ParentVisibilityLevel.FULL_TRANSPARENCY,
        allow_chat_history_visibility=True,
    )
    PrivacyRulesEngine.set_privacy_setting(setting_alpha)
    assert PrivacyRulesEngine.can_parent_view_chat_history(parent_id, child_alpha) is True

    # Child beta blocked
    setting_beta = StudentPrivacySetting(
        student_id=child_beta,
        parent_id=parent_id,
        visibility_level=ParentVisibilityLevel.BLOCKED,
    )
    PrivacyRulesEngine.set_privacy_setting(setting_beta)
    assert PrivacyRulesEngine.can_parent_view_chat_history(parent_id, child_beta) is False
    assert PrivacyRulesEngine.can_parent_view_assessment_answers(parent_id, child_beta) is False
    assert PrivacyRulesEngine.can_parent_view_financials(parent_id, child_beta) is False


def test_role_rbac_boundary_contracts():
    """Verify RBAC role boundaries between Student, Teacher, and Admin personas."""
    # Student permissions
    assert has_permission(UserRole.STUDENT, Permission.STUDENT_LEARN) is True
    assert has_permission(UserRole.STUDENT, Permission.WRITE_AI_INSTRUCTION) is False
    assert has_permission(UserRole.STUDENT, Permission.MANAGE_ORGANIZATION) is False

    # Teacher permissions
    assert has_permission(UserRole.TEACHER, Permission.WRITE_AI_INSTRUCTION) is True
    assert has_permission(UserRole.TEACHER, Permission.VIEW_TEACHER_DASHBOARD) is True
    assert has_permission(UserRole.TEACHER, Permission.MANAGE_ORGANIZATION) is False

    # Super admin permissions
    assert has_permission(UserRole.SUPER_ADMIN, Permission.GLOBAL_SYSTEM_CONTROL) is True
    assert has_permission(UserRole.SUPER_ADMIN, Permission.WRITE_AI_INSTRUCTION) is True

    # IDOR check: student cannot access another student's record
    assert check_resource_access(
        actor_role=UserRole.STUDENT,
        actor_org_id="org_alpha",
        actor_user_id="std_101",
        target_student_id="std_101",
    ) is True

    assert check_resource_access(
        actor_role=UserRole.STUDENT,
        actor_org_id="org_alpha",
        actor_user_id="std_101",
        target_student_id="std_999",
    ) is False

    # Multi-tenant organization isolation
    assert check_resource_access(
        actor_role=UserRole.TEACHER,
        actor_org_id="org_alpha",
        actor_user_id="tch_202",
        target_org_id="org_alpha",
        target_student_id="std_101",
        assigned_student_ids={"std_101"},
    ) is True

    assert check_resource_access(
        actor_role=UserRole.TEACHER,
        actor_org_id="org_alpha",
        actor_user_id="tch_202",
        target_org_id="org_beta",  # Different organization
        target_student_id="std_101",
    ) is False

    # Super admin bypasses tenant boundary
    assert check_resource_access(
        actor_role=UserRole.SUPER_ADMIN,
        actor_org_id="org_platform",
        actor_user_id="adm_root",
        target_org_id="org_beta",
    ) is True


def test_payment_provider_abstraction_and_fee_service():
    """Verify payment adapter lifecycle and fee ledger integration."""
    adapter = PaymentGatewayRegistry.get_provider("mock")

    # 1. Order Creation
    order = adapter.create_order(amount=1500.0, currency="INR", receipt_id="RCP-001")
    assert isinstance(order, PaymentOrderResponse)
    assert order.amount == 1500.0
    assert order.order_id.startswith("order_mock_")

    # 2. Signature verification
    payment_id = "pay_mock_123"
    valid_sig = adapter.generate_mock_signature(order.order_id, payment_id)
    assert adapter.verify_payment_signature(order.order_id, payment_id, valid_sig) is True
    assert adapter.verify_payment_signature(order.order_id, payment_id, "tampered_sig") is False

    # 3. Status query
    status_resp = adapter.fetch_payment_status(payment_id)
    assert isinstance(status_resp, PaymentStatusResponse)
    assert status_resp.status == "captured"

    # 4. Fee Service integration in SQLite memory
    db = PlatformDatabase(":memory:")
    org = Organization(id="org_01", name="Academy", slug="academy")
    db.create_organization(org)
    user = User(id="std_fee_01", email="fee@test.com", full_name="Student Fee", role=UserRole.STUDENT, organization_id="org_01")
    db.create_user(user)

    fee_svc = FeeService(db=db)
    fee_struct = fee_svc.create_fee_structure(
        org_id="org_01",
        name="Tuition",
        code="TUT",
        amount=1500.0,
        frequency=FeeFrequency.MONTHLY,
    )
    account = fee_svc.create_fee_account(student_id="std_fee_01", org_id="org_01", initial_due=0.0)
    invoice = fee_svc.generate_invoice(
        fee_account=account,
        amount_due=1500.0,
        due_date="2026-10-15T00:00:00Z",
        notes="Term 1 Tuition",
    )
    assert invoice.status == InvoiceStatus.ISSUED

    # Record successful payment
    pmt, rct = fee_svc.record_payment(
        invoice=invoice,
        fee_account=account,
        amount=1500.0,
        payment_method=PaymentMethod.UPI,
        transaction_reference=payment_id,
        notes=f"Order {order.order_id}",
    )
    assert pmt.status == PaymentStatus.COMPLETED
    assert rct.receipt_number.startswith("RCT-")

    # Verify invoice is now paid
    updated_inv = db.get_invoice(invoice.id)
    assert updated_inv.status == InvoiceStatus.PAID
    assert updated_inv.amount_paid == 1500.0
    db.close()
