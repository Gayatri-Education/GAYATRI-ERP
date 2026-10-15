# Phase 07 Log: Assessment, Question Bank, Grading, and Anti-Fallback Integrity

**Phase:** PHASE-07  
**Status:** PASSED  
**Date:** 2026-10-15  
**Branch:** `dev/phase-00-baseline`  
**Commit / Checkpoint:** `9fc62f3`  

---

## 1. Discovery and Dependency Map
- **Modules Under Review:**
  - `central_platform/api/routes/assessments.py`
  - `central_platform/assessment/service.py`
  - `central_platform/assessment/sanitizer.py`
  - `central_platform/assessment/grading.py`
  - `central_platform/auth/dependencies.py`
  - `central_platform/api/schemas.py`
  - `tests/conftest.py`
- **Target Issues:**
  - **ERP-016**: Assessment bank serving fallback sample questions when empty in production mode, disguising missing/unconfigured content as real data.
  - Legacy submit endpoint `/api/v1/assessments/submit` auto-provisioning demo content on unknown assessments in production mode.
  - Answer key and teacher explanation disclosure to student personas on question bank endpoints.
  - Cross-course and cross-tenant question item contamination on assessment creation.
  - Missing student self-access isolation (IDOR) on attempt start, submit, and listing.
  - Attempt lifecycle immutability and duration expiration enforcement.
  - Unauthorized teacher review submission by student users.

---

## 2. Reproduction Steps and Evidence
Authored reproduction suite: `tests/test_qa_phase07_assessment_integrity.py`.

Prior to remediation, all 8 targeted tests failed:
1. `test_erp016_empty_bank_returns_empty_list_in_production`: Failed because `GET /api/v1/assessments/items` returned `SAMPLE_QUESTION_BANK` in production mode.
2. `test_erp016_demo_fallback_requires_explicit_request_in_non_prod`: Failed because `GET /api/v1/assessments/items` returned sample items by default without `include_demo=true`.
3. `test_erp016_legacy_submit_rejects_missing_assessment_in_production`: Failed because `POST /api/v1/assessments/submit` auto-provisioned demo items and returned HTTP 200 instead of HTTP 404.
4. `test_answer_keys_scrubbed_for_student_users`: Failed because student users received `correct_answer` and `explanation`.
5. `test_cross_course_and_tenant_question_validation`: Failed because `create_assessment` did not reject items belonging to other courses or tenants.
6. `test_student_isolation_idor_protection`: Failed because students could start attempts for other students (HTTP 201 instead of 403).
7. `test_attempt_lifecycle_immutability_and_expiry`: Failed because expired attempts were accepted without raising ValueError.
8. `test_teacher_review_role_authorization`: Failed because students could review attempts (HTTP 200 instead of 403).

---

## 3. Plan and Acceptance Criteria
1. Gate question bank fallback: In production mode (`is_production_mode() == True`), empty question bank queries must return `ApiResponse(ok=True, data=[])`. In non-prod, fallback is permitted only when `include_demo=True` or `GAYATRI_DEMO_MODE=true`.
2. In production mode, reject legacy submit with HTTP 404 when assessment does not exist.
3. Protect answer keys: Set `correct_answer=None` and `explanation=None` on question item responses for student users.
4. Enforce tenant & course boundaries: Fail closed if questions in an assessment belong to another course or organization.
5. Enforce student self-access boundaries on attempt start, submit, and history. Block students from teacher review (HTTP 403).
6. Enforce attempt immutability (double-submission rejected) and attempt duration expiration.
7. Maintain backward compatibility for test fixtures by seeding baseline course, question, and assessment in `tests/conftest.py`.

---

## 4. Human Approval
- Bounded strictly to assessment anti-fallback integrity, question banks, grading, and RBAC boundaries.
- All existing production gates and test suites preserved.

---

## 5. Implementation Summary
- **API Router (`central_platform/api/routes/assessments.py`):**
  - Integrated `get_db` and `get_current_user_optional`.
  - Added `_enforce_assessment_access` and `_enforce_student_isolation` guards.
  - Updated `list_assessment_items` to gate `SAMPLE_QUESTION_BANK` fallback behind `not is_production_mode()` and `allow_demo`.
  - Scrubbed `correct_answer` and `explanation` for student users.
  - Blocked students from question bank creation, assessment creation, and teacher reviews (HTTP 403).
  - Enforced student ID matching on attempt start, submission, and retrieval (HTTP 403 on IDOR).
  - Hardened `submit_assessment_legacy` to return HTTP 404 in production mode on unknown assessments.
- **Service (`central_platform/assessment/service.py`):**
  - In `create_assessment`, deduplicated `item_ids` and validated that questions match `course_id` and `organization_id`.
  - In `submit_attempt`, rejected already finalized attempts (`GRADED`, `SUBMITTED`, `REVIEWED`, `ABANDONED`) and enforced duration expiry with grace period.
- **Schemas (`central_platform/api/schemas.py`):**
  - Updated `QuestionBankItemResponse` so `correct_answer` and `explanation` are `Optional[str] = None`.
- **Auth Dependencies (`central_platform/auth/dependencies.py`):**
  - Injected `db: PlatformDatabase = Depends(get_db)` into `get_current_user` and `get_current_user_optional` for seamless dependency overrides.
- **Test Sandbox (`tests/conftest.py`):**
  - Seeded baseline course, question, and assessment into `gayatri_isolated_test.db` to ensure existing regression tests query real database rows.

---

## 6. Tests Run
1. Targeted Reproduction Suite:
   `python -m pytest tests/test_qa_phase07_assessment_integrity.py -v`
   - Exit code: 0
   - 8 passed in 4.44s.
2. Related Assessment Test Suites:
   `python -m pytest tests/test_phase07_assessment_remediation.py tests/test_phase11_generic_assessment_evaluation.py tests/test_phase12_real_online_api_boundary.py tests/test_phase19_assessment_platform.py tests/test_phase02_platform_api.py tests/test_phase7_assessment_engine.py -v`
   - Exit code: 0
   - 74 passed in 6.02s.

---

## 7. Debugging and Root Cause
- **Root Cause of ERP-016:** `list_assessment_items` unconditionally populated `items` with `SAMPLE_QUESTION_BANK` whenever the query result was empty, regardless of deployment environment or caller intent. In production, this disguised unconfigured or empty question banks as functional demo data. Remediation ensures production mode strictly rejects demo fallback, and non-production environments only return sample questions when explicitly requested (`include_demo=True`).

---

## 8. Regression Results
- Running full automated non-GUI regression suite: `python -m pytest -q -m "not gui"`
- Result: **1,706 passed, 2 warnings in 155.68s (0 failures, 0 skipped)**. Zero test regressions across entire platform.

---

## 9. Security, Privacy, and Data Integrity Review
- **Answer Key Protection:** Answer keys and explanations are stripped when delivered to students.
- **Student Isolation:** Students cannot start, submit, or inspect attempts belonging to other students (HTTP 403 IDOR prevention).
- **Role Enforcement:** Students cannot create question bank items, create assessments, or submit teacher reviews.
- **Data Integrity:** Cross-course and cross-tenant questions cannot be bundled into an assessment.

---

## 10. Documentation and Cleanup Impact
- `docs/qa/phase-logs/PHASE_07_PLAN.md` created.
- `docs/qa/phase-logs/PHASE_07_LOG.md` created and updated.
- `docs/qa/PROGRESS_TRACKER.yaml` and `GAYATRI_ERP_PROGRESS_TRACKER.yaml` updated to DONE.
- `docs/qa/ISSUE_REGISTER.md` and `GAYATRI_ERP_ISSUE_REGISTER.md` updated (`ERP-016` -> `FIXED_VERIFIED`).

---

## 11. GitHub Issue / Commit Links
- Commit `9fc62f3` ("feat(phase-07): resolve ERP-016 assessment anti-fallback and enforce test lifecycle immutability")

---

## 12. Residual Risks and Blockers
- None. Assessment bank fallback, attempt lifecycle, answer key protection, and cross-tenant boundaries are strictly certified with regression evidence.

---

## 13. Gate Decision: PASS / FAIL / BLOCKED
- **GATE DECISION: PASS**
- Acceptance criteria fulfilled with zero weakened assertions and 1,706 passing tests. Ready to proceed to PHASE-08.

