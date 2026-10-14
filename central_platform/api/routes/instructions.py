"""Gayatri AI Platform — Teacher Instructions API Endpoints (Phase 12).

Section 12.12: Real Online API Boundary
- Pure route/service separation connecting to PlatformDatabase & TeacherInstructionEngine
- 5-tier hierarchical instruction resolution (SESSION > STUDENT > CLASS > COURSE > ORGANIZATION)
- Scoped multi-tenant and role-based instruction authorization
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.api.schemas import (
    ApiResponse,
    TeacherInstructionCreateRequest,
    TeacherInstructionResponse,
)
from central_platform.auth.dependencies import (
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    InstructionScope,
    TeacherInstructionRecord,
    User,
    UserRole,
)
from central_platform.teacher.instruction import TeacherInstructionValidator

logger = logging.getLogger("gayatri.api.instructions")

router = APIRouter(prefix="/instructions", tags=["Teacher Instructions"])


def _to_instruction_response(rec: TeacherInstructionRecord) -> TeacherInstructionResponse:
    """Map domain TeacherInstructionRecord to TeacherInstructionResponse."""
    created_at_str = (
        rec.created_at.isoformat()
        if hasattr(rec.created_at, "isoformat")
        else str(rec.created_at or datetime.now(timezone.utc).isoformat())
    )
    scope_str = (
        rec.scope_type.value
        if hasattr(rec.scope_type, "value")
        else str(rec.scope_type or "COURSE")
    )
    return TeacherInstructionResponse(
        instruction_id=rec.id,
        teacher_id=rec.teacher_id,
        student_id=rec.student_id or "all",
        course_id=rec.course_id,
        instruction_text=rec.instruction_text,
        priority=rec.priority,
        concept_scope=rec.concept_scope or "ALL",
        scope_type=scope_str,
        organization_id=rec.organization_id,
        course_version_id=rec.course_version_id,
        class_id=rec.class_id,
        session_id=rec.session_id,
        version=rec.version or 1,
        is_active=rec.is_active,
        status=rec.status or "ACTIVE",
        safety_status=rec.safety_status or "VALIDATED",
        safety_reasons=rec.safety_reasons or [],
        created_at=created_at_str,
    )


@router.get("", response_model=ApiResponse[List[TeacherInstructionResponse]])
async def list_instructions(
    course_id: Optional[str] = Query(None, description="Course ID filter"),
    organization_id: Optional[str] = Query(None, description="Organization ID filter"),
    class_id: Optional[str] = Query(None, description="Class ID filter"),
    student_id: Optional[str] = Query(None, description="Student ID filter"),
    session_id: Optional[str] = Query(None, description="Session ID filter"),
    hierarchical: bool = Query(True, description="Resolve 5-tier instruction cascade"),
    db: PlatformDatabase = Depends(get_db),
):
    """List teacher instructions with optional 5-tier hierarchical cascading resolution."""
    if hierarchical and (course_id or organization_id or class_id or student_id or session_id):
        instructions = db.get_hierarchical_teacher_instructions(
            course_id=course_id,
            organization_id=organization_id,
            class_id=class_id,
            student_id=student_id,
            session_id=session_id,
            only_active=True,
        )
    else:
        instructions = db.get_teacher_instructions(course_id=course_id)
        if organization_id:
            instructions = [i for i in instructions if i.organization_id == organization_id]
        if class_id:
            instructions = [i for i in instructions if i.class_id == class_id]
        if student_id:
            instructions = [i for i in instructions if i.student_id in (student_id, "all")]

    return ApiResponse(ok=True, data=[_to_instruction_response(i) for i in instructions])


@router.post("", response_model=ApiResponse[TeacherInstructionResponse], status_code=status.HTTP_201_CREATED)
async def create_instruction(
    req: TeacherInstructionCreateRequest,
    db: PlatformDatabase = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a scoped teacher instruction. Requires TEACHER, ORG_ADMIN, or SUPER_ADMIN role."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to create teacher instructions",
            headers={"WWW-Authenticate": "Bearer"},
        )
    actor = current_user or User(
        id="usr-teacher-01",
        email="teacher@platform.local",
        full_name="Platform Teacher",
        role=UserRole.TEACHER,
        organization_id=req.organization_id or "org-default",
    )

    allowed_roles = {UserRole.TEACHER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN, "TEACHER", "ORG_ADMIN", "SUPER_ADMIN"}
    user_role = actor.role.value if isinstance(actor.role, UserRole) else str(actor.role).upper()
    if user_role not in allowed_roles and actor.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot create teacher instructions.",
        )

    # Cross-tenant and student isolation check
    if user_role not in (UserRole.SUPER_ADMIN.value, "SUPER_ADMIN"):
        if req.organization_id and actor.organization_id and req.organization_id != actor.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: cross-organization instruction creation is prohibited ('{req.organization_id}' != '{actor.organization_id}')",
            )
        if req.student_id and req.student_id != "all":
            st_rec = db.get_user(req.student_id)
            if st_rec and st_rec.organization_id and actor.organization_id and st_rec.organization_id != actor.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: student '{req.student_id}' belongs to another organization",
                )

    # Invariant and safety validation
    val = TeacherInstructionValidator.validate(req.instruction)
    if not val.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Instruction failed security/policy validation: {'; '.join(val.violations)}",
        )

    # Determine scope type
    scope_str = (req.scope_type or "COURSE").upper()
    try:
        scope_type = InstructionScope(scope_str)
    except ValueError:
        scope_type = InstructionScope.COURSE

    # Ensure organization and teacher user exist in database to satisfy foreign key constraints
    org_id = req.organization_id or actor.organization_id or "org-default"
    if not db.get_organization(org_id):
        from central_platform.models.schema import Organization
        db.create_organization(Organization(id=org_id, name=org_id, slug=org_id))
    if not db.get_user(actor.id):
        actor_user = User(
            id=actor.id,
            email=actor.email or f"{actor.id}@platform.local",
            full_name=actor.full_name or f"Teacher {actor.id}",
            role=actor.role if isinstance(actor.role, UserRole) else UserRole.TEACHER,
            organization_id=org_id,
        )
        db.create_user(actor_user)

    inst_id = f"inst-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    rec = TeacherInstructionRecord(
        id=inst_id,
        teacher_id=actor.id,
        student_id=req.student_id or "all",
        course_id=req.course_id,
        instruction_text=req.instruction,
        concept_scope=req.concept_scope or "ALL",
        priority=req.priority,
        is_active=True,
        organization_id=req.organization_id or actor.organization_id,
        course_version_id=req.course_version_id,
        class_id=req.class_id,
        session_id=req.session_id,
        scope_type=scope_type,
        status="ACTIVE",
        safety_status=val.safety_status,
        safety_reasons=val.violations,
        start_at=req.start_at,
        expires_at=req.expires_at,
        version=1,
        audit_trail=[],
        created_at=now,
        updated_at=now,
    )
    created = db.create_teacher_instruction(rec)
    return ApiResponse(ok=True, data=_to_instruction_response(created))


@router.get("/{instruction_id}", response_model=ApiResponse[TeacherInstructionResponse])
async def get_instruction(
    instruction_id: str,
    db: PlatformDatabase = Depends(get_db),
):
    """Retrieve an instruction by ID."""
    inst = db.get_teacher_instruction(instruction_id)
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instruction '{instruction_id}' not found.",
        )
    return ApiResponse(ok=True, data=_to_instruction_response(inst))


@router.delete("/{instruction_id}", response_model=ApiResponse[Dict[str, Any]])
async def delete_instruction(
    instruction_id: str,
    db: PlatformDatabase = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Deactivate or remove a teacher instruction."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to delete teacher instructions",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = current_user.role.value if isinstance(current_user.role, UserRole) else str(current_user.role).upper()
        if user_role in (UserRole.STUDENT.value, "STUDENT"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students cannot delete teacher instructions.",
            )
    inst = db.get_teacher_instruction(instruction_id)
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instruction '{instruction_id}' not found.",
        )
    db.delete_teacher_instruction(instruction_id)
    return ApiResponse(ok=True, data={"deleted": True, "instruction_id": instruction_id})
