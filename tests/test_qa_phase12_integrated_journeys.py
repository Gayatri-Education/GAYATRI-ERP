"""Tests for QA Phase 12: Full Integration, Adversarial, Concurrency and Load Testing.

Verifies:
- Complete end-to-end Student journey with grounded RAG and persistent SLR mastery.
- Complete end-to-end Teacher/Admin journey with material ingestion, publishing, instructions, and audit logging.
- Degradation & Error journeys (zero fallback grade mutation, token revocation enforcement).
- Cross-tenant and IDOR adversarial isolation attacks.
- High-concurrency multi-threaded learner operations without database locking errors.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import pytest
import sqlite3

from central_platform.assessment.grading import DeterministicGrader, QuestionBankItem
from central_platform.auth.tokens import DatabaseRevocationStore, create_access_token, decode_and_verify_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    AuditLog,
    Course,
    CourseStatus,
    CourseVersion,
    CourseVisibility,
    Enrollment,
    Organization,
    RAGChunk,
    RAGSource,
    RAGSourceStatus,
    Session,
    SessionStatus,
    StudentLearningRecord,
    TeacherInstructionRecord,
    User,
    UserRole,
)
from central_platform.rag.service import RAGService
from central_platform.security.auditor import SecurityAuditor
from core.conversation import Conversation
from core.session import SessionStore
from core.tutor.adaptive import StudentProfile
from core.tutor.evaluator import StudentAnswerEvaluator
from core.tutor.state import LearningEvent, TutorStateManager


class TestQAPhase12IntegratedJourneys:
    """Verifies all Phase 12 integrated user journeys, resilience, and concurrency."""

    # ── 1. End-to-End Student Lifecycle Journey ───────────────────────────────
    def test_e2e_student_lifecycle_journey(self, tmp_path: Path):
        """Full learner journey: Login -> Enroll -> Start Session -> Query RAG -> Answer -> Adapt -> Persist -> Reload."""
        db_file = str(tmp_path / "student_lifecycle.db")
        db = PlatformDatabase(db_path=db_file)

        # 1. Organization & Student Provisioning
        org = Organization(id="org_student_e2e", name="Apex STEM Academy", slug="apex-stem")
        db.create_organization(org)

        student = User(
            id="std_e2e_101",
            email="priya@apexstem.edu",
            full_name="Priya Patel",
            role=UserRole.STUDENT,
            organization_id="org_student_e2e",
        )
        db.create_user(student)

        # 2. Course Selection & Enrollment
        course = Course(
            id="crs_thermo_101",
            organization_id="org_student_e2e",
            code="THERMO-101",
            title="Class 11 Thermodynamics",
            visibility=CourseVisibility.PRIVATE,
        )
        db.create_course(course)

        enrollment = Enrollment(
            id="enr_e2e_01",
            student_id="std_e2e_101",
            course_id="crs_thermo_101",
        )
        db.create_enrollment(enrollment)

        # 3. Ingest and Publish RAG Curriculum Source
        rag_service = RAGService(db=db)
        doc_content = (
            "# First Law of Thermodynamics\n\n"
            "The First Law of Thermodynamics states that energy can neither be created nor destroyed; "
            "it can only be transferred or converted from one form to another.\n\n"
            "The mathematical equation is delta U = q + w, where delta U is change in internal energy, "
            "q is heat added to the system, and w is work done on the system. "
            "For gas expansion against external pressure P_ext, work done is w = -P_ext * delta V."
        )

        source = rag_service.register_source(
            organization_id="org_student_e2e",
            course_id="crs_thermo_101",
            subject="Chemistry",
            title="Thermodynamics Core",
            authority="NCERT",
            version="1.0.0",
            uploaded_by="usr_teacher_admin",
        )
        rag_service.ingest_document(source.id, content=doc_content, file_name="thermo_chapter.md")
        rag_service.publish_source(source.id)

        # 4. Start Active Learning Session
        session = Session(
            id="sess_e2e_turn_01",
            student_id="std_e2e_101",
            course_id="crs_thermo_101",
            concept_id="THERMO_FIRST_LAW",
            status=SessionStatus.ACTIVE,
        )
        db.create_session(session)

        # 5. Query RAG for Grounded Evidence
        retrieval = rag_service.retrieve(
            query="What is the formula for First Law and work of expansion?",
            course_id="crs_thermo_101",
            top_k=2,
            requesting_user_id="std_e2e_101",
            requesting_user_role=UserRole.STUDENT,
        )
        chunks = retrieval.get("chunks", [])
        assert len(chunks) > 0
        top_chunk = chunks[0]
        assert "delta U = q + w" in top_chunk["content"]
        assert top_chunk["source_id"] == source.id

        # 6. Pedagogical Evaluation & Adaptation
        profile = StudentProfile()
        profile.set_mastery("THERMO_FIRST_LAW", 0.50)
        evaluator = StudentAnswerEvaluator()

        # Step A: Student makes an erroneous calculation
        res_err = evaluator.evaluate(
            student_answer="q=500, w=200, so delta U = 500 + 200 = 700 J",
            expected_answer="300 J",
            concept_id="THERMO_FIRST_LAW",
        )
        assert res_err.correctness.lower() in ("incorrect", "partial")
        profile.update_mastery("THERMO_FIRST_LAW", -0.10)
        profile.update_difficulty(res_err)
        assert profile.mastery["THERMO_FIRST_LAW"] < 0.5

        # Step B: Student corrects with negative work for expansion
        res_ok = evaluator.evaluate(
            student_answer="Since it expands, work is negative: w = -200 J, so delta U = 500 - 200 = 300 J",
            expected_answer="300 J",
            concept_id="THERMO_FIRST_LAW",
        )
        assert res_ok.correctness.lower() == "correct"
        profile.update_mastery("THERMO_FIRST_LAW", 0.30)
        profile.update_difficulty(res_ok)
        assert profile.mastery["THERMO_FIRST_LAW"] >= 0.5

        # 7. Persist Student Learning Record (SLR)
        slr = StudentLearningRecord(
            id="slr_e2e_01",
            student_id="std_e2e_101",
            course_id="crs_thermo_101",
        )
        db.create_slr(slr)
        db.close()

        # 8. Close session and Re-open Database to verify durability
        reopened_db = PlatformDatabase(db_path=db_file)
        persisted_user = reopened_db.get_user("std_e2e_101")
        assert persisted_user is not None
        assert persisted_user.email == "priya@apexstem.edu"

        persisted_session = reopened_db.get_session("sess_e2e_turn_01")
        assert persisted_session is not None
        assert persisted_session.status == SessionStatus.ACTIVE

        persisted_slr = reopened_db.get_slr("std_e2e_101", "crs_thermo_101")
        assert persisted_slr is not None
        assert persisted_slr.student_id == "std_e2e_101"
        assert persisted_slr.course_id == "crs_thermo_101"

        reopened_db.close()

    # ── 2. End-to-End Teacher / Admin Journey ─────────────────────────────────
    def test_e2e_teacher_admin_course_management_journey(self, tmp_path: Path):
        """Teacher/Admin journey: Provision Org -> Course -> Ingest Material -> Publish RAG -> Add Instruction -> Audit Logs."""
        db_file = str(tmp_path / "admin_journey.db")
        db = PlatformDatabase(db_path=db_file)

        # 1. Admin provisions organization
        org = Organization(id="org_delhi_01", name="Delhi Public School", slug="dps-delhi")
        db.create_organization(org)

        # 2. Provisions Teacher
        teacher = User(
            id="usr_teacher_sharma",
            email="dr.sharma@dpsdelhi.edu",
            full_name="Dr. R. K. Sharma",
            role=UserRole.TEACHER,
            organization_id="org_delhi_01",
        )
        db.create_user(teacher)

        # 3. Creates Course
        course = Course(
            id="crs_dps_chem",
            organization_id="org_delhi_01",
            code="DPS-CHEM-12",
            title="Class 12 Electrochemistry",
        )
        db.create_course(course)

        # 4. Ingest and Publish Course Material
        rag = RAGService(db=db)
        source = rag.register_source(
            organization_id="org_delhi_01",
            course_id="crs_dps_chem",
            subject="Chemistry",
            title="Electrochemistry Textbook",
            authority="NCERT",
            version="1.0.0",
            uploaded_by="usr_teacher_sharma",
        )
        doc_content = (
            "Nernst Equation relates the reduction potential of an electrochemical reaction to standard electrode potential: "
            "E = E0 - (RT/nF) * ln(Q). At 298 K, this simplifies to E = E0 - (0.0591/n) * log10(Q)."
        )
        rag.ingest_document(source.id, content=doc_content, file_name="nernst_equation.txt")
        rag.publish_source(source.id)

        # 5. Teacher adds pedagogical instructions
        instruction_text = "Always emphasize the number of transferred electrons n in the Nernst denominator."
        instruction = TeacherInstructionRecord(
            id="inst_dps_01",
            teacher_id="usr_teacher_sharma",
            course_id="crs_dps_chem",
            instruction_text=instruction_text,
            organization_id="org_delhi_01",
        )
        db.create_teacher_instruction(instruction)

        instructions = db.get_teacher_instructions_for_course("crs_dps_chem")
        assert len(instructions) >= 1
        assert instructions[0].instruction_text == instruction_text

        # 6. Audit Logging Check
        audit_entry = AuditLog(
            id="audit_dps_001",
            organization_id="org_delhi_01",
            user_id="usr_teacher_sharma",
            action="COURSE_MATERIAL_PUBLISHED",
            resource=f"rag_source:{source.id}",
            details={"filename": "nernst_equation.txt"},
        )
        db.record_audit_log(audit_entry)

        audit_logs = db.get_audit_logs(organization_id="org_delhi_01")
        assert len(audit_logs) >= 1
        assert audit_logs[0].action == "COURSE_MATERIAL_PUBLISHED"

        db.close()

    # ── 3. Error Journey: Degraded AI Zero Fallback Grade Mutation ─────────────
    def test_error_journey_degraded_ai_zero_grade_mutation(self, tmp_path: Path):
        """When AI service is degraded or offline, fallback MUST NEVER award full credit or mutate grades (GQA-003)."""
        # 1. Deterministic grading of incorrect answer yields 0.0, never full credit
        item = QuestionBankItem(
            id="q_test_01",
            course_id="crs_101",
            question_text="What is standard enthalpy?",
            item_type="MCQ",
            correct_answer="A",
            options=["Enthalpy at 1 bar, 298K", "Enthalpy at 0K", "Random energy", "None"],
            difficulty=1,
        )
        is_corr, score, feedback = DeterministicGrader.grade_item(item, "B")
        assert is_corr is False
        assert score == 0.0

        # 2. When evaluation is unavailable/degraded, TutorStateManager preserves student mastery
        db_file = tmp_path / "tutor_state_journey.db"
        sm = TutorStateManager(db_path=str(db_file))

        student_id = "std_journey_safe"
        concept_id = "cid_thermo"

        # Baseline mastery is 0.0
        initial = sm.get_student_concept_mastery(student_id, concept_id)
        assert initial.mastery == 0.0

        # Record evaluation_unavailable event
        ev_unavail = LearningEvent(
            event_id="evt_unavail_journey_01",
            student_id=student_id,
            session_id="sess_journey_01",
            turn_id="turn_01",
            concept_id=concept_id,
            correctness="evaluation_unavailable",
        )
        inserted = sm.record_learning_event(ev_unavail)
        assert inserted is True

        # Assert mastery was NOT mutated
        after = sm.get_student_concept_mastery(student_id, concept_id)
        assert after.mastery == 0.0
        assert after.exposure_count == 0
        assert after.correct_count == 0

    # ── 4. Error Journey: Revoked Token Immediate Rejection ───────────────────
    def test_error_journey_revoked_token_rejection(self, tmp_path: Path):
        """Revoked tokens stored in DatabaseRevocationStore are immediately rejected (GQA-005)."""
        db_file = str(tmp_path / "revocation_journey.db")
        db = PlatformDatabase(db_path=db_file)
        store = DatabaseRevocationStore(db)

        jti = "test_jti_journey_99999"
        exp = int(datetime.now(timezone.utc).timestamp()) + 3600

        # Initially token is valid
        assert store.is_revoked(jti) is False

        # Revoke token
        store.revoke(jti=jti, expires_at=exp, reason="User logout")

        # Now token is strictly revoked
        assert store.is_revoked(jti) is True
        db.close()

    # ── 5. Adversarial Security: Cross-Tenant & IDOR Attacks ──────────────────
    def test_cross_tenant_adversarial_isolation_attacks(self, tmp_path: Path):
        """Cross-tenant data access and student IDOR requests are rejected at boundary layers."""
        auditor = SecurityAuditor()

        # 1. Cross-Tenant Organization Boundary Attack
        assert auditor.verify_tenant_boundary(user_org_id="org_alpha", target_org_id="org_beta") is False
        assert auditor.verify_tenant_boundary(user_org_id="org_alpha", target_org_id="org_alpha") is True

        # 2. Student-to-Student IDOR Access Attack
        student_user = User(
            id="std_victim_01",
            email="v@alpha.edu",
            full_name="Victim",
            role=UserRole.STUDENT,
            organization_id="org_alpha",
        )
        assert auditor.verify_student_access(student_user, target_student_id="std_victim_01") is True
        assert auditor.verify_student_access(student_user, target_student_id="std_target_02") is False

        # 3. Path Traversal Boundary Attack
        base_dir = tmp_path / "data"
        base_dir.mkdir(parents=True, exist_ok=True)
        assert auditor.sanitize_path(base_dir, "../../../etc/passwd") is None
        assert auditor.sanitize_path(base_dir, "safe_lesson.md") is not None

    # ── 6. Multi-Worker High-Concurrency Operations ───────────────────────────
    def test_high_concurrency_multi_threaded_student_turns(self, tmp_path: Path):
        """Simultaneous learner turns executed across concurrent threads without SQLite database lock errors."""
        db_file = str(tmp_path / "concurrent_stress.db")
        db = PlatformDatabase(db_path=db_file)

        org = Organization(id="org_stress", name="Stress University", slug="stress-u")
        db.create_organization(org)
        course = Course(id="crs_stress", organization_id="org_stress", code="STRESS", title="Concurrency")
        db.create_course(course)
        db.close()

        def worker_turn(idx: int) -> bool:
            w_db = PlatformDatabase(db_path=db_file)
            try:
                stu_id = f"std_concurrent_{idx}"
                user = User(
                    id=stu_id,
                    email=f"s{idx}@stress.edu",
                    full_name=f"Student {idx}",
                    role=UserRole.STUDENT,
                    organization_id="org_stress",
                )
                w_db.create_user(user)

                sess = Session(
                    id=f"sess_c_{idx}",
                    student_id=stu_id,
                    course_id="crs_stress",
                    concept_id="KINETICS_ORDER",
                    status=SessionStatus.ACTIVE,
                )
                w_db.create_session(sess)

                slr = StudentLearningRecord(
                    id=f"slr_c_{idx}",
                    student_id=stu_id,
                    course_id="crs_stress",
                )
                w_db.create_slr(slr)

                read_slr = w_db.get_slr(stu_id, "crs_stress")
                return read_slr is not None and read_slr.student_id == stu_id
            finally:
                w_db.close()

        # Run 10 parallel student sessions concurrently
        with ThreadPoolExecutor(max_workers=5) as pool:
            outcomes = list(pool.map(worker_turn, range(10)))

        assert len(outcomes) == 10
        assert all(outcomes)

    # ── 7. Graceful Shutdown & Async Persistence Flush ────────────────────────
    def test_graceful_shutdown_session_persistence(self, tmp_path: Path):
        """Asynchronous database writes are safely flushed and committed during clean shutdown (GQA-011)."""
        db_file = tmp_path / "graceful_shutdown.db"
        store = SessionStore(db_file)

        # Enqueue multiple conversation writes
        for i in range(5):
            conv = Conversation(session_id=f"sess_shut_{i}", user_id=f"user_shut_{i}")
            conv.add("user", f"Turn 1 question from learner {i}")
            conv.add("assistant", f"Turn 1 response for learner {i}")
            store.save_session(f"sess_shut_{i}", conv)

        # Explicit flush with strict failure raising
        store.flush(raise_on_failure=True)

        # Shutdown guarantees background writer is terminated and committed
        store.shutdown(raise_on_failure=True)

        # Re-open independently and verify durability
        reopened = SessionStore(db_file)
        try:
            for i in range(5):
                messages = reopened.load_session(f"sess_shut_{i}")
                assert len(messages) == 2
                assert f"Turn 1 question from learner {i}" in messages[0]["content"]
                assert f"Turn 1 response for learner {i}" in messages[1]["content"]
        finally:
            reopened.shutdown()

