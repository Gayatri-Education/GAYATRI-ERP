# Phase 08 Log: Tutor Orchestration, RAG Grounding, and Blocked-Turn Semantics

**Phase:** PHASE-08  
**Status:** PASSED  
**Date:** 2026-10-15  
**Branch:** `dev/phase-00-baseline`  
**Commit / Checkpoint:** `038a179`  

---

## 1. Discovery and Dependency Map
- **Modules Under Review:**
  - `central_platform/api/routes/tutor.py`
  - `central_platform/tutor/orchestrator.py`
  - `central_platform/rag/service.py`
  - `central_platform/ai/response_validator.py`
  - `central_platform/ai/context_builder.py`
- **Target Issues:**
  - **ERP-017**: Blocked tutoring turns returning ambiguous contract (`turn-blocked-*` ID and friendly text) that clients could mistake for a completed successful turn.
  - Missing server-side prompt security in direct Python/SDK `GenericTutorOrchestrator.execute_turn` calls.
  - Missing telemetry/audit events in database for blocked turns.
  - Ensuring ungrounded responses (empty RAG index or zero relevant chunks) do not claim source grounding.
  - Ensuring blocked turns cannot mutate student mastery or advance learning state.
  - Durable deduplication across orchestrator instances and process sessions.

---

## 2. Reproduction Steps and Evidence
Authored reproduction suite: `tests/test_qa_phase08_tutor_integrity.py`.

Prior to remediation:
1. `test_erp017_blocked_turn_has_explicit_contract_flags`: Failed because `is_blocked`, `is_completed`, `turn_type` were missing from response contract.
2. `test_erp017_blocked_turn_does_not_mutate_mastery`: Failed to verify due to mastery method resolution.
3. `test_erp017_blocked_turn_logged_without_polluting_history`: Failed because `is_blocked` was absent and blocked event was not persisted.
4. `test_direct_orchestrator_enforces_prompt_security`: Failed because `TutorTurnResult` did not have `is_blocked` and orchestrator did not execute prompt security.
5. `test_empty_rag_index_is_ungrounded_without_fabricated_sources`: Failed because `is_grounded` was absent.
6. `test_grounded_turn_with_published_assets`: Failed because `is_grounded` was absent.
7. `test_duplicate_turn_idempotency_does_not_duplicate_state`: Failed because orchestrator instance recreated per request lost in-memory deduplication set.

---

## 3. Plan and Acceptance Criteria
1. Add authoritative contract indicator fields (`is_blocked`, `is_completed`, `is_grounded`, `turn_type`) to both `TutorTurnResult` and `TutorTurnApiResponse`.
2. Move prompt security into `GenericTutorOrchestrator.execute_turn` so non-HTTP callers are protected.
3. Record `TUTOR_TURN_BLOCKED` learning event in the database for blocked turns without mutating mastery or polluting conversation history.
4. Set `is_grounded=True` only when authoritative RAG chunks are retrieved and response passes validation; set `is_grounded=False` when index is empty or RAG is unavailable.
5. Ensure idempotent deduplication is durable across requests using class-level cache and session event history.

---

## 4. Human Approval
- Bounded strictly to tutor turn semantics, prompt security, RAG grounding, and deduplication.
- Existing production gates and test suites preserved.

---

## 5. Implementation Summary
- **Orchestrator (`central_platform/tutor/orchestrator.py`):**
  - Added `is_blocked`, `is_completed`, `is_grounded`, `turn_type` to `TutorTurnResult`.
  - Added durable deduplication via `_GLOBAL_PROCESSED_TURNS` and session learning event lookup.
  - Added server-side prompt injection check via `SecurityAuditor.sanitize_prompt`.
  - Ensured session existence before logging `TUTOR_TURN_BLOCKED` event in DB.
  - Resolved authoritative `source_title` from RAG source records in DB.
  - Explicitly mapped `is_grounded = bool(rag_sources_used) and val_result.is_valid`.
- **API Router (`central_platform/api/routes/tutor.py`):**
  - Added `is_blocked`, `is_completed`, `is_grounded`, `turn_type` to `TutorTurnApiResponse`.
  - Ensured session exists and recorded `TUTOR_TURN_BLOCKED` event when route guard triggers.
  - Mapped contract flags from `TutorTurnResult` into `TutorTurnApiResponse`.

---

## 6. Tests Run
1. Targeted Reproduction Suite:
   `python -m pytest tests/test_qa_phase08_tutor_integrity.py -v`
   - Exit code: 0
   - 9 passed in 5.94s.
2. Related Tutor & Security Test Suites:
   `python -m pytest tests/test_phase10_generic_tutor_orchestrator.py tests/test_phase22_security_privacy_isolation_audit.py tests/test_phase24_e2e_journeys_real.py tests/test_phase18_teacher_instruction_rag_integration.py tests/test_phase07_tutor_continuity_remediation.py -v`
   - Exit code: 0
   - 51 passed in 6.82s.

---

## 7. Debugging and Root Cause
- **Root Cause of ERP-017:** Blocked turns returned `turn-blocked-*` IDs and textual responses with `state_committed=False`, but omitted unambiguous contract flags (`is_blocked`, `is_completed`, `is_grounded`, `turn_type`). Clients reading only `turn_id` or `response_text` could treat blocked turns as successful learning turns. Direct calls to `GenericTutorOrchestrator` also lacked prompt security checks. Remediating both layers guarantees explicit, non-ambiguous turn semantics and eliminates student mastery mutation on blocked turns.

---

## 8. Regression Results
- Running full automated non-GUI regression suite: `python -m pytest -q -m "not gui"`
- Result: **1,715 passed, 2 warnings in 158.05s (0 failures, 0 skipped)**. Zero regressions across entire platform.

---

## 9. Security, Privacy, and Data Integrity Review
- **Blocked Turn Isolation:** Blocked turns never advance student mastery or SLR state.
- **Auditability:** Blocked turns record `TUTOR_TURN_BLOCKED` events without contaminating conversation history.
- **Source Grounding:** Only genuine retrieved chunks earn `is_grounded=True`.
- **Idempotency:** Replayed turns do not duplicate learning events.

---

## 10. Documentation and Cleanup Impact
- `docs/qa/phase-logs/PHASE_08_PLAN.md` created.
- `docs/qa/phase-logs/PHASE_08_LOG.md` created and updated.
- `docs/qa/PROGRESS_TRACKER.yaml` and `GAYATRI_ERP_PROGRESS_TRACKER.yaml` updated to DONE.
- `docs/qa/ISSUE_REGISTER.md` and `GAYATRI_ERP_ISSUE_REGISTER.md` updated (`ERP-017` -> `FIXED_VERIFIED`).

---

## 11. GitHub Issue / Commit Links
- Commit `038a179` ("feat(phase-08): resolve ERP-017 blocked-turn semantics, enforce RAG grounding and server-side prompt security")

---

## 12. Residual Risks and Blockers
- None. Tutor turn semantics, grounding flags, prompt security, and deduplication are certified with full regression evidence.

---

## 13. Gate Decision: PASS / FAIL / BLOCKED
- **GATE DECISION: PASS**
- Acceptance criteria fulfilled with zero weakened assertions and 1,715 passing tests. Ready to proceed to PHASE-09.
