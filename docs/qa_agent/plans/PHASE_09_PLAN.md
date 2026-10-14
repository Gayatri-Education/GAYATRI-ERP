# Phase 09 Plan — Training & Model Build Pipeline

**Objective:** Create a deterministic, reproducible, and verifiable model-training, dataset-validation, and quantization pipeline. Resolve QA-012 (unchecked shell commands), QA-013 (training reproducibility & dataset integrity), and QA-014 (pedagogical evaluation matrix).

---

## 1. Scope & Targeted Subsystems

1. **Checked Subprocess Execution (QA-012):**
   - Replace unchecked `os.system` calls in `training/train_slm.py` and `training/train_colab.py` with `subprocess.run(..., check=True)` / checked execution helper.
   - Capture return codes, stderr/stdout diagnostics, and raise informative errors on failure.

2. **Dataset Validation & Decontamination (QA-013):**
   - Create `training/dataset_validator.py` implementing `DatasetValidator`.
   - Check line-by-line JSONL validity, `messages` schema (`role`, `content`), minimum turns.
   - Detect empty records, exact duplicate examples, and train/val prompt contamination (preventing memorization / data leakage).
   - Provide automated decontamination utility to generate a clean, strictly isolated validation split.
   - Compute SHA256 checksums for dataset provenance.

3. **Training Determinism (QA-013):**
   - Formalize reproducibility metadata: random seed, base model name/revision, tokenizer revision, hyperparameters (learning rate, batch size, warmup, lora_r, lora_alpha, target_modules), sequence length, precision (fp16/bf16).

4. **Model Pedagogical Evaluation Matrix (QA-014):**
   - Evaluate across 8 canonical dimensions:
     1. Factual correctness
     2. Pedagogical alignment
     3. Grounding
     4. Safety & toxicity
     5. Answer leakage avoidance
     6. Mathematical accuracy
     7. Chemistry domain validity
     8. Socratic style adherence

5. **GGUF Binary Validation Tooling:**
   - Verify GGUF binary magic header (`b'GGUF'` / `0x46554747`), version, tensor/metadata count, and file integrity without requiring full native llama-cpp installation.

---

## 2. Dev Loop Steps

1. **Phase Start & Plan Authoring:** Commit `docs/qa_agent/plans/PHASE_09_PLAN.md`.
2. **Implementation:**
   - Update `training/train_slm.py` and `training/train_colab.py` with checked subprocess runners.
   - Create `training/dataset_validator.py` for dataset schema validation, contamination detection, SHA256 hashing, and decontamination.
   - Create `training/gguf_validator.py` for GGUF magic header and quantization format inspection.
3. **Focused Tests:**
   - Author `tests/test_qa_phase09_training_pipeline.py`.
   - Run focused suite (`pytest tests/test_qa_phase09_training_pipeline.py tests/test_slm_pedagogical_alignment.py tests/architecture/test_anti_chemistry_coupling.py -v`).
4. **Full Regression:**
   - Run `pytest -q` across the entire codebase.
5. **Decisions & Reporting:**
   - Log `DEC-009` in `docs/qa_agent/decisions/DECISION_LOG.md`.
   - Write `docs/qa_agent/reports/PHASE_09_REPORT.md`.
   - Update `docs/qa_agent/MASTER_PROGRESS.md`.
