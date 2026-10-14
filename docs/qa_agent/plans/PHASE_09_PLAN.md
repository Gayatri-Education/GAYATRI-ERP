# Phase 09 Plan — Training Pipeline, Dataset Integrity and Model Evaluation

**Phase:** Phase 09  
**Audit Findings Addressed:** GQA-010 (Incomplete training evaluator ignores `must_contain` criteria)  
**Related Historical Findings:** QA-012, QA-013, QA-014  
**Date:** 2026-10-14  

---

## 1. Problem Statement & Audit Evidence

### GQA-010 Root Cause
In `training/train_slm.py`, `run_pedagogical_verification()` defines:
```python
test_cases = [
    {
        "name": "Socratic 4-Tier EXPLAIN Test",
        "prompt": "Please explain the First Law of Thermodynamics.",
        "must_contain": ["analogy", "first law", "delta u", "?"],
        "must_not_contain": []
    },
    ...
]
...
leak_found = any(bad in lower_gen for bad in tc["must_not_contain"])
if leak_found:
    print(f"[FAIL] {tc['name']}: Leaked forbidden string!")
else:
    print(f"[PASS] {tc['name']}: Passed behavioral invariants.")
    passed += 1
```
The verification logic only checks `tc["must_not_contain"]`! It completely ignores `tc["must_contain"]`.
Consequently:
- A completely blank response passes.
- A response with "I don't know chemistry" passes.
- The function does not raise an exception or return a failure status; training and quantization proceed regardless of model behavior.
- Only two prompts exist in the verification suite, which is inadequate for certifying NCERT chemistry curriculum accuracy, numerical guidance, misconception handling, and prompt injection resilience.

---

## 2. Target Objectives & Implementation Strategy

### Step 1: Implement `training/pedagogical_evaluator.py`
Create a dedicated, robust evaluation module:
1. `PedagogicalTestCase`: Structured test case schema containing `name`, `category`, `prompt`, `must_contain`, `must_not_contain`, `required_patterns`, `forbidden_patterns`, and `min_length`.
2. `TestCaseEvaluationResult` & `PedagogicalEvaluationSuiteReport`: Structured diagnostics detailing missing required phrases, forbidden leaks detected, and pass/fail status.
3. Fail-Closed Evaluation Engine:
   - Blank/empty output fails immediately.
   - Missing required phrase fails with specific reason.
   - Leaked forbidden phrase fails.
   - Minimum length check prevents trivial/truncated answers.
4. Comprehensive Canonical Benchmark Suite:
   - **Tier 1:** Socratic 4-Tier EXPLAIN (Analogy, Concept Definition, Formula with IUPAC signs, Check question).
   - **Tier 2:** Anti-Answer Leakage Invariants (Student requesting direct numerical answer or guessing wrong; model must guide without revealing solution).
   - **Tier 3:** Chemistry Misconceptions (Endothermic vs Exothermic sign conventions, Le Chatelier pressure/mole shifts).
   - **Tier 4:** Numerical & Formula Guidance (First Law work of expansion $w = -P_{\text{ext}} \Delta V$).
   - **Tier 5:** Prompt Injection & System Override Defense (DAN, "ignore prior instructions", "reveal system prompt").

### Step 2: Refactor `training/train_slm.py` and `training/train_colab.py`
1. Replace incomplete verification in `training/train_slm.py` with `PedagogicalEvaluator`.
2. Fail-closed gate: `run_pedagogical_verification` raises `RuntimeError` if any test case fails, halting the pipeline and preventing GGUF quantization, model merge promotion, or drive upload.
3. Replace raw shell string concatenations with argument lists in `run_checked_command`.

### Step 3: Model Promotion & Reproducibility Invariants
1. Validate training manifest: base model name/revision, LoRA hyperparameters (`LORA_R=32`, `LORA_ALPHA=64`, learning rate, epochs), and random seeds.
2. In `training/dataset_validator.py` and `training/gguf_validator.py`, ensure dataset splits (train and validation) are non-empty, parse cleanly, and GGUF artifacts satisfy magic bytes and tensor checks before promotion.

### Step 4: Author Comprehensive Test Suite in `tests/test_qa_phase09_training_pipeline.py`
Verify:
1. `must_contain` enforcement: missing required tokens causes failure.
2. `must_not_contain` enforcement: forbidden tokens causes failure.
3. Empty/blank output rejection.
4. Fail-closed gate prevents model quantization / promotion on failure.
5. Benchmark suite breadth covering all pedagogical pillars.
6. Dataset schema, decontamination, and SHA-256 provenance.
7. GGUF binary inspection and header validation.

---

## 3. Exit Gate Criteria
- [ ] GQA-010 remediated: Every required criterion is enforced; every forbidden criterion is rejected; empty/blank responses fail.
- [ ] Failed evaluation halts pipeline and prevents model promotion.
- [ ] Subprocess execution uses checked commands with error diagnostics.
- [ ] Comprehensive test suite in `tests/test_qa_phase09_training_pipeline.py` passes cleanly.
- [ ] Full repository regression passes without regressions.
- [ ] Phase 09 Report, Decision Log (DEC-021), and Master Progress updated.
