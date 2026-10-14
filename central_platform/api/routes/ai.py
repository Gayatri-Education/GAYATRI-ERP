"""Gayatri AI Platform — Unified AI Gateway & Model Router API Endpoints (Phase 17).

Exposes provider-neutral AI execution, routing preview, provider management,
and kill switch / budget safety controls.
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from central_platform.ai.gateway import AIGatewayService
from central_platform.ai.schema import (
    AIExecutionRequest,
    ModelTier,
    ProviderConfig,
    ProviderType,
    TaskType,
)
from central_platform.api.schemas import (
    AIAllowlistUpdateRequest,
    AIBudgetStatusResponse,
    AIBudgetUpdateRequest,
    AIExecutionApiRequest,
    AIExecutionApiResponse,
    AIExecutionLogResponse,
    AIKillSwitchRequest,
    AIProviderCreateRequest,
    AIProviderResponse,
    AIRoutePreviewRequest,
    AIRoutePreviewResponse,
    AIStatusResponse,
    ApiResponse,
    ErrorDetail,
)
from central_platform.auth.dependencies import get_db

router = APIRouter(prefix="/ai", tags=["AI Gateway"])
_ai_gateway_service: Optional[AIGatewayService] = None


def get_ai_gateway_service() -> AIGatewayService:
    global _ai_gateway_service
    if _ai_gateway_service is None:
        db = get_db()
        _ai_gateway_service = AIGatewayService(db=db)
    return _ai_gateway_service


@router.get("/status", response_model=ApiResponse[AIStatusResponse])
async def get_ai_status():
    """Retrieve AI model router health, token usage, active provider, and budget."""
    svc = get_ai_gateway_service()
    data = svc.get_status()
    return ApiResponse(
        ok=True,
        data=AIStatusResponse(
            gateway_status=data["gateway_status"],
            active_provider=data["active_provider"],
            active_model=data["active_model"],
            available_providers=data["available_providers"],
            token_usage_today=data["token_usage_today"],
            tokens_measured_today=data.get("tokens_measured_today", 0),
            tokens_estimated_today=data.get("tokens_estimated_today", 0),
            token_provenance=data.get("token_provenance", "UNKNOWN"),
            token_breakdown=data.get("token_breakdown", {}),
            budget_remaining_usd=data["budget_remaining_usd"],
            kill_switch_active=data["kill_switch_active"],
            providers_status=data.get("providers_status", {}),
            last_successful_inference_at=data.get("last_successful_inference_at"),
        ),
    )


@router.post("/execute", response_model=ApiResponse[AIExecutionApiResponse])
async def execute_ai_prompt(req: AIExecutionApiRequest):
    """Execute AI generation through the Gateway pipeline with routing, policy checks, and failover."""
    svc = get_ai_gateway_service()
    try:
        task_type_enum = TaskType(req.task_type) if req.task_type in TaskType._value2member_map_ else TaskType.GENERAL
    except Exception:
        task_type_enum = TaskType.GENERAL

    exec_req = AIExecutionRequest(
        prompt=req.prompt,
        system_prompt=req.system_prompt,
        task_type=task_type_enum,
        student_id=req.student_id,
        course_id=req.course_id,
        preferred_provider=req.preferred_provider,
        preferred_model=req.preferred_model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        teacher_directives=req.teacher_directives,
        rag_context=req.rag_context,
    )

    result = svc.execute(exec_req)
    if not result.success:
        return ApiResponse(
            ok=False,
            error=ErrorDetail(
                code=result.error_class or "AI_EXECUTION_ERROR",
                message=result.error_message or "AI Execution failed",
            ),
            data=AIExecutionApiResponse(
                request_id=result.request_id,
                content="",
                provider=result.provider,
                model=result.model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
                latency_ms=result.latency_ms,
                estimated_cost_usd=result.estimated_cost_usd,
                success=False,
                error_class=result.error_class,
                error_message=result.error_message,
                fallback_used=result.fallback_used,
                original_provider=result.original_provider,
                mock=getattr(result, "mock", False),
                status=result.status.value if hasattr(result.status, "value") else str(result.status or ""),
            ),
        )


    return ApiResponse(
        ok=True,
        data=AIExecutionApiResponse(
            request_id=result.request_id,
            content=result.content,
            provider=result.provider,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            latency_ms=result.latency_ms,
            estimated_cost_usd=result.estimated_cost_usd,
            success=True,
            fallback_used=result.fallback_used,
            original_provider=result.original_provider,
            mock=getattr(result, "mock", False),
            status=result.status.value if hasattr(result.status, "value") else str(result.status or "MODEL_SUCCESS"),
        ),
    )



@router.get("/providers", response_model=ApiResponse[List[AIProviderResponse]])
async def list_providers():
    """List all registered AI providers and their configured models."""
    svc = get_ai_gateway_service()
    providers = list(svc.router.providers.values())
    return ApiResponse(
        ok=True,
        data=[
            AIProviderResponse(
                provider_name=p.provider_name,
                provider_type=p.provider_type.value if isinstance(p.provider_type, ProviderType) else str(p.provider_type),
                api_key_ref=p.api_key_ref,
                base_url=p.base_url,
                enabled=p.enabled,
                priority=p.priority,
                fallback_provider=p.fallback_provider,
                rate_limit_rpm=p.rate_limit_rpm,
                daily_budget_usd=p.daily_budget_usd,
                models=[m.to_dict() for m in p.models],
            )
            for p in providers
        ],
    )


@router.post("/providers", response_model=ApiResponse[AIProviderResponse], status_code=status.HTTP_201_CREATED)
async def create_or_update_provider(req: AIProviderCreateRequest):
    """Register or update an AI provider configuration."""
    svc = get_ai_gateway_service()
    try:
        ptype = ProviderType(req.provider_type) if req.provider_type in ProviderType._value2member_map_ else ProviderType.MOCK
    except Exception:
        ptype = ProviderType.MOCK

    cfg = ProviderConfig(
        provider_name=req.provider_name,
        provider_type=pttype,
        api_key_ref=req.api_key_ref,
        base_url=req.base_url,
        enabled=req.enabled,
        priority=req.priority,
        fallback_provider=req.fallback_provider,
        rate_limit_rpm=req.rate_limit_rpm,
        daily_budget_usd=req.daily_budget_usd,
    )
    svc.register_provider(cfg)

    return ApiResponse(
        ok=True,
        data=AIProviderResponse(
            provider_name=cfg.provider_name,
            provider_type=cfg.provider_type.value,
            api_key_ref=cfg.api_key_ref,
            base_url=cfg.base_url,
            enabled=cfg.enabled,
            priority=cfg.priority,
            fallback_provider=cfg.fallback_provider,
            rate_limit_rpm=cfg.rate_limit_rpm,
            daily_budget_usd=cfg.daily_budget_usd,
            models=[m.to_dict() for m in cfg.models],
        ),
    )


@router.post("/providers/{provider_name}/toggle", response_model=ApiResponse[dict])
async def toggle_provider(provider_name: str, enabled: bool = Query(...)):
    """Enable or disable a specific provider (provider kill switch)."""
    svc = get_ai_gateway_service()
    if provider_name not in svc.router.providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found.")

    svc.router.providers[provider_name].enabled = enabled
    svc.policy_engine.provider_kill_switches[provider_name] = not enabled
    return ApiResponse(ok=True, data={"provider_name": provider_name, "enabled": enabled})


@router.post("/killswitch", response_model=ApiResponse[dict])
async def toggle_global_killswitch(req: AIKillSwitchRequest):
    """Toggle global AI kill switch to instantly halt or resume all AI generation."""
    svc = get_ai_gateway_service()
    svc.policy_engine.global_kill_switch = req.enabled
    return ApiResponse(
        ok=True,
        data={
            "global_kill_switch_active": req.enabled,
            "reason": req.reason,
        },
    )


@router.post("/route", response_model=ApiResponse[AIRoutePreviewResponse])
async def preview_routing(req: AIRoutePreviewRequest):
    """Preview which provider and model the router will select for a workload."""
    svc = get_ai_gateway_service()
    try:
        task_type_enum = TaskType(req.task_type) if req.task_type in TaskType._value2member_map_ else TaskType.GENERAL
    except Exception:
        task_type_enum = TaskType.GENERAL

    decision = svc.router.route(
        task_type=task_type_enum,
        preferred_provider=req.preferred_provider,
        preferred_model=req.preferred_model,
    )

    return ApiResponse(
        ok=True,
        data=AIRoutePreviewResponse(
            task_type=decision.task_type.value,
            target_provider=decision.target_provider,
            target_model=decision.target_model,
            target_tier=decision.target_tier.value,
            fallback_chain=decision.fallback_chain,
            rationale=decision.rationale,
        ),
    )


# ── Phase 18: AI Governance & Observability Endpoints ────────────────────

def get_governance_service():
    from central_platform.ai.governance import AIGovernanceService
    gw = get_ai_gateway_service()
    return AIGovernanceService(gateway=gw, db=gw.db)


@router.get("/observability/metrics", response_model=ApiResponse[dict])
async def get_observability_metrics():
    """Retrieve system-wide aggregated telemetry and performance metrics."""
    gov = get_governance_service()
    metrics = gov.get_observability_metrics()
    return ApiResponse(ok=True, data=metrics)


@router.get("/observability/logs", response_model=ApiResponse[List[AIExecutionLogResponse]])
async def get_observability_logs(
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    student_id: Optional[str] = Query(None),
    course_id: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Retrieve privacy-preserving telemetry logs (prompt hash only)."""
    gov = get_governance_service()
    logs = gov.get_execution_logs(
        provider=provider,
        model=model,
        student_id=student_id,
        course_id=course_id,
        task_type=task_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        ok=True,
        data=[
            AIExecutionLogResponse(
                id=l["id"],
                request_id=l.get("request_id", ""),
                provider=l.get("provider", ""),
                model=l.get("model", ""),
                student_id=l.get("student_id"),
                session_id=l.get("session_id"),
                course_id=l.get("course_id"),
                task_type=l.get("task_type", "general"),
                prompt_tokens=l.get("prompt_tokens", 0),
                completion_tokens=l.get("completion_tokens", 0),
                latency_ms=l.get("latency_ms", 0.0),
                status=l.get("status", "SUCCESS"),
                error_class=l.get("error_class"),
                estimated_cost_usd=l.get("estimated_cost_usd", 0.0),
                fallback_used=l.get("fallback_used", False),
                prompt_hash=l.get("prompt_hash", ""),
                created_at=l.get("created_at", ""),
            )
            for l in logs
        ],
    )


@router.get("/governance/budgets", response_model=ApiResponse[AIBudgetStatusResponse])
async def get_budget_status():
    """Retrieve daily budget usage, remaining spend, and alert status."""
    gov = get_governance_service()
    status_data = gov.get_budget_status()
    return ApiResponse(
        ok=True,
        data=AIBudgetStatusResponse(
            daily_budget_usd=status_data["daily_budget_usd"],
            daily_spend_usd=status_data["daily_spend_usd"],
            remaining_budget_usd=status_data["remaining_budget_usd"],
            percentage_used=status_data["percentage_used"],
            budget_alert=status_data["budget_alert"],
            budget_exceeded=status_data["budget_exceeded"],
        ),
    )


@router.put("/governance/budgets", response_model=ApiResponse[AIBudgetStatusResponse])
async def update_budget_limit(req: AIBudgetUpdateRequest):
    """Update daily AI budget threshold in USD."""
    gov = get_governance_service()
    try:
        updated = gov.set_budget(req.daily_budget_usd)
        return ApiResponse(
            ok=True,
            data=AIBudgetStatusResponse(
                daily_budget_usd=updated["daily_budget_usd"],
                daily_spend_usd=updated["daily_spend_usd"],
                remaining_budget_usd=updated["remaining_budget_usd"],
                percentage_used=updated["percentage_used"],
                budget_alert=updated["budget_alert"],
                budget_exceeded=updated["budget_exceeded"],
            ),
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/governance/circuit-breakers", response_model=ApiResponse[dict])
async def get_circuit_breakers():
    """Retrieve real-time circuit breaker states across all providers."""
    gov = get_governance_service()
    return ApiResponse(ok=True, data=gov.get_circuit_breaker_statuses())


@router.post("/governance/circuit-breakers/{provider_name}/reset", response_model=ApiResponse[dict])
async def reset_circuit_breaker(provider_name: str):
    """Manually reset a tripped circuit breaker to CLOSED state."""
    gov = get_governance_service()
    reset = gov.reset_circuit_breaker(provider_name)
    if not reset:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' has no active circuit breaker.")
    return ApiResponse(ok=True, data={"provider_name": provider_name, "reset": True})


@router.get("/governance/allowlist", response_model=ApiResponse[List[str]])
async def get_allowlist():
    """Retrieve active model allowlist."""
    gov = get_governance_service()
    return ApiResponse(ok=True, data=gov.get_model_allowlist())


@router.post("/governance/allowlist", response_model=ApiResponse[List[str]])
async def update_allowlist(req: AIAllowlistUpdateRequest):
    """Set or replace model allowlist."""
    gov = get_governance_service()
    updated = gov.set_model_allowlist(req.models)
    return ApiResponse(ok=True, data=updated)


@router.delete("/governance/allowlist/{model_name}", response_model=ApiResponse[List[str]])
async def remove_from_allowlist(model_name: str):
    """Remove a model from the active allowlist."""
    gov = get_governance_service()
    updated = gov.remove_model_from_allowlist(model_name)
    return ApiResponse(ok=True, data=updated)


@router.get("/governance/cost-breakdown", response_model=ApiResponse[dict])
async def get_cost_breakdown():
    """Retrieve authoritative cost allocation across providers and tasks."""
    gov = get_governance_service()
    return ApiResponse(ok=True, data=gov.get_cost_breakdown())

