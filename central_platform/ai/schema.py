"""Gayatri AI Platform — AI Gateway & Model Router Data Models (Phase 17).

Defines provider-neutral descriptors, execution requests, routing decisions,
cost structures, and policy telemetry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskType(str, Enum):
    """Categorization of AI workloads for intelligent routing."""
    TUTORING = "tutoring"
    ASSESSMENT_GRADING = "assessment_grading"
    COPILOT_SUMMARY = "copilot_summary"
    INTERVENTION_RECOMMENDATION = "intervention_recommendation"
    INTENT_CLASSIFICATION = "intent_classification"
    EMBEDDING = "embedding"
    GENERAL = "general"


class ModelTier(str, Enum):
    """Model performance/cost tier."""
    TIER_1_HEAVY = "tier_1_heavy"        # GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro
    TIER_2_STANDARD = "tier_2_standard"  # GPT-4o-mini, Claude 3.5 Haiku, Gemini 2.0 Flash
    TIER_3_FAST = "tier_3_fast"          # Local SLM, Qwen2.5-3B, Llama-3.2-3B


class ProviderType(str, Enum):
    """Supported provider adapters."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    LOCAL_GGUF = "local_gguf"
    MOCK = "mock"


class RoutingStrategy(str, Enum):
    """Routing strategies for local vs cloud execution (Phase 21)."""
    LOCAL_ONLY = "local_only"
    LOCAL_FIRST = "local_first"
    CLOUD_PREFERRED = "cloud_preferred"


class ModelExecutionStatus(str, Enum):
    """Normalized provider execution states (Phase 4 / F-011, F-012)."""
    MODEL_SUCCESS = "MODEL_SUCCESS"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MODEL_RATE_LIMITED = "MODEL_RATE_LIMITED"
    MODEL_CONFIGURATION_ERROR = "MODEL_CONFIGURATION_ERROR"
    MODEL_INVALID_RESPONSE = "MODEL_INVALID_RESPONSE"


class ExecutionProvenance(str, Enum):
    """Explicit AI execution provenance status (QA-001, QA-002)."""
    REAL_MODEL = "REAL_MODEL"
    MOCK = "MOCK"
    DEGRADED_FALLBACK = "DEGRADED_FALLBACK"
    FAILED = "FAILED"




@dataclass
class AIModelDescriptor:
    """Descriptor for an AI model supported by a provider."""
    model_id: str
    model_name: str
    tier: ModelTier = ModelTier.TIER_2_STANDARD
    context_window: int = 8192
    max_output_tokens: int = 2048
    supports_system_prompt: bool = True
    supports_tools: bool = True
    supports_json: bool = True
    capabilities: List[str] = field(default_factory=list)
    cost_per_1k_input_usd: float = 0.00015
    cost_per_1k_output_usd: float = 0.0006
    latency_p50_ms: float = 350.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "tier": self.tier.value if isinstance(self.tier, ModelTier) else str(self.tier),
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_system_prompt": self.supports_system_prompt,
            "supports_tools": self.supports_tools,
            "supports_json": self.supports_json,
            "capabilities": self.capabilities,
            "cost_per_1k_input_usd": self.cost_per_1k_input_usd,
            "cost_per_1k_output_usd": self.cost_per_1k_output_usd,
            "latency_p50_ms": self.latency_p50_ms,
        }


@dataclass
class ProviderConfig:
    """Configuration for an AI model provider."""
    provider_name: str
    provider_type: ProviderType = ProviderType.MOCK
    api_key_ref: str = ""  # Name of environment variable holding API key (e.g. "OPENAI_API_KEY")
    base_url: Optional[str] = None
    enabled: bool = True
    priority: int = 1  # Lower integer = higher priority
    fallback_provider: Optional[str] = None
    rate_limit_rpm: int = 600
    daily_budget_usd: float = 50.0
    timeout_seconds: float = 15.0
    models: List[AIModelDescriptor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "provider_type": self.provider_type.value if isinstance(self.provider_type, ProviderType) else str(self.provider_type),
            "api_key_ref": self.api_key_ref,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "priority": self.priority,
            "fallback_provider": self.fallback_provider,
            "rate_limit_rpm": self.rate_limit_rpm,
            "daily_budget_usd": self.daily_budget_usd,
            "timeout_seconds": self.timeout_seconds,
            "models": [m.to_dict() for m in self.models],
        }


@dataclass
class AIExecutionRequest:
    """Execution request passed to the AI Gateway."""
    prompt: str
    system_prompt: Optional[str] = None
    task_type: TaskType = TaskType.GENERAL
    student_id: Optional[str] = None
    session_id: Optional[str] = None
    course_id: Optional[str] = None
    preferred_model: Optional[str] = None
    preferred_provider: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    stop_sequences: List[str] = field(default_factory=list)
    rag_context: Optional[str] = None
    teacher_directives: List[str] = field(default_factory=list)
    timeout_seconds: Optional[float] = None
    request_id: Optional[str] = None


@dataclass
class AIExecutionResult:
    """Authoritative result returned by the AI Gateway."""
    request_id: str
    content: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    success: bool = True
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    fallback_used: bool = False
    original_provider: Optional[str] = None
    status: ModelExecutionStatus = ModelExecutionStatus.MODEL_SUCCESS
    mock: bool = False
    cached: bool = False
    execution_provenance: ExecutionProvenance = ExecutionProvenance.MOCK

    def to_dict(self) -> Dict[str, Any]:
        prov_val = (
            self.execution_provenance.value
            if isinstance(self.execution_provenance, ExecutionProvenance)
            else str(self.execution_provenance)
        )
        return {
            "request_id": self.request_id,
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "mock": self.mock,
            "execution_provenance": prov_val,
            "real_model": prov_val == ExecutionProvenance.REAL_MODEL.value,
            "status": self.status.value if isinstance(self.status, ModelExecutionStatus) else str(self.status),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "estimated_cost_usd": self.estimated_cost_usd,
            "success": self.success,
            "error_class": self.error_class,
            "error_message": self.error_message,
            "fallback_used": self.fallback_used,
            "original_provider": self.original_provider,
            "cached": self.cached,
        }

    @property
    def provenance(self) -> Dict[str, Any]:
        """Machine-readable provenance record (F-014 / QA-001)."""
        prov_val = (
            self.execution_provenance.value
            if isinstance(self.execution_provenance, ExecutionProvenance)
            else str(self.execution_provenance)
        )
        return {
            "provider": self.provider,
            "model": self.model,
            "mock": self.mock,
            "status": self.status.value if isinstance(self.status, ModelExecutionStatus) else str(self.status),
            "execution_provenance": prov_val,
            "real_model": prov_val == ExecutionProvenance.REAL_MODEL.value,
        }



@dataclass
class RoutingDecision:
    """Decision produced by the Model Router."""
    task_type: TaskType
    target_provider: str
    target_model: str
    target_tier: ModelTier
    fallback_chain: List[str] = field(default_factory=list)
    rationale: str = ""
