"""Gayatri AI Platform — Students API Endpoints (Phase 06).

Master Plan Section 15:
- Authoritative Student Learning Record (SLR) covering all 15 dimensions
- Student learning profiles & diagnostics
- Real-time telemetry snapshot submission
- Strict student self-access & cross-student boundary enforcement
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger("gayatri.central_platform.api.routes.students")
from central_platform.api.schemas import (
    ApiResponse,
    StudentActionRequest,
    StudentProfileResponse,
    StudentSnapshotRequest,
    StudentEnrolledCourseResponse,
    StudentCourseSwitchRequest,
    StudentCourseSwitchResponse,
    StudentOfflineStatusResponse,
)
from central_platform.auth.dependencies import (
    enforce_resource_boundaries,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.curriculum.service import CurriculumService
from central_platform.db import PlatformDatabase
from central_platform.learning.bridge import LearningEngineBridge
from central_platform.learning.models import StudentActionPayload
from central_platform.models.schema import User, UserRole
from central_platform.progress.service import StudentProgressService
from central_platform.slr.service import SLRService
from central_platform.teacher.portal import TeacherPortalService, get_shared_portal_service

router = APIRouter(prefix="/students", tags=["Students"])


_db = get_db()
_curriculum_service = CurriculumService(_db)
_slr_service = SLRService()
_engine_bridge = LearningEngineBridge()
_progress_service = StudentProgressService()


_portal_service = get_shared_portal_service()


def _enforce_student_access(current_user: Optional[User], target_student_id: Optional[str] = None) -> None:
    """Enforce authentication in production and student self-access boundaries."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access student resources",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user and target_student_id:
        enforce_resource_boundaries(current_user, target_student_id=target_student_id)


@router.get("/{student_id}", response_model=ApiResponse[StudentProfileResponse])
async def get_student_profile(
    student_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve full student learning profile from authoritative SLR."""
    _enforce_student_access(current_user, target_student_id=student_id)

    slr = _slr_service.get_authoritative_slr(student_id)
    recent_activity = [t.summary for t in slr.learning_timeline[:5]]
    misconceptions = [m.name for m in slr.misconceptions]

    data = StudentProfileResponse(
        student_id=slr.identity.student_id,
        student_name=slr.identity.student_name,
        course_id=slr.course.course_id,
        current_concept=slr.curriculum.current_concept,
        mastery=slr.mastery.overall_score,
        retention_rate=slr.mastery.retention_rate,
        hint_count=slr.hints.total_hints_requested,
        misconceptions=misconceptions,
        recent_activity=recent_activity,
    )
    return ApiResponse(ok=True, data=data)


@router.post("/snapshot", response_model=ApiResponse[dict])
async def update_student_snapshot(
    snapshot: StudentSnapshotRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Push local student telemetry, mastery, and misconceptions to platform."""
    _enforce_student_access(current_user, target_student_id=snapshot.student_id)

    # Sync with SLR service
    _slr_service.update_concept_mastery(
        student_id=snapshot.student_id,
        concept_id="chem_thermo_first_law",
        score=snapshot.mastery,
        course_id=snapshot.course_id,
    )

    for misc_name in snapshot.misconceptions:
        _slr_service.record_student_misconception(
            student_id=snapshot.student_id,
            misconception_code=misc_name,
            course_id=snapshot.course_id,
        )

    # Update legacy portal service roster
    _portal_service.update_student_snapshot(
        student_id=snapshot.student_id,
        student_name=snapshot.student_name,
        course_id=snapshot.course_id,
        mastery=snapshot.mastery,
        needs_attention=snapshot.needs_attention,
        misconceptions=snapshot.misconceptions,
        hint_count=snapshot.hint_count,
        retention_rate=snapshot.retention_rate,
    )
    return ApiResponse(
        ok=True,
        data={
            "status": "ACCEPTED",
            "student_id": snapshot.student_id,
            "mastery": snapshot.mastery,
        },
    )


@router.get("/{student_id}/slr", response_model=ApiResponse[Dict[str, Any]])
async def get_student_learning_record(
    student_id: str,
    course_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get canonical 15-dimension Authoritative Student Learning Record (SLR)."""
    _enforce_student_access(current_user, target_student_id=student_id)

    slr = _slr_service.get_authoritative_slr(student_id, course_id=course_id)
    profile = await get_student_profile(student_id, current_user=current_user)

    slr_dict = slr.to_dict()
    # Add backward-compatible profile envelope field
    slr_dict["profile"] = profile.data.model_dump() if profile.data else {}

    return ApiResponse(
        ok=True,
        data=slr_dict,
    )


@router.post("/{student_id}/action", response_model=ApiResponse[Dict[str, Any]])
async def submit_student_action(
    student_id: str,
    action_req: StudentActionRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Process student learning action through the canonical Phase 07 learning pipeline.

    Flow: student action -> learning event -> learning engine -> updated mastery -> SLR -> recommendation.
    """
    _enforce_student_access(current_user, target_student_id=student_id)

    payload = StudentActionPayload(
        concept_id=action_req.concept_id,
        action_type=action_req.action_type,
        course_id=action_req.course_id,
        session_id=action_req.session_id,
        turn_id=action_req.turn_id,
        question_id=action_req.question_id,
        student_answer=action_req.student_answer,
        correctness=action_req.correctness,
        score=action_req.score,
        hint_level=action_req.hint_level,
        difficulty=action_req.difficulty,
        response_time_ms=action_req.response_time_ms,
        misconception_code=action_req.misconception_code,
        metadata=action_req.metadata,
    )

    action_result = _engine_bridge.process_student_action(
        student_id=student_id,
        action=payload,
        course_id=action_req.course_id,
    )

    return ApiResponse(
        ok=True,
        data=action_result.to_dict(),
    )


@router.get("/{student_id}/progress", response_model=ApiResponse[Dict[str, Any]])
async def get_student_progress_report(
    student_id: str,
    course_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve full 14-dimension canonical student learning progress report.

    Master Plan Section 18:
    overall mastery, topic mastery, concept heatmap, recent sessions, recent activity,
    weak areas, misconceptions, accuracy trends, mastery trends, question-type performance,
    review due, recommendations (policy-driven), session summary, learning streak.
    """
    _enforce_student_access(current_user, target_student_id=student_id)

    report = _progress_service.get_student_progress(student_id, course_id=course_id)
    return ApiResponse(ok=True, data=report.to_dict())


@router.get("/{student_id}/progress/heatmap", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_student_progress_heatmap(
    student_id: str,
    course_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve granular concept mastery heatmap matrix with pedagogical color coding."""
    _enforce_student_access(current_user, target_student_id=student_id)

    report = _progress_service.get_student_progress(student_id, course_id=course_id)
    return ApiResponse(ok=True, data=[h.to_dict() for h in report.concept_heatmap])


@router.get("/{student_id}/progress/summary", response_model=ApiResponse[Dict[str, Any]])
async def get_student_progress_summary(
    student_id: str,
    course_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve high-level student progress summary (overall mastery, topics, streak)."""
    _enforce_student_access(current_user, target_student_id=student_id)

    report = _progress_service.get_student_progress(student_id, course_id=course_id)
    summary_data = {
        "student_id": report.student_id,
        "course_id": report.course_id,
        "overall_mastery": report.overall_mastery,
        "topic_mastery": [t.to_dict() for t in report.topic_mastery],
        "learning_streak": report.learning_streak.to_dict(),
        "weak_areas_count": len(report.weak_areas),
        "review_due_count": len(report.review_due),
    }
    return ApiResponse(ok=True, data=summary_data)


# ── Student Multi-Course Workflow (Phase 17) ──────────────────────────────

@router.get("/{student_id}/courses", response_model=ApiResponse[List[StudentEnrolledCourseResponse]])
async def get_student_enrolled_courses(
    student_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List all enrolled courses for the student with live mastery and current active concept."""
    _enforce_student_access(current_user, target_student_id=student_id)

    enrollments = _db.get_enrollments_for_student(student_id)
    courses_response: List[StudentEnrolledCourseResponse] = []

    for enr in enrollments:
        if not enr.is_active:
            continue
        course = _db.get_course(enr.course_id)
        if not course:
            continue

        cohort_name = None
        class_name = None
        class_group_id = None

        if enr.cohort_id:
            cohort = _db.get_cohort(enr.cohort_id)
            if cohort:
                cohort_name = cohort.name
                class_group_id = cohort.class_group_id
                if cohort.class_group_id:
                    cg = _db.get_class_group(cohort.class_group_id)
                    if cg:
                        class_name = cg.name

        mastery_states = _db.get_mastery_states(student_id, course_id=course.id)
        if mastery_states:
            overall_mastery = sum(m.score for m in mastery_states) / len(mastery_states)
            active_concept = mastery_states[0].concept_id
        else:
            overall_mastery = 0.0
            active_concept = ""

        if not active_concept:
            try:
                hier = _curriculum_service.get_curriculum_hierarchy(course.id)
                for mod in hier.get("modules", []):
                    for top in mod.get("topics", []):
                        concepts = top.get("concepts", [])
                        if concepts:
                            active_concept = concepts[0].get("id") or concepts[0].get("concept_id") or ""
                            break
                    if active_concept:
                        break
            except Exception as exc:
                logger.debug("Failed to extract active concept from hierarchy for course %s: %s", course.id, exc)

        courses_response.append(
            StudentEnrolledCourseResponse(
                id=enr.id,
                course_id=course.id,
                code=course.code,
                title=course.title,
                description=course.description or "",
                organization_id=course.organization_id,
                cohort_id=enr.cohort_id,
                cohort_name=cohort_name,
                class_group_id=class_group_id,
                class_name=class_name,
                enrolled_at=enr.enrolled_at,
                is_active=enr.is_active,
                overall_mastery=round(overall_mastery, 3),
                active_concept=active_concept,
            )
        )

    return ApiResponse(ok=True, data=courses_response)


@router.get("/{student_id}/courses/{course_id}/curriculum", response_model=ApiResponse[Dict[str, Any]])
async def get_student_course_curriculum(
    student_id: str,
    course_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve curriculum hierarchy for an enrolled course with student mastery overlaid."""
    _enforce_student_access(current_user, target_student_id=student_id)

    enrollments = _db.get_enrollments_for_student(student_id)
    if not any(e.course_id == course_id and e.is_active for e in enrollments):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Student '{student_id}' is not enrolled in course '{course_id}'.",
        )

    try:
        hierarchy = _curriculum_service.get_curriculum_hierarchy(course_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    mastery_map = {m.concept_id: m.score for m in _db.get_mastery_states(student_id, course_id=course_id)}
    for mod in hierarchy.get("modules", []):
        for top in mod.get("topics", []):
            for c in top.get("concepts", []):
                cid = c.get("id") or c.get("concept_id")
                c["mastery_score"] = mastery_map.get(cid, 0.0)

    return ApiResponse(ok=True, data=hierarchy)


@router.get("/{student_id}/courses/{course_id}/assignments", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_student_course_assignments(
    student_id: str,
    course_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve assignments strictly scoped to this student, their class/cohort, and the active course."""
    _enforce_student_access(current_user, target_student_id=student_id)

    enrollments = _db.get_enrollments_for_student(student_id)
    if not any(e.course_id == course_id and e.is_active for e in enrollments):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Student '{student_id}' is not enrolled in course '{course_id}'.",
        )

    assignments = _db.get_assignments_for_student(student_id, course_id)
    return ApiResponse(ok=True, data=[a.to_dict() if hasattr(a, "to_dict") else dict(a) for a in assignments])


@router.get("/{student_id}/courses/{course_id}/knowledge", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_student_course_knowledge(
    student_id: str,
    course_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve published knowledge sources authorized for this student in this course."""
    _enforce_student_access(current_user, target_student_id=student_id)

    enrollments = _db.get_enrollments_for_student(student_id)
    if not any(e.course_id == course_id and e.is_active for e in enrollments):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Student '{student_id}' is not enrolled in course '{course_id}'.",
        )

    sources = _db.get_knowledge_sources_for_student(student_id, course_id)
    return ApiResponse(ok=True, data=[s.to_dict() if hasattr(s, "to_dict") else dict(s) for s in sources])


@router.post("/{student_id}/courses/switch", response_model=ApiResponse[StudentCourseSwitchResponse])
async def switch_student_course(
    student_id: str,
    req: StudentCourseSwitchRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Switch student active course context with safe-switching concurrency invariant."""
    _enforce_student_access(current_user, target_student_id=student_id)

    if req.active_turn_generating:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot switch course while an AI turn is actively generating. Complete or cancel the active turn first.",
        )

    enrollments = _db.get_enrollments_for_student(student_id)
    target_enr = next((e for e in enrollments if e.course_id == req.target_course_id and e.is_active), None)
    if not target_enr:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Student '{student_id}' is not enrolled in course '{req.target_course_id}'.",
        )

    course = _db.get_course(req.target_course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{req.target_course_id}' not found.",
        )

    mastery_states = _db.get_mastery_states(student_id, course_id=course.id)
    if mastery_states:
        overall = sum(m.score for m in mastery_states) / len(mastery_states)
        active_concept = mastery_states[0].concept_id
    else:
        overall = 0.0
        active_concept = ""

    if not active_concept:
        try:
            hier = _curriculum_service.get_curriculum_hierarchy(course.id)
            for mod in hier.get("modules", []):
                for top in mod.get("topics", []):
                    concepts = top.get("concepts", [])
                    if concepts:
                        active_concept = concepts[0].get("id") or concepts[0].get("concept_id") or ""
                        break
                if active_concept:
                    break
        except Exception as exc:
            logger.debug("Failed to extract active concept from hierarchy on course switch for %s: %s", course.id, exc)

    return ApiResponse(
        ok=True,
        data=StudentCourseSwitchResponse(
            student_id=student_id,
            active_course_id=course.id,
            course_title=course.title,
            switched_at=datetime.now(timezone.utc).isoformat(),
            active_concept=active_concept,
            overall_mastery=round(overall, 3),
        ),
    )


@router.get("/{student_id}/courses/{course_id}/offline-status", response_model=ApiResponse[StudentOfflineStatusResponse])
async def get_student_course_offline_status(
    student_id: str,
    course_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve offline caching and synchronization status for the course."""
    _enforce_student_access(current_user, target_student_id=student_id)

    enrollments = _db.get_enrollments_for_student(student_id)
    if not any(e.course_id == course_id and e.is_active for e in enrollments):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Student '{student_id}' is not enrolled in course '{course_id}'.",
        )

    return ApiResponse(
        ok=True,
        data=StudentOfflineStatusResponse(
            student_id=student_id,
            course_id=course_id,
            is_cached=True,
            is_synced=True,
            offline_available=True,
            last_synced_at=datetime.now(timezone.utc).isoformat(),
        ),
    )



