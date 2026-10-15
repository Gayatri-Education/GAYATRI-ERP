"""Gayatri AI Platform — Generic Tutor Orchestrator REST Routes (Phase 10).

Exposes the course-independent 16-step tutoring lifecycle over HTTP REST.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import (
    enforce_resource_boundaries,
    get_current_user,
    get_db,
)
from central_platform.courses.service import CourseNotFoundError
from central_platform.db import PlatformDatabase
from central_platform.models.schema import LearningEvent, Session, SessionStatus, User
from central_platform.security.auditor import SecurityAuditor
from central_platform.tutor.orchestrator import (
    EnrollmentError,
    GenericTutorOrchestrator,
    TutorTurnRequest,
    TutorTurnResult,
)

logger = logging.getLogger("gayatri.api.routes.tutor")

router = APIRouter(prefix="/tutor", tags=["Tutor Orchestrator"])


class TutorTurnApiRequest(BaseModel):
    """REST request body for submitting a course tutoring turn."""
    student_id: str = Field(..., description="Student unique identifier")
    session_id: str = Field(..., description="Active session unique identifier")
    course_id: str = Field(..., description="Target course unique identifier")
    message: Optional[str] = Field(None, description="Student query or message")
    student_input: Optional[str] = Field(None, description="Alternative alias for student query")
    course_version_id: Optional[str] = Field(None, description="Optional pinned course version")
    class_id: Optional[str] = Field(None, description="Optional class/cohort identifier")
    concept_id: Optional[str] = Field(None, description="Optional target concept identifier")
    max_tokens: int = Field(512, ge=1, le=4096, description="Max generation tokens")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    preferred_provider: Optional[str] = Field(None, description="Requested provider")
    preferred_model: Optional[str] = Field(None, description="Requested model")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="Recent conversation turns")


class TutorTurnApiResponse(BaseModel):
    """REST response body for a completed tutoring turn."""
    turn_id: str
    session_id: str
    student_id: str
    course_id: str
    concept_id: str
    response_text: str
    pedagogical_action: str
    validation_passed: bool
    state_committed: bool
    rag_sources_used: List[str] = Field(default_factory=list)
    tools_invoked: List[str] = Field(default_factory=list)
    teacher_instructions_applied: int = 0
    latency_ms: float = 0.0
    provider_used: str = "local"
    model_used: str = "default"
    status: str = "SUCCESS"
    validation_issues: List[Dict[str, Any]] = Field(default_factory=list)
    applied_instruction_ids: List[str] = Field(default_factory=list)
    contributed_source_ids: List[str] = Field(default_factory=list)
    contributed_chunk_ids: List[str] = Field(default_factory=list)
    provenance_records: List[Dict[str, Any]] = Field(default_factory=list)
    ok: bool = True
    assistant_text: Optional[str] = None
    is_blocked: bool = Field(False, description="True if turn was blocked by safety/security policies")
    is_completed: bool = Field(True, description="True only if turn was successfully completed")
    is_grounded: bool = Field(False, description="True only if response is grounded in authoritative sources")
    turn_type: str = Field("COMPLETED", description="Turn category: COMPLETED, BLOCKED, VALIDATION_FAILED, ERROR")


@router.post("/turn", response_model=TutorTurnApiResponse)
async def submit_tutor_turn(
    req: TutorTurnApiRequest,
    db: PlatformDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TutorTurnApiResponse:
    # ── Identity & Resource Boundary Enforcement (Phase 1 / F-001, F-002) ──
    enforce_resource_boundaries(
        current_user=current_user,
        target_student_id=req.student_id,
    )

    query_text = req.message or req.student_input or ""
    if not query_text.strip():
        raise HTTPException(status_code=400, detail="Missing message or student_input text.")

    # ── Prompt Injection Guard (Phase 22 Security) ──────────────────────────
    _auditor = SecurityAuditor()
    audit_result = _auditor.sanitize_prompt(query_text)
    if not audit_result.is_safe:
        logger.warning(
            "Prompt injection/hazardous pattern blocked for student %s: %s",
            req.student_id,
            audit_result.violations,
        )
        # Record blocked learning event in DB for auditability without mutating student mastery
        try:
            if req.session_id and not db.get_session(req.session_id):
                db.create_session(Session(
                    id=req.session_id,
                    student_id=req.student_id,
                    course_id=req.course_id,
                    concept_id=req.concept_id or f"{req.course_id}_foundations",
                    status=SessionStatus.ACTIVE,
                    course_version_id=req.course_version_id,
                ))
            db.record_learning_event(LearningEvent(
                id=f"evt-block-{uuid.uuid4().hex[:8]}",
                session_id=req.session_id,
                student_id=req.student_id,
                event_type="TUTOR_TURN_BLOCKED",
                concept_id=req.concept_id or f"{req.course_id}_foundations",
                course_id=req.course_id,
                course_version_id=req.course_version_id,
                payload={
                    "student_message": query_text,
                    "query": query_text,
                    "violations": audit_result.violations,
                    "status": "BLOCKED_INJECTION",
                    "is_blocked": True,
                    "is_completed": False,
                },
            ))
        except Exception as ev_exc:
            logger.warning(f"Could not record blocked turn telemetry event: {ev_exc}")

        # Return a safe pedagogical response — do NOT forward to LLM
        return TutorTurnApiResponse(
            turn_id=f"turn-blocked-{uuid.uuid4().hex[:8]}",
            session_id=req.session_id,
            student_id=req.student_id,
            course_id=req.course_id,
            concept_id=req.concept_id or "",
            response_text=(
                "I noticed your message contains content I can't process in this learning context. "
                "Please ask a genuine question about your coursework — I'm here to help you learn!"
            ),
            pedagogical_action="SAFE_REDIRECT",
            validation_passed=False,
            state_committed=False,
            status="BLOCKED_INJECTION",
            ok=False,
            assistant_text=None,
            is_blocked=True,
            is_completed=False,
            is_grounded=False,
            turn_type="BLOCKED",
        )

    try:
        orchestrator = GenericTutorOrchestrator(db=db)
        turn_req = TutorTurnRequest(
            student_id=req.student_id,
            session_id=req.session_id,
            course_id=req.course_id,
            message=query_text,
            course_version_id=req.course_version_id,
            class_id=req.class_id,
            concept_id=req.concept_id,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            preferred_provider=req.preferred_provider,
            preferred_model=req.preferred_model,
            conversation_history=req.conversation_history,
        )
        res: TutorTurnResult = orchestrator.execute_turn(turn_req)
        turn_dict = res.to_dict()
        turn_dict["ok"] = (res.status == "SUCCESS")
        turn_dict["assistant_text"] = res.response_text
        turn_dict["is_blocked"] = getattr(res, "is_blocked", False)
        turn_dict["is_completed"] = getattr(res, "is_completed", res.status == "SUCCESS")
        turn_dict["is_grounded"] = getattr(res, "is_grounded", bool(res.rag_sources_used))
        turn_dict["turn_type"] = getattr(res, "turn_type", "COMPLETED" if res.status == "SUCCESS" else res.status)
        return TutorTurnApiResponse(**turn_dict)

    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except EnrollmentError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Unexpected error in tutor turn endpoint: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Tutoring turn execution failed.")
