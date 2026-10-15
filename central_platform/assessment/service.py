"""Authoritative Unified Assessment Service for Gayatri AI Platform (Phase 19).

Fulfills Master Plan Section 28:
- Question Bank management (CRUD, filtering, difficulty, Bloom levels, Rubrics)
- Diagnostic, Formative, Summative, and Adaptive assessments
- Assignment distribution & student attempts
- Hybrid grading (deterministic + AI-assisted rubric grading)
- Teacher manual reviews, adjustments, and approvals
- Targeted reassessment generation for weak concepts
- Complete integration with Learning Event Store & Authoritative SLR
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("gayatri.central_platform.assessment.service")

from central_platform.assessment.adaptive import AdaptiveTestingEngine
from central_platform.assessment.grading import AssessmentGradingEngine
from central_platform.assessment.models import (
    AdaptiveState,
    AssessmentType,
    AttemptStatus,
    ItemGradingResult,
    Rubric,
)
from central_platform.assessment.rubrics import RubricEngine
from central_platform.db import PlatformDatabase
from central_platform.events.models import LearningEventIngest
from central_platform.events.store import LearningEventStore
from central_platform.events.types import LearningEventType
from central_platform.models.schema import (
    Assessment,
    AssessmentAttempt,
    AssessmentItem,
    Assignment,
    Course,
    Organization,
    QuestionBankItem,
    Reassessment,
    Session,
    SessionStatus,
    User,
    UserRole,
)
from central_platform.assessment.sanitizer import AssessmentSanitizer
from central_platform.slr.service import SLRService


class AssessmentService:
    """Central service managing the entire assessment lifecycle, question banks, grading, and SLR sync."""

    def __init__(
        self,
        db: Optional[PlatformDatabase] = None,
        event_store: Optional[LearningEventStore] = None,
        slr_service: Optional[SLRService] = None,
        allow_auto_provision: bool = False,
    ):
        self.db = db or PlatformDatabase()
        self.event_store = event_store or LearningEventStore(self.db)
        self.slr_service = slr_service or SLRService(self.db, self.event_store)
        self.allow_auto_provision = allow_auto_provision

    def _ensure_entities(
        self,
        course_id: Optional[str] = None,
        org_id: Optional[str] = None,
        student_id: Optional[str] = None,
    ) -> None:
        """Ensure parent foreign key entities exist before writing items.

        Under production policy (allow_auto_provision=False), fail closed if
        referenced organization, student, or course does not exist.
        """
        if self.allow_auto_provision:
            effective_org = org_id or "org-default"
            try:
                if not self.db.get_organization(effective_org):
                    self.db.create_organization(Organization(id=effective_org, name="Default Organization", slug=f"slug-{effective_org}"))
            except Exception as exc:
                logger.warning("Failed to auto-provision organization %s: %s", effective_org, exc)

            if student_id:
                try:
                    if not self.db.get_user(student_id):
                        self.db.create_user(
                            User(
                                id=student_id,
                                email=f"{student_id}@student.gayatri.ai",
                                full_name=student_id,
                                role=UserRole.STUDENT,
                                organization_id=effective_org,
                            )
                        )
                except Exception as exc:
                    logger.warning("Failed to auto-provision student %s: %s", student_id, exc)

            effective_course = course_id or "crs-general-101"
            try:
                if not self.db.get_course(effective_course):
                    course_code = "CHEM101" if "chem" in effective_course.lower() else effective_course.upper()[:10]
                    course_title = "General Chemistry" if "chem" in effective_course.lower() else f"Course {effective_course}"
                    self.db.create_course(
                        Course(
                            id=effective_course,
                            organization_id=effective_org,
                            code=course_code,
                            title=course_title,
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to auto-provision course %s: %s", effective_course, exc)
            return

        # Fail closed on non-existent entities
        if org_id and not self.db.get_organization(org_id):
            raise ValueError(f"Organization '{org_id}' not found.")

        if student_id:
            user = self.db.get_user(student_id)
            if not user:
                raise ValueError(f"Student '{student_id}' not found.")
            if org_id and user.organization_id and user.organization_id != org_id:
                raise ValueError(f"Student '{student_id}' belongs to organization '{user.organization_id}', not '{org_id}'.")

        if course_id and not self.db.get_course(course_id):
            raise ValueError(f"Course '{course_id}' not found.")

    # ── 1. Question Bank Operations ──────────────────────────────────────────

    def create_question(self, item: QuestionBankItem) -> QuestionBankItem:
        """Create or update a question in the question bank."""
        if not item.id:
            item.id = f"qb-{uuid.uuid4().hex[:10]}"
        self._ensure_entities(course_id=item.course_id, org_id=item.organization_id)
        return self.db.create_question_bank_item(item)

    def get_question(self, item_id: str) -> Optional[QuestionBankItem]:
        """Retrieve question by ID."""
        return self.db.get_question_bank_item(item_id)

    def list_questions(
        self,
        course_id: Optional[str] = None,
        concept_id: Optional[str] = None,
        difficulty: Optional[int] = None,
        item_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[QuestionBankItem]:
        """Query and filter question bank items."""
        return self.db.list_question_bank_items(
            course_id=course_id,
            concept_id=concept_id,
            difficulty=difficulty,
            item_type=item_type,
            limit=limit,
        )

    def bulk_create_questions(self, items: List[QuestionBankItem]) -> List[QuestionBankItem]:
        """Bulk insert question bank items."""
        created = []
        for it in items:
            created.append(self.create_question(it))
        return created

    # ── 2. Assessment Definition Management ──────────────────────────────────

    def create_assessment(self, assessment: Assessment) -> Assessment:
        """Define an assessment (Diagnostic, Formative, Summative, Adaptive, etc.)."""
        if not assessment.id:
            assessment.id = f"asmt-{uuid.uuid4().hex[:10]}"
        if not assessment.created_at:
            assessment.created_at = datetime.now(timezone.utc).isoformat()
        self._ensure_entities(course_id=assessment.course_id, org_id=assessment.organization_id)

        # Deduplicate item_ids while preserving order
        if assessment.item_ids:
            seen = set()
            deduped = []
            for iid in assessment.item_ids:
                if iid not in seen:
                    seen.add(iid)
                    deduped.append(iid)
            assessment.item_ids = deduped

            # Validate question item course and tenant boundaries
            if not self.allow_auto_provision:
                for iid in assessment.item_ids:
                    item = self.get_question(iid)
                    if item:
                        if item.course_id and assessment.course_id and item.course_id != assessment.course_id:
                            raise ValueError(
                                f"Cross-course contamination: Question item '{iid}' belongs to course '{item.course_id}', "
                                f"not assessment course '{assessment.course_id}'."
                            )
                        if item.organization_id and assessment.organization_id and item.organization_id != assessment.organization_id:
                            raise ValueError(
                                f"Cross-tenant contamination: Question item '{iid}' belongs to organization '{item.organization_id}', "
                                f"not assessment organization '{assessment.organization_id}'."
                            )

        return self.db.create_assessment(assessment)

    def get_assessment(self, assessment_id: str) -> Optional[Assessment]:
        """Retrieve assessment definition by ID."""
        return self.db.get_assessment(assessment_id)

    def list_assessments(
        self,
        course_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        assessment_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Assessment]:
        """List assessments with optional filters."""
        return self.db.list_assessments(
            course_id=course_id,
            organization_id=organization_id,
            assessment_type=assessment_type,
            status=status,
            limit=limit,
        )

    def publish_assessment(self, assessment_id: str) -> Optional[Assessment]:
        """Publish an assessment to make it available for assignment and testing."""
        asmt = self.get_assessment(assessment_id)
        if not asmt:
            return None
        asmt.status = "published"
        asmt.updated_at = datetime.now(timezone.utc).isoformat()
        return self.db.create_assessment(asmt)

    def get_sanitized_assessment(self, assessment_id: str, allow_hints: bool = False) -> Optional[Dict[str, Any]]:
        """Retrieve assessment and its items safely sanitized for student examination without answer leakage."""
        asmt = self.get_assessment(assessment_id)
        if not asmt:
            return None

        # Fetch items
        items = []
        for item_id in asmt.item_ids:
            qb_item = self.get_question(item_id)
            if qb_item:
                items.append(qb_item)

        return AssessmentSanitizer.sanitize_assessment_for_student(asmt, items, allow_hints=allow_hints)

    # ── 3. Assignment Distribution ───────────────────────────────────────────

    def create_assignment(self, assignment: Assignment) -> Assignment:
        """Assign an assessment to a cohort, class group, or course."""
        if not assignment.id:
            assignment.id = f"assign-{uuid.uuid4().hex[:10]}"
        if not assignment.created_at:
            assignment.created_at = datetime.now(timezone.utc).isoformat()
        self._ensure_entities(course_id=assignment.course_id, org_id=assignment.organization_id)
        return self.db.create_assignment(assignment)

    def get_assignment(self, assignment_id: str) -> Optional[Assignment]:
        """Retrieve assignment details."""
        return self.db.get_assignment(assignment_id)

    def list_assignments(
        self,
        course_id: Optional[str] = None,
        cohort_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Assignment]:
        """List active assignments."""
        return self.db.list_assignments(
            course_id=course_id,
            cohort_id=cohort_id,
            organization_id=organization_id,
            limit=limit,
        )

    # ── 4. Assessment Attempt Lifecycle ──────────────────────────────────────

    def start_attempt(
        self,
        assessment_id: str,
        student_id: str,
        assignment_id: Optional[str] = None,
        initial_difficulty: int = 2,
    ) -> AssessmentAttempt:
        """Start a new assessment attempt."""
        asmt = self.get_assessment(assessment_id)
        if not asmt:
            raise ValueError(f"Assessment '{assessment_id}' not found.")

        self._ensure_entities(course_id=asmt.course_id, org_id=asmt.organization_id, student_id=student_id)

        # Determine existing attempt count for student
        existing_attempts = self.get_student_attempts(student_id)
        asmt_attempts = [a for a in existing_attempts if a.assessment_id == assessment_id]
        attempt_num = len(asmt_attempts) + 1

        attempt_id = f"att-{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Handle adaptive state
        adaptive_state_dict = {}
        if asmt.assessment_type == AssessmentType.ADAPTIVE:
            target_concepts = asmt.config.get("target_concepts", [])
            state = AdaptiveTestingEngine.initialize_state(target_concepts, initial_difficulty)
            adaptive_state_dict = state.to_dict()

        attempt = AssessmentAttempt(
            id=attempt_id,
            assessment_id=assessment_id,
            student_id=student_id,
            assignment_id=assignment_id,
            attempt_number=attempt_num,
            status=AttemptStatus.IN_PROGRESS.value,
            started_at=now_iso,
            max_score=asmt.total_marks,
            current_difficulty=initial_difficulty,
            answers={"_adaptive_state": adaptive_state_dict} if adaptive_state_dict else {},
        )
        return self.db.record_assessment_attempt(attempt)

    def get_next_adaptive_item(self, attempt_id: str) -> Optional[QuestionBankItem]:
        """Select next optimal question item for an active adaptive attempt."""
        attempt = self.db.get_assessment_attempt(attempt_id)
        if not attempt:
            raise ValueError(f"Attempt '{attempt_id}' not found.")

        asmt = self.get_assessment(attempt.assessment_id)
        if not asmt or asmt.assessment_type != AssessmentType.ADAPTIVE:
            return None

        state_data = attempt.answers.get("_adaptive_state", {})
        adaptive_state = AdaptiveState(
            current_difficulty=state_data.get("current_difficulty", 2),
            consecutive_correct=state_data.get("consecutive_correct", 0),
            consecutive_incorrect=state_data.get("consecutive_incorrect", 0),
            tested_concepts=state_data.get("tested_concepts", []),
            remaining_concepts=state_data.get("remaining_concepts", []),
            items_administered=state_data.get("items_administered", []),
            history=state_data.get("history", []),
        )

        # Get candidates from question bank matching course or concept scope
        candidates = []
        if asmt.item_ids:
            for iid in asmt.item_ids:
                q = self.get_question(iid)
                if q:
                    candidates.append(q)
        else:
            candidates = self.list_questions(course_id=asmt.course_id, limit=200)

        next_item = AdaptiveTestingEngine.select_next_item(candidates, adaptive_state)
        return next_item

    def record_adaptive_response(
        self,
        attempt_id: str,
        item_id: str,
        student_answer: Any,
    ) -> Tuple[AssessmentAttempt, ItemGradingResult]:
        """Record and immediately evaluate response in adaptive test to adjust difficulty."""
        attempt = self.db.get_assessment_attempt(attempt_id)
        if not attempt:
            raise ValueError(f"Attempt '{attempt_id}' not found.")

        item = self.get_question(item_id)
        if not item:
            raise ValueError(f"Question item '{item_id}' not found.")

        # Grade single item
        grading_res = AssessmentGradingEngine.grade_submission([item], {item_id: student_answer})
        item_result_dict = grading_res["item_results"].get(item_id, {})
        is_correct = bool(item_result_dict.get("is_correct", False))

        state_data = attempt.answers.get("_adaptive_state", {})
        adaptive_state = AdaptiveState(
            current_difficulty=state_data.get("current_difficulty", 2),
            consecutive_correct=state_data.get("consecutive_correct", 0),
            consecutive_incorrect=state_data.get("consecutive_incorrect", 0),
            tested_concepts=state_data.get("tested_concepts", []),
            remaining_concepts=state_data.get("remaining_concepts", []),
            items_administered=state_data.get("items_administered", []),
            history=state_data.get("history", []),
        )

        updated_state = AdaptiveTestingEngine.update_state_on_response(adaptive_state, item, is_correct)
        attempt.answers[item_id] = student_answer
        attempt.answers["_adaptive_state"] = updated_state.to_dict()
        attempt.item_results[item_id] = item_result_dict
        attempt.current_difficulty = updated_state.current_difficulty

        self.db.record_assessment_attempt(attempt)
        return attempt, ItemGradingResult(**item_result_dict)

    def submit_attempt(
        self,
        attempt_id: str,
        answers: Dict[str, Any],
        student_id: Optional[str] = None,
    ) -> AssessmentAttempt:
        """Submit assessment answers, execute hybrid grading, and feed central learning events."""
        attempt = self.db.get_assessment_attempt(attempt_id)
        if not attempt:
            raise ValueError(f"Attempt '{attempt_id}' not found.")

        if attempt.status in (AttemptStatus.GRADED.value, AttemptStatus.SUBMITTED.value, "reviewed", AttemptStatus.ABANDONED.value, "expired"):
            raise ValueError(f"Attempt '{attempt_id}' is already finalized or closed (status: {attempt.status}).")

        if student_id and attempt.student_id != student_id:
            raise ValueError(f"Student ID mismatch: attempt '{attempt_id}' belongs to '{attempt.student_id}', but was submitted by '{student_id}'.")

        asmt = self.get_assessment(attempt.assessment_id)
        if not asmt:
            raise ValueError(f"Assessment '{attempt.assessment_id}' not found.")

        # Check duration limit if configured (with 5 minute grace period)
        if asmt.duration_minutes and asmt.duration_minutes > 0 and attempt.started_at:
            started_dt = datetime.fromisoformat(attempt.started_at)
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            elapsed_minutes = (now_dt - started_dt).total_seconds() / 60.0
            max_allowed_minutes = float(asmt.duration_minutes) + 5.0
            if elapsed_minutes > max_allowed_minutes:
                attempt.status = AttemptStatus.ABANDONED.value
                self.db.record_assessment_attempt(attempt)
                raise ValueError(
                    f"Attempt '{attempt_id}' has expired. Time limit of {asmt.duration_minutes} minutes exceeded "
                    f"({round(elapsed_minutes, 1)} minutes elapsed)."
                )

        # Retrieve items to grade
        items_to_grade: List[QuestionBankItem] = []
        if asmt.item_ids:
            for iid in asmt.item_ids:
                q = self.get_question(iid)
                if q:
                    items_to_grade.append(q)
        elif asmt.assessment_type == AssessmentType.ADAPTIVE:
            # In adaptive, grade all items answered in this session
            for q_id in answers.keys():
                if q_id.startswith("_"):
                    continue
                q = self.get_question(q_id)
                if q:
                    items_to_grade.append(q)
        else:
            # Fallback to course items
            items_to_grade = self.list_questions(course_id=asmt.course_id, limit=50)

        # Build rubric if defined on assessment
        assessment_rubric = None
        if asmt.rubric:
            criteria_list = []
            for c_id, c_data in asmt.rubric.get("criteria", {}).items():
                criteria_list.append(
                    RubricEngine.get_standard_rubrics().get(
                        c_id,
                        RubricEngine.get_standard_rubrics()["stem_problem_solving"].criteria[0]
                    )
                )
            if criteria_list:
                assessment_rubric = Rubric(
                    rubric_id=asmt.rubric.get("rubric_id", f"rubric_{asmt.id}"),
                    title=asmt.rubric.get("title", asmt.title),
                    criteria=criteria_list,
                )

        # Execute Hybrid Grading
        grade_results = AssessmentGradingEngine.grade_submission(
            items=items_to_grade,
            answers=answers,
            assessment_rubric=assessment_rubric,
            passing_threshold=asmt.passing_score,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        started_dt = datetime.fromisoformat(attempt.started_at) if attempt.started_at else datetime.now(timezone.utc)
        completed_dt = datetime.fromisoformat(now_iso)
        time_spent = int((completed_dt - started_dt).total_seconds())

        attempt.status = AttemptStatus.GRADED.value
        attempt.completed_at = now_iso
        attempt.time_spent_seconds = max(1, time_spent)
        attempt.score = grade_results["total_score"]
        attempt.max_score = grade_results["max_score"]
        attempt.percentage = grade_results["percentage"]
        attempt.passed = grade_results["passed"]
        attempt.answers = answers
        attempt.item_results = grade_results["item_results"]
        attempt.ai_grading_summary = grade_results["ai_grading_summary"]
        attempt.reassessment_recommendations = grade_results["reassessment_recommendations"]

        self.db.record_assessment_attempt(attempt)

        # ── CRITICAL INVARIANT: Emit Learning Events & Sync SLR ─────────────
        self._emit_assessment_learning_events(attempt, asmt, items_to_grade, grade_results)

        return attempt

    def _emit_assessment_learning_events(
        self,
        attempt: AssessmentAttempt,
        asmt: Assessment,
        items: List[QuestionBankItem],
        grade_results: Dict[str, Any],
    ) -> None:
        """Feed assessment outcomes into Central Learning Event Store and SLR."""
        session_id = f"sess-asmt-{attempt.id}"
        student_id = attempt.student_id
        course_id = asmt.course_id
        org_id = asmt.organization_id or "org-default"

        # 1. Ingest individual question attempt events
        for item in items:
            item_res = grade_results["item_results"].get(item.id, {})
            score_val = item_res.get("score", 0.0) / max(item_res.get("max_marks", 1.0), 1e-4)

            q_event = LearningEventIngest(
                event_id=f"evt-asmt-{attempt.id}-{item.id}",
                session_id=session_id,
                student_id=student_id,
                organization_id=org_id,
                course_id=course_id,
                concept_id=item.concept_id or "",
                event_type=LearningEventType.QUESTION_ATTEMPTED,
                score=score_val,
                source="assessment_platform",
                payload={
                    "assessment_id": asmt.id,
                    "assessment_type": asmt.assessment_type.value if hasattr(asmt.assessment_type, "value") else str(asmt.assessment_type),
                    "item_id": item.id,
                    "item_type": item.item_type,
                    "is_correct": item_res.get("is_correct", False),
                    "score": item_res.get("score", 0.0),
                    "max_marks": item_res.get("max_marks", 0.0),
                    "ai_graded": item_res.get("ai_graded", False),
                    "misconception_code": item_res.get("misconception_code"),
                },
            )
            self.event_store.ingest_event(q_event)

            # If a misconception was detected, record it
            misc_code = item_res.get("misconception_code")
            if misc_code:
                misc_event = LearningEventIngest(
                    event_id=f"evt-misc-{attempt.id}-{item.id}",
                    session_id=session_id,
                    student_id=student_id,
                    organization_id=org_id,
                    course_id=course_id,
                    concept_id=item.concept_id or "",
                    event_type=LearningEventType.MISCONCEPTION_DETECTED,
                    score=0.0,
                    source="assessment_ai_grader",
                    payload={"misconception_code": misc_code, "item_id": item.id},
                )
                self.event_store.ingest_event(misc_event)

        # 2. Ingest overall assessment completed event
        overall_score = grade_results["percentage"] / 100.0
        complete_event = LearningEventIngest(
            event_id=f"evt-asmt-complete-{attempt.id}",
            session_id=session_id,
            student_id=student_id,
            organization_id=org_id,
            course_id=course_id,
            concept_id="",
            event_type=LearningEventType.ASSESSMENT_COMPLETED,
            score=overall_score,
            source="assessment_platform",
            payload={
                "assessment_id": asmt.id,
                "assessment_title": asmt.title,
                "assessment_type": asmt.assessment_type.value if hasattr(asmt.assessment_type, "value") else str(asmt.assessment_type),
                "total_score": attempt.score,
                "max_score": attempt.max_score,
                "percentage": attempt.percentage,
                "passed": attempt.passed,
                "weak_concepts": grade_results["reassessment_recommendations"],
            },
        )
        self.event_store.ingest_event(complete_event)

        # 3. Synchronize verified assessment outcomes directly with authoritative SLR
        for item in items:
            if item.concept_id:
                item_res = grade_results["item_results"].get(item.id, {})
                score_val = item_res.get("score", 0.0) / max(item_res.get("max_marks", 1.0), 1e-4)
                try:
                    self.slr_service.update_concept_mastery(
                        student_id=student_id,
                        concept_id=item.concept_id,
                        score=score_val,
                        course_id=course_id,
                    )
                except Exception as exc:
                    logger.warning("Failed to update SLR concept mastery for %s: %s", item.concept_id, exc)

                misc_code = item_res.get("misconception_code")
                if misc_code:
                    try:
                        self.slr_service.record_student_misconception(
                            student_id=student_id,
                            concept_id=item.concept_id,
                            misconception_code=misc_code,
                            course_id=course_id,
                        )
                    except Exception as exc:
                        logger.warning("Failed to record SLR misconception %s: %s", misc_code, exc)

    def teacher_review_attempt(
        self,
        attempt_id: str,
        teacher_id: str,
        item_score_adjustments: Dict[str, float],
        teacher_comments: str = "",
        status: str = "reviewed",
    ) -> AssessmentAttempt:
        """Allow teacher to inspect, adjust scores per question, and sign off on an attempt."""
        attempt = self.db.get_assessment_attempt(attempt_id)
        if not attempt:
            raise ValueError(f"Attempt '{attempt_id}' not found.")

        asmt = self.get_assessment(attempt.assessment_id)
        passing_threshold = asmt.passing_score if asmt else 70.0

        # Apply score adjustments
        new_total_score = 0.0
        for item_id, item_data in attempt.item_results.items():
            if item_id in item_score_adjustments:
                adj_score = float(item_score_adjustments[item_id])
                item_data["score"] = adj_score
                item_data["teacher_adjusted"] = True
                item_data["teacher_comment"] = teacher_comments
                max_m = item_data.get("max_marks", 4.0)
                item_data["is_correct"] = (adj_score / max(max_m, 1e-4)) >= 0.70
                item_data["percentage"] = round((adj_score / max(max_m, 1e-4)) * 100.0, 2)
            new_total_score += item_data.get("score", 0.0)

        attempt.score = round(new_total_score, 2)
        attempt.percentage = round((attempt.score / max(attempt.max_score, 1e-4)) * 100.0, 2)
        attempt.passed = attempt.percentage >= passing_threshold
        attempt.status = status
        attempt.teacher_id = teacher_id
        attempt.teacher_feedback = teacher_comments
        attempt.teacher_review = {
            "teacher_id": teacher_id,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "comments": teacher_comments,
            "teacher_comments": teacher_comments,
            "adjusted_items": list(item_score_adjustments.keys()),
            "status": status,
        }

        self.db.record_assessment_attempt(attempt)
        return attempt

    def review_attempt(
        self,
        attempt_id: str,
        teacher_id: str,
        score_adjustments: Optional[Dict[str, float]] = None,
        teacher_feedback: str = "",
        approved: bool = True,
        status: Optional[str] = None,
    ) -> AssessmentAttempt:
        """Alias and ergonomic wrapper for teacher review of student attempts."""
        effective_status = status or ("graded" if approved else "in_review")
        return self.teacher_review_attempt(
            attempt_id=attempt_id,
            teacher_id=teacher_id,
            item_score_adjustments=score_adjustments or {},
            teacher_comments=teacher_feedback,
            status=effective_status,
        )

    # ── 5. Reassessment & Remediation ────────────────────────────────────────

    def generate_reassessment(
        self,
        original_attempt_id: str,
        target_score: float = 80.0,
    ) -> Tuple[Assessment, Reassessment]:
        """Generate targeted diagnostic/adaptive reassessment focused on weak concepts."""
        original_attempt = self.db.get_assessment_attempt(original_attempt_id)
        if not original_attempt:
            raise ValueError(f"Original attempt '{original_attempt_id}' not found.")

        original_asmt = self.get_assessment(original_attempt.assessment_id)
        if not original_asmt:
            raise ValueError(f"Assessment '{original_attempt.assessment_id}' not found.")

        weak_concepts = original_attempt.reassessment_recommendations or []
        if not weak_concepts:
            # If no explicit recommendations, check items with score < 70%
            for iid, r in original_attempt.item_results.items():
                if not r.get("is_correct", False):
                    q = self.get_question(iid)
                    if q and q.concept_id:
                        weak_concepts.append(q.concept_id)
            weak_concepts = list(set(weak_concepts))

        # Build targeted reassessment definition
        re_asmt_id = f"asmt-re-{uuid.uuid4().hex[:8]}"
        re_asmt = Assessment(
            id=re_asmt_id,
            course_id=original_asmt.course_id,
            organization_id=original_asmt.organization_id,
            title=f"Reassessment: {original_asmt.title} Remediation",
            description=f"Targeted reassessment addressing {len(weak_concepts)} weak concepts.",
            assessment_type=AssessmentType.REASSESSMENT,
            duration_minutes=original_asmt.duration_minutes,
            passing_score=target_score,
            total_marks=50.0,
            config={"target_concepts": weak_concepts, "original_attempt_id": original_attempt_id},
            status="published",
        )
        self.create_assessment(re_asmt)

        # Record reassessment tracking entity
        reassessment_rec = Reassessment(
            id=f"re-{uuid.uuid4().hex[:8]}",
            original_attempt_id=original_attempt_id,
            student_id=original_attempt.student_id,
            course_id=original_asmt.course_id,
            generated_assessment_id=re_asmt_id,
            target_concepts=weak_concepts,
            status="PENDING",
            target_score=target_score,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.create_reassessment(reassessment_rec)

        return re_asmt, reassessment_rec

    def get_student_attempts(self, student_id: str, limit: int = 50) -> List[AssessmentAttempt]:
        """List all assessment attempts for a student."""
        return self.db.get_assessment_attempts_for_student(student_id, limit=limit)

    def get_attempt(self, attempt_id: str) -> Optional[AssessmentAttempt]:
        """Get assessment attempt details."""
        return self.db.get_assessment_attempt(attempt_id)
