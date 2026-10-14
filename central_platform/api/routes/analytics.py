"""Gayatri AI Platform — Authoritative Analytics & Telemetry API Endpoints (Phase 20).

Derives real student learning analytics, cohort mastery distributions, teacher intervention rates,
and admin platform observability directly from authoritative event stores and databases.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.analytics.service import AnalyticsService
from central_platform.auth.dependencies import (
    get_current_user_optional,
    is_production_mode,
)
from central_platform.rbac.engine import normalize_role
from central_platform.api.schemas import (
    AdminSystemAnalyticsResponse,
    ApiResponse,
    CohortAnalyticsResponse,
    StudentAnalyticsResponse,
    TeacherClassAnalyticsResponse,
)
from central_platform.models.schema import User, UserRole

router = APIRouter(prefix="/analytics", tags=["Analytics"])

_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service


# ── 1. Student Learning Analytics ─────────────────────────────────────────────

@router.get("/student/{student_id}", response_model=ApiResponse[StudentAnalyticsResponse])
async def get_student_analytics(
    student_id: str,
    course_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve authoritative student learning analytics (mastery, accuracy, retention, velocity, weak concepts)."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view student analytics",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role == UserRole.STUDENT and current_user.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students may only view their own analytics",
            )
        if user_role == UserRole.PARENT:
            from central_platform.privacy.policies import ParentVisibilityLevel, PrivacyRulesEngine
            if not PrivacyRulesEngine.is_parent_linked(current_user.id, student_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: parent is not linked to this student",
                )
            setting = PrivacyRulesEngine.get_privacy_setting(current_user.id, student_id)
            if setting.visibility_level == ParentVisibilityLevel.BLOCKED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: access to student analytics is blocked by privacy policy",
                )
        if user_role in (UserRole.TEACHER, UserRole.ORG_ADMIN):
            target_student = service.db.get_user(student_id)
            if target_student and target_student.organization_id and current_user.organization_id:
                if target_student.organization_id not in ("org-default", None) and current_user.organization_id not in ("org-default", None):
                    if target_student.organization_id != current_user.organization_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Forbidden: cross-organization student access prohibited",
                        )
            if user_role == UserRole.TEACHER:
                assigned = service.db.get_assigned_student_ids_for_teacher(current_user.id)
                if assigned and student_id not in assigned:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Forbidden: student '{student_id}' is not assigned to this teacher",
                    )

    analytics = service.get_student_analytics(student_id=student_id, course_id=course_id)
    return ApiResponse(ok=True, data=StudentAnalyticsResponse(**analytics.to_dict()))


# ── 2. Cohort & Class Analytics ───────────────────────────────────────────────

@router.get("/cohort/{cohort_id}", response_model=ApiResponse[CohortAnalyticsResponse])
async def get_cohort_analytics(
    cohort_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve aggregate learning analytics, class mastery, misconceptions, and intervention metrics."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view cohort analytics",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role in (UserRole.STUDENT, UserRole.PARENT):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: role not authorized to view cohort analytics",
            )
        if user_role != UserRole.SUPER_ADMIN and current_user.organization_id:
            cohort = service.db.get_cohort(cohort_id)
            if cohort and cohort.organization_id and cohort.organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: cross-organization cohort access prohibited",
                )

    analytics = service.get_class_analytics(cohort_id=cohort_id)
    
    weak_concept_ids = [c["concept_id"] for c in analytics.difficult_concepts]
    frequent_misconceptions = [
        {"code": m["code"], "affected_students": m["affected_students"]}
        for m in analytics.misconceptions
    ]

    return ApiResponse(
        ok=True,
        data=CohortAnalyticsResponse(
            cohort_id=cohort_id,
            student_count=analytics.student_count,
            average_mastery=analytics.class_mastery,
            mastery_tiers=analytics.mastery_tiers,
            weak_concepts=weak_concept_ids,
            frequent_misconceptions=frequent_misconceptions,
            student_activity=analytics.student_activity,
            difficult_concepts=analytics.difficult_concepts,
            intervention_rates=analytics.intervention_rates,
            assessment_outcomes=analytics.assessment_outcomes,
        ),
    )


@router.get("/class", response_model=ApiResponse[TeacherClassAnalyticsResponse])
async def get_teacher_class_analytics(
    cohort_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve full teacher class diagnostics: mastery, difficult concepts, misconceptions, and interventions."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view class analytics",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role in (UserRole.STUDENT, UserRole.PARENT):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: role not authorized to view class analytics",
            )
        if user_role != UserRole.SUPER_ADMIN and current_user.organization_id:
            if course_id:
                course = service.db.get_course(course_id)
                if course and course.organization_id and course.organization_id != current_user.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: cross-organization class access prohibited",
                    )
            if cohort_id:
                cohort = service.db.get_cohort(cohort_id)
                if cohort and cohort.organization_id and cohort.organization_id != current_user.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: cross-organization cohort access prohibited",
                    )

    analytics = service.get_class_analytics(cohort_id=cohort_id, course_id=course_id)
    return ApiResponse(ok=True, data=TeacherClassAnalyticsResponse(**analytics.to_dict()))


# ── 3. Admin System & Telemetry Analytics ─────────────────────────────────────

@router.get("/system", response_model=ApiResponse[AdminSystemAnalyticsResponse])
async def get_system_analytics(
    organization_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve platform-wide telemetry, DAU/WAU/MAU, course usage, AI token metrics, costs, and health."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view system analytics",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative privileges required to inspect system telemetry",
            )
        if user_role == UserRole.ORG_ADMIN:
            if organization_id and organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: cross-organization access to '{organization_id}' prohibited",
                )

    target_org_id = organization_id or (current_user.organization_id if current_user else None)
    analytics = service.get_system_analytics(organization_id=target_org_id)
    return ApiResponse(ok=True, data=AdminSystemAnalyticsResponse(**analytics.to_dict()))


@router.get("/ai", response_model=ApiResponse[Dict[str, Any]])
async def get_ai_usage_analytics(
    organization_id: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve AI model router token usage, provider latency percentiles, and cost attribution."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view AI observability analytics",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if current_user:
        user_role = normalize_role(current_user.role)
        if user_role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrative privileges required to inspect AI observability",
            )
        if user_role == UserRole.ORG_ADMIN:
            if organization_id and organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: cross-organization access to '{organization_id}' prohibited",
                )

    target_org_id = organization_id or (current_user.organization_id if current_user else None)
    analytics = service.get_system_analytics(organization_id=target_org_id)
    return ApiResponse(
        ok=True,
        data={
            "ai_usage": analytics.ai_usage,
            "cost": analytics.cost,
            "performance": analytics.performance,
        },
    )
