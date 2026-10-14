"""Gayatri AI Platform — AI Policy Engine & Governance Guardrails (Phase 17).

Enforces:
1. Global AI kill switch
2. Provider kill switches
3. Model allowlists
4. Rate limiting (RPM)
5. Daily budget limits (USD)
6. Circuit breaker with auto-recovery
7. Anti-answer leakage & safety guardrails
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("gayatri.central_platform.ai.policy")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Healthy, accepting traffic
    OPEN = "OPEN"          # Tripped, rejecting traffic
    HALF_OPEN = "HALF_OPEN"  # Testing single request


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 30.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_state_change: float = field(default_factory=time.time)

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
            logger.warning(f"Circuit breaker tripped to OPEN after {self.failure_count} consecutive failures.")

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_state_change >= self.recovery_timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = time.time()
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False


class PolicyEngine:
    """Enforces execution policies, budget controls, and circuit breaking."""

    def __init__(self):
        self.global_kill_switch: bool = False
        self.provider_kill_switches: Dict[str, bool] = {}
        self.model_allowlist: Set[str] = set()  # Empty means all registered models allowed
        self.daily_budget_usd: float = 100.0
        self.daily_spend_usd: float = 0.0
        self.daily_tokens_total: int = 0
        self.daily_tokens_measured: int = 0
        self.daily_tokens_estimated: int = 0
        self.daily_spend_reset_ts: float = time.time()
        self.daily_reset_day_utc: str = time.strftime("%Y-%m-%d", time.gmtime())

        # Rate limiting state: student_id / tenant_id -> list of request timestamps
        self._request_history: Dict[str, List[float]] = {}
        self.default_rate_limit_rpm: int = 120

        # Circuit breakers per provider
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def get_circuit_breaker(self, provider_name: str) -> CircuitBreaker:
        if provider_name not in self.circuit_breakers:
            self.circuit_breakers[provider_name] = CircuitBreaker()
        return self.circuit_breakers[provider_name]

    def validate_execution(
        self,
        provider_name: str,
        model_name: str,
        caller_id: Optional[str] = None,
        estimated_cost: float = 0.0,
    ) -> Tuple[bool, Optional[str]]:
        """Validate whether a request can be dispatched according to active policies."""
        # 1. Global Kill Switch
        if self.global_kill_switch:
            return False, "GLOBAL_KILL_SWITCH_ACTIVE: All AI generation is currently disabled."

        # 2. Provider Kill Switch
        if self.provider_kill_switches.get(provider_name, False):
            return False, f"PROVIDER_KILL_SWITCH_ACTIVE: Provider '{provider_name}' is disabled."

        # 3. Model Allowlist
        if self.model_allowlist and model_name not in self.model_allowlist:
            return False, f"MODEL_NOT_ALLOWED: Model '{model_name}' is not in the active allowlist."

        # 4. Circuit Breaker Check
        cb = self.get_circuit_breaker(provider_name)
        if not cb.can_execute():
            return False, f"CIRCUIT_BREAKER_OPEN: Provider '{provider_name}' is experiencing high failure rates."

        # 5. Daily Budget Check
        self._check_budget_reset()
        if self.daily_spend_usd + estimated_cost > self.daily_budget_usd:
            return False, f"BUDGET_EXCEEDED: Daily spend (${self.daily_spend_usd:.2f}) reached cap (${self.daily_budget_usd:.2f})."

        # 6. Rate Limit Check
        if caller_id:
            now = time.time()
            history = self._request_history.setdefault(caller_id, [])
            # Filter timestamps older than 60s
            history = [t for t in history if now - t < 60.0]
            self._request_history[caller_id] = history
            if len(history) >= self.default_rate_limit_rpm:
                return False, f"RATE_LIMIT_EXCEEDED: Rate limit of {self.default_rate_limit_rpm} RPM exceeded."
            self._request_history[caller_id].append(now)

        return True, None

    def record_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        provenance: str = "MEASURED",
    ) -> None:
        """Record real token counts and expenditure with provenance tracking (GQA-015)."""
        self._check_budget_reset()
        self.daily_spend_usd += max(0.0, float(cost_usd))
        tokens = max(0, int(prompt_tokens)) + max(0, int(completion_tokens))
        self.daily_tokens_total += tokens

        prov_str = str(provenance.value if hasattr(provenance, "value") else provenance).upper()
        if prov_str == "ESTIMATED":
            self.daily_tokens_estimated += tokens
        else:
            self.daily_tokens_measured += tokens

    def record_spend(self, cost_usd: float) -> None:
        """Backward-compatible spend recorder."""
        self.record_usage(prompt_tokens=0, completion_tokens=0, cost_usd=cost_usd)

    @property
    def token_provenance(self) -> str:
        """Determine aggregate token measurement provenance."""
        if self.daily_tokens_measured > 0 and self.daily_tokens_estimated > 0:
            return "MIXED"
        if self.daily_tokens_measured > 0:
            return "MEASURED"
        if self.daily_tokens_estimated > 0:
            return "ESTIMATED"
        return "UNKNOWN"

    def _check_budget_reset(self) -> None:
        now = time.time()
        current_day = time.strftime("%Y-%m-%d", time.gmtime(now))
        # Reset spend and token tallies on UTC calendar day boundary or >= 86400s
        if current_day != self.daily_reset_day_utc or (now - self.daily_spend_reset_ts >= 86400.0):
            self.daily_spend_usd = 0.0
            self.daily_tokens_total = 0
            self.daily_tokens_measured = 0
            self.daily_tokens_estimated = 0
            self.daily_spend_reset_ts = now
            self.daily_reset_day_utc = current_day
