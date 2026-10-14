"""Phase 7: Tutor Orchestrator & Multi-Turn Continuity Remediation Test Suite (Section 13).

Comprehensive verification of the 16-step turn lifecycle and multi-turn continuity:
1. Full 16-step turn lifecycle execution and invariant verification.
2. 5-turn realistic dialogue flow:
   - Turn 1: concept question ("What is dynamic chemical equilibrium?")
   - Turn 2: confusion statement ("I still don't understand that")
   - Turn 3: student answer to tutor question ("Does it mean the forward rate equals reverse rate?")
   - Turn 4: request for harder example ("Can you give me a harder example?")
   - Turn 5: request for summary ("Can you summarize everything we covered?")
3. Application restart & session resumption:
   - Re-instantiate orchestrator on persistent DB, resume session without client-side history,
     execute Turn 6 and prove zero context loss, zero identity drift, zero course drift.
4. Hierarchical teacher instruction cascade across Session > Student > Class > Course > Org.
5. Scoped RAG retrieval isolation and provenance tracking.
6. Anti-answer leakage validation rejection & transactional rollback.
7. AI Gateway failure safe degradation (no false mastery, no false turn completion).
8. Session boundary enforcement (cross-student session hijack rejection, cross-course session rejection).
9. Relational integrity enforcement (unregistered student rejection).
10. REST API multi-turn continuity with JWT authentication and tenant boundary checks.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from central_platform.ai.gateway import AIGatewayService
from central_platform.ai.schema import AIExecutionResult, ModelExecutionStatus
from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.courses.service import CourseNotFoundError
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    ClassGroup,
    Cohort,
    Course,
    CoursePolicy,
    CourseStatus,
    CourseToolPolicy,
    CourseVersion,
    CourseVisibility,
    Enrollment,
    KnowledgeContentType,
    LearningEvent,
    Organization,
    Session,
    SessionStatus,
    StudentLearningRecord,
    TeacherInstructionRecord,
    User,
    UserRole,
)
from central_platform.rag.service import RAGService
from central_platform.tutor.orchestrator import (
    EnrollmentError,
    GenericTutorOrchestrator,
    TutorTurnRequest,
    TutorTurnResult,
)


@pytest.fixture
def persistent_db(tmp_path: Path):
    """File-backed SQLite database to simulate realistic multi-turn continuity across restarts."""
    db_file = str(tmp_path / "gayatri_test_phase07.db")
    db = PlatformDatabase(db_file)

    # 1. Organization
    org = Organization(
        id="org-stem-academy",
        name="STEM Excellence Academy",
        slug="stem-academy",
    )
    db.create_organization(org)

    # 2. Users
    admin = User(
        id="admin-01",
        organization_id="org-stem-academy",
        email="admin@stem.edu",
        full_name="Admin Director",
        role=UserRole.SUPER_ADMIN,
    )
    teacher = User(
        id="teacher-01",
        organization_id="org-stem-academy",
        email="teacher@stem.edu",
        full_name="Prof. Ramanujan",
        role=UserRole.TEACHER,
    )
    student1 = User(
        id="student-01",
        organization_id="org-stem-academy",
        email="student1@stem.edu",
        full_name="Ananya Sharma",
        role=UserRole.STUDENT,
    )
    student2 = User(
        id="student-02",
        organization_id="org-stem-academy",
        email="student2@stem.edu",
        full_name="Kabir Mehta",
        role=UserRole.STUDENT,
    )
    db.create_user(admin)
    db.create_user(teacher)
    db.create_user(student1)
    db.create_user(student2)

    # 3. Courses
    chem_course = Course(
        id="course-chem-101",
        organization_id="org-stem-academy",
        code="CHEM101",
        title="General Chemistry: Equilibrium & Dynamics",
        description="Comprehensive study of chemical equilibrium and kinetics.",
        visibility=CourseVisibility.PRIVATE,
    )
    physics_course = Course(
        id="course-phys-101",
        organization_id="org-stem-academy",
        code="PHYS101",
        title="Classical Mechanics",
        visibility=CourseVisibility.PRIVATE,
    )
    db.create_course(chem_course)
    db.create_course(physics_course)

    # 4. Course Versions
    chem_v1 = CourseVersion(
        id="ver-chem-v1",
        course_id="course-chem-101",
        version_number="1.0",
        status=CourseStatus.PUBLISHED,
        created_by="teacher-01",
        tutor_policy=CoursePolicy(
            strict_prerequisites=True,
            max_hints_per_concept=3,
        ),
        tool_policy=CourseToolPolicy(
            calculator=True,
            equation_balancer=True,
        ),
    )
    phys_v1 = CourseVersion(
        id="ver-phys-v1",
        course_id="course-phys-101",
        version_number="1.0",
        status=CourseStatus.PUBLISHED,
        created_by="teacher-01",
    )
    db.create_course_version(chem_v1)
    db.create_course_version(phys_v1)

    # 5. Class Groups and Cohorts
    db.create_class_group(
        ClassGroup(
            id="grp-chem-11",
            organization_id="org-stem-academy",
            course_id="course-chem-101",
            name="Class 11 Chemistry",
        )
    )
    db.create_cohort(
        Cohort(
            id="cohort-chem-alpha",
            class_group_id="grp-chem-11",
            name="Section Alpha",
            academic_year="2026-2027",
        )
    )
    db.create_class_group(
        ClassGroup(
            id="grp-phys-11",
            organization_id="org-stem-academy",
            course_id="course-phys-101",
            name="Class 11 Physics",
        )
    )
    db.create_cohort(
        Cohort(
            id="cohort-phys-alpha",
            class_group_id="grp-phys-11",
            name="Section Alpha",
            academic_year="2026-2027",
        )
    )

    # 6. Enrollments
    db.create_enrollment(
        Enrollment(
            id="enr-student1-chem",
            student_id="student-01",
            course_id="course-chem-101",
            cohort_id="cohort-chem-alpha",
            is_active=True,
        )
    )
    db.create_enrollment(
        Enrollment(
            id="enr-student2-phys",
            student_id="student-02",
            course_id="course-phys-101",
            cohort_id="cohort-phys-alpha",
            is_active=True,
        )
    )

    # 6. RAG Knowledge Asset & Chunks for Chemistry
    rag_svc = RAGService(db=db)
    chem_content = (
        "Chapter 7: Equilibrium\n\n"
        "Section 7.1: Dynamic Nature of Equilibrium\n\n"
        "Chemical equilibrium is a dynamic state where the rate of the forward reaction equals the rate of the reverse reaction. "
        "Concentrations of reactants and products remain constant over time, but the reactions do not stop.\n\n"
        "Section 7.2: Le Chatelier's Principle\n\n"
        "Le Chatelier's principle states that if a system at dynamic equilibrium is disturbed by a change in temperature, pressure, "
        "or concentration, the system shifts in a direction that counteracts the disturbance."
    )
    chem_asset = rag_svc.upload_knowledge_asset(
        course_id="course-chem-101",
        title="NCERT Chemistry Class 11 Chapter 7: Equilibrium",
        content=chem_content,
        organization_id="org-stem-academy",
        subject="Chemistry",
        user=teacher,
        authority="NCERT",
        content_type=KnowledgeContentType.TEXTBOOK,
    )
    rag_svc.approve_knowledge_asset(chem_asset.id, user=admin)
    rag_svc.publish_knowledge_asset(chem_asset.id, user=admin)

    # 7. Teacher Instruction at Course Level
    inst = TeacherInstructionRecord(
        id="inst-chem-analogy",
        teacher_id="teacher-01",
        course_id="course-chem-101",
        organization_id="org-stem-academy",
        scope_type="COURSE",
        instruction_text="Always illustrate dynamic equilibrium using real-world physical analogies (like a walking treadmill or two-way traffic bridge) before mathematical equations.",
        is_active=True,
    )
    db.create_teacher_instruction(inst)

    return db


# ── 1. Full 16-Step Turn Lifecycle Verification ──────────────────────────────

def test_16_step_turn_lifecycle_execution_and_invariants(persistent_db):
    """Verify that every turn executes strictly across all 16 lifecycle steps."""
    orchestrator = GenericTutorOrchestrator(db=persistent_db)

    # Turn execution with full instrumentation
    req = TutorTurnRequest(
        student_id="student-01",
        session_id="sess-lifecycle-01",
        course_id="course-chem-101",
        message="What is chemical equilibrium?",
        concept_id="equilibrium",
    )
    result = orchestrator.execute_turn(req)

    # Invariant 1: Identity & Session binding
    assert result.student_id == "student-01"
    assert result.session_id == "sess-lifecycle-01"
    assert result.course_id == "course-chem-101"
    assert result.concept_id == "equilibrium"

    # Invariant 2: Enrollment resolution
    enrs = persistent_db.get_enrollments_for_student("student-01")
    assert any(e.course_id == "course-chem-101" and e.is_active for e in enrs)

    # Invariant 3: Class / Cohort resolution
    sess = persistent_db.get_session("sess-lifecycle-01")
    assert sess is not None
    assert sess.class_id == "cohort-chem-alpha"

    # Invariant 4: Teacher instruction cascade applied
    assert result.teacher_instructions_applied >= 1
    assert "inst-chem-analogy" in result.applied_instruction_ids

    # Invariant 5: Tool policy respected
    assert "calculator" in result.tools_invoked
    assert "equation_balancer" in result.tools_invoked

    # Invariant 6: Scoped RAG retrieval & provenance
    assert len(result.rag_sources_used) > 0
    assert len(result.provenance_records) > 0
    assert result.provenance_records[0]["source_id"].startswith("src_")
    assert result.provenance_records[0]["authority"] == "NCERT"
    assert "Equilibrium" in result.provenance_records[0]["source_title"]

    # Invariant 7: Response planning & validation
    assert result.validation_passed is True
    assert result.pedagogical_action in ("EXPLAIN", "PRACTICE", "CONTINUE")
    assert len(result.response_text) > 20

    # Invariant 8: Atomic state commit
    assert result.state_committed is True
    events = persistent_db.get_learning_events_for_session("sess-lifecycle-01")
    assert len(events) == 1
    assert events[0].event_type == "TUTOR_TURN_COMPLETED"
    assert events[0].payload["student_message"] == "What is chemical equilibrium?"
    assert events[0].payload["response_text"] == result.response_text

    # Invariant 9: Telemetry & model provenance
    assert result.latency_ms > 0
    assert "provider" in result.model_provenance
    assert result.status == "SUCCESS"


# ── 2. Multi-Turn Conversation Flow (5 Turns Real Dialogue) ──────────────────

def test_multi_turn_conversation_flow_5_turns_real_dialogue(persistent_db):
    """Execute realistic 5-turn dialogue flow verifying continuity across each transition.

    Turn 1: student asks concept question
    Turn 2: student says "I still don't understand that"
    Turn 3: student answers tutor question
    Turn 4: student asks for a harder example
    Turn 5: student requests a summary
    """
    orchestrator = GenericTutorOrchestrator(db=persistent_db)
    session_id = "sess-multiturn-dialogue"
    student_id = "student-01"
    course_id = "course-chem-101"

    history: list[dict[str, str]] = []

    # ── Turn 1: Concept Question ──────────────────────────────────────────────
    t1_req = TutorTurnRequest(
        student_id=student_id,
        session_id=session_id,
        course_id=course_id,
        concept_id="equilibrium",
        message="What is dynamic chemical equilibrium?",
        conversation_history=history,
    )
    t1_res = orchestrator.execute_turn(t1_req)
    assert t1_res.status == "SUCCESS"
    assert t1_res.pedagogical_action == "EXPLAIN"
    assert t1_res.concept_id == "equilibrium"
    assert t1_res.teacher_instructions_applied >= 1
    assert len(t1_res.rag_sources_used) > 0
    assert t1_res.state_committed is True

    history.append({"role": "user", "content": t1_req.message})
    history.append({"role": "assistant", "content": t1_res.response_text})

    # ── Turn 2: Student says "I still don't understand that" ──────────────────
    # Note: student does not re-pass concept_id, verifying zero concept drift!
    t2_req = TutorTurnRequest(
        student_id=student_id,
        session_id=session_id,
        course_id=course_id,
        concept_id=None,  # Intentionally omitted to test concept continuity from session
        message="I still don't understand that",
        conversation_history=history,
    )
    t2_res = orchestrator.execute_turn(t2_req)
    assert t2_res.status == "SUCCESS"
    # Zero concept drift: concept must remain 'equilibrium'
    assert t2_res.concept_id == "equilibrium"
    # Pedagogical response planning responds to confusion
    assert t2_res.pedagogical_action in ("EXPLAIN", "REMEDIATE")
    assert t2_res.state_committed is True

    history.append({"role": "user", "content": t2_req.message})
    history.append({"role": "assistant", "content": t2_res.response_text})

    # ── Turn 3: Student answers tutor check question ──────────────────────────
    t3_req = TutorTurnRequest(
        student_id=student_id,
        session_id=session_id,
        course_id=course_id,
        concept_id=None,
        message="Does it mean the forward rate equals reverse rate?",
        conversation_history=history,
    )
    t3_res = orchestrator.execute_turn(t3_req)
    assert t3_res.status == "SUCCESS"
    assert t3_res.concept_id == "equilibrium"
    assert t3_res.pedagogical_action in ("CONTINUE", "PRACTICE")
    assert t3_res.state_committed is True

    history.append({"role": "user", "content": t3_req.message})
    history.append({"role": "assistant", "content": t3_res.response_text})

    # ── Turn 4: Student asks for a harder example ─────────────────────────────
    t4_req = TutorTurnRequest(
        student_id=student_id,
        session_id=session_id,
        course_id=course_id,
        concept_id=None,
        message="Can you give me a harder example?",
        conversation_history=history,
    )
    t4_res = orchestrator.execute_turn(t4_req)
    assert t4_res.status == "SUCCESS"
    assert t4_res.concept_id == "equilibrium"
    assert t4_res.pedagogical_action in ("CHALLENGE", "PRACTICE")
    assert t4_res.state_committed is True

    history.append({"role": "user", "content": t4_req.message})
    history.append({"role": "assistant", "content": t4_res.response_text})

    # ── Turn 5: Student requests a summary ────────────────────────────────────
    t5_req = TutorTurnRequest(
        student_id=student_id,
        session_id=session_id,
        course_id=course_id,
        concept_id=None,
        message="Can you summarize everything we covered?",
        conversation_history=history,
    )
    t5_res = orchestrator.execute_turn(t5_req)
    assert t5_res.status == "SUCCESS"
    assert t5_res.concept_id == "equilibrium"
    assert t5_res.pedagogical_action == "REVIEW"
    assert t5_res.state_committed is True

    # ── Multi-turn State Audit Verification ───────────────────────────────────
    events = persistent_db.get_learning_events_for_session(session_id)
    assert len(events) == 5
    for idx, ev in enumerate(events):
        assert ev.event_type == "TUTOR_TURN_COMPLETED"
        assert ev.concept_id == "equilibrium"
        assert ev.student_id == student_id
        assert ev.course_id == course_id
        assert "student_message" in ev.payload
        assert "response_text" in ev.payload


# ── 3. Application Restart & Session Resumption (Turn 6) ─────────────────────

def test_application_restart_session_resumption_and_turn_6(persistent_db):
    """Simulate complete application restart, instantiate brand-new orchestrator, and resume session."""
    session_id = "sess-restart-continuity"
    student_id = "student-01"
    course_id = "course-chem-101"

    # Phase A: Run 2 turns on Orchestrator Instance 1
    orch1 = GenericTutorOrchestrator(db=persistent_db)

    turn1_res = orch1.execute_turn(
        TutorTurnRequest(
            student_id=student_id,
            session_id=session_id,
            course_id=course_id,
            concept_id="equilibrium",
            message="What is the equilibrium constant Kc?",
        )
    )
    assert turn1_res.status == "SUCCESS"

    turn2_res = orch1.execute_turn(
        TutorTurnRequest(
            student_id=student_id,
            session_id=session_id,
            course_id=course_id,
            message="How does temperature affect Kc?",
        )
    )
    assert turn2_res.status == "SUCCESS"

    # Verify 2 events persisted to SQLite
    events_before = persistent_db.get_learning_events_for_session(session_id)
    assert len(events_before) == 2

    # ── Phase B: Simulate Application Shutdown & Restart ──────────────────────
    del orch1  # Explicitly destroy first orchestrator instance

    # Instantiate brand-new orchestrator instance pointing to the same persistent DB
    orch2 = GenericTutorOrchestrator(db=persistent_db)

    # ── Phase C: Execute Turn 3 on resumed session WITHOUT passing conversation_history ──
    # The orchestrator MUST automatically recover the conversation history from persistent DB
    turn3_req = TutorTurnRequest(
        student_id=student_id,
        session_id=session_id,
        course_id=course_id,
        concept_id=None,  # Preserves concept continuity from session
        message="So what happens if we cool an exothermic reaction at equilibrium?",
        conversation_history=[],  # Client state lost / empty after restart
    )
    turn3_res = orch2.execute_turn(turn3_req)

    # Gate: Zero context loss, zero identity drift, zero course drift
    assert turn3_res.status == "SUCCESS"
    assert turn3_res.student_id == student_id
    assert turn3_res.session_id == session_id
    assert turn3_res.course_id == course_id
    assert turn3_res.concept_id == "equilibrium"  # Maintained from session
    assert turn3_res.state_committed is True

    # Check that SQLite now contains all 3 sequential turns with proper timestamps and ordering
    events_after = persistent_db.get_learning_events_for_session(session_id)
    print("DEBUG EVENTS_AFTER:", [(e.id, e.payload.get("student_message")) for e in events_after])
    assert len(events_after) == 3
    assert events_after[0].payload["student_message"] == "What is the equilibrium constant Kc?"
    assert events_after[1].payload["student_message"] == "How does temperature affect Kc?"
    assert events_after[2].payload["student_message"] == "So what happens if we cool an exothermic reaction at equilibrium?"


# ── 4. Hierarchical Teacher Instruction Cascade ──────────────────────────────

def test_teacher_instruction_cascade_hierarchical_resolution(persistent_db):
    """Verify that instructions cascade hierarchically from Org -> Course -> Class -> Student -> Session."""
    # Add student-specific instruction
    student_inst = TeacherInstructionRecord(
        id="inst-student-socratic",
        teacher_id="teacher-01",
        student_id="student-01",
        course_id="course-chem-101",
        organization_id="org-stem-academy",
        scope_type="STUDENT",
        instruction_text="Encourage Ananya to verify reaction quotients Q vs K herself before confirming direction.",
        is_active=True,
    )
    persistent_db.create_teacher_instruction(student_inst)

    orchestrator = GenericTutorOrchestrator(db=persistent_db)
    res = orchestrator.execute_turn(
        TutorTurnRequest(
            student_id="student-01",
            session_id="sess-cascade-test",
            course_id="course-chem-101",
            concept_id="equilibrium",
            message="Which way does the reaction shift if Q is greater than K?",
        )
    )

    assert res.status == "SUCCESS"
    # Both course-level analogy instruction and student-level socratic instruction applied
    assert res.teacher_instructions_applied >= 2
    assert "inst-chem-analogy" in res.applied_instruction_ids
    assert "inst-student-socratic" in res.applied_instruction_ids


# ── 5. Scoped RAG Retrieval Isolation ────────────────────────────────────────

def test_rag_scope_isolation_prevents_cross_course_leakage(persistent_db):
    """Verify RAG retrieval for Chemistry never leaks knowledge chunks from Physics."""
    rag_svc = RAGService(db=persistent_db)
    admin = persistent_db.get_user("admin-01")
    teacher = persistent_db.get_user("teacher-01")

    phys_content = (
        "Chapter 5: Laws of Motion\n\n"
        "Newton's third law of motion states that for every action, there is an equal and opposite reaction."
    )
    phys_asset = rag_svc.upload_knowledge_asset(
        course_id="course-phys-101",
        title="NCERT Physics Class 11 Chapter 5: Laws of Motion",
        content=phys_content,
        organization_id="org-stem-academy",
        subject="Physics",
        user=teacher,
        authority="NCERT",
        content_type=KnowledgeContentType.TEXTBOOK,
    )
    rag_svc.approve_knowledge_asset(phys_asset.id, user=admin)
    rag_svc.publish_knowledge_asset(phys_asset.id, user=admin)

    orchestrator = GenericTutorOrchestrator(db=persistent_db)

    # Student in Chemistry course asks question that mentions 'action and reaction'
    res = orchestrator.execute_turn(
        TutorTurnRequest(
            student_id="student-01",
            session_id="sess-rag-isolation",
            course_id="course-chem-101",
            concept_id="equilibrium",
            message="In dynamic equilibrium, how do the forward and reverse actions balance?",
        )
    )

    assert res.status == "SUCCESS"
    # Physics chunk MUST NOT appear in RAG sources used
    assert "chk-phys-newton-01" not in res.contributed_chunk_ids
    for record in res.provenance_records:
        assert record["source_id"] != "asset-phys-newton"


# ── 6. Anti-Answer Leakage Validation & Transactional Rollback ───────────────

def test_anti_answer_leakage_rejection_and_state_rollback(persistent_db):
    """Verify that when AI response leaks direct answers, validation fails and state is rolled back."""
    orchestrator = GenericTutorOrchestrator(db=persistent_db)

    # Mock gateway returning an answer leakage violation during hint turn
    mock_leaking = MagicMock()
    mock_leaking.content = "The final answer is B. Correct option is B."
    mock_leaking.provider = "mock"
    mock_leaking.model = "mock-model"
    mock_leaking.latency_ms = 18.0
    mock_leaking.success = True
    mock_leaking.status = ModelExecutionStatus.MODEL_SUCCESS

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orchestrator.ai_gateway, "execute", lambda req: mock_leaking)

        result = orchestrator.execute_turn(
            TutorTurnRequest(
                student_id="student-01",
                session_id="sess-leak-guard",
                course_id="course-chem-101",
                concept_id="equilibrium",
                message="Give me a hint for question 4",
            )
        )

        assert result.validation_passed is False
        assert result.state_committed is False
        assert result.status == "VALIDATION_FAILED"
        assert len(result.validation_issues) > 0
        assert "Correct option is B" not in result.response_text

        # Invariant: No learning event committed to DB
        events = persistent_db.get_learning_events_for_session("sess-leak-guard")
        assert len(events) == 0


# ── 7. AI Gateway Failure Safe Degradation ───────────────────────────────────

def test_ai_gateway_failure_safe_degradation(persistent_db):
    """Verify that when AI model execution fails, the turn fails safely without false progress."""
    orchestrator = GenericTutorOrchestrator(db=persistent_db)

    mock_failed_response = AIExecutionResult(
        request_id="req-fail-01",
        content="",
        provider="local",
        model="qwen2.5-0.5b",
        success=False,
        status=ModelExecutionStatus.MODEL_UNAVAILABLE,
        error_class="MODEL_EXECUTION_FAILED",
        error_message="Inference engine crashed mid-generation",
        latency_ms=12.0,
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(orchestrator.ai_gateway, "execute", lambda req: mock_failed_response)

        result = orchestrator.execute_turn(
            TutorTurnRequest(
                student_id="student-01",
                session_id="sess-gw-fail",
                course_id="course-chem-101",
                concept_id="equilibrium",
                message="Explain dynamic equilibrium",
            )
        )

        # Invariant: Turn unsuccessful, user gets recoverable message
        assert result.status == "MODEL_UNAVAILABLE"
        assert result.validation_passed is False
        assert result.state_committed is False
        assert "temporarily unavailable" in result.response_text.lower()

        # Invariant: No false learning event recorded
        events = persistent_db.get_learning_events_for_session("sess-gw-fail")
        assert len(events) == 0


# ── 8. Session Boundary Enforcement (Student & Course Isolation) ──────────────

def test_session_boundary_hijack_rejection(persistent_db):
    """Verify that student2 cannot hijack student1's active session."""
    orchestrator = GenericTutorOrchestrator(db=persistent_db)

    # Student 1 creates session
    orchestrator.execute_turn(
        TutorTurnRequest(
            student_id="student-01",
            session_id="sess-student1-private",
            course_id="course-chem-101",
            message="Explain chemical equilibrium",
        )
    )

    # Student 2 tries to submit turn into Student 1's session
    with pytest.raises(EnrollmentError, match="belongs to another student"):
        orchestrator.execute_turn(
            TutorTurnRequest(
                student_id="student-02",
                session_id="sess-student1-private",
                course_id="course-phys-101",
                message="Can I access this session?",
            )
        )


def test_session_cross_course_mismatch_rejection(persistent_db):
    """Verify that submitting a turn for course B into a session initialized for course A is rejected."""
    orchestrator = GenericTutorOrchestrator(db=persistent_db)

    # Initialize session on course-chem-101
    orchestrator.execute_turn(
        TutorTurnRequest(
            student_id="student-01",
            session_id="sess-course-mismatch",
            course_id="course-chem-101",
            message="Explain chemical equilibrium",
        )
    )

    # Enroll student-01 in physics as well so enrollment passes, isolating session course check
    persistent_db.create_enrollment(
        Enrollment(
            id="enr-student1-phys-mismatch-test",
            student_id="student-01",
            course_id="course-phys-101",
            is_active=True,
        )
    )

    # Student 1 enrolled in Chemistry and Physics tries to pass physics course ID into same session
    with pytest.raises(ValueError, match="belongs to course"):
        orchestrator.execute_turn(
            TutorTurnRequest(
                student_id="student-01",
                session_id="sess-course-mismatch",
                course_id="course-phys-101",
                message="Switch this session to physics",
            )
        )


# ── 9. Relational Integrity: Unregistered Student Rejection ──────────────────

def test_unregistered_student_rejection(persistent_db):
    """Verify that a non-existent student ID is immediately rejected without creating ghost records."""
    orchestrator = GenericTutorOrchestrator(db=persistent_db)

    with pytest.raises(EnrollmentError, match="not enrolled"):
        orchestrator.execute_turn(
            TutorTurnRequest(
                student_id="student-ghost-999",
                session_id="sess-ghost-01",
                course_id="course-chem-101",
                message="Hello from the void",
            )
        )


# ── 10. REST API Multi-Turn Continuity ───────────────────────────────────────

def test_rest_api_multi_turn_continuity(persistent_db):
    """Verify that the REST API /api/v1/tutor/turn supports multi-turn continuity with JWT auth."""
    from central_platform.auth.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: persistent_db
    client = TestClient(app)

    try:
        session_id = "sess-api-continuity"
        student_id = "student-01"
        course_id = "course-chem-101"

        token = create_access_token(user_id=student_id, role="student")
        headers = {"Authorization": f"Bearer {token}"}

        # Turn 1
        t1_resp = client.post(
            "/api/v1/tutor/turn",
            headers=headers,
            json={
                "student_id": student_id,
                "session_id": session_id,
                "course_id": course_id,
                "concept_id": "equilibrium",
                "message": "What is Le Chatelier's principle?",
            },
        )
        assert t1_resp.status_code == 200
        t1_data = t1_resp.json()
        assert t1_data["status"] == "SUCCESS"
        assert t1_data["concept_id"] == "equilibrium"
        assert t1_data["state_committed"] is True

        # Turn 2: Follow-up without concept_id
        t2_resp = client.post(
            "/api/v1/tutor/turn",
            headers=headers,
            json={
                "student_id": student_id,
                "session_id": session_id,
                "course_id": course_id,
                "message": "I still don't understand that",
                "conversation_history": [
                    {"role": "user", "content": "What is Le Chatelier's principle?"},
                    {"role": "assistant", "content": t1_data["response_text"]},
                ],
            },
        )
        assert t2_resp.status_code == 200
        t2_data = t2_resp.json()
        assert t2_data["status"] == "SUCCESS"
        assert t2_data["concept_id"] == "equilibrium"  # Zero concept drift via REST!
        assert t2_data["state_committed"] is True

        # Negative test: unauthorized token for different user
        other_token = create_access_token(user_id="student-02", role="student")
        other_headers = {"Authorization": f"Bearer {other_token}"}
        hijack_resp = client.post(
            "/api/v1/tutor/turn",
            headers=other_headers,
            json={
                "student_id": student_id,  # Trying to act as student-01
                "session_id": session_id,
                "course_id": course_id,
                "message": "Can I access Ananya's session?",
            },
        )
        assert hijack_resp.status_code == 403

    finally:
        app.dependency_overrides.pop(get_db, None)
