"""Gayatri AI Platform — Pydantic Request, Response, and Envelope Schemas (Phase 02).

Defines standard schemas for all versioned platform endpoints (/api/v1/*),
ensuring type safety, validation, and consistent error envelopes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Metadata and Envelopes ───────────────────────────────────────────────

class MetaDetail(BaseModel):
    request_id: str = Field(default="", description="Unique request correlation ID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    api_version: str = Field(default="v1", description="API Version")


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Granular error context")


class ApiResponse(BaseModel, Generic[T]):
    ok: bool = Field(default=True, description="Success flag")
    data: Optional[T] = Field(default=None, description="Payload data")
    error: Optional[ErrorDetail] = Field(default=None, description="Error detail if ok is False")
    meta: MetaDetail = Field(default_factory=MetaDetail, description="Request metadata")


# ── Health & Probes ──────────────────────────────────────────────────────

class HealthStatusResponse(BaseModel):
    status: str = "ONLINE"
    service: str = "GayatriPlatformAPI"
    version: str = "v2.0-reconciliation"
    database: str = "CONNECTED"
    students_monitored: int = 5
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Authentication & Users ───────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=4)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 3600
    user_id: str
    username: str
    role: str
    organization_id: str = "org-default"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: str
    new_password: str = Field(..., min_length=4)
    token: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    organization_id: str
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=4)
    role: str = Field(default="STUDENT")
    organization_id: str = Field(default="org-default")


# ── Student & Telemetry ──────────────────────────────────────────────────

class StudentSnapshotRequest(BaseModel):
    student_id: str
    student_name: str
    course_id: str = "crs-chem-101"
    mastery: float = Field(default=0.5, ge=0.0, le=1.0)
    needs_attention: bool = False
    misconceptions: List[str] = Field(default_factory=list)
    hint_count: int = 0
    retention_rate: float = Field(default=0.85, ge=0.0, le=1.0)


class StudentProfileResponse(BaseModel):
    student_id: str
    student_name: str
    course_id: str
    current_concept: str
    mastery: float
    retention_rate: float
    hint_count: int
    misconceptions: List[str]
    recent_activity: Any = Field(default_factory=list)


class StudentEnrolledCourseResponse(BaseModel):
    id: str
    course_id: str
    code: str
    title: str
    description: str = ""
    organization_id: str
    cohort_id: Optional[str] = None
    cohort_name: Optional[str] = None
    class_group_id: Optional[str] = None
    class_name: Optional[str] = None
    enrolled_at: str
    is_active: bool = True
    overall_mastery: float = 0.0
    active_concept: str = ""


class StudentCourseSwitchRequest(BaseModel):
    target_course_id: str
    active_turn_generating: bool = False


class StudentCourseSwitchResponse(BaseModel):
    student_id: str
    active_course_id: str
    course_title: str
    switched_at: str
    active_concept: str
    overall_mastery: float


class StudentOfflineStatusResponse(BaseModel):
    student_id: str
    course_id: str
    is_cached: bool = True
    is_synced: bool = True
    offline_available: bool = True
    last_synced_at: Optional[str] = None


# ── Teacher & Directives ─────────────────────────────────────────────────

class TeacherInstructionCreateRequest(BaseModel):
    instruction: str = Field(..., min_length=3)
    student_id: str = Field(default="all")
    course_id: str = Field(default="crs-chem-101")
    priority: int = Field(default=2, ge=1, le=5)
    concept_scope: str = Field(default="ALL")
    start_at: Optional[str] = None
    expires_at: Optional[str] = None
    scope_type: Optional[str] = None
    organization_id: Optional[str] = None
    course_version_id: Optional[str] = None
    class_id: Optional[str] = None
    session_id: Optional[str] = None


class TeacherInstructionResponse(BaseModel):
    instruction_id: str
    teacher_id: str
    student_id: str
    course_id: str
    instruction_text: str
    priority: int
    concept_scope: str
    scope_type: str = "STUDENT"
    organization_id: Optional[str] = None
    course_version_id: Optional[str] = None
    class_id: Optional[str] = None
    session_id: Optional[str] = None
    version: int = 1
    is_active: bool
    status: str = "ACTIVE"
    start_at: Optional[str] = None
    expires_at: Optional[str] = None
    safety_status: str = "VALIDATED"
    safety_reasons: List[str] = Field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: Optional[str] = None


class TeacherInstructionUpdateRequest(BaseModel):
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    concept_scope: Optional[str] = None
    expires_at: Optional[str] = None
    status: Optional[str] = None
    instruction_text: Optional[str] = None


class TeacherInstructionValidateRequest(BaseModel):
    instruction: str = Field(..., min_length=1)


class TeacherInstructionValidateResponse(BaseModel):
    is_valid: bool
    safety_status: str
    violations: List[str] = Field(default_factory=list)
    sanitized_text: str = ""
    target_invariants: List[str] = Field(default_factory=list)


class TeacherInstructionToggleRequest(BaseModel):
    instruction_id: str
    active: bool


class AlertResolveRequest(BaseModel):
    alert_id: str
    resolution_note: str = Field(default="Resolved by teacher directive")


# ── Teacher Interventions (Section 21) ──────────────────────────────────

class TeacherInterventionCreateRequest(BaseModel):
    student_id: str
    course_id: str = Field(default="crs-chem-101")
    reason: str = Field(..., min_length=5)
    priority: str = Field(default="MEDIUM")
    assigned_teacher: Optional[str] = None
    due_at: Optional[str] = None
    trigger_type: str = Field(default="teacher_created")
    trigger_evidence: Dict[str, Any] = Field(default_factory=dict)


class TeacherInterventionResponse(BaseModel):
    intervention_id: str
    student_id: str
    course_id: str
    reason: str
    priority: str
    assigned_teacher: Optional[str] = None
    trigger_type: str
    trigger_evidence: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    due_at: Optional[str] = None
    status: str
    resolution: Optional[str] = None
    teacher_notes: List[Dict[str, Any]] = Field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    dismissed_at: Optional[str] = None
    dismissed_by: Optional[str] = None
    dismissal_reason: Optional[str] = None


class TeacherInterventionUpdateRequest(BaseModel):
    priority: Optional[str] = None
    due_at: Optional[str] = None
    assigned_teacher: Optional[str] = None
    status: Optional[str] = None


class TeacherInterventionNoteRequest(BaseModel):
    text: str = Field(..., min_length=1)


class TeacherInterventionResolveRequest(BaseModel):
    resolution_note: str = Field(..., min_length=3)


class TeacherInterventionDismissRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class TeacherInterventionEvaluateRequest(BaseModel):
    student_id: str
    course_id: str = Field(default="crs-chem-101")


class TeacherDashboardResponse(BaseModel):
    total_students: int
    active_today: int
    average_mastery: float
    critical_alerts_count: int
    mastery_distribution: Dict[str, int]
    chapter_averages: Dict[str, float]
    recent_alerts: List[Dict[str, Any]]
    students: List[Dict[str, Any]]
    # Master Plan Section 19 Core Teacher Dimensions
    students_active: int = 0
    difficult_concepts: List[Dict[str, Any]] = Field(default_factory=list)
    common_misconceptions: List[Dict[str, Any]] = Field(default_factory=list)
    recent_activity: List[Dict[str, Any]] = Field(default_factory=list)
    intervention_alerts: List[Dict[str, Any]] = Field(default_factory=list)

class TeacherClassGroupCreateRequest(BaseModel):
    course_id: str
    name: str = Field(..., min_length=1, max_length=100)
    section: str = Field(default="A", max_length=20)


class TeacherClassGroupResponse(BaseModel):
    id: str
    organization_id: str
    course_id: str
    name: str
    section: str
    created_at: str


class TeacherClassNoteCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class TeacherClassNoteResponse(BaseModel):
    id: str
    class_id: str
    course_id: str
    title: str
    chunks_created: int
    status: str
    created_at: str


class TeacherRemedialContentCreateRequest(BaseModel):
    course_id: str
    target_student_ids: List[str] = Field(..., min_items=1)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class TeacherRemedialContentResponse(BaseModel):
    id: str
    course_id: str
    target_student_ids: List[str]
    title: str
    chunks_created: int
    status: str
    created_at: str


class TeacherAssignmentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    course_id: str
    description: Optional[str] = ""
    class_group_id: Optional[str] = None
    due_date: Optional[str] = None
    instructions: Optional[str] = ""


class TeacherAssignmentResponse(BaseModel):
    id: str
    course_id: str
    title: str
    description: Optional[str] = ""
    class_group_id: Optional[str] = None
    assigned_by: Optional[str] = None
    due_date: Optional[str] = None
    instructions: str = ""
    is_active: bool = True
    created_at: str


class TeacherCourseResponse(BaseModel):
    id: str
    organization_id: str
    code: str
    title: str
    description: str = ""
    visibility: str = "PUBLIC"
    status: str = "ACTIVE"


# ── Curriculum & Courses ─────────────────────────────────────────────────

class CourseResponse(BaseModel):
    course_id: str
    title: str
    description: str = ""
    subject: str = "General"
    grade_level: str = "All"
    total_concepts: int = 12
    version: str = "v1.0"
    visibility: str = "PUBLIC"
    code: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: Optional[str] = None


class CourseCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(default="")
    visibility: str = Field(default="PUBLIC")  # PUBLIC or PRIVATE
    organization_id: Optional[str] = Field(default=None)
    subject: str = Field(default="General")
    grade_level: str = Field(default="All")


class CourseSelectRequest(BaseModel):
    organization_id: str
    course_version_id: Optional[str] = None


class CourseOfferingResponse(BaseModel):
    id: str
    course_id: str
    organization_id: str
    course_version_id: Optional[str] = None
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CourseVersionCreateApiRequest(BaseModel):
    version_tag: str = Field(..., min_length=1)
    changelog: str = Field(default="")
    curriculum_payload: Optional[Dict[str, Any]] = None


class CourseVersionApiResponse(BaseModel):
    id: str
    course_id: str
    version_tag: str
    status: str
    changelog: str = ""
    created_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CourseArchiveResponse(BaseModel):
    ok: bool = True
    course_id: str
    status: str = "ARCHIVED"
    message: str = "Course successfully archived"


class CourseReviewQueueItemResponse(BaseModel):
    version_id: str
    course_id: str
    course_code: str
    course_title: str
    version_number: str
    status: str
    created_by: str
    created_at: str
    organization_id: Optional[str] = None
    visibility: str = "PRIVATE"



class EnrollmentCreateRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    course_id: str = Field(..., min_length=1)
    course_offering_id: Optional[str] = None
    class_id: Optional[str] = None


class EnrollmentResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    course_offering_id: Optional[str] = None
    class_id: Optional[str] = None
    status: str = "ACTIVE"
    enrolled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ClassGroupCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    course_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    teacher_id: Optional[str] = None


class ClassGroupResponse(BaseModel):
    id: str
    name: str
    course_id: str
    organization_id: str
    teacher_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CohortCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    class_id: str = Field(..., min_length=1)
    course_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)


class CohortResponse(BaseModel):
    id: str
    name: str
    class_id: str
    course_id: str
    organization_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    slug: str = Field(..., min_length=2)
    id: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SanitizedQuestionItemResponse(BaseModel):
    id: str
    course_id: str
    question_text: str
    item_type: str
    options: Optional[List[str]] = None
    difficulty: float = 0.5
    bloom_level: str = "UNDERSTAND"
    hints: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class SanitizedAssessmentResponse(BaseModel):
    id: str
    course_id: str
    title: str
    assessment_type: str
    duration_minutes: int = 30
    passing_score: float = 70.0
    items: List[SanitizedQuestionItemResponse] = Field(default_factory=list)
    status: str = "PUBLISHED"


class SubsystemHealthDetail(BaseModel):
    name: str
    status: str
    latency_ms: float = 0.0
    error: Optional[str] = None
    warning: Optional[str] = None
    driver: Optional[str] = None
    total_models: Optional[int] = None
    db_path: Optional[str] = None


class PlatformHealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str
    subsystems: Dict[str, Any]



class CurriculumResponse(BaseModel):
    course_id: str
    chapters: List[Dict[str, Any]]
    total_topics: int
    total_concepts: int


# ── Plug-and-Play Curriculum (Phase 15 / Section 24) ──────────────────────

class CurriculumHierarchyResponse(BaseModel):
    curriculum_id: str
    version_id: Optional[str] = None
    course_id: str
    course_title: Optional[str] = ""
    title: str
    version: str
    status: str = "draft"
    subjects: List[Dict[str, Any]] = Field(default_factory=list)
    modules: List[Dict[str, Any]] = Field(default_factory=list)
    total_modules: int = 0
    total_topics: int = 0
    total_concepts: int = 0


class CurriculumValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    concept_count: int = 0
    cycle_nodes: List[str] = Field(default_factory=list)
    orphan_prerequisites: List[str] = Field(default_factory=list)
    dag_depth: int = 0


class CurriculumImportRequest(BaseModel):
    course_id: str
    package: Dict[str, Any]
    publish: bool = False


class CurriculumImportResponse(BaseModel):
    curriculum_id: str
    version_id: str
    version: str
    title: str
    status: str
    concept_count: int


class CurriculumVersionCreateRequest(BaseModel):
    version_num: str
    change_log: str = ""
    base_version_id: Optional[str] = None


class CurriculumVersionPublishResponse(BaseModel):
    version_id: str
    version_num: str
    status: str
    published_at: str


class CurriculumExportResponse(BaseModel):
    curriculum_id: str
    version_id: Optional[str] = None
    version: str
    title: str
    course_id: Optional[str] = None
    course_code: Optional[str] = None
    status: str = "draft"
    published_at: Optional[str] = None
    concepts: List[Dict[str, Any]] = Field(default_factory=list)
    modules: List[Dict[str, Any]] = Field(default_factory=list)


# ── Sessions & Learning Events ───────────────────────────────────────────

class SessionStartRequest(BaseModel):
    student_id: str
    course_id: str = "crs-chem-101"
    initial_concept: Optional[str] = "chem_thermo_first_law"


class SessionResponse(BaseModel):
    session_id: str
    student_id: str
    course_id: str
    active_concept: str
    status: str = "ACTIVE"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LearningEventSchema(BaseModel):
    event_id: str
    student_id: str
    session_id: str
    event_type: str = "question_attempted"
    organization_id: str = "org-default"
    course_id: str = "crs-chem-101"
    source: str = "student_desktop"
    payload: Dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "1.0.0"
    turn_id: str = "turn-01"
    concept_id: str = ""
    correctness: str = "correct"
    hint_used: int = 0
    difficulty: float = 0.5
    score: Optional[float] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    misconception_code: str = ""


# ── Assessments & Question Bank ──────────────────────────────────────────

class AssessmentItemSchema(BaseModel):
    question_id: str
    topic_id: str
    difficulty: int
    question: str
    question_type: str = "mcq"
    options: List[str] = Field(default_factory=list)


class AssessmentSubmitRequest(BaseModel):
    assessment_id: str
    student_id: str
    answers: Dict[str, Any]


class AssessmentSubmitResponse(BaseModel):
    assessment_id: str
    student_id: str
    score: float
    total_questions: int
    passed: bool
    feedback: Dict[str, Any] = Field(default_factory=dict)
    item_results: Dict[str, Any] = Field(default_factory=dict)
    reassessment_recommendations: List[str] = Field(default_factory=list)


class QuestionBankItemCreateRequest(BaseModel):
    course_id: str
    question_text: str
    item_type: str = Field(default="MCQ")  # MCQ, NUMERICAL, SHORT_ANSWER, ESSAY, CODE
    organization_id: Optional[str] = None
    subject_id: Optional[str] = None
    concept_id: str = ""
    topic_id: str = ""
    options: List[str] = Field(default_factory=list)
    correct_answer: str = ""
    rubric: Dict[str, Any] = Field(default_factory=dict)
    difficulty: int = Field(default=1, ge=1, le=5)
    bloom_level: str = Field(default="recall")
    hints: List[str] = Field(default_factory=list)
    explanation: str = ""
    tags: List[str] = Field(default_factory=list)


class QuestionBankItemResponse(BaseModel):
    id: str
    course_id: str
    question_text: str
    item_type: str
    organization_id: Optional[str] = None
    subject_id: Optional[str] = None
    concept_id: str = ""
    topic_id: str = ""
    options: List[str] = Field(default_factory=list)
    correct_answer: Optional[str] = None
    rubric: Dict[str, Any] = Field(default_factory=dict)
    difficulty: int = 1
    bloom_level: str = "recall"
    hints: List[str] = Field(default_factory=list)
    explanation: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: str
    question_id: Optional[str] = None
    question: Optional[str] = None
    question_type: Optional[str] = None

    def __init__(self, **data: Any):
        if "question_id" not in data and "id" in data:
            data["question_id"] = data["id"]
        if "question" not in data and "question_text" in data:
            data["question"] = data["question_text"]
        if "question_type" not in data and "item_type" in data:
            data["question_type"] = data["item_type"].lower()
        if "topic_id" not in data or not data["topic_id"]:
            data["topic_id"] = data.get("concept_id", "")
        super().__init__(**data)


class AssessmentCreateRequest(BaseModel):
    course_id: str
    title: str
    assessment_type: str = Field(default="formative")  # diagnostic, formative, summative, adaptive, reassessment
    organization_id: Optional[str] = None
    description: str = ""
    duration_minutes: int = 0
    passing_score: float = 70.0
    item_ids: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    rubric: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="published")


class AssessmentResponse(BaseModel):
    id: str
    course_id: str
    title: str
    assessment_type: str
    total_marks: float
    organization_id: Optional[str] = None
    description: str = ""
    duration_minutes: int = 0
    passing_score: float = 70.0
    item_ids: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    rubric: Dict[str, Any] = Field(default_factory=dict)
    status: str = "published"
    created_at: str
    updated_at: str


class AssignmentCreateRequest(BaseModel):
    course_id: str
    assessment_id: str
    title: str
    organization_id: Optional[str] = None
    cohort_id: Optional[str] = None
    class_group_id: Optional[str] = None
    instructions: str = ""
    due_at: Optional[str] = None


class AssignmentResponse(BaseModel):
    id: str
    course_id: str
    assessment_id: str
    title: str
    organization_id: Optional[str] = None
    cohort_id: Optional[str] = None
    class_group_id: Optional[str] = None
    assigned_by: Optional[str] = None
    instructions: str = ""
    due_at: Optional[str] = None
    is_active: bool = True
    created_at: str


class AttemptStartRequest(BaseModel):
    assessment_id: str
    student_id: str
    assignment_id: Optional[str] = None
    initial_difficulty: int = Field(default=2, ge=1, le=5)


class AttemptStartResponse(BaseModel):
    attempt_id: str
    assessment_id: str
    student_id: str
    assignment_id: Optional[str] = None
    attempt_number: int = 1
    status: str = "in_progress"
    started_at: str
    max_score: float = 100.0
    current_difficulty: int = 2


class AttemptSubmitRequest(BaseModel):
    answers: Dict[str, Any]
    student_id: Optional[str] = None


class AttemptDetailResponse(BaseModel):
    id: str
    assessment_id: str
    student_id: str
    assignment_id: Optional[str] = None
    attempt_number: int = 1
    status: str
    started_at: str
    completed_at: Optional[str] = None
    time_spent_seconds: int = 0
    score: float = 0.0
    max_score: float = 100.0
    percentage: float = 0.0
    passed: bool = False
    current_difficulty: int = 1
    answers: Dict[str, Any] = Field(default_factory=dict)
    item_results: Dict[str, Any] = Field(default_factory=dict)
    ai_grading_summary: Dict[str, Any] = Field(default_factory=dict)
    teacher_review: Dict[str, Any] = Field(default_factory=dict)
    reassessment_recommendations: List[str] = Field(default_factory=list)


class TeacherReviewAttemptRequest(BaseModel):
    item_score_adjustments: Dict[str, float] = Field(default_factory=dict)
    teacher_comments: str = Field(default="")
    status: str = Field(default="reviewed")


class ReassessmentGenerateRequest(BaseModel):
    original_attempt_id: str
    target_score: float = Field(default=80.0)


class ReassessmentResponse(BaseModel):
    reassessment_id: str
    original_attempt_id: str
    student_id: str
    course_id: str
    generated_assessment_id: str
    target_concepts: List[str] = Field(default_factory=list)
    status: str = "PENDING"
    target_score: float = 80.0
    created_at: str



# ── RAG & Evidence ───────────────────────────────────────────────────────

class RAGSourceCreateRequest(BaseModel):
    course_id: str
    subject: str
    title: str
    source_type: str = Field(default="text")
    authority: str = Field(default="NCERT")
    version: str = Field(default="1.0.0")
    content_type: str = Field(default="textbook")
    course_version_id: Optional[str] = None
    visibility_scope: str = Field(default="course")
    class_id: Optional[str] = None
    target_student_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGSourceResponse(BaseModel):
    id: str
    organization_id: str
    course_id: str
    subject: str
    title: str
    source_type: str
    authority: str
    version: str
    status: str
    checksum: str = ""
    chunk_count: int = 0
    content_type: str = "textbook"
    uploaded_by: Optional[str] = None
    published_by: Optional[str] = None
    published_at: Optional[str] = None
    error_message: Optional[str] = None
    course_version_id: Optional[str] = None
    visibility_scope: str = "course"
    class_id: Optional[str] = None
    target_student_ids: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class RAGIngestRequest(BaseModel):
    content: str = Field(..., min_length=1)
    file_name: str = ""
    override_source_type: Optional[str] = None


class RAGIngestResponse(BaseModel):
    source_id: str
    status: str
    sections_parsed: int
    chunks_created: int
    checksum: str


class RAGValidateResponse(BaseModel):
    valid: bool
    source_id: str
    status: str
    chunk_count: int
    average_chunk_chars: float
    concepts_covered: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RAGPublishResponse(BaseModel):
    source_id: str
    status: str
    updated_at: str


class RAGChunkResponse(BaseModel):
    id: str
    source_id: str
    course_id: str
    subject: str
    chapter: str
    topic: str
    concept: str = ""
    difficulty: float = 0.5
    page: int = 1
    section: str = ""
    content_type: str = "explanation"
    text: str
    clean_text: str
    provenance_type: str = "NCERT"
    course_version_id: Optional[str] = None
    visibility_scope: str = "course"
    class_id: Optional[str] = None
    created_at: str


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    course_id: Optional[str] = None
    subject: Optional[str] = None
    concept_id: Optional[str] = None
    course_version_id: Optional[str] = None
    class_id: Optional[str] = None
    student_id: Optional[str] = None
    top_k: int = Field(default=3, ge=1, le=20)
    confidence_threshold: float = Field(default=0.1, ge=0.0, le=1.0)


class RAGResultItem(BaseModel):
    chunk_id: str
    chapter: str
    topic: str
    page: int
    text: str
    score: float
    citation: str
    concept: Optional[str] = None
    source_id: Optional[str] = None
    course_version_id: Optional[str] = None
    visibility_scope: Optional[str] = None
    class_id: Optional[str] = None
    provenance_type: Optional[str] = None
    content_type: Optional[str] = None


class RAGQueryResponse(BaseModel):
    status: str
    query: str
    results: List[RAGResultItem]
    count: int
    data_context: Optional[str] = None
    reason: Optional[str] = None


# ── AI Gateway & Governance ──────────────────────────────────────────────

class AIExecutionApiRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None
    task_type: str = Field(default="general")
    student_id: Optional[str] = None
    course_id: Optional[str] = None
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    teacher_directives: List[str] = Field(default_factory=list)
    rag_context: Optional[str] = None


class AIExecutionApiResponse(BaseModel):
    request_id: str
    content: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    success: bool
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    fallback_used: bool = False
    original_provider: Optional[str] = None
    mock: bool = False
    status: Optional[str] = None



class AIProviderCreateRequest(BaseModel):
    provider_name: str
    provider_type: str = "mock"
    api_key_ref: str = ""
    base_url: Optional[str] = None
    enabled: bool = True
    priority: int = 1
    fallback_provider: Optional[str] = None
    rate_limit_rpm: int = 600
    daily_budget_usd: float = 50.0


class AIProviderResponse(BaseModel):
    provider_name: str
    provider_type: str
    api_key_ref: str = ""
    base_url: Optional[str] = None
    enabled: bool = True
    priority: int = 1
    fallback_provider: Optional[str] = None
    rate_limit_rpm: int = 600
    daily_budget_usd: float = 50.0
    models: List[Dict[str, Any]] = Field(default_factory=list)


class AIKillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = ""


class AIRoutePreviewRequest(BaseModel):
    task_type: str = "general"
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None


class AIRoutePreviewResponse(BaseModel):
    task_type: str
    target_provider: str
    target_model: str
    target_tier: str
    fallback_chain: List[str] = Field(default_factory=list)
    rationale: str


class AIStatusResponse(BaseModel):
    gateway_status: str = "HEALTHY"
    active_provider: str = "local_llama"
    active_model: str = "Qwen2.5-3B-Instruct-Q4_K_M"
    available_providers: List[str] = Field(default_factory=lambda: ["local_llama", "ollama", "openai", "gemini"])
    token_usage_today: int = 4210
    tokens_measured_today: int = 0
    tokens_estimated_today: int = 0
    token_provenance: str = "UNKNOWN"
    token_breakdown: Dict[str, Any] = Field(default_factory=dict)
    budget_remaining_usd: float = 98.45
    kill_switch_active: bool = False
    providers_status: Dict[str, Any] = Field(default_factory=dict)
    last_successful_inference_at: Optional[str] = None


class AIExecutionLogResponse(BaseModel):
    id: str
    request_id: str
    provider: str
    model: str
    student_id: Optional[str] = None
    session_id: Optional[str] = None
    course_id: Optional[str] = None
    task_type: str = "general"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    status: str = "SUCCESS"
    error_class: Optional[str] = None
    estimated_cost_usd: float = 0.0
    fallback_used: bool = False
    prompt_hash: str = ""
    created_at: str


class AIBudgetStatusResponse(BaseModel):
    daily_budget_usd: float
    daily_spend_usd: float
    remaining_budget_usd: float
    percentage_used: float
    budget_alert: bool
    budget_exceeded: bool


class AIBudgetUpdateRequest(BaseModel):
    daily_budget_usd: float = Field(..., gt=0.0)


class AIAllowlistUpdateRequest(BaseModel):
    models: List[str] = Field(default_factory=list)




# ── Analytics ────────────────────────────────────────────────────────────

class StudentAnalyticsResponse(BaseModel):
    student_id: str
    course_id: Optional[str] = None
    mastery: float
    mastery_distribution: Dict[str, int] = Field(default_factory=dict)
    accuracy: float
    total_questions_attempted: int
    correct_questions: int
    retention: float
    session_frequency: Dict[str, Any] = Field(default_factory=dict)
    learning_velocity: float
    weak_concepts: List[Dict[str, Any]] = Field(default_factory=list)
    review_compliance: float
    generated_at: str


class TeacherClassAnalyticsResponse(BaseModel):
    cohort_id: Optional[str] = None
    course_id: Optional[str] = None
    student_count: int
    class_mastery: float
    mastery_tiers: Dict[str, int] = Field(default_factory=dict)
    student_activity: Dict[str, Any] = Field(default_factory=dict)
    difficult_concepts: List[Dict[str, Any]] = Field(default_factory=list)
    misconceptions: List[Dict[str, Any]] = Field(default_factory=list)
    intervention_rates: Dict[str, Any] = Field(default_factory=dict)
    assessment_outcomes: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str


class CohortAnalyticsResponse(BaseModel):
    cohort_id: str = ""
    student_count: int = 0
    average_mastery: float = 0.0
    mastery_tiers: Dict[str, int] = Field(default_factory=dict)
    weak_concepts: List[str] = Field(default_factory=list)
    frequent_misconceptions: List[Dict[str, Any]] = Field(default_factory=list)
    student_activity: Optional[Dict[str, Any]] = None
    difficult_concepts: Optional[List[Dict[str, Any]]] = None
    intervention_rates: Optional[Dict[str, Any]] = None
    assessment_outcomes: Optional[Dict[str, Any]] = None


class AdminSystemAnalyticsResponse(BaseModel):
    organization_id: Optional[str] = None
    active_users: Dict[str, Any] = Field(default_factory=dict)
    course_usage: List[Dict[str, Any]] = Field(default_factory=list)
    ai_usage: Dict[str, Any] = Field(default_factory=dict)
    cost: Dict[str, Any] = Field(default_factory=dict)
    performance: Dict[str, Any] = Field(default_factory=dict)
    system_health: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str


# ── Notifications ────────────────────────────────────────────────────────

class NotificationCreateRequest(BaseModel):
    recipient_id: str
    title: str
    message: str
    channel: str = "in_app"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sync_deliver: bool = True


class NotificationBatchRequest(BaseModel):
    recipient_ids: List[str]
    title: str
    message: str
    channel: str = "in_app"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    id: str = ""
    notification_id: str = ""
    recipient_id: str
    channel: str = "in_app"
    title: str
    message: str
    status: str = "delivered"
    is_read: bool = False
    retry_count: int = 0
    delivered_at: Optional[str] = None
    error_message: Optional[str] = None
    provider_message_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str

    def __init__(self, **data):
        if "id" in data and not data.get("notification_id"):
            data["notification_id"] = data["id"]
        elif "notification_id" in data and not data.get("id"):
            data["id"] = data["notification_id"]
        super().__init__(**data)


class NotificationStatusResponse(BaseModel):
    notification_id: str
    recipient_id: str
    channel: str
    status: str
    retry_count: int
    max_retries: int
    next_retry_at: Optional[str] = None
    delivered_at: Optional[str] = None
    error_message: Optional[str] = None
    provider_message_id: Optional[str] = None
    is_read: bool = False


class NotificationQueueStatsResponse(BaseModel):
    pending_count: int
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_channel: Dict[str, int] = Field(default_factory=dict)


# ── Sync ─────────────────────────────────────────────────────────────────

class BatchSyncEventsRequest(BaseModel):
    student_id: str
    events: List[Dict[str, Any]]
    operation_id: Optional[str] = None
    course_id: Optional[str] = None
    device_id: Optional[str] = None
    course_version: Optional[str] = None


class BatchSyncEventsResponse(BaseModel):
    ok: bool = True
    operation_id: Optional[str] = None
    synced_count: int
    duplicate_count: int = 0
    failed_count: int = 0
    acknowledged_ids: List[str] = Field(default_factory=list)
    conflicts_resolved: int = 0
    status: str = "SYNCED"
    latest_mastery: float = 0.50
    server_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_replay: bool = False
    sequence_gaps: List[Dict[str, int]] = Field(default_factory=list)


class SyncStatusResponse(BaseModel):
    student_id: str
    course_id: str
    total_operations: int
    total_synced_events: int
    registered_devices: List[str] = Field(default_factory=list)
    last_operation_id: Optional[str] = None
    last_synced_at: Optional[str] = None
    latest_mastery: float = 0.0
    status: str = "HEALTHY"


class DeviceBindRequest(BaseModel):
    device_id: str
    student_id: str
    organization_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = "desktop"


class DeviceBindResponse(BaseModel):
    device_id: str
    student_id: str
    device_name: Optional[str] = None
    status: str = "ACTIVE"
    bound_at: str


class DeviceListItem(BaseModel):
    device_id: str
    student_id: str
    organization_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: str = "desktop"
    status: str = "ACTIVE"
    bound_at: str
    last_synced_at: Optional[str] = None




# ── Student Actions & Learning Engine Bridge (Phase 07) ─────────────────

class StudentActionRequest(BaseModel):
    concept_id: str
    action_type: str = "answer_submitted"
    course_id: str = "crs-chem-101"
    session_id: Optional[str] = None
    turn_id: Optional[str] = None
    question_id: Optional[str] = None
    student_answer: Optional[str] = None
    correctness: Optional[str] = None
    score: Optional[float] = None
    hint_level: int = 0
    difficulty: Optional[float] = None
    response_time_ms: Optional[float] = None
    misconception_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Teacher Copilot (Phase 13 / Section 22) ───────────────────────────────

class CopilotEvidenceItemSchema(BaseModel):
    evidence_id: str
    category: str
    concept_id: Optional[str] = None
    metric_value: Optional[float] = None
    description: str = ""
    timestamp: Optional[str] = None


class CopilotSourceRecordSchema(BaseModel):
    record_id: str
    record_type: str
    timestamp: str = ""
    summary: str = ""


class CopilotCitationSchema(BaseModel):
    evidence_id: str
    category: str
    summary: str


class TeacherCopilotQueryRequest(BaseModel):
    query: str
    student_id: Optional[str] = None
    course_id: Optional[str] = None
    time_window_days: Optional[int] = 7


class TeacherCopilotQueryResponse(BaseModel):
    answer: str
    evidence: List[CopilotEvidenceItemSchema] = Field(default_factory=list)
    source_records: List[CopilotSourceRecordSchema] = Field(default_factory=list)
    confidence: float = 1.0
    recommended_action: str = ""
    citations: List[CopilotCitationSchema] = Field(default_factory=list)
    summary: Optional[str] = None
    recommended_focus_concept: Optional[str] = None
    query: Optional[str] = None
    student_id: Optional[str] = None
    course_id: Optional[str] = None


# ── Admin Portal (Phase 14 / Section 23) ──────────────────────────────────

class AdminDashboardResponse(BaseModel):
    organizations_count: int = 0
    total_users: int = 0
    teachers_count: int = 0
    students_count: int = 0
    courses_count: int = 0
    curricula_count: int = 0
    classes_count: int = 0
    cohorts_count: int = 0
    enrollments_count: int = 0
    active_models_count: int = 0
    system_status: str = "HEALTHY"
    kill_switch_active: bool = False
    ai_policy_level: str = "strict"


class AdminUserCreateRequest(BaseModel):
    email: str
    full_name: str
    role: str  # SUPER_ADMIN, ORG_ADMIN, COURSE_ADMIN, TEACHER, STUDENT
    organization_id: Optional[str] = None
    password: Optional[str] = "TemporaryPass123!"


class AdminUserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    organization_id: Optional[str] = None


class AdminUserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    organization_id: Optional[str] = None
    is_active: bool = True
    created_at: str
    updated_at: str


class AdminOrganizationCreateRequest(BaseModel):
    name: str
    slug: str
    tier: Optional[str] = "STANDARD"
    student_quota: Optional[int] = 250


class AdminOrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    tier: str = "STANDARD"
    student_quota: int = 250
    created_at: str


class AdminCourseCreateRequest(BaseModel):
    code: str
    title: str
    description: Optional[str] = ""
    organization_id: Optional[str] = None


class AdminCourseResponse(BaseModel):
    id: str
    organization_id: Optional[str] = None
    code: str
    title: str
    description: str = ""
    created_at: str


class AdminCurriculumCreateRequest(BaseModel):
    course_id: str
    title: str
    version: str = "v1.0"
    is_active: bool = True


class AdminCurriculumResponse(BaseModel):
    id: str
    course_id: str
    title: str
    version: str
    is_active: bool = True
    created_at: str


class AdminClassCreateRequest(BaseModel):
    name: str
    section: str
    course_id: str
    organization_id: Optional[str] = None


class AdminClassResponse(BaseModel):
    id: str
    organization_id: Optional[str] = None
    course_id: str
    name: str
    section: str
    created_at: str


class AdminCohortCreateRequest(BaseModel):
    name: str
    academic_year: str
    class_group_id: str


class AdminCohortResponse(BaseModel):
    id: str
    class_group_id: str
    name: str
    academic_year: str
    created_at: str


class AdminEnrollmentCreateRequest(BaseModel):
    student_id: str
    course_id: str
    cohort_id: Optional[str] = None


class AdminEnrollmentResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    cohort_id: Optional[str] = None
    enrolled_at: str
    is_active: bool = True


class AdminAIProviderCreateRequest(BaseModel):
    name: str
    provider_type: str  # local, anthropic, openai, vllm, ollama
    base_url: Optional[str] = ""
    is_active: bool = True


class AdminAIProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str = ""
    is_active: bool = True
    created_at: str


class AdminAIModelCreateRequest(BaseModel):
    provider_id: str
    model_name: str
    context_window: Optional[int] = 8192
    is_default: bool = False


class AdminAIModelResponse(BaseModel):
    id: str
    provider_id: str
    model_name: str
    context_window: int = 8192
    is_default: bool = False
    created_at: str


class AdminAIPolicyUpdateRequest(BaseModel):
    ai_policy_level: Optional[str] = None  # strict, balanced, permissive
    anti_answer_leakage: Optional[bool] = None
    max_tokens_per_turn: Optional[int] = None
    temperature: Optional[float] = None


class AdminAIPolicyResponse(BaseModel):
    ai_policy_level: str = "strict"
    anti_answer_leakage: bool = True
    max_tokens_per_turn: int = 1024
    temperature: float = 0.2
    updated_at: str


class AdminFeatureFlagsUpdateRequest(BaseModel):
    flags: Dict[str, bool]


class AdminFeatureFlagsResponse(BaseModel):
    flags: Dict[str, bool]
    updated_at: str


class AdminAuditEventResponse(BaseModel):
    id: str
    actor_id: str
    actor_role: str
    action: str
    target_entity: str
    target_id: str
    organization_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str


# ── Course Tools (Phase 08) ──────────────────────────────────────────────

class ToolCapabilityResponse(BaseModel):
    tool_id: str
    name: str
    description: str
    category: str
    allowed_roles: List[str] = Field(default_factory=list)
    resource_limits: Dict[str, Any] = Field(default_factory=dict)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)


class ToolExecuteRequest(BaseModel):
    tool_id: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    course_id: str = "crs-chem-101"
    session_id: Optional[str] = None


class ToolExecuteResponse(BaseModel):
    tool_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    resource_usage: Dict[str, Any] = Field(default_factory=dict)



