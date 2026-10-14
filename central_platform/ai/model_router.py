"""Gayatri AI Platform — AI Model Router (Phase 17 & Phase 21).

Intelligently routes requests to optimal providers and models based on task type,
routing strategy (LOCAL_ONLY, LOCAL_FIRST, CLOUD_PREFERRED), capability matching,
performance tier, cost constraints, and available fallback chains.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Set


from central_platform.ai.adapters import is_production_mode
from central_platform.ai.schema import (
    AIModelDescriptor,
    ModelTier,
    ProviderConfig,
    ProviderType,
    RoutingDecision,
    RoutingStrategy,
    TaskType,
)


class ModelRouter:
    """Selects the best provider and model for a given AI workload."""

    TASK_TIER_MAPPING: Dict[TaskType, ModelTier] = {
        TaskType.TUTORING: ModelTier.TIER_2_STANDARD,
        TaskType.ASSESSMENT_GRADING: ModelTier.TIER_1_HEAVY,
        TaskType.COPILOT_SUMMARY: ModelTier.TIER_2_STANDARD,
        TaskType.INTERVENTION_RECOMMENDATION: ModelTier.TIER_2_STANDARD,
        TaskType.INTENT_CLASSIFICATION: ModelTier.TIER_3_FAST,
        TaskType.GENERAL: ModelTier.TIER_2_STANDARD,
    }

    def __init__(self, providers: Optional[Dict[str, ProviderConfig]] = None):
        self.providers: Dict[str, ProviderConfig] = providers or {}

    def register_provider(self, config: ProviderConfig) -> None:
        self.providers[config.provider_name] = config

    @staticmethod
    def _matches_capabilities(model: AIModelDescriptor, required_capabilities: Optional[List[str]]) -> bool:
        if not required_capabilities:
            return True
        model_caps = set(model.capabilities)
        return all(cap.lower() in {c.lower() for c in model_caps} for cap in required_capabilities)

    def route(
        self,
        task_type: TaskType,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
        strategy: RoutingStrategy = RoutingStrategy.LOCAL_FIRST,
        required_capabilities: Optional[List[str]] = None,
    ) -> RoutingDecision:
        """Determine target provider, model, and fallback chain with strategy and capability matching."""
        # 0. If explicit preferred_model requested, search across enabled providers
        if preferred_model:
            for p in self.providers.values():
                if p.enabled:
                    for m in p.models:
                        if (m.model_name.lower() == preferred_model.lower() or m.model_id.lower() == preferred_model.lower()) and self._matches_capabilities(m, required_capabilities):
                            fallback = [p.fallback_provider] if p.fallback_provider else []
                            return RoutingDecision(
                                task_type=task_type,
                                target_provider=p.provider_name,
                                target_model=m.model_name,
                                target_tier=m.tier,
                                fallback_chain=[f for f in fallback if f and f in self.providers],
                                rationale=f"Explicitly requested model '{preferred_model}'.",
                            )

        # 1. If explicit provider requested and available
        if preferred_provider and preferred_provider in self.providers:
            provider = self.providers[preferred_provider]
            if provider.enabled:
                target_m = None
                if provider.models:
                    for m in provider.models:
                        if self._matches_capabilities(m, required_capabilities):
                            target_m = m
                            break
                    if not target_m:
                        target_m = provider.models[0]

                target_model = preferred_model or (target_m.model_name if target_m else "default-model")
                fallback = [provider.fallback_provider] if provider.fallback_provider else []
                return RoutingDecision(
                    task_type=task_type,
                    target_provider=provider.provider_name,
                    target_model=target_model,
                    target_tier=target_m.tier if target_m else ModelTier.TIER_2_STANDARD,
                    fallback_chain=[f for f in fallback if f and f in self.providers],
                    rationale=f"Explicitly requested provider '{preferred_provider}'.",
                )

        # 2. Determine target tier based on task
        target_tier = self.TASK_TIER_MAPPING.get(task_type, ModelTier.TIER_2_STANDARD)

        # 3. Apply Routing Strategy Filter
        enabled_providers = [p for p in self.providers.values() if p.enabled]

        if strategy == RoutingStrategy.LOCAL_ONLY:
            # Strictly filter to local GGUF / Mock local providers
            eligible_providers = [
                p for p in enabled_providers
                if p.provider_type in (ProviderType.LOCAL_GGUF, ProviderType.MOCK) or "local" in p.provider_name.lower()
            ]
            fallback_chain = []
        elif strategy == RoutingStrategy.LOCAL_FIRST:
            # Sort local providers first, then cloud providers
            local_p = [p for p in enabled_providers if p.provider_type in (ProviderType.LOCAL_GGUF, ProviderType.MOCK) or "local" in p.provider_name.lower()]
            cloud_p = [p for p in enabled_providers if p not in local_p]
            eligible_providers = sorted(local_p, key=lambda x: x.priority) + sorted(cloud_p, key=lambda x: x.priority)
        else:  # CLOUD_PREFERRED
            cloud_p = [p for p in enabled_providers if p.provider_type not in (ProviderType.LOCAL_GGUF, ProviderType.MOCK) and "local" not in p.provider_name.lower()]
            local_p = [p for p in enabled_providers if p not in cloud_p]
            eligible_providers = sorted(cloud_p, key=lambda x: x.priority) + sorted(local_p, key=lambda x: x.priority)

        # 4. Capability & Tier Matching Selection
        target_p: Optional[ProviderConfig] = None
        target_m: Optional[AIModelDescriptor] = None

        # Pass A: Match target tier AND required capabilities
        for p in eligible_providers:
            for m in p.models:
                if m.tier == target_tier and self._matches_capabilities(m, required_capabilities):
                    target_p = p
                    target_m = m
                    break
            if target_p:
                break

        # Pass B: Match required capabilities in any tier
        if not target_p:
            for p in eligible_providers:
                for m in p.models:
                    if self._matches_capabilities(m, required_capabilities):
                        target_p = p
                        target_m = m
                        break
                if target_p:
                    break

        # Pass C: Fallback to any eligible provider if capability requirement permits
        if not target_p and eligible_providers:
            target_p = eligible_providers[0]
            target_m = target_p.models[0] if target_p.models else AIModelDescriptor(
                model_id="default",
                model_name="default",
                tier=ModelTier.TIER_2_STANDARD,
            )

        if not target_p:
            if is_production_mode():
                return RoutingDecision(
                    task_type=task_type,
                    target_provider="",
                    target_model="",
                    target_tier=target_tier,
                    fallback_chain=[],
                    rationale=f"No provider found matching strategy '{strategy.value}' in production mode (F-011, F-012). Mock engine prohibited.",
                )
            return RoutingDecision(
                task_type=task_type,
                target_provider="mock_engine",
                target_model="mock-default-model",
                target_tier=target_tier,
                fallback_chain=[],
                rationale=f"No provider found matching strategy '{strategy.value}' and capabilities '{required_capabilities}'; defaulting to mock engine.",
            )


        # Build fallback chain
        fallback_chain = [
            p.provider_name for p in eligible_providers
            if p.provider_name != target_p.provider_name
        ]

        return RoutingDecision(
            task_type=task_type,
            target_provider=target_p.provider_name,
            target_model=target_m.model_name if target_m else "default",
            target_tier=target_tier,
            fallback_chain=fallback_chain,
            rationale=f"Routed via strategy '{strategy.value}' to '{target_p.provider_name}' ({target_m.model_name if target_m else 'default'}) for tier {target_tier.value}.",
        )
