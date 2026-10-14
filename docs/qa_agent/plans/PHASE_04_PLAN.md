# Phase 04 Implementation Plan: Gateway Observability, Metrics & Degraded-State Visibility

**Document:** `docs/qa_agent/plans/PHASE_04_PLAN.md`  
**Phase:** 04  
**Maps to:** GQA-004 (P1), GQA-015 (P2)  
**Status:** IN_PROGRESS  

---

## 1. Architectural Scope & Problem Statement

### 1.1 Root Cause & GQA Findings
- **GQA-004 (P1):** In `central_platform/ai/gateway.py:get_status()`, provider status is determined purely by configuration order (`enabled_providers[0]`) rather than runtime verification. Providers are claimed as active/healthy even if they have never executed inference, have failed connectivity, or are experiencing repeated crashes.
- **GQA-015 (P2):** In `central_platform/ai/gateway.py:get_status()`, the daily token count is computed via a synthetic multiplier:
  ```python
  "token_usage_today": int(self.policy_engine.daily_spend_usd * 10000)  # Representative count
  ```
  This synthetic approximation fabricates usage metrics and distorts observability, billing auditing, and capacity planning.
- **Degraded-State Visibility & Privacy Invariants:**
  - When primary providers fail, fallback failover must be explicitly visible in gateway telemetry without exposing raw API keys, bearer tokens, or internal tracebacks to users or logs.
  - Correlation IDs (`request_id`) and structured `error_class` must survive failover.

---

## 2. Technical Design & Architecture

### 2.1 Provider Runtime State Lifecycle (`ProviderRuntimeStatus`)
We define a canonical runtime lifecycle:
- `CONFIGURED`: Provider declared in system configuration, not yet probed or active.
- `ENABLED`: Provider enabled in router, awaiting incoming requests or health probe.
- `HEALTHY`: Provider successfully completed runtime inference recently.
- `DEGRADED`: Provider experiencing intermittent errors or operating as secondary fallback.
- `UNAVAILABLE`: Provider failing consecutively or circuit breaker is tripped `OPEN`.

### 2.2 Provider Runtime Telemetry
Each registered provider adapter is tracked by `ProviderRuntimeTelemetry`:
```python
@dataclass
class ProviderRuntimeTelemetry:
    provider_name: str
    status: ProviderRuntimeStatus = ProviderRuntimeStatus.CONFIGURED
    last_successful_inference_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    last_error: Optional[str] = None
    last_error_class: Optional[str] = None
    consecutive_failures: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
```

### 2.3 Genuine Token & Spend Tracking (`PolicyEngine`)
Replace synthetic multiplier `daily_spend_usd * 10000` with real usage tracking:
- `daily_tokens_total: int = 0`
- `daily_tokens_measured: int = 0` (from provider API usage payloads)
- `daily_tokens_estimated: int = 0` (from local SLM tokenizer / character heuristics)
- `record_usage(prompt_tokens, completion_tokens, cost_usd, provenance="measured")`
- Explicit provenance: `TokenMeasurementProvenance` (`MEASURED`, `ESTIMATED`, `UNKNOWN`, `MIXED`).
- Calendar UTC day-boundary reset: reset daily spend and token tallies on UTC midnight boundary or >= 86400s.

### 2.4 Error & Log Redaction
- Implement `sanitize_error_message(msg: str) -> str` to strip:
  - Bearer tokens (`Bearer eyJ...`, `Bearer <token>`).
  - API keys (`sk-[a-zA-Z0-9]{20,}`, `AIzaSy...`, `key=...`).
  - Sensitive authorization headers.
- Ensure `_log_execution` preserves `request_id`, prompt hash, and sanitized error class.

---

## 3. Implementation Steps

1. **Update `central_platform/ai/schema.py`:**
   - Define `ProviderRuntimeStatus` enum (`CONFIGURED`, `ENABLED`, `HEALTHY`, `DEGRADED`, `UNAVAILABLE`).
   - Define `TokenMeasurementProvenance` enum (`MEASURED`, `ESTIMATED`, `UNKNOWN`, `MIXED`).
   - Add `token_provenance` to `AIExecutionResult`.
2. **Update `central_platform/ai/policy_engine.py`:**
   - Add real token metrics (`daily_tokens_total`, `daily_tokens_measured`, `daily_tokens_estimated`).
   - Add `record_usage(prompt_tokens, completion_tokens, cost_usd, provenance)`.
   - Update `_check_budget_reset()` to reset both spend and token tallies on UTC calendar day boundary.
3. **Update `central_platform/ai/gateway.py`:**
   - Add `sanitize_error_message()` helper.
   - Track `provider_telemetry` per provider in `AIGatewayService`.
   - Update `execute()` to update provider telemetry and policy engine usage on success and failure.
   - Refactor `get_status()` to return evidence-based `active_provider`, `providers_status`, real `token_usage_today`, `token_breakdown`, and `gateway_status`.
4. **Author Comprehensive Test Suite `tests/test_qa_phase04_gateway_observability.py`:**
   - Test 1: Configured provider without runtime proof is not marked HEALTHY.
   - Test 2: Successful runtime inference marks provider HEALTHY with `last_successful_inference_at`.
   - Test 3: Provider failure updates status to DEGRADED and UNAVAILABLE when circuit trips.
   - Test 4: Real token aggregation without synthetic multipliers (GQA-015).
   - Test 5: UTC day boundary resets daily tokens and spend.
   - Test 6: Multi-provider failover maintains correlation ID and updates telemetry without double-counting spend.
   - Test 7: Secret redaction in error messages and execution logs.
5. **Run Verification & Full Repository Regression (1,461+ tests).**
6. **Documentation & Progression:**
   - Author `docs/qa_agent/reports/PHASE_04_REPORT.md`.
   - Append `DEC-016` to `docs/qa_agent/decisions/DECISION_LOG.md`.
   - Update `docs/qa_agent/MASTER_PROGRESS.md` marking Phase 04 PASSED and GQA-004/GQA-015 RESOLVED.
