"""Gayatri AI Platform — Generic Tutor Orchestrator (Phase 10).

Central course-independent tutoring flow enforcing the complete 16-step turn lifecycle:
1. Identity validation (rejects magic identity fallbacks per Rule 4)
2. Enrollment validation
3. Course & Version resolution
4. Class / Cohort resolution
5. Learning state resolution (partitioned by (student_id, course_id))
6. Hierarchical instruction resolution (SESSION > STUDENT > CLASS > COURSE > ORGANIZATION)
7. Course policy enforcement
8. Course tool policy check
9. Scoped RAG retrieval (version & org pinned)
10. 7-layer context assembly
11. Pedagogy response planning
12. AI Gateway execution (provider-neutral routing)
13. 7-invariant response validation
14. Learning evidence staging
15. Two-phase transactional state commit (rollback on validation failure)
16. Telemetry and audit logging
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from central_platform.ai.context_builder import ContextBuilder
from central_platform.ai.gateway import AIGatewayService
from central_platform.ai.query_understanding import QueryUnderstandingEngine
from central_platform.ai.response_planner import PedagogicalResponsePlan, ResponsePlannerEngine
from central_platform.ai.response_validator import ResponseValidatorEngine, ValidationResult
from central_platform.ai.schema import AIExecutionRequest, TaskType
from central_platform.courses.service import CourseNotFoundError, CourseService
from central_platform.db import PlatformDatabase
from central_platform.learning.actions import NextActionDecision, NextActionEngine, NextActionType
from central_platform.learning.commit_pipeline import CommitResult, StateCommitPipeline
from central_platform.learning.state import LearningStateManager
from central_platform.models.schema import (
    Course,
    CourseLearningContext,
    CoursePolicy,
    CourseToolPolicy,
    CourseVisibility,
    Enrollment,
    LearningEvent,
    MasteryState,
    Session,
    SessionStatus,
    User,
    UserRole,
)
from central_platform.rag.service import RAGService
from central_platform.recovery.manager import FailureRecoveryManager
from central_platform.teacher.instruction import TeacherInstructionEngine
from central_platform.tools.registry import ToolRegistry

logger = logging.getLogger("gayatri.tutor.orchestrator")


class EnrollmentError(PermissionError):
    """Raised when a student is not enrolled or authorized in the requested course."""
    pass


class TutorOrchestratorError(Exception):
    """Raised when orchestrator encounters an unrecoverable turn failure."""
    pass


@dataclass
class TutorTurnRequest:
    """Input contract for a single generic tutoring turn."""
    student_id: str
    session_id: str
    course_id: str
    message: str
    course_version_id: Optional[str] = None
    class_id: Optional[str] = None
    cohort_id: Optional[str] = None
    concept_id: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TutorTurnResult:
    """Output contract for a completed generic tutoring turn."""
    turn_id: str
    session_id: str
    student_id: str
    course_id: str
    concept_id: str
    response_text: str
    pedagogical_action: str
    validation_passed: bool
    state_committed: bool
    rag_sources_used: List[str] = field(default_factory=list)
    tools_invoked: List[str] = field(default_factory=list)
    teacher_instructions_applied: int = 0
    latency_ms: float = 0.0
    provider_used: str = "local"
    model_used: str = "default"
    status: str = "SUCCESS"  # SUCCESS, VALIDATION_FAILED, OFFLINE_FALLBACK, ERROR
    validation_issues: List[Dict[str, Any]] = field(default_factory=list)
    applied_instruction_ids: List[str] = field(default_factory=list)
    contributed_source_ids: List[str] = field(default_factory=list)
    contributed_chunk_ids: List[str] = field(default_factory=list)
    provenance_records: List[Dict[str, Any]] = field(default_factory=list)
    model_provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



class GenericTutorOrchestrator:
    """Course-Independent Tutor Orchestrator managing end-to-end pedagogical turns."""

    def __init__(
        self,
        db: Optional[PlatformDatabase] = None,
        ai_gateway: Optional[AIGatewayService] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.db = db or PlatformDatabase()
        self.ai_gateway = ai_gateway or AIGatewayService(self.db)
        self.course_service = CourseService(self.db)
        self.learning_state = LearningStateManager(self.db)
        self.commit_pipeline = StateCommitPipeline(self.db)
        self.teacher_engine = TeacherInstructionEngine(self.db)
        self.rag_service = RAGService(self.db)
        self.context_builder = ContextBuilder(self.db)
        self.query_engine = QueryUnderstandingEngine()
        self.planner_engine = ResponsePlannerEngine()
        self.validator_engine = ResponseValidatorEngine()
        self.tool_registry = tool_registry or ToolRegistry()
        self._processed_turns: set[str] = set()

    def execute_turn(self, req: TutorTurnRequest) -> TutorTurnResult:
        """Execute a complete course-scoped tutoring turn through the 16-step lifecycle."""
        t0 = time.perf_counter()
        turn_id = f"turn-{uuid.uuid4().hex[:12]}"

        # ── 1. Identity Validation (Rule 4: Never add magic identity) ──────
        if not req.student_id or not str(req.student_id).strip():
            raise ValueError("Identity validation failed: student_id must be an explicit non-empty string.")
        if not req.session_id or not str(req.session_id).strip():
            raise ValueError("Identity validation failed: session_id must be an explicit non-empty string.")
        if not req.course_id or not str(req.course_id).strip():
            raise ValueError("Identity validation failed: course_id must be an explicit non-empty string.")
        if not req.message or not str(req.message).strip():
            raise ValueError("Query validation failed: message must be a non-empty string.")

        clean_message = str(req.message).strip()

        # Deduplication check (Audit invariant)
        turn_fingerprint = f"{req.student_id}:{req.session_id}:{clean_message}"
        if turn_fingerprint in self._processed_turns:
            logger.info(f"Duplicate turn detected for {turn_fingerprint}; returning idempotent replay.")
            # Return idempotent turn result
            return TutorTurnResult(
                turn_id=turn_id,
                session_id=req.session_id,
                student_id=req.student_id,
                course_id=req.course_id,
                concept_id=req.concept_id or "foundations",
                response_text="I noticed your message was sent again. Let's continue from our previous point.",
                pedagogical_action="CONTINUE",
                validation_passed=True,
                state_committed=False,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                status="SUCCESS",
            )

        # ── 2. Enrollment Validation ───────────────────────────────────────
        enrollments = self.db.get_enrollments_for_student(req.student_id)
        enrolled_course_ids = {e.course_id for e in enrollments if e.is_active}

        # ── 3. Course & Version Resolution ─────────────────────────────────
        course = self.db.get_course(req.course_id)
        if not course:
            raise CourseNotFoundError(f"Course '{req.course_id}' does not exist.")

        # Enforce Enrollment Authorization (Phase 2 / F-003: No auto-enrollment in tutor orchestrator)
        if req.course_id not in enrolled_course_ids:
            course_type = "private course" if course.visibility == CourseVisibility.PRIVATE else "course"
            logger.warning("Student '%s' is not enrolled in %s '%s'.", req.student_id, course_type, req.course_id)
            raise EnrollmentError(
                f"Student '{req.student_id}' is not enrolled in {course_type} '{req.course_id}'."
            )

        # Resolve pinned or published version
        version_id = req.course_version_id
        if version_id:
            ver = self.db.get_course_version(version_id)
            if ver:
                if ver.course_id != req.course_id:
                    raise CourseNotFoundError(f"Version '{version_id}' does not belong to course '{req.course_id}'.")
                status_str = ver.status.value if hasattr(ver.status, "value") else str(ver.status)
                if status_str.upper() in ("DRAFT", "ARCHIVED"):
                    raise CourseNotFoundError(f"Course version '{version_id}' is unpublished (status={status_str}).")
            elif not version_id.startswith("v"):
                raise CourseNotFoundError(f"Course version '{version_id}' not found.")
        else:
            latest_pub = self.db.get_latest_published_course_version(req.course_id)
            if latest_pub:
                version_id = latest_pub.id
            else:
                versions = self.db.get_course_versions_by_course(req.course_id)
                version_id = versions[-1].id if versions else "v1.0"

        # ── 4. Class / Cohort Resolution ───────────────────────────────────
        class_id = req.class_id
        if not class_id:
            for e in enrollments:
                if e.course_id == req.course_id and e.cohort_id:
                    class_id = e.cohort_id
                    break

        # ── 5. Learning State Resolution (Partitioned by course) ───────────
        canonical_state = self.learning_state.get_canonical_state(req.student_id, req.course_id)

        # Enforce user existence for relational integrity (Phase 2 / F-003: No auto-creation)
        if not self.db.get_user(req.student_id):
            raise EnrollmentError(
                f"Student '{req.student_id}' does not exist in platform directory."
            )

        existing_session = self.db.get_session(req.session_id)
        if existing_session:
            if existing_session.student_id != req.student_id:
                raise EnrollmentError(f"Session '{req.session_id}' belongs to another student.")
            if existing_session.course_id != req.course_id:
                raise ValueError(f"Session '{req.session_id}' belongs to course '{existing_session.course_id}', not '{req.course_id}'.")

        target_concept = req.concept_id
        if not target_concept:
            if existing_session and existing_session.concept_id:
                target_concept = existing_session.concept_id
            elif canonical_state.slr and getattr(canonical_state.slr, "active_concept_id", None):
                target_concept = canonical_state.slr.active_concept_id
            else:
                target_concept = f"{req.course_id}_foundations"

        if not existing_session:
            self.db.create_session(
                Session(
                    id=req.session_id,
                    student_id=req.student_id,
                    course_id=req.course_id,
                    concept_id=target_concept,
                    status=SessionStatus.ACTIVE,
                    course_version_id=version_id,
                    class_id=class_id,
                )
            )
        elif req.concept_id and req.concept_id != existing_session.concept_id:
            existing_session.concept_id = target_concept
            self.db.create_session(existing_session)

        mastery_info = canonical_state.mastery.get(target_concept)
        current_mastery = mastery_info.score if mastery_info else 0.50

        # ── 6. Hierarchical Instruction Resolution ────────────────────────
        instructions = self.teacher_engine.resolve_hierarchical_instructions(
            organization_id=course.organization_id,
            course_id=req.course_id,
            class_id=class_id,
            student_id=req.student_id,
            session_id=req.session_id,
            concept_id=target_concept,
            course_version_id=version_id,
        )
        teacher_directives = self.teacher_engine.format_prompt_directive(instructions)
        applied_instruction_ids = [inst.instruction_id for inst in instructions]

        # ── 7. Course Policy Enforcement ──────────────────────────────────
        course_version = self.db.get_course_version(version_id) if version_id else None
        course_policy = (course_version.tutor_policy if course_version else None) or CoursePolicy()

        # ── 8. Course Tool Policy Check ────────────────────────────────────
        tool_policy = (course_version.tool_policy if course_version else None) or CourseToolPolicy()
        allowed_tools = [
            t for t in ["calculator", "graphing", "code_execution", "equation_balancer", "periodic_table"]
            if getattr(tool_policy, t, False)
        ] + [k for k, v in tool_policy.custom_tools.items() if v]

        # ── 9. Scoped RAG Retrieval ────────────────────────────────────────
        rag_sources_used: List[str] = []
        contributed_source_ids: List[str] = []
        contributed_chunk_ids: List[str] = []
        provenance_records: List[Dict[str, Any]] = []
        rag_payload = ""
        raw_rag_results: List[Dict[str, Any]] = []

        try:
            rag_query_res = self.rag_service.query(
                query_text=clean_message,
                course_id=req.course_id,
                student_id=req.student_id,
                class_id=class_id,
                course_version_id=version_id,
                concept=target_concept,
                top_k=3,
            )
            raw_rag_results = rag_query_res.get("results", [])
            rag_payload = rag_query_res.get("data_context", "")

            for r in raw_rag_results:
                cid = r.get("chunk_id")
                sid = r.get("source_id")
                if cid:
                    contributed_chunk_ids.append(cid)
                    rag_sources_used.append(cid)
                if sid and sid not in contributed_source_ids:
                    contributed_source_ids.append(sid)

                provenance_records.append({
                    "source_id": sid or "src-unknown",
                    "chunk_id": cid or "chk-unknown",
                    "source_title": r.get("source_title", r.get("chapter", "Course Material")),
                    "authority": r.get("provenance_type", "NCERT"),
                    "provenance_type": r.get("provenance_type", "NCERT"),
                    "visibility_scope": r.get("visibility_scope", "course"),
                    "citation": r.get("citation", ""),
                    "class_id": r.get("class_id"),
                    "course_version_id": r.get("course_version_id"),
                    "score": r.get("score"),
                })
        except Exception as exc:
            rag_rec = FailureRecoveryManager.handle_rag_failure(
                error=exc,
                fallback_concept=target_concept,
                course_id=req.course_id,
            )
            logger.warning(f"Scoped RAG retrieval degraded for turn {turn_id}: {rag_rec.technical_diagnostic}")

        try:
            # ── 10. 7-Layer Context Assembly ──────────────────────────────────
            effective_history = list(req.conversation_history or [])
            if not effective_history and req.session_id:
                try:
                    past_events = self.db.get_learning_events_for_session(req.session_id)
                    for ev in past_events:
                        if ev.event_type == "TUTOR_TURN_COMPLETED" and isinstance(ev.payload, dict):
                            q = ev.payload.get("student_message") or ev.payload.get("query")
                            a = ev.payload.get("response_text") or ev.payload.get("response")
                            if q and a:
                                effective_history.append({"role": "user", "content": q})
                                effective_history.append({"role": "assistant", "content": a})
                except Exception as exc:
                    logger.warning(f"Could not load session conversation history: {exc}")

            assembled_context = self.context_builder.build_context(
                query=clean_message,
                student_id=req.student_id,
                course_id=req.course_id,
                concept_id=target_concept,
                class_id=class_id,
                session_id=req.session_id,
                course_version_id=version_id,
                organization_id=course.organization_id,
                conversation_history=effective_history,
                instructions=instructions,
                rag_results=raw_rag_results,
            )

            sys_prompt = ContextBuilder.build_system_prompt(
                subject=course.title,
                grade_level=getattr(course, "grade_level", None) or "Standard",
                formatted_directives=teacher_directives,
            )

            user_prompt = ContextBuilder.build_user_prompt(
                user_query=clean_message,
                rag_context=rag_payload,
                misconception_alerts=[m.code for m in canonical_state.misconceptions],
            )

            # ── 11. Pedagogy Response Planning ────────────────────────────────
            structured_interp = self.query_engine.fallback_interpret(clean_message)
            intent = structured_interp.intent
            msg_lower = clean_message.lower()

            if intent in ("summary", "revision") or any(w in msg_lower for w in ["summarize", "summary", "recap", "wrap up", "in short"]):
                ped_action = NextActionType.REVIEW
                rec_mode = "SUMMARY"
                reason = "Student requested summary / review of concept."
            elif intent in ("challenge",) or any(w in msg_lower for w in ["harder", "difficult", "challenging"]):
                ped_action = NextActionType.CHALLENGE
                rec_mode = "CHALLENGE"
                reason = "Student requested a harder challenge problem."
            elif intent in ("clarification", "remediation") or any(w in msg_lower for w in ["don't understand", "dont understand", "still don't", "confused", "unclear"]):
                ped_action = NextActionType.REMEDIATE if canonical_state.misconceptions else NextActionType.EXPLAIN
                rec_mode = "REMEDIATE" if canonical_state.misconceptions else "EXPLAIN"
                reason = "Student expressed confusion / requested clarification."
            elif intent in ("hint",) or any(w in msg_lower for w in ["hint", "give me a hint", "clue"]):
                ped_action = NextActionType.HINT
                rec_mode = "QUESTION"
                reason = "Student requested a progressive hint."
            elif intent in ("answer_check",) or any(w in msg_lower for w in ["equals", "equal to", "is it", "my answer"]):
                ped_action = NextActionType.CONTINUE
                rec_mode = "QUESTION"
                reason = "Student provided an answer to check."
            elif current_mastery < 0.6:
                ped_action = NextActionType.EXPLAIN
                rec_mode = "EXPLAIN"
                reason = f"Concept mastery is foundational ({current_mastery:.2f})."
            else:
                ped_action = NextActionType.PRACTICE
                rec_mode = "QUESTION"
                reason = f"Concept mastery is developing ({current_mastery:.2f})."

            action_decision = NextActionDecision(
                action=ped_action,
                target_concept_id=target_concept,
                target_concept_name=target_concept,
                recommended_mode=rec_mode,
                reason=reason,
            )
            response_plan = self.planner_engine.create_deterministic_plan(
                interpretation=structured_interp,
                action_decision=action_decision,
                assembled_context=assembled_context,
            )
            if course_policy and getattr(course_policy, "anti_answer_leakage", True):
                response_plan.anti_answer_leakage_guard = True

            # ── 12. AI Gateway Execution ──────────────────────────────────────
            ai_req = AIExecutionRequest(
                prompt=user_prompt,
                system_prompt=sys_prompt,
                task_type=TaskType.TUTORING,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                preferred_provider=req.preferred_provider,
                preferred_model=req.preferred_model,
            )
            ai_res = self.ai_gateway.execute(ai_req)

            # ── 12b. Gateway Failure Handling (F-013, F-014) ──────────────────
            if not ai_res.success:
                latency_total = round((time.perf_counter() - t0) * 1000.0, 2)
                ai_status_val = (
                    ai_res.status.value if hasattr(ai_res.status, "value") else str(ai_res.status or "MODEL_UNAVAILABLE")
                )
                logger.error(
                    "AI Gateway failed for student %s, course %s: provider=%s, status=%s, error=%s",
                    req.student_id,
                    req.course_id,
                    ai_res.provider,
                    ai_status_val,
                    ai_res.error_message,
                )
                return TutorTurnResult(
                    turn_id=turn_id,
                    session_id=req.session_id,
                    student_id=req.student_id,
                    course_id=req.course_id,
                    concept_id=target_concept,
                    response_text="The AI tutoring service is temporarily unavailable. Please try again shortly.",
                    pedagogical_action="SERVICE_UNAVAILABLE",
                    validation_passed=False,
                    state_committed=False,
                    rag_sources_used=rag_sources_used,
                    tools_invoked=allowed_tools,
                    teacher_instructions_applied=len(instructions),
                    latency_ms=latency_total,
                    provider_used=ai_res.provider,
                    model_used=ai_res.model,
                    status=ai_status_val,
                    validation_issues=[{
                        "code": ai_res.error_class or "MODEL_EXECUTION_FAILED",
                        "message": ai_res.error_message or "AI model execution failed",
                    }],
                    applied_instruction_ids=applied_instruction_ids,
                    contributed_source_ids=contributed_source_ids,
                    contributed_chunk_ids=contributed_chunk_ids,
                    provenance_records=provenance_records,
                    model_provenance={
                        "provider": ai_res.provider,
                        "model": ai_res.model,
                        "mock": getattr(ai_res, "mock", False),
                        "status": ai_status_val,
                        "success": False,
                    },
                )


            generated_text = ai_res.content

            # ── 13. 7-Invariant Response Validation ───────────────────────────
            val_result: ValidationResult = self.validator_engine.validate_response(
                generated_response=generated_text,
                response_plan=response_plan,
                target_concept=target_concept,
                rag_sources_required=bool(rag_sources_used),
            )

            # ── 14. Learning Evidence Staging ─────────────────────────────────
            # Per Master Plan Phase 06 (F-019):
            # A tutor response alone must NOT fabricate an increase in student mastery.
            # An explanatory or conversational turn records an interaction event (e.g. TUTOR_TURN_COMPLETED),
            # but does not arbitrarily advance student mastery score.
            # Mastery advances only when learner performance evidence (assessments, answers) is evaluated.
            mastery_updates: List[MasteryState] = []
            proposed_event = LearningEvent(
                id=f"evt-{uuid.uuid4().hex[:8]}",
                session_id=req.session_id,
                student_id=req.student_id,
                event_type="TUTOR_TURN_COMPLETED",
                concept_id=target_concept,
                course_id=req.course_id,
                course_version_id=version_id,
                payload={
                    "course_id": req.course_id,
                    "version_id": version_id,
                    "student_message": clean_message,
                    "query": clean_message,
                    "response_text": generated_text,
                    "response": generated_text,
                    "val_valid": val_result.is_valid,
                    "latency_ms": ai_res.latency_ms,
                    "pedagogical_action": action_decision.action.value,
                },
            )

            staged_changes = self.commit_pipeline.stage_changes(
                student_id=req.student_id,
                course_id=req.course_id,
                mastery_updates=mastery_updates,
                learning_events=[proposed_event],
            )

            # ── 15. Transactional State Commit ────────────────────────────────
            if val_result.is_valid:
                commit_result = self.commit_pipeline.validate_and_commit(
                    staged=staged_changes,
                    generated_response=generated_text,
                    target_concept=target_concept,
                    response_plan=response_plan,
                )
            else:
                commit_result = CommitResult(
                    committed=False,
                    reason="Validation failed. State changes rolled back.",
                    staged_summary={"mastery_updates": 0, "misconception_records": 0, "learning_events": 0},
                    validation_result=val_result,
                )

            # If validation failed, use safe sanitized or fallback response
            final_text = generated_text
            turn_status = "SUCCESS"
            if not val_result.is_valid:
                turn_status = "VALIDATION_FAILED"
                final_text = (
                    val_result.fallback_response
                    or "Let's approach this step-by-step. What foundational concept or principle explains this behavior?"
                )
                logger.warning(f"Turn response failed validation: {[i.to_dict() for i in val_result.issues]}. State rolled back.")

            # ── 16. Audit & Telemetry ─────────────────────────────────────────
            latency_total = round((time.perf_counter() - t0) * 1000.0, 2)
            self._processed_turns.add(turn_fingerprint)

            ai_status_val = (
                ai_res.status.value if hasattr(ai_res.status, "value") else str(ai_res.status or "MODEL_SUCCESS")
            )
            return TutorTurnResult(
                turn_id=turn_id,
                session_id=req.session_id,
                student_id=req.student_id,
                course_id=req.course_id,
                concept_id=target_concept,
                response_text=final_text,
                pedagogical_action=response_plan.pedagogical_action,
                validation_passed=val_result.is_valid,
                state_committed=commit_result.committed,
                rag_sources_used=rag_sources_used,
                tools_invoked=allowed_tools,
                teacher_instructions_applied=len(instructions),
                latency_ms=latency_total,
                provider_used=ai_res.provider,
                model_used=ai_res.model,
                status=turn_status,
                validation_issues=[i.to_dict() for i in val_result.issues],
                applied_instruction_ids=applied_instruction_ids,
                contributed_source_ids=contributed_source_ids,
                contributed_chunk_ids=contributed_chunk_ids,
                provenance_records=provenance_records,
                model_provenance={
                    "provider": ai_res.provider,
                    "model": ai_res.model,
                    "mock": getattr(ai_res, "mock", False),
                    "status": ai_status_val,
                    "success": True,
                },
            )


        except (ValueError, CourseNotFoundError, EnrollmentError):
            raise
        except Exception as crash_exc:
            logger.error("Turn execution crashed for student %s on course %s: %s", req.student_id, req.course_id, crash_exc, exc_info=True)
            rec = FailureRecoveryManager.handle_crash_mid_turn(
                error=crash_exc,
                turn_id=turn_id,
                student_id=req.student_id,
                step="ORCHESTRATOR_EXECUTE_TURN",
            )
            return TutorTurnResult(
                turn_id=turn_id,
                session_id=req.session_id,
                student_id=req.student_id,
                course_id=req.course_id,
                concept_id=target_concept,
                response_text=rec.user_message,
                pedagogical_action="SAFE_ERROR_RECOVERY",
                validation_passed=False,
                state_committed=False,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                status="CRASH_RECOVERED",
                validation_issues=[{"code": "APP_CRASH_MID_TURN", "message": rec.technical_diagnostic}],
            )
