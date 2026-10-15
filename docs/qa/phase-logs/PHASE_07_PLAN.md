# Phase 07 Plan: Assessment, Question Bank, Grading, and Anti-Fallback Integrity

**Phase:** PHASE-07  
**Status:** IN_PLANNING  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer  

---

## 1. Goal & Scope
Implement and verify assessment platform integrity, eliminating hidden demo fallbacks (ERP-016), enforcing fail-closed entity ownership across courses and tenants, protecting answer keys from student-side disclosure, and certifying attempt lifecycle determinism and immutability.

---

## 2. Target Findings & Invariants
- **ERP-016**: `central_platform/api/routes/assessments.py` unconditionally falls back to `SAMPLE_QUESTION_BANK` when the question bank is empty.
- **Anti-Fallback Invariant**:
  - In production mode (`is_production_mode() == True`), question bank queries MUST NEVER return synthetic or sample fallback questions; an empty bank must return `ApiResponse(ok=True, data=[])`.
  - Outside of production, sample questions may only be returned when explicitly requested via `include_demo=True` query parameter or `GAYATRI_DEMO_MODE=true`.
  - Legacy submission `POST /api/v1/assessments/submit` must fail closed (HTTP 404) in production if the assessment does not exist, rather than auto-provisioning demo content.
- **Answer Key Protection Invariant**:
  - Students accessing question items or sanitized assessments must NEVER receive `correct_answer`, `rubric`, or `explanation`.
- **Tenant & Course Scoping Invariant**:
  - An assessment cannot be created with question items from a different course or a different organization (fail-closed with HTTP 400).
- **Attempt Lifecycle Invariant**:
  - Attempts cannot be submitted twice once finalized (`GRADED`, `REVIEWED`, `SUBMITTED`, `ABANDONED`).
  - Attempts exceeding duration limit plus grace period cannot be submitted.
  - Scores are computed strictly by server-side deterministic/rubric engines; client-supplied scores are ignored.
  - Cross-student attempt starting, viewing, or submitting is blocked with HTTP 403.
  - Students cannot review teacher attempts (HTTP 403).

---

## 3. Implementation Plan
1. **Remediate `central_platform/api/routes/assessments.py`**:
   - Inject `db: PlatformDatabase = Depends(get_db)` and `current_user: Optional[User] = Depends(get_current_user_optional)`.
   - Gate question bank fallback in `list_assessment_items`: only allow fallback when NOT in production mode AND (`include_demo=True` or `GAYATRI_DEMO_MODE=true`).
   - Remove auto-provision fallback in `submit_assessment_legacy` when in production mode (raise HTTP 404).
   - Strip `correct_answer` and `explanation` from `QuestionBankItemResponse` when caller is a student.
   - Enforce authentication in production mode (HTTP 401).
   - Enforce role boundaries: Students cannot create question items, create assessments, or submit teacher reviews (HTTP 403).
   - Enforce student self-access on attempt start, submit, and attempt listing (HTTP 403 on IDOR).
2. **Remediate `central_platform/assessment/service.py`**:
   - In `create_assessment`, deduplicate `item_ids` and validate that all items belong to `assessment.course_id` and `assessment.organization_id` when `allow_auto_provision=False`.
   - In `submit_attempt`, reject submissions if attempt status is already finalized or expired. Check `duration_minutes` against elapsed time.
3. **Remediate `tests/conftest.py`**:
   - Seed baseline question bank items and assessment into `gayatri_isolated_test.db` so existing tests (e.g. `test_phase02_platform_api.py`) test against real database rows without relying on demo fallback.
4. **Author Reproduction Suite (`tests/test_qa_phase07_assessment_integrity.py`)**:
   - Verify empty bank returns `[]` in production mode.
   - Verify empty bank returns `[]` without `include_demo=true` in non-prod.
   - Verify `include_demo=true` returns sample items in non-prod, but is rejected/empty in prod.
   - Verify legacy `/submit` 404s on missing assessment in prod.
   - Verify answer key scrubbing for students.
   - Verify cross-course and cross-tenant question creation rejection.
   - Verify student self-access isolation (HTTP 403 on IDOR).
   - Verify double-submission rejection (HTTP 400).
   - Verify expired attempt rejection (HTTP 400).
   - Verify student cannot perform teacher review (HTTP 403).
5. **Run targeted tests & full regression suite**.
6. **Update logs, trackers, and issue registers, commit changes**.
