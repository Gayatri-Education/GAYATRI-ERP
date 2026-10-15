# Remediation Plan — Phase 07: AI Task Validation, Tutor Context, RAG Trust, and Honest Degraded States (QA-007)

**Phase ID:** 07  
**Target Vulnerability / Finding:** QA-007 (Invalid Task Type Coercion, Synthetic Context Fallbacks, RAG Grounding Verification & Degraded State Integrity)  
**Contract Reference:** [`../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md) Section 10  
**Branch:** `qa/production-readiness-remediation`  
**Status:** IN_PROGRESS  

---

## 1. Inspection Findings & Root Cause Analysis

1. **Silent Coercion of Invalid `task_type` (HTTP 422 Bypass):**
   - In `central_platform/api/routes/ai.py` (lines 140–144), the endpoint `execute_ai()` attempts to map `req.task_type` to `TaskType`, but catches any `Exception` and falls back to `TaskType.GENERAL`.
   - In `central_platform/api/schemas.py`, `AIExecutionApiRequest` and `AIRoutePreviewRequest` declare `task_type: str = "general"` without Pydantic enum validation or a field validator.
   - **Impact:** An invalid, misspelled, or malicious task type (e.g., `"bogus_ai_task"`, `"hack"`) is silently routed to general model tier inference instead of being rejected with HTTP 422 Unprocessable Entity.

2. **Synthetic Student & Course Fallback Placeholders in Client UI:**
   - In `app/ui/design_system/student.js`:
     - `startReview()` uses `const resolvedStudentId = studentId || 'current';` and `course_id: courseId || 'crs-chem-101'`.
     - `loadReviewQueue()` uses `const resolvedStudentId = studentId || 'current';`.
   - **Impact:** When student identity or active course context is unestablished or corrupted, the client issues requests with magic string literals (`'current'`, `'crs-chem-101'`), corrupting analytics and breaking real-user multi-course separation.

3. **RAG Grounding & Degraded State Truthfulness:**
   - When RAG index is empty or all sources are filtered out, the tutor or RAG endpoint must not claim grounded success.
   - `is_grounded` must strictly be `False` whenever authoritative citations are absent.
   - Cross-tenant RAG retrieval across private courses must return `RAG_DENIED` or HTTP 403.

4. **Tutor Turn Integrity & Mastery Preservation:**
   - Turns blocked by prompt injection, policy violation, or model unavailability must report explicit degraded statuses (`BLOCKED_INJECTION`, `VALIDATION_FAILED`, `SERVICE_UNAVAILABLE`).
   - Failed or blocked turns must have `state_committed = False` and must never advance student mastery or record false progress.

---

## 2. Remediation Strategy

### Step 1: Strict `task_type` Schema Validation (HTTP 422)
- In `central_platform/api/schemas.py`:
  - Add `@field_validator("task_type")` to `AIExecutionApiRequest` and `AIRoutePreviewRequest`.
  - Validate that non-null `task_type` values belong to `[t.value for t in TaskType]`.
  - Raise `ValueError` for invalid task types so FastAPI/Pydantic returns HTTP 422 Unprocessable Entity.
- In `central_platform/api/routes/ai.py`:
  - Remove silent fallback to `TaskType.GENERAL` on invalid values. Distinguish omitted (defaults to `"general"`) from invalid (rejected with 422).

### Step 2: Eliminate Magic Fallbacks in Student Portal JavaScript
- In `app/ui/design_system/student.js`:
  - Refactor `startReview()` and `loadReviewQueue()` to resolve student identity from `window.GayatriApp?.getCurrentStudentId?.() || window.sessionStorage?.getItem('student_id') || studentId`.
  - If student identity or course context is missing, fail honestly with an error toast / rejection rather than injecting `'current'` or `'crs-chem-101'`.

### Step 3: RAG Grounding & Multi-Tenant Retrieval Hardening
- Verify that `RAGService.query()` strictly returns `RAG_EMPTY` with `count: 0` when no published sources exist or when all chunks are filtered.
- Verify cross-tenant isolation: student in tenant A cannot query private course knowledge from tenant B.

### Step 4: Tutor Turn & Degraded State Verification
- Confirm that prompt injection triggers `status: "BLOCKED_INJECTION"`, `is_blocked: True`, `is_completed: False`, `state_committed: False`.
- Confirm that model failures trigger `turn_type: "ERROR"`, `state_committed: False`, with 0 mastery gain.

---

## 3. Step-by-Step Execution Plan

- [ ] **Step 1 (Inspect):** Analyze `ai.py`, `schemas.py`, `student.js`, `tutor/orchestrator.py`, and `rag/service.py`. (Completed)
- [ ] **Step 2 (Plan):** Author `docs/qa/plans/PHASE_07_PLAN.md`. (This document)
- [ ] **Step 3 (Reproduce):** Author `tests/test_phase07_ai_task_rag_trust.py` and reproduce:
  - Acceptance of invalid `task_type` without HTTP 422.
  - Client script magic fallback usage.
  - Degraded state handling on blocked turns.
- [ ] **Step 4 (Implement):**
  - Implement Pydantic validators on `AIExecutionApiRequest` and `AIRoutePreviewRequest`.
  - Refactor `central_platform/api/routes/ai.py`.
  - Refactor `app/ui/design_system/student.js`.
- [ ] **Step 5 (Test):** Run `tests/test_phase07_ai_task_rag_trust.py` and connected tutor/rag test suites.
- [ ] **Step 6 (Debug):** Fix any edge cases, casing, or schema mismatches.
- [ ] **Step 7 (Review):** Verify zero regressions across Phases 01–06.
- [ ] **Step 8 (Record):** Author `docs/qa/phase-logs/REMEDIATION_PHASE_07_LOG.md`, update master tracker and issue register.
- [ ] **Step 9 (Commit):** Commit with `fix(qa-007): ai task validation, honest degraded states, and tutor context (Phase 07)`.
- [ ] **Step 10 (Advance):** Proceed to Phase 08.

---

## 4. Exit Criteria

1. Submitting an invalid `task_type` returns HTTP 422 Unprocessable Entity with clear error details.
2. No client script or production API path relies on `'current'` or `'crs-chem-101'` magic placeholders.
3. Blocked and degraded turns never commit state or advance student mastery score.
4. RAG retrieval honors multi-tenant boundaries and never fabricates citations when empty or ungrounded.
5. All tests pass with zero weakened assertions or broad xfails.
