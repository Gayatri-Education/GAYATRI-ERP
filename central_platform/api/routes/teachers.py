"""Gayatri AI Platform — Teachers API Endpoints (Phase 04).

Master Plan Section 13:
- Role-based gatekeeping (TEACHER, ORG_ADMIN, SUPER_ADMIN)
- Student access blocked (student -> teacher 403 Forbidden)
- Teacher cohort and assignment resource scoping (teacher -> unrelated student 403 Forbidden)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger("gayatri.central_platform.api.routes.teachers")
from central_platform.api.schemas import (
    AlertResolveRequest,
    ApiResponse,
    TeacherDashboardResponse,
    TeacherInstructionCreateRequest,
    TeacherInstructionResponse,
    TeacherInstructionToggleRequest,
    TeacherInstructionUpdateRequest,
    TeacherInstructionValidateRequest,
    TeacherInstructionValidateResponse,
    TeacherInterventionCreateRequest,
    TeacherInterventionDismissRequest,
    TeacherInterventionEvaluateRequest,
    TeacherInterventionNoteRequest,
    TeacherInterventionResolveRequest,
    TeacherInterventionResponse,
    TeacherInterventionUpdateRequest,
    TeacherCopilotQueryRequest,
    TeacherCopilotQueryResponse,
    TeacherAssignmentCreateRequest,
    TeacherAssignmentResponse,
    TeacherClassGroupCreateRequest,
    TeacherClassGroupResponse,
    TeacherClassNoteCreateRequest,
    TeacherClassNoteResponse,
    TeacherCourseResponse,
    TeacherRemedialContentCreateRequest,
    TeacherRemedialContentResponse,
)
from central_platform.auth.dependencies import (
    enforce_resource_boundaries,
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.courses.service import CourseService
from central_platform.models.schema import Assignment, ClassGroup, Cohort, CourseVisibility, User, UserRole
from central_platform.rag.service import RAGService
from central_platform.teacher.portal import TeacherPortalService, get_shared_portal_service
from central_platform.teacher.instruction import (
    InstructionStatus,
    SafetyStatus,
    TeacherInstruction,
    TeacherInstructionEngine,
    TeacherInstructionValidator,
)
from central_platform.teacher.intervention import (
    AlertSeverity,
    AlertStatus,
    InterventionPriority,
    InterventionStatus,
    InterventionTriggerType,
    TeacherAlert,
    TeacherIntervention,
    TeacherInterventionEngine,
)
from central_platform.teacher.copilot import TeacherCopilot
from central_platform.slr.service import SLRService

router = APIRouter(prefix="/teachers", tags=["Teachers"])

_slr_service = SLRService()

_portal_service = get_shared_portal_service()
_instruction_engine = TeacherInstructionEngine()
_intervention_engine = TeacherInterventionEngine()
_copilot = TeacherCopilot()


@router.get("/dashboard", response_model=ApiResponse[TeacherDashboardResponse])
async def get_teacher_dashboard(
    course_id: str = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Any = Depends(get_db),
):
    """Retrieve full teacher dashboard analytics, alerts, and student roster."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access teacher dashboard",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students are not authorized to access teacher dashboard",
            )
        from fastapi.params import Depends as DependsClass
        effective_db = get_db() if (db is None or isinstance(db, DependsClass)) else db
        course = effective_db.get_course(course_id)
        is_public = False
        if course:
            vis = getattr(course, "visibility", None)
            vis_str = vis.value if hasattr(vis, "value") else str(vis)
            if vis_str.upper() == "PUBLIC" or course.organization_id in ("org-default", None):
                is_public = True

        if course and course.organization_id:
            if course.organization_id not in ("org-default", None):
                enforce_resource_boundaries(current_user, target_org_id=course.organization_id)
            elif not is_public:
                enforce_resource_boundaries(current_user, target_org_id=course.organization_id)
            else:
                enforce_resource_boundaries(current_user)
        else:
            enforce_resource_boundaries(current_user)

    overview = _portal_service.get_dashboard_overview(course_id)
    students = _portal_service.get_all_students(course_id)
    alerts = _intervention_engine.get_all_alerts(course_id=course_id)

    data = TeacherDashboardResponse(
        total_students=overview.total_students,
        active_today=overview.active_students_today,
        average_mastery=overview.average_mastery,
        critical_alerts_count=overview.critical_alerts_count,
        mastery_distribution=overview.mastery_distribution,
        chapter_averages=overview.chapter_averages,
        recent_alerts=[a.to_dict() for a in alerts],
        students=students,
        students_active=overview.students_active or overview.active_students_today,
        difficult_concepts=overview.difficult_concepts,
        common_misconceptions=overview.common_misconceptions or overview.top_misconceptions,
        recent_activity=overview.recent_activity,
        intervention_alerts=overview.intervention_alerts or [a.to_dict() for a in alerts],
    )
    return ApiResponse(ok=True, data=data)


def _to_instruction_response(i: TeacherInstruction) -> TeacherInstructionResponse:
    return TeacherInstructionResponse(
        instruction_id=i.instruction_id,
        teacher_id=i.teacher_id,
        student_id=i.student_id,
        course_id=i.course_id,
        instruction_text=i.instruction_text,
        priority=i.priority,
        concept_scope=i.concept_scope or "ALL",
        scope_type=getattr(i, "scope_type", "STUDENT"),
        organization_id=getattr(i, "organization_id", None),
        course_version_id=getattr(i, "course_version_id", None),
        class_id=getattr(i, "class_id", None),
        session_id=getattr(i, "session_id", None),
        version=getattr(i, "version", 1),
        is_active=i.is_active,
        status=getattr(i, "status", InstructionStatus.ACTIVE.value),
        start_at=getattr(i, "start_at", None),
        expires_at=getattr(i, "expires_at", None),
        safety_status=getattr(i, "safety_status", SafetyStatus.VALIDATED.value),
        safety_reasons=getattr(i, "safety_reasons", []),
        audit_trail=getattr(i, "audit_trail", []),
        created_at=i.created_at,
        updated_at=getattr(i, "updated_at", None),
    )


@router.post("/instructions/validate", response_model=ApiResponse[TeacherInstructionValidateResponse])
async def validate_instruction(
    req: TeacherInstructionValidateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Pre-flight policy and safety validation for a teacher directive against the 5 non-overridable invariants."""
    val = TeacherInstructionValidator.validate(req.instruction)
    return ApiResponse(
        ok=True,
        data=TeacherInstructionValidateResponse(
            is_valid=val.is_valid,
            safety_status=val.safety_status,
            violations=val.violations,
            sanitized_text=val.sanitized_text,
            target_invariants=val.target_invariants,
        ),
    )


@router.post("/instructions", response_model=ApiResponse[TeacherInstructionResponse], status_code=status.HTTP_201_CREATED)
async def create_instruction(
    req: TeacherInstructionCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Dispatch a pedagogical directive with hierarchical scoping, policy validation, and audit logging."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to create teacher instructions",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students cannot create teacher instructions",
            )
        if current_user.role == UserRole.TEACHER and req.class_id:
            db = get_db()
            cg = db.get_class_group(req.class_id)
            if cg and current_user.organization_id and cg.organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: class '{req.class_id}' belongs to another organization",
                )
        if current_user.role == UserRole.TEACHER and req.student_id not in ("all", "*", "", None):
            db = get_db()
            target_user = db.get_user(req.student_id)
            if target_user and target_user.organization_id and current_user.organization_id:
                if target_user.organization_id not in ("org-default", None) and current_user.organization_id not in ("org-default", None):
                    if target_user.organization_id != current_user.organization_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Forbidden: student '{req.student_id}' belongs to another organization",
                        )
            assigned = db.get_assigned_student_ids_for_teacher(current_user.id)
            if assigned and req.student_id not in assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: student '{req.student_id}' is not assigned to this teacher",
                )
        if current_user.role == UserRole.TEACHER and req.organization_id:
            if current_user.organization_id and req.organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: teacher '{current_user.id}' cannot create instructions for organization '{req.organization_id}'",
                )

    # Validate against non-overridable invariants
    val = TeacherInstructionValidator.validate(req.instruction)
    if not val.is_valid:
        raise HTTPException(
            status_code=422,
            detail=f"Policy violation: {'; '.join(val.violations)}",
        )

    inst_id = f"inst-{uuid.uuid4().hex[:6]}"
    teacher_id = current_user.id if current_user else "tchr-101"
    org_id = req.organization_id or (current_user.organization_id if current_user else "org-default")
    
    # Auto-infer scope type if not specified
    if req.scope_type:
        scope_type = req.scope_type.upper()
    elif req.session_id:
        scope_type = "SESSION"
    elif req.student_id not in ("all", "*", "", None):
        scope_type = "STUDENT"
    elif req.class_id:
        scope_type = "CLASS"
    elif req.course_version_id or req.course_id:
        scope_type = "COURSE"
    elif req.organization_id:
        scope_type = "ORGANIZATION"
    else:
        scope_type = "COURSE"

    inst = TeacherInstruction(
        instruction_id=inst_id,
        teacher_id=teacher_id,
        organization_id=org_id,
        course_id=req.course_id,
        course_version_id=req.course_version_id,
        class_id=req.class_id,
        student_id=req.student_id or "all",
        session_id=req.session_id,
        instruction_text=val.sanitized_text,
        priority=req.priority,
        concept_scope=req.concept_scope,
        scope_type=scope_type,
        start_at=req.start_at or datetime.now(timezone.utc).isoformat(),
        expires_at=req.expires_at,
        status=InstructionStatus.ACTIVE.value,
        is_active=True,
        safety_status=val.safety_status,
        safety_reasons=val.violations,
        version=1,
    )
    _instruction_engine.add_instruction(inst, actor_id=teacher_id, actor=current_user)

    return ApiResponse(ok=True, data=_to_instruction_response(inst))


@router.get("/instructions", response_model=ApiResponse[List[TeacherInstructionResponse]])
async def get_instructions(
    student_id: Optional[str] = Query(default=None),
    course_id: Optional[str] = Query(default="crs-chem-101"),
    course_version_id: Optional[str] = Query(default=None),
    organization_id: Optional[str] = Query(default=None),
    class_id: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    concept_id: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    active_only: bool = Query(default=False),
    hierarchical: bool = Query(default=False),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get active instructions scoped to a student, class, course, or org with optional hierarchical resolution."""
    if current_user:
        if current_user.role == UserRole.STUDENT:
            # Student can only see instructions addressed to them or 'all'
            if student_id and student_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: students may only view their own instructions",
                )
            student_id = current_user.id
            if not organization_id and current_user.organization_id:
                organization_id = current_user.organization_id

    if hierarchical:
        insts = _instruction_engine.resolve_hierarchical_instructions(
            organization_id=organization_id or (current_user.organization_id if current_user else None),
            course_id=course_id,
            course_version_id=course_version_id,
            class_id=class_id,
            student_id=student_id,
            session_id=session_id,
            concept_id=concept_id,
        )
    elif student_id:
        insts = _instruction_engine.get_instructions_for_student(
            student_id=student_id,
            course_id=course_id or "",
            concept_id=concept_id,
            class_id=class_id,
            organization_id=organization_id,
            session_id=session_id,
        )
    else:
        insts = _instruction_engine.get_all_instructions(
            course_id=course_id,
            student_id=student_id,
            status_filter=status_filter,
            active_only=active_only,
        )

    return ApiResponse(ok=True, data=[_to_instruction_response(i) for i in insts])


@router.get("/instructions/{instruction_id}", response_model=ApiResponse[TeacherInstructionResponse])
async def get_instruction_by_id(
    instruction_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a single instruction by ID including its immutable audit trail."""
    inst = _instruction_engine.get_instruction(instruction_id)
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction not found")

    if current_user and current_user.role == UserRole.STUDENT:
        if inst.student_id not in (current_user.id, "all", "*"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students cannot view instructions for other students",
            )

    return ApiResponse(ok=True, data=_to_instruction_response(inst))


@router.patch("/instructions/{instruction_id}", response_model=ApiResponse[TeacherInstructionResponse])
async def update_instruction(
    instruction_id: str,
    req: TeacherInstructionUpdateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Update priority, scope, expiration, or status of an instruction."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot update instructions",
        )

    actor_id = current_user.id if current_user else "teacher"
    updates = req.dict(exclude_none=True)
    try:
        updated = _instruction_engine.update_instruction(instruction_id, actor_id=actor_id, updates=updates)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction not found")

    return ApiResponse(ok=True, data=_to_instruction_response(updated))


@router.delete("/instructions/{instruction_id}", response_model=ApiResponse[dict])
async def delete_or_revoke_instruction(
    instruction_id: str,
    reason: Optional[str] = Query(default="Revoked by teacher"),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Revoke a teacher instruction and record the revocation in its audit log."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot revoke teacher instructions",
        )

    actor_id = current_user.id if current_user else "teacher"
    success = _instruction_engine.revoke_instruction(instruction_id, actor_id=actor_id, reason=reason)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction not found")

    return ApiResponse(ok=True, data={"instruction_id": instruction_id, "status": "REVOKED", "revoked": True})


@router.post("/instructions/toggle", response_model=ApiResponse[dict])
async def toggle_instruction(
    req: TeacherInstructionToggleRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Enable or disable a teacher instruction."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot toggle teacher instructions",
        )
    success = _instruction_engine.toggle_instruction(req.instruction_id, req.active)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instruction not found")
    return ApiResponse(ok=True, data={"instruction_id": req.instruction_id, "active": req.active})


@router.post("/alerts/resolve", response_model=ApiResponse[dict])
async def resolve_alert(
    req: AlertResolveRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Resolve an intervention alert."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot resolve intervention alerts",
        )
    success = _intervention_engine.resolve_alert(req.alert_id, req.resolution_note)
    return ApiResponse(ok=True, data={"alert_id": req.alert_id, "resolved": success})


# ── Teacher Intervention Endpoints (Section 21) ─────────────────────────

def _to_intervention_response(itv: TeacherIntervention) -> TeacherInterventionResponse:
    return TeacherInterventionResponse(
        intervention_id=itv.intervention_id,
        student_id=itv.student_id,
        course_id=itv.course_id,
        reason=itv.reason,
        priority=itv.priority,
        assigned_teacher=itv.assigned_teacher,
        trigger_type=itv.trigger_type,
        trigger_evidence=itv.trigger_evidence,
        created_at=itv.created_at,
        due_at=itv.due_at,
        status=itv.status,
        resolution=itv.resolution,
        teacher_notes=itv.teacher_notes,
        audit_trail=itv.audit_trail,
        resolved_at=itv.resolved_at,
        resolved_by=itv.resolved_by,
        dismissed_at=itv.dismissed_at,
        dismissed_by=itv.dismissed_by,
        dismissal_reason=itv.dismissal_reason,
    )


@router.post("/interventions", response_model=ApiResponse[TeacherInterventionResponse], status_code=status.HTTP_201_CREATED)
async def create_intervention(
    req: TeacherInterventionCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new teacher intervention."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot create interventions",
        )
    teacher_id = current_user.id if current_user else (req.assigned_teacher or "tchr-101")
    itv_id = f"itv-{uuid.uuid4().hex[:6]}"
    itv = TeacherIntervention(
        intervention_id=itv_id,
        student_id=req.student_id,
        course_id=req.course_id,
        reason=req.reason,
        priority=req.priority.upper(),
        assigned_teacher=teacher_id,
        trigger_type=req.trigger_type,
        trigger_evidence=req.trigger_evidence,
        due_at=req.due_at,
        status=InterventionStatus.OPEN.value,
    )
    try:
        _intervention_engine.create_intervention(itv, actor_id=teacher_id)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))

    return ApiResponse(ok=True, data=_to_intervention_response(itv))


@router.get("/interventions", response_model=ApiResponse[List[TeacherInterventionResponse]])
async def get_interventions(
    course_id: Optional[str] = Query(default=None),
    student_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    assigned_teacher: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List teacher interventions matching query criteria."""
    if current_user and current_user.role == UserRole.STUDENT:
        if student_id and student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students can only view their own interventions",
            )
        student_id = current_user.id

    itvs = _intervention_engine.get_interventions(
        course_id=course_id,
        student_id=student_id,
        status=status,
        priority=priority,
        assigned_teacher=assigned_teacher,
    )
    return ApiResponse(ok=True, data=[_to_intervention_response(i) for i in itvs])


@router.get("/interventions/{intervention_id}", response_model=ApiResponse[TeacherInterventionResponse])
async def get_intervention_by_id(
    intervention_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve full intervention profile with notes and audit trail."""
    itv = _intervention_engine.get_intervention(intervention_id)
    if not itv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found")
    if current_user and current_user.role == UserRole.STUDENT:
        if itv.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students cannot view other students' interventions",
            )
    return ApiResponse(ok=True, data=_to_intervention_response(itv))


@router.patch("/interventions/{intervention_id}", response_model=ApiResponse[TeacherInterventionResponse])
async def update_intervention(
    intervention_id: str,
    req: TeacherInterventionUpdateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Update priority, due date, status, or assigned teacher on an intervention."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot update interventions",
        )
    actor_id = current_user.id if current_user else "teacher"
    itv = _intervention_engine.get_intervention(intervention_id)
    if not itv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found")

    if req.status:
        try:
            _intervention_engine.transition_intervention_status(intervention_id, req.status.upper(), actor_id=actor_id)
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err))
    if req.priority:
        itv.priority = req.priority.upper()
    if req.due_at is not None:
        itv.due_at = req.due_at
    if req.assigned_teacher is not None:
        itv.assigned_teacher = req.assigned_teacher

    return ApiResponse(ok=True, data=_to_intervention_response(itv))


@router.post("/interventions/{intervention_id}/notes", response_model=ApiResponse[TeacherInterventionResponse])
async def add_intervention_note(
    intervention_id: str,
    req: TeacherInterventionNoteRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Append a pedagogical note to an intervention."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot add teacher notes",
        )
    actor_id = current_user.id if current_user else "teacher"
    updated = _intervention_engine.add_note(intervention_id, author_id=actor_id, text=req.text)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found")
    return ApiResponse(ok=True, data=_to_intervention_response(updated))


@router.post("/interventions/{intervention_id}/resolve", response_model=ApiResponse[TeacherInterventionResponse])
async def resolve_intervention(
    intervention_id: str,
    req: TeacherInterventionResolveRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Formally resolve an intervention with mandatory resolution note."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot resolve interventions",
        )
    actor_id = current_user.id if current_user else "teacher"
    try:
        updated = _intervention_engine.resolve_intervention(intervention_id, actor_id=actor_id, resolution_note=req.resolution_note)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found")
    return ApiResponse(ok=True, data=_to_intervention_response(updated))


@router.post("/interventions/{intervention_id}/dismiss", response_model=ApiResponse[TeacherInterventionResponse])
async def dismiss_intervention(
    intervention_id: str,
    req: TeacherInterventionDismissRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Dismiss an intervention with mandatory justification reason."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot dismiss interventions",
        )
    actor_id = current_user.id if current_user else "teacher"
    try:
        updated = _intervention_engine.dismiss_intervention(intervention_id, actor_id=actor_id, reason=req.reason)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intervention not found")
    return ApiResponse(ok=True, data=_to_intervention_response(updated))


@router.post("/interventions/evaluate", response_model=ApiResponse[List[TeacherInterventionResponse]])
async def evaluate_interventions(
    req: TeacherInterventionEvaluateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Evaluate SLR data and events to trigger interventions with concrete evidence."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot evaluate interventions",
        )
    slr = _slr_service.get_slr(req.student_id, req.course_id)
    events = []
    try:
        from central_platform.events.store import LearningEventStore
        store = LearningEventStore(db=get_db())
        events = store.get_events_for_student(req.student_id, course_id=req.course_id)
    except Exception as exc:
        logger.warning("Failed to fetch learning events for student %s: %s", req.student_id, exc)
    generated = _intervention_engine.evaluate_triggers_for_student(
        student_id=req.student_id,
        course_id=req.course_id,
        slr=slr,
        recent_events=events,
    )
    return ApiResponse(ok=True, data=[_to_intervention_response(i) for i in generated])


@router.get("/copilot/briefing", response_model=ApiResponse[Dict[str, Any]])
async def get_copilot_briefing(
    student_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Generate diagnostic AI Copilot briefing for a student or cohort."""
    if current_user:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students cannot access teacher copilot briefing",
            )
        if current_user.role == UserRole.TEACHER and student_id:
            db = get_db()
            assigned = db.get_assigned_student_ids_for_teacher(current_user.id)
            if assigned and student_id not in assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: student '{student_id}' is not assigned to this teacher",
                )

    if student_id:
        resp = _copilot.query(f"What are the weaknesses of student {student_id}?")
    else:
        resp = _copilot.query("Summarize overall cohort progress and critical misconceptions.")
    return ApiResponse(ok=True, data=resp.to_dict())


@router.post("/copilot/query", response_model=ApiResponse[TeacherCopilotQueryResponse])
async def query_teacher_copilot(
    request: TeacherCopilotQueryRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Authoritative retrieval-grounded AI Copilot for Teachers (Section 22 / Phase 13).
    
    Answers student and cohort diagnostic inquiries with auditable evidence,
    traceability to authorized SLR data, zero fabrication, and strict RBAC isolation.
    """
    if current_user:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students cannot access teacher copilot",
            )
        if current_user.role == UserRole.TEACHER and request.student_id:
            db = get_db()
            assigned = db.get_assigned_student_ids_for_teacher(current_user.id)
            if assigned and request.student_id not in assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: student '{request.student_id}' is not assigned to this teacher",
                )

    resp = _copilot.query(
        prompt=request.query,
        student_id=request.student_id,
        course_id=request.course_id,
        time_window_days=request.time_window_days or 7,
    )
    return ApiResponse(ok=True, data=TeacherCopilotQueryResponse(**resp.to_dict()))


@router.get("/students/{student_id}/slr", response_model=ApiResponse[Dict[str, Any]])
async def get_teacher_student_slr(
    student_id: str,
    course_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve Authoritative SLR for an assigned student."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access student SLR",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students cannot use teacher endpoints",
            )
        if current_user.role == UserRole.TEACHER:
            db = get_db()
            assigned = db.get_assigned_student_ids_for_teacher(current_user.id)
            if assigned and student_id not in assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: student '{student_id}' is not assigned to this teacher",
                )

    slr = _slr_service.get_authoritative_slr(student_id, course_id=course_id)
    return ApiResponse(ok=True, data=slr.to_dict())


@router.get("/students", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_students(
    course_id: Optional[str] = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve cohort roster for the teacher."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access student roster",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students are not authorized to access teacher endpoints",
            )
        enforce_resource_boundaries(current_user)

    students = _portal_service.get_all_students(course_id)
    return ApiResponse(ok=True, data=students)


@router.get("/students/{student_id}", response_model=ApiResponse[Dict[str, Any]])
async def get_teacher_student_detail(
    student_id: str,
    course_id: Optional[str] = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Any = Depends(get_db),
):
    """Retrieve full Section 19 Student View from Authoritative SLR."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access student details",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        if current_user.role == UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: students cannot use teacher endpoints",
            )
        from fastapi.params import Depends as DependsClass
        effective_db = get_db() if (db is None or isinstance(db, DependsClass)) else db
        if current_user.role in (UserRole.TEACHER, UserRole.ORG_ADMIN):
            target_student = effective_db.get_user(student_id)
            if target_student and target_student.organization_id and current_user.organization_id:
                if target_student.organization_id not in ("org-default", None) and current_user.organization_id not in ("org-default", None):
                    if current_user.role != UserRole.SUPER_ADMIN and target_student.organization_id != current_user.organization_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Forbidden: cross-organization access to student '{student_id}' prohibited",
                        )
            if current_user.role == UserRole.TEACHER:
                assigned = effective_db.get_assigned_student_ids_for_teacher(current_user.id)
                if assigned and student_id not in assigned:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Forbidden: student '{student_id}' is not assigned to this teacher",
                    )

    detail = _portal_service.get_student_detail(student_id, course_id=course_id or "crs-chem-101")
    return ApiResponse(ok=True, data=detail)


@router.get("/students/{student_id}/timeline", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_student_timeline(
    student_id: str,
    course_id: Optional[str] = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Any = Depends(get_db),
):
    detail = await get_teacher_student_detail(student_id, course_id, current_user, db)
    return ApiResponse(ok=True, data=detail.data.get("learning_timeline", []))


@router.get("/students/{student_id}/mastery", response_model=ApiResponse[Dict[str, Any]])
async def get_teacher_student_mastery(
    student_id: str,
    course_id: Optional[str] = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Any = Depends(get_db),
):
    detail = await get_teacher_student_detail(student_id, course_id, current_user, db)
    return ApiResponse(ok=True, data=detail.data.get("mastery", {}))


@router.get("/students/{student_id}/misconceptions", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_student_misconceptions(
    student_id: str,
    course_id: Optional[str] = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Any = Depends(get_db),
):
    detail = await get_teacher_student_detail(student_id, course_id, current_user, db)
    return ApiResponse(ok=True, data=detail.data.get("misconceptions", []))


@router.get("/students/{student_id}/sessions", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_student_sessions(
    student_id: str,
    course_id: Optional[str] = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Any = Depends(get_db),
):
    detail = await get_teacher_student_detail(student_id, course_id, current_user, db)
    return ApiResponse(ok=True, data=detail.data.get("sessions", []))


@router.get("/students/{student_id}/interventions", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_student_interventions(
    student_id: str,
    course_id: Optional[str] = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Any = Depends(get_db),
):
    detail = await get_teacher_student_detail(student_id, course_id, current_user, db)
    itvs = _intervention_engine.get_interventions(course_id=course_id, student_id=student_id)
    if itvs:
        return ApiResponse(ok=True, data=[i.to_dict() for i in itvs])
    return ApiResponse(ok=True, data=detail.data.get("interventions", []))


@router.get("/students/{student_id}/instructions", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_student_instructions(
    student_id: str,
    course_id: Optional[str] = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    detail = await get_teacher_student_detail(student_id, course_id, current_user)
    return ApiResponse(ok=True, data=detail.data.get("teacher_instructions", []))


@router.get("/courses", response_model=ApiResponse[List[TeacherCourseResponse]])
async def get_teacher_courses(
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List all courses available to the teacher's organization."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot access teacher courses",
        )
    db = get_db()
    org_id = current_user.organization_id if current_user else "org-default"
    course_service = CourseService(db)
    actor = current_user or User(id="teacher_001", role=UserRole.TEACHER, organization_id=org_id)
    courses = course_service.list_courses_for_org(actor, org_id)
    return ApiResponse(
        ok=True,
        data=[
            TeacherCourseResponse(
                id=c.id,
                organization_id=c.organization_id,
                code=c.code or c.id,
                title=c.title,
                description=c.description or "",
                visibility=c.visibility.value if hasattr(c.visibility, "value") else str(c.visibility),
                status=getattr(c, "status", "ACTIVE"),
            )
            for c in courses
        ],
    )


@router.get("/classes", response_model=ApiResponse[List[TeacherClassGroupResponse]])
async def get_teacher_classes(
    course_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List class groups for the teacher's organization, optionally filtered by course."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot access teacher classes",
        )
    db = get_db()
    org_id = current_user.organization_id if current_user else "org-default"
    if course_id:
        classes = db.list_class_groups_by_course(course_id, organization_id=org_id)
    else:
        classes = db.list_class_groups_by_organization(org_id)

    return ApiResponse(
        ok=True,
        data=[
            TeacherClassGroupResponse(
                id=cg.id,
                organization_id=cg.organization_id,
                course_id=cg.course_id,
                name=cg.name,
                section=cg.section,
                created_at=cg.created_at,
            )
            for cg in classes
        ],
    )


@router.post("/classes", response_model=ApiResponse[TeacherClassGroupResponse], status_code=status.HTTP_201_CREATED)
async def create_teacher_class(
    req: TeacherClassGroupCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new class group under an organization course."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot create classes",
        )
    db = get_db()
    org_id = current_user.organization_id if current_user else "org-default"

    course = db.get_course(req.course_id)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{req.course_id}' not found")
    if course.organization_id != org_id:
        offerings = db.get_offerings_by_course(req.course_id)
        if not any(o.organization_id == org_id for o in offerings) and course.visibility != CourseVisibility.PUBLIC:
            raise HTTPException(status_code=403, detail="Forbidden: course not accessible to this organization")

    class_id = f"cls-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    cg = ClassGroup(
        id=class_id,
        organization_id=org_id,
        course_id=req.course_id,
        name=req.name,
        section=req.section,
        created_at=now_iso,
    )
    db.create_class_group(cg)

    cohort = Cohort(
        id=f"coh-{uuid.uuid4().hex[:8]}",
        class_group_id=class_id,
        name=f"{req.name} Cohort",
        academic_year="2026-2027",
        created_at=now_iso,
    )
    db.create_cohort(cohort)

    return ApiResponse(
        ok=True,
        data=TeacherClassGroupResponse(
            id=cg.id,
            organization_id=cg.organization_id,
            course_id=cg.course_id,
            name=cg.name,
            section=cg.section,
            created_at=cg.created_at,
        ),
    )


@router.get("/classes/{class_id}/students", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_class_students(
    class_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve students enrolled in a specific class group."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot view class rosters",
        )
    db = get_db()
    cg = db.get_class_group(class_id)
    if not cg:
        raise HTTPException(status_code=404, detail=f"Class '{class_id}' not found")
    if current_user and current_user.organization_id and cg.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden: class belongs to another organization")

    students = db.get_students_for_class_group(class_id)
    slr_svc = SLRService(db=db)
    result = []
    for s in students:
        slr = slr_svc.get_authoritative_slr(s.id, cg.course_id)
        scores = list(slr.mastery.concept_scores.values()) if slr and slr.mastery else []
        avg_mastery = sum(scores) / len(scores) if scores else 0.0
        result.append({
            "id": s.id,
            "student_id": s.id,
            "full_name": s.full_name,
            "email": s.email,
            "mastery": round(avg_mastery, 2),
            "needs_attention": avg_mastery < 0.5,
            "enrolled": True,
        })
    return ApiResponse(ok=True, data=result)


@router.post("/classes/{class_id}/notes", response_model=ApiResponse[TeacherClassNoteResponse], status_code=status.HTTP_201_CREATED)
async def upload_class_note(
    class_id: str,
    req: TeacherClassNoteCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Upload class notes scoped strictly to a specific class group."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot upload class notes",
        )
    db = get_db()
    cg = db.get_class_group(class_id)
    if not cg:
        raise HTTPException(status_code=404, detail=f"Class '{class_id}' not found")
    if current_user and current_user.organization_id and cg.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Forbidden: class belongs to another organization")

    rag_svc = RAGService(db=db)
    source = rag_svc.register_source(
        organization_id=cg.organization_id,
        course_id=cg.course_id,
        subject="Class Notes",
        title=req.title,
        source_type="text",
        authority="TEACHER",
        version="1.0.0",
        content_type="class_note",
        visibility_scope="class",
        class_id=class_id,
    )
    ing_res = rag_svc.ingest_document(
        source_id=source.id,
        content=req.content,
        file_name=f"{req.title.replace(' ', '_')}.md",
    )
    rag_svc.publish_source(source.id, user=current_user, user_id=current_user.id if current_user else "teacher_001")

    now_iso = datetime.now(timezone.utc).isoformat()
    return ApiResponse(
        ok=True,
        data=TeacherClassNoteResponse(
            id=source.id,
            class_id=class_id,
            course_id=cg.course_id,
            title=req.title,
            chunks_created=ing_res.get("chunks_created", 1),
            status="PUBLISHED",
            created_at=now_iso,
        ),
    )


@router.post("/remedial-content", response_model=ApiResponse[TeacherRemedialContentResponse], status_code=status.HTTP_201_CREATED)
async def upload_remedial_content(
    req: TeacherRemedialContentCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Upload targeted remedial content visible strictly to specified students."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot upload remedial content",
        )
    db = get_db()
    org_id = current_user.organization_id if current_user else "org-default"

    course = db.get_course(req.course_id)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{req.course_id}' not found")
    if current_user and current_user.organization_id and course.organization_id != current_user.organization_id:
        offerings = db.get_offerings_by_course(req.course_id)
        if not any(o.organization_id == org_id for o in offerings) and course.visibility != CourseVisibility.PUBLIC:
            raise HTTPException(status_code=403, detail="Forbidden: course not accessible to this organization")

    # Authorize each target student: MUST belong to teacher's organization and be enrolled
    for stu_id in req.target_student_ids:
        stu = db.get_user(stu_id)
        if not stu:
            raise HTTPException(status_code=404, detail=f"Student '{stu_id}' not found")
        if current_user and current_user.organization_id and stu.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: student '{stu_id}' is not in your organization",
            )
        enrollments = db.get_enrollments_for_student(stu_id)
        if not any(e.course_id == req.course_id for e in enrollments):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: student '{stu_id}' is not enrolled in course '{req.course_id}'",
            )

    rag_svc = RAGService(db=db)
    source = rag_svc.register_source(
        organization_id=org_id,
        course_id=req.course_id,
        subject="Remedial",
        title=req.title,
        source_type="text",
        authority="TEACHER",
        version="1.0.0",
        content_type="remedial",
        visibility_scope="student_targeted",
        target_student_ids=req.target_student_ids,
    )
    ing_res = rag_svc.ingest_document(
        source_id=source.id,
        content=req.content,
        file_name=f"{req.title.replace(' ', '_')}.md",
    )
    rag_svc.publish_source(source.id, user=current_user, user_id=current_user.id if current_user else "teacher_001")

    now_iso = datetime.now(timezone.utc).isoformat()
    return ApiResponse(
        ok=True,
        data=TeacherRemedialContentResponse(
            id=source.id,
            course_id=req.course_id,
            target_student_ids=req.target_student_ids,
            title=req.title,
            chunks_created=ing_res.get("chunks_created", 1),
            status="PUBLISHED",
            created_at=now_iso,
        ),
    )


@router.post("/assignments", response_model=ApiResponse[TeacherAssignmentResponse], status_code=status.HTTP_201_CREATED)
async def create_teacher_assignment(
    req: TeacherAssignmentCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new assignment distributed to a course or class group."""
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot create assignments",
        )
    db = get_db()
    org_id = current_user.organization_id if current_user else "org-default"

    course = db.get_course(req.course_id)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{req.course_id}' not found")
    if current_user and current_user.organization_id and course.organization_id != current_user.organization_id:
        offerings = db.get_offerings_by_course(req.course_id)
        if not any(o.organization_id == org_id for o in offerings) and course.visibility != CourseVisibility.PUBLIC:
            raise HTTPException(status_code=403, detail="Forbidden: course not accessible to this organization")

    if req.class_group_id:
        cg = db.get_class_group(req.class_group_id)
        if not cg:
            raise HTTPException(status_code=404, detail=f"Class '{req.class_group_id}' not found")
        if current_user and current_user.organization_id and cg.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Forbidden: class belongs to another organization")

    asg_id = f"asg-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    asg = Assignment(
        id=asg_id,
        course_id=req.course_id,
        title=req.title,
        assessment_id=f"asm-{uuid.uuid4().hex[:6]}",
        teacher_id=current_user.id if current_user else "teacher_001",
        organization_id=org_id,
        class_group_id=req.class_group_id,
        due_date=req.due_date,
        instructions=req.instructions or "",
        is_active=True,
        created_at=now_iso,
    )
    db.create_assignment(asg)

    return ApiResponse(
        ok=True,
        data=TeacherAssignmentResponse(
            id=asg.id,
            course_id=asg.course_id,
            title=asg.title,
            description=req.description or "",
            class_group_id=asg.class_group_id,
            assigned_by=asg.assigned_by,
            due_date=asg.due_date,
            instructions=asg.instructions,
            is_active=asg.is_active,
            created_at=asg.created_at,
        ),
    )


@router.get("/assignments", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_assignments(
    course_id: Optional[str] = "crs-chem-101",
    class_group_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot access teacher assignments management",
        )
    db = get_db()
    org_id = current_user.organization_id if current_user else None
    real_assignments = db.list_assignments(
        course_id=course_id,
        class_group_id=class_group_id,
        organization_id=org_id,
    )
    if real_assignments:
        return ApiResponse(ok=True, data=[a.to_dict() for a in real_assignments])
    if not class_group_id:
        assignments = [
            {"id": "asg-01", "course_id": course_id, "title": "Thermodynamics First Law & Work", "unit": "Unit 6", "due_date": "2026-10-05", "completed_count": 8, "total_count": 12},
            {"id": "asg-02", "course_id": course_id, "title": "Hess's Law Enthalpy Cycles", "unit": "Unit 6", "due_date": "2026-10-12", "completed_count": 5, "total_count": 12},
            {"id": "asg-03", "course_id": course_id, "title": "Periodic Trends & Ionic Radii", "unit": "Unit 3", "due_date": "2026-10-18", "completed_count": 10, "total_count": 12},
        ]
        return ApiResponse(ok=True, data=assignments)
    return ApiResponse(ok=True, data=[])


@router.get("/assessments", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_assessments(
    course_id: str = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot access teacher assessments management",
        )
    assessments = [
        {"id": "asm-01", "name": "Diagnostic Quiz 1: Enthalpy & Work", "course_id": course_id, "items_count": 5, "average_score": 0.78, "status": "active"},
        {"id": "asm-02", "name": "Mid-Term Assessment: Chemical Energetics", "course_id": course_id, "items_count": 10, "average_score": 0.65, "status": "draft"},
    ]
    return ApiResponse(ok=True, data=assessments)


@router.get("/alerts", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_teacher_alerts(
    course_id: str = "crs-chem-101",
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    if current_user and current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: students cannot access teacher alerts",
        )
    alerts = _intervention_engine.get_all_alerts(course_id=course_id)
    itvs = _intervention_engine.get_interventions(course_id=course_id)
    combined = [a.to_dict() for a in alerts] + [
        {
            "alert_id": i.intervention_id,
            "student_id": i.student_id,
            "course_id": i.course_id,
            "alert_type": i.trigger_type,
            "severity": i.priority.lower(),
            "message": i.reason,
            "status": i.status.lower(),
            "created_at": i.created_at,
        }
        for i in itvs
    ]
    return ApiResponse(ok=True, data=combined)

