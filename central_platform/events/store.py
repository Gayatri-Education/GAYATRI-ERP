"""Authoritative Learning Event Store and Replay Projection Engine (Phase 05).

Master Plan Section 14:
- Append-only immutable persistence
- Idempotent ingestion and deduplication by event_id
- Multi-tenant and student-scoped time-series querying
- Chronological event replay projection for mastery, misconceptions, and hints
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("gayatri.central_platform.events.store")

from central_platform.db import PlatformDatabase
from central_platform.events.models import (
    BatchLearningEventIngest,
    LearningEventFilter,
    LearningEventIngest,
    ReplayProjectionResult,
)
from central_platform.events.types import LearningEventType
from central_platform.models.schema import (
    Course,
    LearningEvent,
    Organization,
    Session,
    SessionStatus,
    User,
    UserRole,
)


class LearningEventStore:
    """Authoritative event store managing immutable learning events and state projection."""

    def __init__(self, db: Optional[PlatformDatabase] = None):
        self.db = db or PlatformDatabase()

    def _ensure_entities(
        self,
        student_id: str,
        session_id: str,
        organization_id: Optional[str] = None,
        course_id: Optional[str] = None,
    ) -> None:
        """Ensure parent foreign key entities exist before appending event."""
        org_id = organization_id or "org-default"
        try:
            if not self.db.get_organization(org_id):
                self.db.create_organization(Organization(id=org_id, name="Default Organization", slug=f"slug-{org_id}"))
        except Exception as exc:
            logger.warning("Failed to auto-provision organization %s: %s", org_id, exc)

        try:
            if not self.db.get_user(student_id):
                self.db.create_user(
                    User(
                        id=student_id,
                        email=f"{student_id}@student.gayatri.ai",
                        full_name=student_id,
                        role=UserRole.STUDENT,
                        organization_id=org_id,
                    )
                )
        except Exception as exc:
            logger.warning("Failed to auto-provision student %s: %s", student_id, exc)

        c_id = course_id or "crs-default"
        try:
            if not self.db.get_course(c_id):
                self.db.create_course(
                    Course(
                        id=c_id,
                        organization_id=org_id,
                        code="GEN101" if c_id == "crs-default" else c_id.replace("crs-", "").upper(),
                        title="General Studies" if c_id == "crs-default" else c_id,
                    )
                )
        except Exception as exc:
            logger.warning("Failed to auto-provision course %s: %s", c_id, exc)

        try:
            if not self.db.get_session(session_id):
                self.db.create_session(
                    Session(
                        id=session_id,
                        student_id=student_id,
                        course_id=c_id,
                        concept_id="",
                        status=SessionStatus.ACTIVE,
                    )
                )
        except Exception as exc:
            logger.warning("Failed to auto-provision session %s: %s", session_id, exc)

    def ingest_event(self, req: LearningEventIngest) -> Tuple[LearningEvent, bool]:
        """Ingest a single learning event with idempotent deduplication by event_id.
        
        Returns:
            Tuple[LearningEvent, bool]: (event, was_inserted). was_inserted is False if deduplicated.
        """
        existing = self.db.get_learning_event(req.event_id)
        if existing is not None:
            # Idempotent deduplication: event already stored
            return existing, False

        # Ensure parent entities for relational foreign key constraints
        self._ensure_entities(
            student_id=req.student_id,
            session_id=req.session_id,
            organization_id=req.organization_id,
            course_id=req.course_id,
        )

        # Extract score or concept from root or payload
        score_val = req.score if req.score is not None else req.payload.get("score")
        if score_val is not None:
            try:
                score_val = float(score_val)
            except (ValueError, TypeError):
                score_val = None

        concept_id_val = req.concept_id or req.payload.get("concept_id") or ""
        event_type_str = req.event_type.value if isinstance(req.event_type, LearningEventType) else str(req.event_type)

        event = LearningEvent(
            id=req.event_id,
            session_id=req.session_id,
            student_id=req.student_id,
            concept_id=concept_id_val,
            event_type=event_type_str,
            organization_id=req.organization_id,
            course_id=req.course_id,
            source=req.source,
            payload=dict(req.payload),
            score=score_val,
            schema_version=req.schema_version,
            created_at=req.timestamp,
        )
        self.db.record_learning_event(event)
        return event, True

    def ingest_batch(self, batch: BatchLearningEventIngest) -> Dict[str, Any]:
        """Ingest a collection of events idempotently with high-throughput batching."""
        total = len(batch.events)
        if total == 0:
            return {
                "total": 0,
                "inserted": 0,
                "deduplicated": 0,
                "events": [],
            }

        all_ids = [req.event_id for req in batch.events]
        existing_ids = self.db.get_existing_learning_event_ids(all_ids)

        seen_batch_ids: Set[str] = set()
        seen_entities: Set[Tuple[str, str, str, str]] = set()
        to_insert: List[LearningEvent] = []
        results = []
        inserted = 0
        deduplicated = 0

        for req in batch.events:
            if req.event_id in existing_ids or req.event_id in seen_batch_ids:
                deduplicated += 1
                results.append({"event_id": req.event_id, "status": "DEDUPLICATED"})
                continue
            seen_batch_ids.add(req.event_id)

            entity_key = (
                req.student_id,
                req.session_id,
                req.organization_id or "org-default",
                req.course_id or "crs-default",
            )
            if entity_key not in seen_entities:
                self._ensure_entities(
                    student_id=req.student_id,
                    session_id=req.session_id,
                    organization_id=req.organization_id,
                    course_id=req.course_id,
                )
                seen_entities.add(entity_key)

            score_val = req.score if req.score is not None else req.payload.get("score")
            if score_val is not None:
                try:
                    score_val = float(score_val)
                except (ValueError, TypeError):
                    score_val = None

            concept_id_val = req.concept_id or req.payload.get("concept_id") or ""
            event_type_str = req.event_type.value if isinstance(req.event_type, LearningEventType) else str(req.event_type)

            event = LearningEvent(
                id=req.event_id,
                session_id=req.session_id,
                student_id=req.student_id,
                concept_id=concept_id_val,
                event_type=event_type_str,
                organization_id=req.organization_id,
                course_id=req.course_id,
                source=req.source,
                payload=dict(req.payload),
                score=score_val,
                schema_version=req.schema_version,
                created_at=req.timestamp,
            )
            to_insert.append(event)
            inserted += 1
            results.append({"event_id": req.event_id, "status": "RECORDED"})

        if to_insert:
            self.db.record_learning_events_batch(to_insert)

        return {
            "total": total,
            "inserted": inserted,
            "deduplicated": deduplicated,
            "events": results,
        }

    def get_event(self, event_id: str) -> Optional[LearningEvent]:
        """Retrieve individual event by unique identifier."""
        return self.db.get_learning_event(event_id)

    def query_events(self, filter_params: Optional[LearningEventFilter] = None) -> List[LearningEvent]:
        """Query learning events using filters with chronological ordering."""
        if filter_params is None:
            filter_params = LearningEventFilter()
        return self.db.query_learning_events(
            student_id=filter_params.student_id,
            organization_id=filter_params.organization_id,
            course_id=filter_params.course_id,
            session_id=filter_params.session_id,
            event_type=filter_params.event_type,
            since=filter_params.since,
            until=filter_params.until,
            limit=filter_params.limit,
        )

    def get_student_events(
        self,
        student_id: str,
        course_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[LearningEvent]:
        """Convenience method to retrieve chronological events for a student."""
        flt = LearningEventFilter(
            student_id=student_id,
            course_id=course_id,
            limit=limit,
        )
        return self.query_events(flt)

    def update_event(self, event_id: str, updates: Dict[str, Any]) -> None:
        """Infallible immutability guard: updates are strictly forbidden."""
        raise PermissionError("Learning events are immutable and cannot be updated.")

    def delete_event(self, event_id: str) -> None:
        """Infallible immutability guard: deletions are strictly forbidden."""
        raise PermissionError("Learning events are immutable and cannot be deleted.")

    def replay_events(
        self,
        student_id: str,
        organization_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ReplayProjectionResult:
        """Chronologically replay the complete event stream to project student state."""
        events = self.db.query_learning_events(
            student_id=student_id,
            organization_id=organization_id,
            session_id=session_id,
            limit=5000,
        )

        total_events = len(events)
        current_mastery = 0.50  # Baseline neutral prior
        concept_mastery: Dict[str, float] = {}
        concepts_introduced: Set[str] = set()
        concepts_mastered: Set[str] = set()
        active_misconceptions: Set[str] = set()
        recovered_misconceptions: Set[str] = set()
        questions_attempted = 0
        questions_correct = 0
        hints_used = 0
        teacher_instructions_count = 0
        last_timestamp = None

        for ev in events:
            last_timestamp = ev.created_at
            etype = ev.event_type.lower()
            p = ev.payload or {}

            # Concept trajectory
            if ev.concept_id:
                if ev.concept_id not in concept_mastery:
                    concept_mastery[ev.concept_id] = 0.50
                if etype in ("concept_introduced", "concept_reinforced", "question_attempted"):
                    concepts_introduced.add(ev.concept_id)
                if etype == "concept_mastered":
                    if p.get("authoritative") is False or p.get("mock") is True or p.get("fallback") is True:
                        continue
                    concepts_mastered.add(ev.concept_id)
                    concept_mastery[ev.concept_id] = round(ev.score if ev.score is not None else 0.95, 4)

            # Questions & Answers
            if etype in ("question_attempted",):
                questions_attempted += 1

            if etype in ("answer_submitted", "answer_corrected"):
                # Safe Fallback Policy (GQA-003): Non-authoritative, mock, or uncertain events
                # must NEVER mutate student concept mastery.
                if (
                    p.get("authoritative") is False
                    or p.get("evaluation_unavailable") is True
                    or p.get("mock") is True
                    or p.get("fallback") is True
                ):
                    continue
                correctness = str(p.get("correctness", "")).lower()
                if correctness in ("uncertain", "evaluation_unavailable"):
                    continue
                is_correct = correctness == "correct" or (ev.score is not None and ev.score >= 0.7 and correctness != "incorrect")
                if is_correct:
                    questions_correct += 1
                    # Incremental BKT-style mastery gain
                    current_mastery = min(1.0, current_mastery + 0.05)
                    if ev.concept_id:
                        concept_mastery[ev.concept_id] = min(1.0, concept_mastery.get(ev.concept_id, 0.50) + 0.05)
                else:
                    current_mastery = max(0.05, current_mastery - 0.03)
                    if ev.concept_id:
                        concept_mastery[ev.concept_id] = max(0.05, concept_mastery.get(ev.concept_id, 0.50) - 0.03)

            # Hints
            if etype in ("hint_requested", "hint_used"):
                hints_used += 1
                current_mastery = max(0.05, current_mastery - 0.01)

            # Misconceptions
            if etype == "misconception_detected":
                misc_code = p.get("misconception_code") or ev.concept_id
                if misc_code:
                    active_misconceptions.add(misc_code)
                    current_mastery = max(0.05, current_mastery - 0.04)

            if etype == "misconception_recovered":
                misc_code = p.get("misconception_code") or ev.concept_id
                if misc_code:
                    active_misconceptions.discard(misc_code)
                    recovered_misconceptions.add(misc_code)
                    current_mastery = min(1.0, current_mastery + 0.06)

            # Directives
            if etype in ("teacher_instruction_created", "teacher_intervention_created"):
                teacher_instructions_count += 1

        resolved_org = organization_id or (events[0].organization_id if events and events[0].organization_id else "org-default")

        return ReplayProjectionResult(
            student_id=student_id,
            organization_id=resolved_org,
            total_events=total_events,
            current_mastery=round(current_mastery, 4),
            concept_mastery=concept_mastery,
            concepts_introduced=sorted(list(concepts_introduced)),
            concepts_mastered=sorted(list(concepts_mastered)),
            active_misconceptions=sorted(list(active_misconceptions)),
            recovered_misconceptions=sorted(list(recovered_misconceptions)),
            questions_attempted=questions_attempted,
            questions_correct=questions_correct,
            hints_used=hints_used,
            teacher_instructions_count=teacher_instructions_count,
            last_event_timestamp=last_timestamp,
        )
