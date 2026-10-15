"""Gayatri AI Central Platform — Authoritative Assessments API Endpoints (Phase 19).

Fulfills Master Plan Section 28:
- Question item banks with difficulty, Bloom taxonomy levels, and rubrics
- Diagnostic, Formative, Summative, and Adaptive assessment generation
- Assignments and attempt lifecycle management
- Deterministic and AI-assisted rubric grading
- Teacher manual reviews, adjustments, and sign-offs
- Targeted reassessment recommendations and generation
- Complete learning event ingestion and SLR synchronization
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.api.schemas import (
    ApiResponse,
    AssessmentCreateRequest,
    AssessmentItemSchema,
    AssessmentResponse,
    AssessmentSubmitRequest,
    AssessmentSubmitResponse,
    AssignmentCreateRequest,
    AssignmentResponse,
    AttemptDetailResponse,
    AttemptStartRequest,
    AttemptStartResponse,
    AttemptSubmitRequest,
    QuestionBankItemCreateRequest,
    QuestionBankItemResponse,
    ReassessmentGenerateRequest,
    ReassessmentResponse,
    SanitizedAssessmentResponse,
    SanitizedQuestionItemResponse,
    TeacherReviewAttemptRequest,
)
from central_platform.assessment.models import AssessmentType
from central_platform.assessment.service import AssessmentService
from central_platform.auth.dependencies import (
    enforce_resource_boundaries,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Assessment,
    Assignment,
    QuestionBankItem,
    User,
    UserRole,
)
from core.assessment.manager import SAMPLE_QUESTION_BANK

router = APIRouter(prefix="/assessments", tags=["Assessments"])


def get_assessment_service(db: PlatformDatabase = Depends(get_db)) -> AssessmentService:
    return AssessmentService(db=db)


def _enforce_assessment_access(
    current_user: Optional[User],
    target_org_id: Optional[str] = None,
    require_teacher: bool = False,
) -> None:
    """Enforce authentication in production mode and role/tenant boundaries."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production mode.",
        )
    if current_user:
        if require_teacher and current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: role 'STUDENT' is not authorized for this operation.",
            )
        if target_org_id:
            enforce_resource_boundaries(current_user, target_org_id)


def _enforce_student_isolation(current_user: Optional[User], student_id: Optional[str]) -> None:
    """Enforce authentication in production mode and student self-access isolation."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production mode.",
        )
    if current_user and current_user.role == UserRole.STUDENT and student_id:
        if current_user.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: student '{current_user.id}' cannot access records for student '{student_id}'.",
            )


# ── 1. Question Bank Endpoints ───────────────────────────────────────────────

@router.get("/items", response_model=ApiResponse[List[QuestionBankItemResponse]])
async def list_assessment_items(
    course_id: Optional[str] = Query(None, description="Course ID filter"),
    concept_id: Optional[str] = Query(None, description="Concept ID filter"),
    difficulty: Optional[int] = Query(None, description="Difficulty filter (1-5)"),
    item_type: Optional[str] = Query(None, description="Question type filter"),
    topic_id: Optional[str] = Query(None, description="Legacy topic ID alias"),
    include_demo: bool = Query(False, description="Explicitly request sample questions if bank is empty (prohibited in production)"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Retrieve question bank items with filtering. Defaults to populated bank.
    
    Anti-Fallback Policy (ERP-016):
    In production mode or when include_demo is False, an empty question bank returns an empty list.
    Sample fallback questions are never returned in production mode and require explicit include_demo=True in non-prod.
    """
    _enforce_assessment_access(current_user)
    effective_concept = concept_id or topic_id
    items = service.list_questions(
        course_id=course_id,
        concept_id=effective_concept,
        difficulty=difficulty,
        item_type=item_type,
    )

    is_prod = is_production_mode()
    allow_demo = (not is_prod) and (include_demo or os.environ.get("GAYATRI_DEMO_MODE", "").lower() in ("true", "1"))

    if not items and allow_demo:
        for q in SAMPLE_QUESTION_BANK:
            q_concept = getattr(q, "concept_id", getattr(q, "topic_id", "chem_thermo_first_law"))
            if not effective_concept or q_concept == effective_concept:
                items.append(
                    QuestionBankItem(
                        id=getattr(q, "id", getattr(q, "question_id", "q1")),
                        course_id=course_id or "crs-chem-101",
                        concept_id=q_concept,
                        question_text=getattr(q, "question", getattr(q, "question_text", "")),
                        item_type=str(getattr(q, "type", getattr(q, "question_type", "MCQ"))).upper(),
                        options=getattr(q, "options", ["A", "B", "C", "D"]),
                        correct_answer=str(getattr(q, "answer", getattr(q, "correct_answer", "A"))),
                        difficulty=int(getattr(q, "difficulty", 2)),
                    )
                )

    is_student = current_user and current_user.role == UserRole.STUDENT
    data = [
        QuestionBankItemResponse(
            id=it.id,
            course_id=it.course_id,
            question_text=it.question_text,
            item_type=it.item_type,
            organization_id=it.organization_id,
            subject_id=it.subject_id,
            concept_id=it.concept_id,
            topic_id=it.topic_id,
            options=it.options,
            correct_answer=None if is_student else it.correct_answer,
            rubric={} if is_student else it.rubric,
            difficulty=it.difficulty,
            bloom_level=it.bloom_level,
            hints=it.hints,
            explanation=None if is_student else it.explanation,
            tags=it.tags,
            is_active=it.is_active,
            created_at=it.created_at,
        )
        for it in items
    ]
    return ApiResponse(ok=True, data=data)


@router.post("/items", response_model=ApiResponse[QuestionBankItemResponse], status_code=status.HTTP_201_CREATED)
async def create_question_bank_item(
    req: QuestionBankItemCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Create a new question bank item."""
    _enforce_assessment_access(current_user, target_org_id=req.organization_id, require_teacher=True)
    item = QuestionBankItem(
        id=f"qb-{uuid.uuid4().hex[:10]}",
        course_id=req.course_id,
        question_text=req.question_text,
        item_type=req.item_type,
        organization_id=req.organization_id,
        subject_id=req.subject_id,
        concept_id=req.concept_id,
        topic_id=req.topic_id,
        options=req.options,
        correct_answer=req.correct_answer,
        rubric=req.rubric,
        difficulty=req.difficulty,
        bloom_level=req.bloom_level,
        hints=req.hints,
        explanation=req.explanation,
        tags=req.tags,
    )
    try:
        created = service.create_question(item)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return ApiResponse(
        ok=True,
        data=QuestionBankItemResponse(
            id=created.id,
            course_id=created.course_id,
            question_text=created.question_text,
            item_type=created.item_type,
            organization_id=created.organization_id,
            subject_id=created.subject_id,
            concept_id=created.concept_id,
            topic_id=created.topic_id,
            options=created.options,
            correct_answer=created.correct_answer,
            rubric=created.rubric,
            difficulty=created.difficulty,
            bloom_level=created.bloom_level,
            hints=created.hints,
            explanation=created.explanation,
            tags=created.tags,
            is_active=created.is_active,
            created_at=created.created_at,
        ),
    )


@router.get("/items/{item_id}", response_model=ApiResponse[QuestionBankItemResponse])
async def get_question_bank_item(
    item_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Get question bank item details by ID."""
    _enforce_assessment_access(current_user)
    item = service.get_question(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Question '{item_id}' not found.")
    
    is_student = current_user and current_user.role == UserRole.STUDENT
    return ApiResponse(
        ok=True,
        data=QuestionBankItemResponse(
            id=item.id,
            course_id=item.course_id,
            question_text=item.question_text,
            item_type=item.item_type,
            organization_id=item.organization_id,
            subject_id=item.subject_id,
            concept_id=item.concept_id,
            topic_id=item.topic_id,
            options=item.options,
            correct_answer=None if is_student else item.correct_answer,
            rubric={} if is_student else item.rubric,
            difficulty=item.difficulty,
            bloom_level=item.bloom_level,
            hints=item.hints,
            explanation=None if is_student else item.explanation,
            tags=item.tags,
            is_active=item.is_active,
            created_at=item.created_at,
        ),
    )


# ── 2. Assessment Definition Endpoints ───────────────────────────────────────

@router.post("", response_model=ApiResponse[AssessmentResponse], status_code=status.HTTP_201_CREATED)
async def create_assessment(
    req: AssessmentCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Create an assessment definition (Diagnostic, Formative, Summative, Adaptive, etc.)."""
    _enforce_assessment_access(current_user, target_org_id=req.organization_id, require_teacher=True)
    try:
        asmt_type = AssessmentType(req.assessment_type.lower())
    except ValueError:
        asmt_type = AssessmentType.FORMATIVE

    asmt = Assessment(
        id=f"asmt-{uuid.uuid4().hex[:10]}",
        course_id=req.course_id,
        title=req.title,
        assessment_type=asmt_type,
        total_marks=100.0,
        organization_id=req.organization_id,
        description=req.description,
        duration_minutes=req.duration_minutes,
        passing_score=req.passing_score,
        item_ids=req.item_ids,
        config=req.config,
        rubric=req.rubric,
        status=req.status,
    )
    try:
        created = service.create_assessment(asmt)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return ApiResponse(
        ok=True,
        data=AssessmentResponse(
            id=created.id,
            course_id=created.course_id,
            title=created.title,
            assessment_type=created.assessment_type.value if hasattr(created.assessment_type, "value") else str(created.assessment_type),
            total_marks=created.total_marks,
            organization_id=created.organization_id,
            description=created.description,
            duration_minutes=created.duration_minutes,
            passing_score=created.passing_score,
            item_ids=created.item_ids,
            config=created.config,
            rubric=created.rubric,
            status=created.status,
            created_at=created.created_at,
            updated_at=created.updated_at,
        ),
    )


@router.get("", response_model=ApiResponse[List[AssessmentResponse]])
async def list_assessments(
    course_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    assessment_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """List assessments matching filters."""
    _enforce_assessment_access(current_user, target_org_id=organization_id)
    asmts = service.list_assessments(
        course_id=course_id,
        organization_id=organization_id,
        assessment_type=assessment_type,
        status=status_filter,
    )
    data = [
        AssessmentResponse(
            id=a.id,
            course_id=a.course_id,
            title=a.title,
            assessment_type=a.assessment_type.value if hasattr(a.assessment_type, "value") else str(a.assessment_type),
            total_marks=a.total_marks,
            organization_id=a.organization_id,
            description=a.description,
            duration_minutes=a.duration_minutes,
            passing_score=a.passing_score,
            item_ids=a.item_ids,
            config=a.config,
            rubric=a.rubric,
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in asmts
    ]
    return ApiResponse(ok=True, data=data)


@router.get("/{assessment_id}", response_model=ApiResponse[AssessmentResponse])
async def get_assessment(
    assessment_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Get assessment definition by ID."""
    _enforce_assessment_access(current_user)
    asmt = service.get_assessment(assessment_id)
    if not asmt:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found.")
    return ApiResponse(
        ok=True,
        data=AssessmentResponse(
            id=asmt.id,
            course_id=asmt.course_id,
            title=asmt.title,
            assessment_type=asmt.assessment_type.value if hasattr(asmt.assessment_type, "value") else str(asmt.assessment_type),
            total_marks=asmt.total_marks,
            organization_id=asmt.organization_id,
            description=asmt.description,
            duration_minutes=asmt.duration_minutes,
            passing_score=asmt.passing_score,
            item_ids=asmt.item_ids,
            config=asmt.config,
            rubric=asmt.rubric,
            status=asmt.status,
            created_at=asmt.created_at,
            updated_at=asmt.updated_at,
        ),
    )


@router.get("/{assessment_id}/sanitized", response_model=ApiResponse[SanitizedAssessmentResponse])
async def get_sanitized_assessment(
    assessment_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Retrieve an assessment sanitized for student question delivery.
    
    Anti-Answer-Leakage Invariant:
    All correct answers, answer keys, rubrics, and teacher explanations are scrubbed.
    """
    _enforce_assessment_access(current_user)
    asmt_data = service.get_sanitized_assessment(assessment_id)
    if not asmt_data:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found.")

    items = []
    raw_items = asmt_data.get("items", []) if isinstance(asmt_data, dict) else getattr(asmt_data, "items", [])
    for it in raw_items:
        if isinstance(it, dict):
            items.append(
                SanitizedQuestionItemResponse(
                    id=it.get("id", ""),
                    course_id=it.get("course_id", asmt_data.get("course_id", "") if isinstance(asmt_data, dict) else getattr(asmt_data, "course_id", "")),
                    question_text=it.get("question_text", ""),
                    item_type=it.get("item_type", "MCQ"),
                    options=it.get("options", []),
                    difficulty=it.get("difficulty", 1),
                    bloom_level=it.get("bloom_level", "recall"),
                    hints=it.get("hints", []),
                    tags=it.get("tags", []),
                )
            )
        else:
            items.append(
                SanitizedQuestionItemResponse(
                    id=getattr(it, "id", ""),
                    course_id=getattr(it, "course_id", ""),
                    question_text=getattr(it, "question_text", ""),
                    item_type=getattr(it, "item_type", "MCQ"),
                    options=getattr(it, "options", []),
                    difficulty=getattr(it, "difficulty", 1),
                    bloom_level=getattr(it, "bloom_level", "recall"),
                    hints=getattr(it, "hints", []),
                    tags=getattr(it, "tags", []),
                )
            )

    if isinstance(asmt_data, dict):
        asmt_id = asmt_data.get("id", "")
        course_id = asmt_data.get("course_id", "")
        title = asmt_data.get("title", "")
        asmt_type_str = str(asmt_data.get("assessment_type", "formative"))
        duration_minutes = int(asmt_data.get("duration_minutes", 0))
        passing_score = float(asmt_data.get("passing_score", 70.0))
        status_val = str(asmt_data.get("status", "draft"))
    else:
        asmt_id = asmt_data.id
        course_id = asmt_data.course_id
        title = asmt_data.title
        asmt_type_str = asmt_data.assessment_type.value if hasattr(asmt_data.assessment_type, "value") else str(asmt_data.assessment_type)
        duration_minutes = int(asmt_data.duration_minutes)
        passing_score = float(asmt_data.passing_score)
        status_val = str(asmt_data.status)

    return ApiResponse(
        ok=True,
        data=SanitizedAssessmentResponse(
            id=asmt_id,
            course_id=course_id,
            title=title,
            assessment_type=asmt_type_str,
            duration_minutes=duration_minutes,
            passing_score=passing_score,
            items=items,
            status=status_val,
        ),
    )


@router.post("/{assessment_id}/publish", response_model=ApiResponse[AssessmentResponse])
async def publish_assessment(
    assessment_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Publish an assessment."""
    _enforce_assessment_access(current_user, require_teacher=True)
    published = service.publish_assessment(assessment_id)
    if not published:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found.")
    return ApiResponse(
        ok=True,
        data=AssessmentResponse(
            id=published.id,
            course_id=published.course_id,
            title=published.title,
            assessment_type=published.assessment_type.value if hasattr(published.assessment_type, "value") else str(published.assessment_type),
            total_marks=published.total_marks,
            organization_id=published.organization_id,
            description=published.description,
            duration_minutes=published.duration_minutes,
            passing_score=published.passing_score,
            item_ids=published.item_ids,
            config=published.config,
            rubric=published.rubric,
            status=published.status,
            created_at=published.created_at,
            updated_at=published.updated_at,
        ),
    )


# ── 3. Assignments Endpoints ─────────────────────────────────────────────────

@router.post("/assignments", response_model=ApiResponse[AssignmentResponse], status_code=status.HTTP_201_CREATED)
async def create_assignment(
    req: AssignmentCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Assign an assessment to a course, cohort, or class group."""
    _enforce_assessment_access(current_user, target_org_id=req.organization_id, require_teacher=True)
    assign = Assignment(
        id=f"assign-{uuid.uuid4().hex[:10]}",
        course_id=req.course_id,
        assessment_id=req.assessment_id,
        title=req.title,
        organization_id=req.organization_id,
        cohort_id=req.cohort_id,
        class_group_id=req.class_group_id,
        instructions=req.instructions,
        due_at=req.due_at,
    )
    try:
        created = service.create_assignment(assign)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return ApiResponse(
        ok=True,
        data=AssignmentResponse(
            id=created.id,
            course_id=created.course_id,
            assessment_id=created.assessment_id,
            title=created.title,
            organization_id=created.organization_id,
            cohort_id=created.cohort_id,
            class_group_id=created.class_group_id,
            assigned_by=created.assigned_by,
            instructions=created.instructions,
            due_at=created.due_at,
            is_active=created.is_active,
            created_at=created.created_at,
        ),
    )


@router.get("/assignments", response_model=ApiResponse[List[AssignmentResponse]])
async def list_assignments(
    course_id: Optional[str] = Query(None),
    cohort_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """List active assignments."""
    _enforce_assessment_access(current_user, target_org_id=organization_id)
    assignments = service.list_assignments(
        course_id=course_id,
        cohort_id=cohort_id,
        organization_id=organization_id,
    )
    data = [
        AssignmentResponse(
            id=a.id,
            course_id=a.course_id,
            assessment_id=a.assessment_id,
            title=a.title,
            organization_id=a.organization_id,
            cohort_id=a.cohort_id,
            class_group_id=a.class_group_id,
            assigned_by=a.assigned_by,
            instructions=a.instructions,
            due_at=a.due_at,
            is_active=a.is_active,
            created_at=a.created_at,
        )
        for a in assignments
    ]
    return ApiResponse(ok=True, data=data)


# ── 4. Attempts Lifecycle Endpoints ──────────────────────────────────────────

@router.post("/attempts/start", response_model=ApiResponse[AttemptStartResponse], status_code=status.HTTP_201_CREATED)
async def start_attempt(
    req: AttemptStartRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Start an assessment attempt (Diagnostic, Formative, Summative, Adaptive)."""
    _enforce_student_isolation(current_user, req.student_id)
    try:
        attempt = service.start_attempt(
            assessment_id=req.assessment_id,
            student_id=req.student_id,
            assignment_id=req.assignment_id,
            initial_difficulty=req.initial_difficulty,
        )
        return ApiResponse(
            ok=True,
            data=AttemptStartResponse(
                attempt_id=attempt.id,
                assessment_id=attempt.assessment_id,
                student_id=attempt.student_id,
                assignment_id=attempt.assignment_id,
                attempt_number=attempt.attempt_number,
                status=attempt.status,
                started_at=attempt.started_at,
                max_score=attempt.max_score,
                current_difficulty=attempt.current_difficulty,
            ),
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/attempts/{attempt_id}/adaptive-next", response_model=ApiResponse[Optional[QuestionBankItemResponse]])
async def get_next_adaptive_question(
    attempt_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Get the next dynamically selected question for an adaptive assessment."""
    attempt = service.get_attempt(attempt_id)
    if attempt:
        _enforce_student_isolation(current_user, attempt.student_id)
    try:
        item = service.get_next_adaptive_item(attempt_id)
        if not item:
            return ApiResponse(ok=True, data=None)
        return ApiResponse(
            ok=True,
            data=QuestionBankItemResponse(
                id=item.id,
                course_id=item.course_id,
                question_text=item.question_text,
                item_type=item.item_type,
                organization_id=item.organization_id,
                subject_id=item.subject_id,
                concept_id=item.concept_id,
                topic_id=item.topic_id,
                options=item.options,
                correct_answer=item.correct_answer,
                rubric=item.rubric,
                difficulty=item.difficulty,
                bloom_level=item.bloom_level,
                hints=item.hints,
                explanation=item.explanation,
                tags=item.tags,
                is_active=item.is_active,
                created_at=item.created_at,
            ),
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/attempts/{attempt_id}/submit", response_model=ApiResponse[AttemptDetailResponse])
async def submit_attempt(
    attempt_id: str,
    req: AttemptSubmitRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Submit attempt answers, trigger hybrid grading, and feed central learning events."""
    attempt_rec = service.get_attempt(attempt_id)
    target_student = req.student_id or (attempt_rec.student_id if attempt_rec else None)
    _enforce_student_isolation(current_user, target_student)
    try:
        attempt = service.submit_attempt(
            attempt_id=attempt_id,
            answers=req.answers,
            student_id=req.student_id,
        )
        return ApiResponse(
            ok=True,
            data=AttemptDetailResponse(
                id=attempt.id,
                assessment_id=attempt.assessment_id,
                student_id=attempt.student_id,
                assignment_id=attempt.assignment_id,
                attempt_number=attempt.attempt_number,
                status=attempt.status,
                started_at=attempt.started_at,
                completed_at=attempt.completed_at,
                time_spent_seconds=attempt.time_spent_seconds,
                score=attempt.score,
                max_score=attempt.max_score,
                percentage=attempt.percentage,
                passed=attempt.passed,
                current_difficulty=attempt.current_difficulty,
                answers=attempt.answers,
                item_results=attempt.item_results,
                ai_grading_summary=attempt.ai_grading_summary,
                teacher_review=attempt.teacher_review,
                reassessment_recommendations=attempt.reassessment_recommendations,
            ),
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/attempts/{attempt_id}", response_model=ApiResponse[AttemptDetailResponse])
async def get_attempt(
    attempt_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Retrieve full attempt details with rubric evaluation and feedback."""
    attempt = service.get_attempt(attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail=f"Attempt '{attempt_id}' not found.")
    _enforce_student_isolation(current_user, attempt.student_id)
    return ApiResponse(
        ok=True,
        data=AttemptDetailResponse(
            id=attempt.id,
            assessment_id=attempt.assessment_id,
            student_id=attempt.student_id,
            assignment_id=attempt.assignment_id,
            attempt_number=attempt.attempt_number,
            status=attempt.status,
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
            time_spent_seconds=attempt.time_spent_seconds,
            score=attempt.score,
            max_score=attempt.max_score,
            percentage=attempt.percentage,
            passed=attempt.passed,
            current_difficulty=attempt.current_difficulty,
            answers=attempt.answers,
            item_results=attempt.item_results,
            ai_grading_summary=attempt.ai_grading_summary,
            teacher_review=attempt.teacher_review,
            reassessment_recommendations=attempt.reassessment_recommendations,
        ),
    )


@router.get("/attempts/student/{student_id}", response_model=ApiResponse[List[AttemptDetailResponse]])
async def list_student_attempts(
    student_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """List all assessment attempts for a student."""
    _enforce_student_isolation(current_user, student_id)
    attempts = service.get_student_attempts(student_id, limit=limit)
    data = [
        AttemptDetailResponse(
            id=a.id,
            assessment_id=a.assessment_id,
            student_id=a.student_id,
            assignment_id=a.assignment_id,
            attempt_number=a.attempt_number,
            status=a.status,
            started_at=a.started_at,
            completed_at=a.completed_at,
            time_spent_seconds=a.time_spent_seconds,
            score=a.score,
            max_score=a.max_score,
            percentage=a.percentage,
            passed=a.passed,
            current_difficulty=a.current_difficulty,
            answers=a.answers,
            item_results=a.item_results,
            ai_grading_summary=a.ai_grading_summary,
            teacher_review=a.teacher_review,
            reassessment_recommendations=a.reassessment_recommendations,
        )
        for a in attempts
    ]
    return ApiResponse(ok=True, data=data)


# ── 5. Teacher Review & Reassessment Endpoints ───────────────────────────────

@router.post("/attempts/{attempt_id}/review", response_model=ApiResponse[AttemptDetailResponse])
@router.post("/attempts/{attempt_id}/teacher-review", response_model=ApiResponse[AttemptDetailResponse])
async def teacher_review_attempt(
    attempt_id: str,
    req: TeacherReviewAttemptRequest,
    teacher_id: str = Query("teacher-default"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Teacher review, score override, and approval."""
    _enforce_assessment_access(current_user, require_teacher=True)
    try:
        attempt = service.teacher_review_attempt(
            attempt_id=attempt_id,
            teacher_id=teacher_id,
            item_score_adjustments=req.item_score_adjustments,
            teacher_comments=req.teacher_comments,
            status=req.status,
        )
        return ApiResponse(
            ok=True,
            data=AttemptDetailResponse(
                id=attempt.id,
                assessment_id=attempt.assessment_id,
                student_id=attempt.student_id,
                assignment_id=attempt.assignment_id,
                attempt_number=attempt.attempt_number,
                status=attempt.status,
                started_at=attempt.started_at,
                completed_at=attempt.completed_at,
                time_spent_seconds=attempt.time_spent_seconds,
                score=attempt.score,
                max_score=attempt.max_score,
                percentage=attempt.percentage,
                passed=attempt.passed,
                current_difficulty=attempt.current_difficulty,
                answers=attempt.answers,
                item_results=attempt.item_results,
                ai_grading_summary=attempt.ai_grading_summary,
                teacher_review=attempt.teacher_review,
                reassessment_recommendations=attempt.reassessment_recommendations,
            ),
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/attempts/{attempt_id}/reassess", response_model=ApiResponse[ReassessmentResponse], status_code=status.HTTP_201_CREATED)
async def generate_reassessment(
    attempt_id: str,
    req: ReassessmentGenerateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Generate targeted diagnostic/adaptive reassessment based on weak concepts from a prior attempt."""
    attempt_rec = service.get_attempt(attempt_id)
    target_student = attempt_rec.student_id if attempt_rec else None
    _enforce_student_isolation(current_user, target_student)
    try:
        new_asmt, reassessment = service.generate_reassessment(
            original_attempt_id=attempt_id,
            target_score=req.target_score,
        )
        return ApiResponse(
            ok=True,
            data=ReassessmentResponse(
                reassessment_id=reassessment.id,
                original_attempt_id=reassessment.original_attempt_id,
                student_id=reassessment.student_id,
                course_id=reassessment.course_id,
                generated_assessment_id=reassessment.generated_assessment_id,
                target_concepts=reassessment.target_concepts,
                status=reassessment.status,
                target_score=reassessment.target_score,
                created_at=reassessment.created_at,
            ),
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


# ── 6. Legacy Submit Endpoint ────────────────────────────────────────────────

@router.post("/submit", response_model=ApiResponse[AssessmentSubmitResponse])
async def submit_assessment_legacy(
    submission: AssessmentSubmitRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AssessmentService = Depends(get_assessment_service),
):
    """Legacy backward-compatible submission endpoint."""
    _enforce_student_isolation(current_user, submission.student_id)
    is_prod = is_production_mode()
    legacy_service = AssessmentService(
        db=service.db,
        event_store=service.event_store,
        slr_service=service.slr_service,
        allow_auto_provision=not is_prod,
    )
    total = max(len(submission.answers), 1)
    asmt = legacy_service.get_assessment(submission.assessment_id)
    if not asmt:
        if is_prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assessment '{submission.assessment_id}' not found. Auto-provisioning is prohibited in production.",
            )
        item_ids = []
        for q_id, ans_val in submission.answers.items():
            matching_sample = next((sq for sq in SAMPLE_QUESTION_BANK if getattr(sq, "id", "") == q_id or getattr(sq, "question_id", "") == q_id), None)
            if matching_sample:
                qb_item = QuestionBankItem(
                    id=q_id,
                    course_id="crs-chem-101",
                    concept_id=getattr(matching_sample, "concept_id", "chem_thermo_first_law"),
                    question_text=getattr(matching_sample, "question", getattr(matching_sample, "question_text", f"Question {q_id}")),
                    item_type=str(getattr(matching_sample, "type", getattr(matching_sample, "question_type", "MCQ"))).upper(),
                    options=getattr(matching_sample, "options", ["A", "B", "C", "D"]),
                    correct_answer=str(getattr(matching_sample, "answer", getattr(matching_sample, "correct_answer", ans_val))),
                )
                legacy_service.create_question(qb_item)
                item_ids.append(q_id)
            else:
                qb_item = QuestionBankItem(
                    id=q_id,
                    course_id="crs-chem-101",
                    concept_id="chem_thermo_first_law",
                    question_text=f"Question {q_id}",
                    item_type="SHORT_ANSWER",
                    correct_answer=str(ans_val),
                )
                legacy_service.create_question(qb_item)
                item_ids.append(q_id)

        asmt = Assessment(
            id=submission.assessment_id,
            course_id="crs-chem-101",
            title=f"Assessment {submission.assessment_id}",
            assessment_type=AssessmentType.FORMATIVE,
            total_marks=float(total * 4.0),
            item_ids=item_ids,
        )
        legacy_service.create_assessment(asmt)

    attempt = legacy_service.start_attempt(submission.assessment_id, submission.student_id)
    completed_attempt = legacy_service.submit_attempt(attempt.id, submission.answers, submission.student_id)

    return ApiResponse(
        ok=True,
        data=AssessmentSubmitResponse(
            assessment_id=completed_attempt.assessment_id,
            student_id=completed_attempt.student_id,
            score=completed_attempt.score,
            total_questions=total,
            passed=completed_attempt.passed,
            feedback={"general": "Assessment graded successfully."},
            item_results=completed_attempt.item_results,
            reassessment_recommendations=completed_attempt.reassessment_recommendations,
        ),
    )
