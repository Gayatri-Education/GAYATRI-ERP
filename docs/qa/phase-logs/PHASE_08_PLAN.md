# Phase 08 Plan: Tutor Orchestration, RAG Grounding, and Blocked-Turn Semantics

**Phase:** PHASE-08  
**Status:** IN_PLANNING  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer  

---

## 1. Goal & Scope
Implement and verify authoritative tutor orchestrator turn semantics, eliminating ambiguous blocked-turn representations (ERP-017), strictly preventing synthetic/hallucinated grounding claims, enforcing multi-tenant and course version boundaries, ensuring state rollback on validation failure, and certifying that blocked or failed turns cannot mutate student mastery.

---

## 2. Target Findings & Invariants
- **ERP-017**: `central_platform/api/routes/tutor.py` blocked tutoring path may return a `turn-blocked-*` ID and safe response that clients could mistake for a completed tutoring turn.
- **Blocked-Turn Semantics Invariant**:
  - A turn blocked by safety, prompt injection, or policy rules MUST clearly declare `is_blocked=True`, `is_completed=False`, `ok=False`, `turn_type="BLOCKED"`, and `status="BLOCKED_INJECTION"` (or `"BLOCKED_POLICY"`).
  - Blocked turns must NEVER mutate student mastery, SLR state, or session progress.
  - Blocked turns must record a `TUTOR_TURN_BLOCKED` event or audit log for observability without polluting conversational history.
  - Blocked turns must return safe redirect guidance without echoing prompt injection payload or disclosing system prompts.
- **RAG Grounding Invariant**:
  - A turn must only declare `is_grounded=True` if authoritative RAG retrieval yielded non-empty, validated source chunks for the current tenant and course.
  - When RAG index is empty or retrieval returns zero results, `rag_sources_used` must be `[]`, `is_grounded=False`, and the response must not fabricate source citations.
  - RAG retrieval must respect tenant, course, published status, and version boundaries.
- **Lifecycle & Deduplication Invariant**:
  - Exact duplicate turn requests within the same session must return idempotent replay without duplicating learning events or state mutations (`state_committed=False`).
  - Draft or archived course versions must be rejected fail-closed (HTTP 404).
  - Validation failures (e.g. anti-answer leakage trigger) must roll back state changes (`state_committed=False`, `validation_passed=False`, `is_completed=False`).

---

## 3. Implementation Plan
1. **Remediate `central_platform/tutor/orchestrator.py`**:
   - Update `TutorTurnResult` dataclass to include explicit contract indicators:
     - `is_blocked: bool = False`
     - `is_completed: bool = True`
     - `is_grounded: bool = False`
     - `turn_type: str = "COMPLETED"`
   - Integrate `SecurityAuditor.sanitize_prompt` inside `GenericTutorOrchestrator.execute_turn` as a first-class orchestrator guard (protecting non-HTTP callers).
   - On blocked prompt injection:
     - Return `TutorTurnResult` with `is_blocked=True`, `is_completed=False`, `is_grounded=False`, `turn_type="BLOCKED"`, `status="BLOCKED_INJECTION"`, `state_committed=False`.
     - Record a `TUTOR_TURN_BLOCKED` learning event in the database for auditability without mutating mastery.
   - For normal turns:
     - Set `is_grounded = bool(rag_sources_used) and val_result.is_valid`.
     - If validation fails, set `is_completed = False`, `turn_type = "VALIDATION_FAILED"`, `state_committed = False`.
2. **Remediate `central_platform/api/routes/tutor.py`**:
   - Update `TutorTurnApiResponse` schema with:
     - `is_blocked: bool = Field(False, description="True if turn was blocked by safety/security policies")`
     - `is_completed: bool = Field(True, description="True only if turn was successfully completed")`
     - `is_grounded: bool = Field(False, description="True only if response is grounded in authoritative sources")`
     - `turn_type: str = Field("COMPLETED", description="Turn category: COMPLETED, BLOCKED, VALIDATION_FAILED, ERROR")`
   - In `submit_tutor_turn`, when prompt injection is detected by the route guard:
     - Record `TUTOR_TURN_BLOCKED` learning event in DB.
     - Return `TutorTurnApiResponse` with `is_blocked=True`, `is_completed=False`, `is_grounded=False`, `turn_type="BLOCKED"`, `status="BLOCKED_INJECTION"`, `ok=False`, `state_committed=False`.
   - On successful orchestrator response, cleanly map `is_blocked`, `is_completed`, `is_grounded`, and `turn_type`.
3. **Author Reproduction Suite (`tests/test_qa_phase08_tutor_integrity.py`)**:
   - Test 1: Verify blocked prompt injection returns explicit contract (`is_blocked=True`, `is_completed=False`, `ok=False`, `turn_type="BLOCKED"`, `status="BLOCKED_INJECTION"`).
   - Test 2: Verify blocked turn does NOT increment student mastery or advance SLR.
   - Test 3: Verify blocked turn records `TUTOR_TURN_BLOCKED` event in DB without polluting subsequent conversation history.
   - Test 4: Verify direct orchestrator call blocks prompt injection without HTTP layer.
   - Test 5: Verify empty RAG index produces ungrounded but clean turn (`is_grounded=False`, `rag_sources_used=[]`).
   - Test 6: Verify grounded turn with published knowledge chunks sets `is_grounded=True` and populates provenance.
   - Test 7: Verify draft/unpublished course version is rejected with HTTP 404.
   - Test 8: Verify cross-tenant course access is rejected with HTTP 403.
   - Test 9: Verify answer-leakage trigger fails validation, rolls back state, and sets `is_completed=False`.
   - Test 10: Verify idempotent duplicate turn replay does not duplicate database state.
4. **Execute Reproduction Suite & Verify Initial Failures**.
5. **Apply Implementation & Verify Passing Suite**.
6. **Execute Full Non-GUI Regression Suite (`python -m pytest -q -m "not gui"`)**.
7. **Document in `PHASE_08_LOG.md`, update trackers & issue register, commit changes**.
