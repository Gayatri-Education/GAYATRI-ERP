# Phase 06 Implementation Plan — Adaptive Learning & Pedagogical Correctness

## 1. Context & Objectives
- **Severity Focus:** P0/P1 for core tutor behavior.
- **Goal:** Validate and guarantee that Gayatri AI actually adapts to learner behavior across a continuous, multi-turn educational interaction loop.
- **Key Target Areas:**
  - Complete canonical behavior chain:
    Concept presented → Student answers incorrectly → Evaluator detects error and identifies specific misconception → Mastery decreases → Difficulty decreases via DifficultyManager → Tutor shifts to HINT/REMEDIATE → Student retries with guidance → Correct answer evaluated → Mastery increases → Difficulty increases → Recommendation advances to summary or next topic.
  - Socratic policy adherence: non-leakage of answers on hints, multi-tiered hint progression (Levels 1 through 5).
  - Numerical and conceptual answer evaluation correctness (tolerance, unit checks, misconception classification).
  - Learner archetype differentiation (weak vs. average vs. strong learners receive distinct recommendations).
  - State persistence durability across session reload/restart during tutoring turns.

## 2. Requirements & Acceptance Criteria
1. **Behavior Chain Integration:**
   - Integrate `DifficultyManager` directly into `StudentProfile` and `TutorController` so evaluation outcomes dynamically adjust difficulty level (L1–L5) and question difficulty routing (easy/medium/hard).
   - Ensure `TutorController.handle_evaluate` updates both `mastery` and `current_difficulty`.
   - Ensure `TutorResponse` and event logs capture `difficulty_level`, `mastery_delta`, and `misconception`.
2. **Pedagogical Correctness & Invariants:**
   - Test numerical evaluation with tolerances and unit validation.
   - Verify specific chemistry misconceptions (e.g., `THERMO_SIGN_CONVENTION`, `HESS_LAW_DIRECTION`, `GIBBS_SIGN_CONFUSION`).
   - Socratic policy: verify hints do not prematurely leak final numerical or reaction answers.
3. **Learner Archetype Diversity:**
   - Verify that weak, average, and advanced learner profiles produce divergent adaptive actions (e.g. `REMEDIATE_PREREQUISITE`, `TEST_AND_HINT`, `MASTERED`).
4. **State Durability Across Turns:**
   - Ensure student profile and tutor context persist correctly to disk and restore without losing active concept, mastery, or detected misconceptions.

## 3. Targeted Test Suite
Create `tests/test_qa_phase06_adaptive_learning.py` testing:
- Canonical multi-turn adaptive cycle end-to-end using real components (`TutorController`, `StudentProfile`, `StudentAnswerEvaluator`, `AdaptiveLearningEngine`, `DifficultyManager`).
- Misconception detection, repeated misconception tracking, and remediation routing.
- Numerical tolerance and unit-checking evaluation.
- Learner archetype branching (weak, medium, strong).
- Hint ladder progression (Level 1 through 5) without answer leakage.
- Persistence and restoration across simulated restart.

## 4. Execution Sequence
1. Write this plan to `docs/qa_agent/plans/PHASE_06_PLAN.md`.
2. Update `core/tutor/adaptive.py` to add `current_difficulty` and `update_difficulty()` to `StudentProfile`.
3. Update `core/tutor/controller.py` to bind difficulty transitions in `handle_evaluate` and adapt default question difficulty in `handle_question`.
4. Create `tests/test_qa_phase06_adaptive_learning.py`.
5. Run focused tests: `pytest tests/test_qa_phase06_adaptive_learning.py tests/test_phase6_*.py -v`.
6. Run full regression suite: `pytest -q`.
7. Record decision DEC-006 in `docs/qa_agent/decisions/DECISION_LOG.md`.
8. Write `docs/qa_agent/reports/PHASE_06_REPORT.md`.
9. Update `docs/qa_agent/MASTER_PROGRESS.md`.
