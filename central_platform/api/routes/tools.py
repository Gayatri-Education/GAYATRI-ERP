"""Gayatri AI Platform — Course Tools API Endpoints (Phase 08).

Master Plan Section 12.8:
- Dynamic tool capability listing
- Course-scoped policy filtering
- Secure, resource-bounded execution with RBAC enforcement
"""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.api.schemas import (
    ApiResponse,
    ToolCapabilityResponse,
    ToolExecuteRequest,
    ToolExecuteResponse,
)
from central_platform.auth.dependencies import (
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.models.schema import CourseToolPolicy, User, UserRole
from central_platform.tools import (
    CourseToolPolicyViolation,
    ToolAuthorizationError,
    ToolCapability,
    ToolExecutionContext,
    ToolExecutionEngine,
    ToolNotFoundError,
    ToolTimeoutError,
    ToolValidationError,
    get_configured_tool_registry,
)

logger = logging.getLogger("gayatri.central_platform.api.routes.tools")

router = APIRouter(prefix="/tools", tags=["Course Tools"])


def _to_capability_response(cap: ToolCapability) -> ToolCapabilityResponse:
    return ToolCapabilityResponse(
        tool_id=cap.tool_id,
        name=cap.name,
        description=cap.description,
        category=cap.category.value if hasattr(cap.category, "value") else str(cap.category),
        allowed_roles=[
            r.value if hasattr(r, "value") else str(r) for r in cap.allowed_roles
        ],
        resource_limits=cap.resource_limits.to_dict(),
        input_schema=cap.input_schema,
        output_schema=cap.output_schema,
    )


@router.get("", response_model=ApiResponse[List[ToolCapabilityResponse]])
async def list_tools(
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List all registered tools and their declared capabilities."""
    registry = get_configured_tool_registry()
    caps = registry.list_capabilities()
    return ApiResponse(ok=True, data=[_to_capability_response(c) for c in caps])


@router.get("/{course_id}", response_model=ApiResponse[List[ToolCapabilityResponse]])
async def list_course_tools(
    course_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List tools enabled under the active version policy for a specific course."""
    registry = get_configured_tool_registry()
    db = get_db()
    
    # Try resolving active course version policy
    policy: Optional[CourseToolPolicy] = None
    try:
        versions = db.list_course_versions(course_id)
        if versions:
            # Pick published or latest version
            pub_v = next((v for v in versions if getattr(v, "status", "") in ("published", "PUBLISHED")), versions[0])
            policy = pub_v.tool_policy
    except Exception as exc:
        logger.warning("Failed to resolve course version tool policy for course %s: %s", course_id, exc)

    if policy is None:
        # Default policy enabling calculator and equation_balancer for backwards compatibility
        policy = CourseToolPolicy(calculator=True, equation_balancer=True)

    enabled_caps = registry.list_tools_for_policy(policy)
    return ApiResponse(ok=True, data=[_to_capability_response(c) for c in enabled_caps])


@router.post("/execute", response_model=ApiResponse[ToolExecuteResponse])
async def execute_tool(
    req: ToolExecuteRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Execute a pedagogical computational tool within course policy and resource limits."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    registry = get_configured_tool_registry()
    engine = ToolExecutionEngine(registry)
    db = get_db()

    # 1. Resolve Course Tool Policy
    policy: Optional[CourseToolPolicy] = None
    try:
        versions = db.list_course_versions(req.course_id)
        if versions:
            pub_v = next((v for v in versions if getattr(v, "status", "") in ("published", "PUBLISHED")), versions[0])
            policy = pub_v.tool_policy
    except Exception as exc:
        logger.warning("Failed to resolve course version tool policy for course %s: %s", req.course_id, exc)

    if policy is None:
        policy = CourseToolPolicy(
            calculator=True,
            equation_balancer=True,
            code_execution=True,
            graphing=True,
            periodic_table=True,
        )

    # 2. Resolve User Role
    user_role = current_user.role if current_user else UserRole.STUDENT
    student_id = current_user.id if current_user and current_user.role == UserRole.STUDENT else None

    # 3. Build Execution Context
    ctx = ToolExecutionContext(
        course_id=req.course_id,
        student_id=student_id,
        session_id=req.session_id,
        user_role=user_role,
        course_policy=policy,
    )

    # 4. Execute via Engine
    try:
        result = engine.execute_tool(
            tool_id=req.tool_id,
            arguments=req.arguments,
            context=ctx,
            strict_exceptions=True,
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CourseToolPolicyViolation as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ToolAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ToolValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ToolTimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tool error: {str(exc)}")

    return ApiResponse(
        ok=True,
        data=ToolExecuteResponse(
            tool_id=req.tool_id,
            success=result.success,
            output=result.output,
            error=result.error,
            execution_time_ms=result.execution_time_ms,
            resource_usage=result.resource_usage,
        ),
    )
