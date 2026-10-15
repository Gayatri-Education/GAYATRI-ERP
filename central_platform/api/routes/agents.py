"""Gayatri AI Platform — Agent Subsystem REST API Routes (Phase 44).

Exposes endpoints for:
- POST /agents/execute — Invoking any of the 47 registered agents
- GET  /agents/ — Listing registered agents with RBAC visibility filtering
- GET  /agents/{cluster}/{agent_id} — Retrieving agent descriptor
- GET  /agents/clusters — Summarizing cluster topology and readiness
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.ai.agents.base import AgentContext, AgentResult
from central_platform.ai.agents.registry import agent_registry
from central_platform.auth.dependencies import (
    get_current_user_optional,
    is_production_mode,
    normalize_role,
)
from central_platform.models.schema import User

logger = logging.getLogger("gayatri.api.routes.agents")

router = APIRouter(prefix="/agents", tags=["Agents Subsystem"])


# =====================================================================
# Request & Response Schemas
# =====================================================================

class AgentExecuteApiRequest(BaseModel):
    """Payload to execute a specific agent."""
    cluster: str = Field(..., description="Target cluster: A, B, C, D, or E", example="B")
    agent_id: int = Field(..., description="Unique agent identifier (1 to 47)", example=12)
    payload: Dict[str, Any] = Field(default_factory=dict, description="Task data for the agent")
    session_id: Optional[str] = Field(None, description="Optional active session identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional operational metadata")


class AgentExecuteApiResponse(BaseModel):
    """Standardized response from agent execution."""
    success: bool
    cluster: str
    agent_id: int
    agent_name: str
    confidence: float
    output: Dict[str, Any]
    citations: List[str]
    audit_trail: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    error: Optional[str] = None


class AgentSummaryResponse(BaseModel):
    """Descriptor for a registered agent."""
    cluster: str
    agent_id: int
    name: str
    description: str
    version: str
    required_role: Optional[str] = None


class ClusterSummaryResponse(BaseModel):
    """Summary of cluster state and registered agent counts."""
    clusters: Dict[str, Any]


# =====================================================================
# Endpoints
# =====================================================================

@router.post(
    "/execute",
    response_model=AgentExecuteApiResponse,
    summary="Execute a registered agent",
    status_code=status.HTTP_200_OK,
)
async def execute_agent(
    req: AgentExecuteApiRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> AgentExecuteApiResponse:
    """Execute an agent by cluster and agent ID through the governance pipeline."""
    # Production auth gate
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to invoke agents in production mode",
        )

    user_id = current_user.id if current_user else "anonymous"
    user_role = normalize_role(current_user.role).value if current_user else "student"
    org_id = getattr(current_user, "organization_id", "org-default") if current_user else "org-default"

    # Lookup agent from canonical registry
    agent = agent_registry.get_agent(req.cluster, req.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{req.cluster.upper()}:{req.agent_id}' is not registered on this platform",
        )

    # Build normalized context
    context = AgentContext(
        cluster=req.cluster.upper(),
        agent_id=req.agent_id,
        payload=req.payload,
        user_id=user_id,
        user_role=user_role,
        organization_id=org_id,
        session_id=req.session_id,
        metadata=req.metadata,
    )

    try:
        # Run canonical lifecycle: pre_execute (RBAC gate) -> execute -> post_execute (Audit)
        result: AgentResult = agent.run(context)
    except PermissionError as p_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(p_err),
        )
    except Exception as exc:
        logger.exception("Unexpected error during agent execution: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution encountered an unhandled error: {exc}",
        )

    return AgentExecuteApiResponse(
        success=result.success,
        cluster=req.cluster.upper(),
        agent_id=req.agent_id,
        agent_name=agent.name,
        confidence=result.confidence,
        output=result.output,
        citations=result.citations,
        audit_trail=result.audit_trail,
        execution_time_ms=result.execution_time_ms,
        error=result.error,
    )


@router.get(
    "/",
    response_model=List[AgentSummaryResponse],
    summary="List registered agents",
)
async def list_agents(
    cluster: Optional[str] = Query(None, description="Optional cluster filter (A, B, C, D, E)"),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> List[AgentSummaryResponse]:
    """List all registered agents, filtered by caller's role visibility."""
    user_role = normalize_role(current_user.role).value if current_user else "student"
    agents = agent_registry.list_agents(cluster=cluster, user_role=user_role)
    return [AgentSummaryResponse(**a) for a in agents]


@router.get(
    "/clusters",
    response_model=ClusterSummaryResponse,
    summary="Get topology of all 5 agent clusters",
)
async def get_clusters() -> ClusterSummaryResponse:
    """Retrieve operational topology and registration counts for all clusters."""
    stats = agent_registry.get_cluster_stats()
    return ClusterSummaryResponse(clusters=stats)


@router.get(
    "/{cluster}/{agent_id}",
    response_model=AgentSummaryResponse,
    summary="Get descriptor for a specific agent",
)
async def get_agent_detail(
    cluster: str,
    agent_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> AgentSummaryResponse:
    """Retrieve metadata for a specific agent."""
    agent = agent_registry.get_agent(cluster, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{cluster.upper()}:{agent_id}' not found",
        )

    return AgentSummaryResponse(
        cluster=agent.cluster,
        agent_id=agent.agent_id,
        name=agent.name,
        description=agent.description,
        version=agent.version,
        required_role=agent.required_role,
    )
