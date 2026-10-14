# Phase 02 Implementation Plan — AI Execution Integrity & Provider Routing

## 1. Context and Objective
Resolve QA-001, QA-002, QA-003, and QA-015:
Guarantee that Gayatri explicitly exposes AI execution provenance (`REAL_MODEL`, `MOCK`, `DEGRADED_FALLBACK`, `FAILED`) across all provider adapters and gateway routing. Ensure that missing models, mock modes, or degraded fallbacks can never masquerade as genuine real-model execution. Ensure production validators distinguish model readiness states (`CONFIGURED`, `LOADABLE`, `EXECUTABLE`, `HEALTHY`).

## 2. Dependencies and Affected Modules
- Schemas: `central_platform/ai/schema.py`
- Adapters: `central_platform/ai/adapters.py`
- Gateway: `central_platform/ai/gateway.py`
- Deployment Validator: `central_platform/deployment/validator.py`
- Audit Suite: `tests/test_phase29_final_platform_audit_master.py`
- New Regression Suite: `tests/test_qa_phase02_ai_execution_integrity.py`

## 3. Scope of Tasks
1. **02.1 Map AI Execution Path:** Document complete pipeline from UI/bridge to adapters and response normalization.
2. **02.2 Define Execution Provenance Model:**
   - Implement `ExecutionProvenance` enum (`REAL_MODEL`, `MOCK`, `DEGRADED_FALLBACK`, `FAILED`).
   - Add `execution_provenance` field to `AIExecutionResult` with automated provenance payload (`real_model: bool`, `execution_provenance: str`).
3. **02.3 Fix Local and Mock Fallback Semantics:**
   - In `LocalGGUFAdapter`:
     - When `LocalProvider.is_available()` succeeds with genuine token generation: mark `execution_provenance = ExecutionProvenance.REAL_MODEL`, `mock = False`.
     - When `LocalProvider` fails in production: fail closed with `execution_provenance = ExecutionProvenance.FAILED`, `status = MODEL_UNAVAILABLE`.
     - When `LocalProvider` falls back in non-production mode: mark `execution_provenance = ExecutionProvenance.DEGRADED_FALLBACK`, `mock = True`, `fallback_used = True`.
   - In `MockAIAdapter`: mark `execution_provenance = ExecutionProvenance.MOCK`, `mock = True`.
   - In cloud adapters (`OpenAIAdapter`, `AnthropicAdapter`, `GeminiAdapter`, `OpenRouterAdapter`): mark `execution_provenance = ExecutionProvenance.REAL_MODEL` on success, `ExecutionProvenance.FAILED` on failure.
   - In `AIGatewayService`: preserve and propagate provenance through multi-provider fallback chains.
4. **02.4 Validate Model Manifest & Deployment Validator Health Check (QA-003):**
   - Enhance `DeploymentValidator.validate_model_providers()` and `validate_health_checks()`:
     - Check manifest configuration.
     - Check file presence on disk (`models/...`).
     - Check model checksum and loadability.
     - Differentiate `CONFIGURED`, `LOADABLE`, `EXECUTABLE`, `HEALTHY`.
     - Fail production check if only mock is available or model artifact is missing.
5. **02.5 Comprehensive Test Verification (QA-002):**
   - Create `tests/test_qa_phase02_ai_execution_integrity.py` covering:
     - Model discovery and manifest integrity
     - Distinction between real model vs mock vs degraded fallback
     - Provider error classifications (401, 403, 429, 500, timeout, malformed)
     - Streaming, cancellation, and session safety
     - Multi-turn provenance preservation
   - Update `tests/test_phase29_final_platform_audit_master.py` so intelligence audit tests explicit provenance instead of mere string non-emptiness.
6. **02.6 Regression Verification:** Run focused tests, then full repository test suite (1346+ tests), compilation check, and write Phase 02 completion report.

## 4. Regression Risks & Mitigations
- *Risk:* Existing tests expecting `mock=False` on fallback LocalGGUF adapter outside production mode.
  - *Mitigation:* Review all existing tests; existing tests in `test_phase04_ai_gateway_remediation.py` verify that `LocalGGUFAdapter` fails with `MODEL_UNAVAILABLE` when `LocalProvider.is_available() == False` in production mode. Non-production tests will see `execution_provenance == DEGRADED_FALLBACK`.
