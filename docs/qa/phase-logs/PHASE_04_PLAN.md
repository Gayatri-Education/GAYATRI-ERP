# Phase 04 Plan: AI Execution, Provider Configuration, Kill Switch, and Error Contracts

**Phase:** PHASE-04  
**Status:** IN_PROGRESS  
**Date:** 2026-10-15  
**Target Findings:** ERP-012, ERP-013, ERP-014  

---

## 1. Problem Analysis & Objectives

### 1.1 ERP-013: AI Failures Encoded as HTTP 200
- **Findings & Root Causes:**
  - In `central_platform/api/routes/ai.py`, `execute_ai_prompt` handles `not result.success` by returning `ApiResponse(ok=False, error=..., data=...)`.
  - Because no custom status code is set, FastAPI renders this response with the default route status **HTTP 200 OK**.
  - Calling clients and upstream services cannot distinguish failure, policy blocks, or service outages via standard HTTP status codes.
- **Invariants & Requirements:**
  - Execution failures and policy blocks must NEVER return HTTP 200.
  - Failures must return semantically truthful and machine-detectable HTTP status codes:
    - `HTTP 503 Service Unavailable`: Global kill switch active, provider unavailable, or all providers failed.
    - `HTTP 429 Too Many Requests`: Rate limit exceeded or budget depleted.
    - `HTTP 504 Gateway Timeout`: Provider timeout.
    - `HTTP 422 Unprocessable Entity`: Model configuration error or mock engine requested in production mode.
    - `HTTP 403 Forbidden`: Policy violation or unauthorized target model.
    - `HTTP 502 Bad Gateway`: Upstream provider execution error.
  - The structured body payload must continue returning `{"ok": false, "error": {...}, "data": {...}}` for client compatibility.

### 1.2 ERP-012: Authorization, Tenant & Student Isolation on AI Routes
- **Findings & Root Causes:**
  - In production mode, unauthenticated callers could attempt to invoke `/api/v1/ai/execute`.
  - Students could supply another student's `student_id` in `AIExecutionApiRequest` without server-side verification.
  - Observability and governance endpoints should enforce role checks in production mode.
- **Invariants & Requirements:**
  - In production mode, `/api/v1/ai/execute` requires authentication (HTTP 401).
  - Student self-access isolation: when an authenticated student calls `/ai/execute`, they can only execute AI generation for their own user ID; targeting another student returns HTTP 403 Forbidden.
  - Teachers, org admins, and super admins can execute AI prompts for students within their organization.

### 1.3 ERP-014: Unknown Provider Type Rejection & Model Safety
- **Findings & Root Causes:**
  - Registering a provider with an unknown `provider_type` string must be rejected strictly (HTTP 422 Unprocessable Entity) without falling back to a mock provider.
- **Invariants & Requirements:**
  - Enforce enum validation against `ProviderType`. Reject invalid provider types with HTTP 422.

### 1.4 Stale DB & Dependency Injection Lifecycle in AI Gateway
- **Findings & Root Causes:**
  - `_ai_gateway_service` was stored as a static module-global singleton in `central_platform/api/routes/ai.py`, capturing whatever `PlatformDatabase` was initialized first and ignoring subsequent `app.dependency_overrides[get_db]`.
- **Invariants & Requirements:**
  - Update `get_ai_gateway_service` and `get_governance_service` to accept `db: PlatformDatabase = Depends(get_db)` and automatically invalidate/reinitialize the gateway service if the database reference changes.

---

## 2. Implementation Steps
1. **Targeted Reproduction Suite:**
   - Create `tests/test_qa_phase04_ai_contracts.py` asserting:
     - AI execution failure under kill switch returns HTTP 503, never HTTP 200.
     - AI execution failure under all-providers-failed returns HTTP 503/502, never HTTP 200.
     - Production mode requires authentication on `/api/v1/ai/execute` (HTTP 401).
     - Student isolation on `/api/v1/ai/execute`: Student A cannot execute generation for Student B (HTTP 403).
     - Invalid provider type in `POST /api/v1/ai/providers` returns HTTP 422.
     - Dynamic database injection: `app.dependency_overrides[get_db]` propagates to `AIGatewayService` without capturing a stale database singleton.
2. **Harden `central_platform/api/routes/ai.py`:**
   - Use `JSONResponse` with appropriate HTTP status codes (503, 502, 504, 429, 422, 403) when `not result.success`.
   - Update `get_ai_gateway_service(db = Depends(get_db))` and `get_governance_service(svc = Depends(get_ai_gateway_service))` to dynamic dependency injection.
   - Add student self-access isolation and production auth check to `execute_ai_prompt`.
3. **Run Tests & Verify:**
   - Run `tests/test_qa_phase04_ai_contracts.py`.
   - Run existing AI suites: `test_phase17_ai_gateway_model_router_platform.py`, `test_phase18_ai_governance_observability_platform.py`.
   - Run full regression suite (`pytest -q -m "not gui"`).
4. **Update Records:**
   - Create `docs/qa/phase-logs/PHASE_04_LOG.md`.
   - Update `docs/qa/PROGRESS_TRACKER.yaml` and `GAYATRI_ERP_PROGRESS_TRACKER.yaml`.
   - Update `docs/qa/ISSUE_REGISTER.md`.
