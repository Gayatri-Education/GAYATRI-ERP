# Phase 03 Implementation Plan: Educational Correctness and Safe Fallback Policy

**Document:** `docs/qa_agent/plans/PHASE_03_PLAN.md`  
**Phase:** 03  
**Maps to:** GQA-003 (P0 Release Blocker)  
**Status:** IN_PROGRESS  

---

## 1. Architectural Scope & Problem Statement

### 1.1 Root Cause & GQA-003 Finding
- **GQA-003 (P0):** In `central_platform/ai/adapters.py`, the pedagogical response generator `generate_dynamic_pedagogical_content()` contains an assessment/grading branch that unconditionally returns:
  ```json
  {"score": 1.0, "correct": true, "feedback": "Accurate response demonstrating clear conceptual mastery."}
  ```
  whenever the task type contains `"grading"` or `"evaluate"`, without evaluating the submitted answer. In addition, `tests/test_phase22_cloud_provider_abstraction.py` previously codified this flaw by asserting `'"score": 1.0' in c1`.
- **Systemic Risk:** In an AI-assisted educational platform, awarding full credit to incorrect, empty, or unverified answers completely destroys pedagogical credibility, corrupts Student Learning Records (SLR), inflates mastery, distorts prerequisite tracking in the Learning Dependency Graph (LDG), and misleads teachers and parents.

---

## 2. Technical Design & Educational Safety Policy

### 2.1 Three-Tier Execution & Grading Policy
1. **Tier A: Real Model Inference (`REAL_MODEL`)**
   - Cloud or local SLM inference (Qwen, Llama, OpenAI, Anthropic, Gemini).
   - Capable of rich qualitative feedback and rubric-based assessment.
   - Subject to strict output validation and confidence bounds.
2. **Tier B: Approved Deterministic Rule Engines (`DETERMINISTIC_RULES`)**
   - `AssessmentGrader` / `DeterministicGrader` / `ChemistryEquationEvaluator` / `EquationBalancingEngine`.
   - Used for narrow, verifiable tasks:
     - Multiple-Choice Questions (MCQ) matching canonical answer keys and option permutations.
     - Numerical items with explicit tolerance intervals ($\pm 5\%$) and unit checks.
     - Stoichiometric chemical equations balanced using atomic conservation matrices.
   - Deterministic grading is authoritative only when input schema and answer keys are fully validated.
3. **Tier C: Mock & Degraded Fallback (`MOCK` / `DEGRADED_FALLBACK`)**
   - Used only in offline developer testing, demonstration, or gracefully degraded UI.
   - **Strict Policy Invariant:** No non-authoritative fallback may EVER award credit (`score` must be `None`), assert correctness (`is_correct` must be `None`), or modify student mastery (`mastery_delta = 0.0`).
   - If a real model or deterministic rule engine is unavailable, the system returns a typed `EVALUATION_UNAVAILABLE` status.

### 2.2 Canonical Typed Evaluation Response
When an automated grader or model is unavailable or operating in fallback mode, `generate_dynamic_pedagogical_content()` returns:
```json
{
  "status": "EVALUATION_UNAVAILABLE",
  "score": null,
  "correct": null,
  "is_correct": null,
  "evaluation_available": false,
  "authoritative": false,
  "feedback": "Automated evaluation is unavailable because a verified evaluation engine or active inference model is not connected. Fallback generators cannot award credit or determine correctness."
}
```

### 2.3 Downstream State Transition Invariants
1. **Learning Event Store (`central_platform/events/store.py`):**
   - Events flagged as `EVALUATION_UNAVAILABLE` or with `score is None` or `is_correct is None` cannot be projected into mastery increments.
2. **Tutor Engine (`core/tutor_engine.py`) & Tutor State (`core/tutor/state.py`):**
   - `record_student_response(correct=None)` maintains current mastery unchanged (`new_mastery = ctx.mastery`).
   - `record_learning_event(correctness='uncertain')` returns without modifying `student_concept_mastery`.
   - Idempotent deduplication guarantees that re-submitting an assessment attempt does not duplicate mastery increments.
3. **Tutor Fallback Disclosure:**
   - Any fallback dialogue includes an explicit non-authoritative disclosure metadata or header indicating degraded mode.

---

## 3. Implementation Steps

1. **Fix `central_platform/ai/adapters.py`:**
   - Remove constant `score: 1.0, correct: true` in `generate_dynamic_pedagogical_content()`.
   - Replace with typed `EVALUATION_UNAVAILABLE` payload.
2. **Update `tests/test_phase22_cloud_provider_abstraction.py`:**
   - Update `test_dynamic_pedagogical_content_variations` to verify `EVALUATION_UNAVAILABLE` and null credit.
3. **Audit and Verify State Protection in Downstream Services:**
   - Ensure `AssessmentService`, `LearningEventStore`, `SLRService`, and `TutorStateManager` preserve mastery when evaluations are unavailable or uncertain.
4. **Author Comprehensive Test Suite `tests/test_qa_phase03_educational_correctness.py`:**
   - Test 1: Incorrect student answer cannot receive automatic full credit.
   - Test 2: Correct answer vs incorrect answer yields expected assessment on verified grading path.
   - Test 3: Grader unavailable leaves score and concept mastery unchanged.
   - Test 4: Mock/fallback response cannot produce a `LearningEvent` that asserts `is_correct`, score, or mastery delta.
   - Test 5: Duplicate assessment request does not double-update mastery.
   - Test 6: Tutor fallback appears as degraded and is not presented as authoritative NCERT/source-grounded answer.
   - Test 7: Educational gold set (chemistry stoichiometry, thermodynamics sign conventions, numerical tolerances, prompt injection resistance).
   - Test 8: Safe recovery when real model or authoritative grader becomes available.
5. **Full Regression Verification:**
   - Execute all repository tests (1,446+ tests) to guarantee zero regressions.
6. **Documentation & Progression:**
   - Generate `docs/qa_agent/reports/PHASE_03_REPORT.md`.
   - Record architectural decision `DEC-015` in `docs/qa_agent/decisions/DECISION_LOG.md`.
   - Update `docs/qa_agent/MASTER_PROGRESS.md` marking Phase 03 PASSED and GQA-003 RESOLVED.
