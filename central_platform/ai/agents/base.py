"""Gayatri AI Platform — Agent Contracts & Base Schema (Phase 44).

Defines standardized Pydantic models (AgentContext, AgentResult) and the
canonical BaseAgent abstract base class governing all 47 agents across
the 5 platform clusters (Educational, BFSI, Research, Coding, Governance).
"""
from __future__ import annotations

import abc
import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Normalized execution context provided to any agent."""
    cluster: str = Field(..., description="Cluster identifier: A, B, C, D, or E")
    agent_id: int = Field(..., description="Unique agent identifier between 1 and 47")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Input payload / task arguments")
    user_id: Optional[str] = Field(None, description="Authenticated user ID invoking the agent")
    user_role: Optional[str] = Field("student", description="Canonical role of caller (student, teacher, org_admin, etc.)")
    organization_id: Optional[str] = Field("org-default", description="Multi-tenant organization boundary")
    session_id: Optional[str] = Field(None, description="Active session ID if applicable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Operational metadata and directives")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def get_payload_hash(self) -> str:
        """Deterministic SHA-256 hash of the input payload for audit tracking."""
        raw = str(sorted(self.payload.items()))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class AgentResult(BaseModel):
    """Standardized output produced by any agent execution."""
    success: bool = Field(..., description="Whether the agent completed successfully")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence estimation score (0.0 to 1.0)")
    output: Dict[str, Any] = Field(default_factory=dict, description="Structured agent findings or generation")
    citations: List[str] = Field(default_factory=list, description="Grounding citations (documents, pages, clauses)")
    audit_trail: Optional[Dict[str, Any]] = Field(None, description="Governance and traceability telemetry")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    execution_time_ms: float = Field(0.0, description="Total execution duration in milliseconds")


class BaseAgent(abc.ABC):
    """Abstract Base Agent for all 47 platform agents."""

    name: str = "BaseAgent"
    cluster: str = "A"
    agent_id: int = 1
    description: str = ""
    version: str = "1.0.0"
    required_role: Optional[str] = None  # Minimum role required if restricted

    def pre_execute(self, context: AgentContext) -> None:
        """Lifecycle hook: Security, RBAC validation, and input sanitization before execution."""
        # 1. Cluster & ID integrity check
        if context.agent_id != self.agent_id or context.cluster.upper() != self.cluster.upper():
            raise ValueError(
                f"Context mismatch: Agent {self.cluster}{self.agent_id} invoked with context {context.cluster}{context.agent_id}"
            )

        # 2. In-house RBAC gate
        from central_platform.ai.agents.registry import get_governance_agent
        rbac_agent = get_governance_agent(42)  # Agent 42: RBAC Enforcement
        if rbac_agent:
            rbac_result = rbac_agent.check_permission(context, self.required_role)
            if not rbac_result.get("allowed", True):
                raise PermissionError(
                    f"RBAC Enforcement Failure: Role '{context.user_role}' denied access to {self.name} "
                    f"({rbac_result.get('reason', 'Insufficient permissions')})"
                )

    @abc.abstractmethod
    def execute(self, context: AgentContext) -> AgentResult:
        """Core domain agent execution logic. Must be implemented by concrete subclasses."""
        raise NotImplementedError("Every agent must implement execute(context)")

    def post_execute(self, context: AgentContext, result: AgentResult, duration_ms: float) -> AgentResult:
        """Lifecycle hook: Audit logging, deterministic citation grounding, and result telemetry."""
        result.execution_time_ms = round(duration_ms, 2)

        # In-house Audit Trail Logging (Agent 43)
        from central_platform.ai.agents.registry import get_governance_agent
        audit_agent = get_governance_agent(43)  # Agent 43: Audit Trail
        if audit_agent:
            audit_entry = audit_agent.record_invocation(
                agent_name=self.name,
                cluster=self.cluster,
                agent_id=self.agent_id,
                context=context,
                result=result,
            )
            result.audit_trail = audit_entry

        return result

    def run(self, context: AgentContext) -> AgentResult:
        """Canonical execution pipeline: pre_execute -> execute -> post_execute."""
        start_time = time.perf_counter()
        try:
            self.pre_execute(context)
            result = self.execute(context)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            error_result = AgentResult(
                success=False,
                confidence=0.0,
                output={},
                citations=[],
                error=str(exc),
                execution_time_ms=round(duration_ms, 2),
            )
            return self.post_execute(context, error_result, duration_ms)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return self.post_execute(context, result, duration_ms)
