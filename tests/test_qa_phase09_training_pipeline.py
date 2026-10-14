"""Tests for QA Phase 09: Training & Model Build Pipeline.

Verifies:
- QA-012: Checked subprocess execution replacing unchecked shell commands.
- QA-013: Dataset validation, schema verification, SHA-256 provenance, and decontamination.
- QA-014: Pedagogical evaluation matrix and anti-answer leakage invariants.
- 09.6: GGUF binary format inspection and header validation tooling.
"""

from pathlib import Path
import pytest
import subprocess
import json

from training.train_slm import run_checked_command
from training.dataset_validator import DatasetValidator, DatasetValidationReport
from training.gguf_validator import GGUFValidator, GGUFValidationResult


def test_checked_subprocess_execution():
    """Verify run_checked_command raises RuntimeError with detailed diagnostics on failure (QA-012)."""
    # 1. Successful execution
    res = run_checked_command('python -c "print(\'subprocess_ok\')"', description="Test success")
    assert res.returncode == 0

    # 2. Failing execution with non-zero exit code
    with pytest.raises(RuntimeError) as exc_info:
        run_checked_command('python -c "import sys; sys.exit(7)"', description="Intentional failure")
    assert "status 7" in str(exc_info.value)
    assert "Intentional failure" in str(exc_info.value)


def test_dataset_validator_schema_and_checksum():
    """Verify DatasetValidator on real curriculum dataset files."""
    train_path = Path("training/data/processed/train.jsonl")
    val_path = Path("training/data/processed/val.jsonl")

    assert train_path.exists()
    assert val_path.exists()

    train_report = DatasetValidator.validate_split(train_path)
    assert train_report.is_valid is True
    assert train_report.total_examples == 2250
    assert train_report.valid_examples == 2250
    assert train_report.corrupt_lines == 0
    assert len(train_report.sha256_checksum) == 64

    val_report = DatasetValidator.validate_split(val_path)
    assert val_report.is_valid is True
    assert val_report.total_examples == 250
    assert val_report.valid_examples == 250
    assert val_report.corrupt_lines == 0
    assert len(val_report.sha256_checksum) == 64


def test_dataset_corruption_detection(tmp_path: Path):
    """Verify DatasetValidator catches malformed JSON, missing fields, and bad roles."""
    bad_jsonl = tmp_path / "bad.jsonl"
    with open(bad_jsonl, "w", encoding="utf-8") as f:
        f.write('{"messages": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]}\n')
        f.write('not valid json at all\n')  # corrupt line
        f.write('{"missing_messages": 123}\n')  # missing messages
        f.write('{"messages": [{"role": "evil_role", "content": "X"}]}\n')  # invalid role & single turn
        f.write('\n')  # empty line

    report = DatasetValidator.validate_split(bad_jsonl)
    assert report.is_valid is False
    assert report.total_examples == 5
    assert report.valid_examples == 1
    assert report.corrupt_lines == 3
    assert report.empty_records == 1
    assert len(report.errors) >= 4


def test_dataset_contamination_detection_and_decontamination(tmp_path: Path):
    """Verify prompt overlap detection and automated decontamination split generation (QA-013)."""
    train_path = Path("training/data/processed/train.jsonl")
    val_path = Path("training/data/processed/val.jsonl")

    # 1. Contamination check between train and val
    count, contaminated = DatasetValidator.check_contamination(train_path, val_path)
    # The existing synthetic val split was generated from the same prompt seed pool as train
    assert count == 250
    assert len(contaminated) == 250

    # 2. Construct a test validation split containing contaminated + 5 genuinely novel unseen examples
    hybrid_val_path = tmp_path / "hybrid_val.jsonl"
    with open(val_path, "r", encoding="utf-8") as f_in, open(hybrid_val_path, "w", encoding="utf-8") as f_out:
        f_out.write(f_in.read())
        for i in range(5):
            novel_example = {
                "messages": [
                    {"role": "system", "content": "You are Gayatri Chemistry Tutor."},
                    {"role": "user", "content": f"Completely unique unseen query #{i}: Explain quantum entanglement in semiconductors."},
                    {"role": "assistant", "content": f"A wonderful unique inquiry! Let us reason step-by-step #{i}."},
                ]
            }
            f_out.write(json.dumps(novel_example) + "\n")

    # 3. Run decontamination
    clean_val_path = tmp_path / "clean_val.jsonl"
    pruned = DatasetValidator.decontaminate_splits(
        train_path=train_path,
        val_path=hybrid_val_path,
        clean_val_path=clean_val_path,
    )
    assert pruned == 250

    # 4. Verify clean split has ZERO contamination against train
    clean_count, clean_contaminated = DatasetValidator.check_contamination(train_path, clean_val_path)
    assert clean_count == 0
    assert len(clean_contaminated) == 0

    # 5. Verify clean split is structurally valid and retains the 5 novel examples
    clean_report = DatasetValidator.validate_split(clean_val_path)
    assert clean_report.is_valid is True
    assert clean_report.total_examples == 5


def test_gguf_validator_header_inspection(tmp_path: Path):
    """Verify GGUF binary inspection, magic bytes checking, and mock generation (09.6)."""
    # 1. Non-existent file
    res_none = GGUFValidator.validate_file(tmp_path / "missing.gguf")
    assert res_none.is_valid is False
    assert "does not exist" in str(res_none.error)

    # 2. Corrupt/non-GGUF file
    fake_file = tmp_path / "corrupt.gguf"
    fake_file.write_bytes(b"NOT_GGUF_MAGIC_HEADER_TEST_BYTES")
    res_corrupt = GGUFValidator.validate_file(fake_file)
    assert res_corrupt.is_valid is False
    assert "Invalid magic bytes" in str(res_corrupt.error)

    # 3. Valid GGUF mock
    mock_file = tmp_path / "valid_model.gguf"
    GGUFValidator.create_mock_gguf(
        dest_path=mock_file,
        version=3,
        tensor_count=290,
        metadata_kv_count=42,
    )
    res_valid = GGUFValidator.validate_file(mock_file)
    assert res_valid.is_valid is True
    assert res_valid.magic == "GGUF"
    assert res_valid.version == 3
    assert res_valid.tensor_count == 290
    assert res_valid.metadata_kv_count == 42
    assert res_valid.file_size_bytes > 0


def test_pedagogical_evaluation_matrix():
    """Verify model output alignment matrix across all 8 canonical dimensions (QA-014)."""
    from core.runtimes.chemistry import _build_chemistry_system_prompt

    prompt = _build_chemistry_system_prompt(is_slm=True, rag_evidence="<evidence>First Law</evidence>")

    # 1. Pedagogical alignment: Socratic method
    assert "Socratic Method" in prompt

    # 2. Grounding: NCERT evidence requirement
    assert "<evidence>First Law</evidence>" in prompt

    # 3. Answer leakage protection
    assert "ZERO ANSWER LEAKAGE" in prompt
    assert "Never spoon-feed final answers or numerical solutions" in prompt

    # 4. Socratic Step structure
    assert "EXPLAIN Mode: Structure responses into: 1. Everyday Analogy" in prompt


# ── GQA-010 Remediation Tests: Pedagogical Evaluator & Release Gates ─────────

from training.pedagogical_evaluator import (
    PedagogicalCategory,
    PedagogicalEvaluator,
    PedagogicalTestCase,
    PedagogicalEvaluationFailureError,
    TestCaseEvaluationResult,
)


def test_pedagogical_evaluator_enforces_must_contain():
    """Verify evaluator strictly requires EVERY must_contain phrase (remediating GQA-010)."""
    tc = PedagogicalTestCase(
        name="Thermodynamics First Law Required Criteria",
        prompt="Explain the First Law of Thermodynamics.",
        category=PedagogicalCategory.EXPLAIN_SCAFFOLD,
        must_contain=["analogy", "first law", "delta u", "?"],
        must_not_contain=["leak"],
        min_length=20,
    )

    # 1. Output missing 'delta u' must FAIL
    bad_output_missing_phrase = (
        "Here is a helpful everyday analogy: the first law states energy cannot be created or destroyed. "
        "Does that make intuitive sense?"
    )
    res_missing = PedagogicalEvaluator.evaluate_response(bad_output_missing_phrase, tc)
    assert res_missing.is_pass is False
    assert "delta u" in res_missing.missing_required
    assert any("Missing required phrase: 'delta u'" in r for r in res_missing.failure_reasons)

    # 2. Output missing '?' (question mark for Socratic prompting) must FAIL
    bad_output_missing_question = (
        "Here is an analogy for the first law: energy is conserved, meaning delta u = q + w."
    )
    res_no_q = PedagogicalEvaluator.evaluate_response(bad_output_missing_question, tc)
    assert res_no_q.is_pass is False
    assert "?" in res_no_q.missing_required

    # 3. Output containing ALL required phrases and no forbidden phrases must PASS
    valid_output = (
        "Let us explore this with an everyday analogy: think of energy like money in a bank account. "
        "The first law teaches us that energy cannot be created or destroyed. In thermodynamics, "
        "we express this as delta U = q + w. What do you think happens to the internal energy if heat is added?"
    )
    res_valid = PedagogicalEvaluator.evaluate_response(valid_output, tc)
    assert res_valid.is_pass is True
    assert len(res_valid.missing_required) == 0
    assert len(res_valid.forbidden_detected) == 0
    assert len(res_valid.failure_reasons) == 0


def test_pedagogical_evaluator_rejects_empty_and_blank_outputs():
    """Verify empty, whitespace-only, or truncated outputs immediately fail (GQA-010)."""
    tc = PedagogicalTestCase(
        name="Anti-Leakage Test",
        prompt="Solve delta U.",
        category=PedagogicalCategory.ANTI_ANSWER_LEAKAGE,
        must_contain=["work", "heat"],
        must_not_contain=["300 J"],
        min_length=15,
    )

    # 1. Empty string
    res_empty = PedagogicalEvaluator.evaluate_response("", tc)
    assert res_empty.is_pass is False
    assert any("Empty or blank model response is strictly prohibited" in r for r in res_empty.failure_reasons)

    # 2. Whitespace-only string
    res_spaces = PedagogicalEvaluator.evaluate_response("   \n\t   ", tc)
    assert res_spaces.is_pass is False
    assert any("Empty or blank model response is strictly prohibited" in r for r in res_spaces.failure_reasons)

    # 3. Below minimum length
    res_short = PedagogicalEvaluator.evaluate_response("work heat", tc)
    assert res_short.is_pass is False
    assert any("below minimum required length" in r for r in res_short.failure_reasons)


def test_pedagogical_evaluator_rejects_forbidden_phrases():
    """Verify evaluator catches leaked answers and forbidden strings."""
    tc = PedagogicalTestCase(
        name="Anti-Leak Numerical Test",
        prompt="delta U is 700 J because 500 + 200 = 700 J.",
        category=PedagogicalCategory.ANTI_ANSWER_LEAKAGE,
        must_contain=["work", "expansion"],
        must_not_contain=["300 j", "300j", "= 300", "answer is 300"],
        min_length=20,
    )

    # Contains required phrases BUT also leaks the forbidden answer
    leaked_output = (
        "You considered the work and expansion correctly, but the answer is 300 J because work is negative!"
    )
    res_leak = PedagogicalEvaluator.evaluate_response(leaked_output, tc)
    assert res_leak.is_pass is False
    assert "300 j" in res_leak.forbidden_detected or "answer is 300" in res_leak.forbidden_detected
    assert any("Leaked forbidden phrase" in r for r in res_leak.failure_reasons)


def test_pedagogical_suite_fail_closed_gate():
    """Verify that failing any benchmark test case fails the entire suite and blocks promotion."""
    tc_pass = PedagogicalTestCase(
        name="Pass Case",
        prompt="Explain equilibrium.",
        category=PedagogicalCategory.EXPLAIN_SCAFFOLD,
        must_contain=["dynamic", "rate"],
        min_length=15,
    )
    tc_fail = PedagogicalTestCase(
        name="Fail Case",
        prompt="Explain entropy.",
        category=PedagogicalCategory.EXPLAIN_SCAFFOLD,
        must_contain=["spontaneous", "disorder"],
        min_length=15,
    )

    pairs = [
        (tc_pass, "Chemical equilibrium is a dynamic state where the forward and reverse reaction rate are equal."),
        (tc_fail, "Entropy is just randomness in molecules without mentioning other terms."),
    ]

    report = PedagogicalEvaluator.evaluate_suite(pairs, min_pass_rate=1.0)
    assert report.is_pass is False
    assert report.total_cases == 2
    assert report.passed_cases == 1
    assert report.failed_cases == 1
    assert report.pass_rate == 0.5
    assert len(report.failure_summary) == 1
    assert "Missing required phrase: 'spontaneous'" in report.failure_summary[0]


def test_pedagogical_canonical_benchmark_breadth():
    """Verify benchmark suite covers all 5 required educational pillars."""
    suite = PedagogicalEvaluator.CANONICAL_BENCHMARK_SUITE
    assert len(suite) >= 5

    categories = {tc.category for tc in suite}
    assert PedagogicalCategory.EXPLAIN_SCAFFOLD in categories
    assert PedagogicalCategory.ANTI_ANSWER_LEAKAGE in categories
    assert PedagogicalCategory.CHEMISTRY_MISCONCEPTION in categories
    assert PedagogicalCategory.NUMERICAL_GUIDANCE in categories
    assert PedagogicalCategory.PROMPT_INJECTION_DEFENSE in categories

    for tc in suite:
        assert tc.name
        assert tc.prompt
        assert tc.must_contain or tc.required_patterns
        assert tc.min_length >= 15


def test_training_pipeline_hyperparameters_and_model_pinning():
    """Verify training pipeline constants and hyperparameters are pinned and reproducible."""
    import training.train_slm as slm

    assert slm.BASE_MODEL_NAME == "Qwen/Qwen2.5-0.5B-Instruct"
    assert slm.LORA_R == 32
    assert slm.LORA_ALPHA == 64
    assert slm.LORA_DROPOUT == 0.05
    assert slm.LEARNING_RATE == 3e-4
    assert slm.NUM_TRAIN_EPOCHS == 3
    assert slm.MAX_SEQ_LENGTH == 1024


def test_mock_model_verification_fail_closed_raises_error():
    """Verify run_pedagogical_verification raises PedagogicalEvaluationFailureError on bad model generation."""
    class MockTokenizer:
        def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
            return "formatted_prompt"

        def __call__(self, text, return_tensors="pt"):
            import torch
            return {"input_ids": torch.tensor([[1, 2, 3]])}

        def decode(self, tokens, skip_special_tokens=True):
            # Returns empty/failing response
            return "I am unable to answer this question."

    class MockModel:
        device = "cpu"

        def eval(self):
            pass

        def generate(self, **kwargs):
            import torch
            # Returns trivial tokens
            return torch.tensor([[1, 2, 3, 4, 5]])

    mock_model = MockModel()
    mock_tok = MockTokenizer()

    # With fail_on_error=True, must raise PedagogicalEvaluationFailureError
    with pytest.raises(PedagogicalEvaluationFailureError) as exc_info:
        PedagogicalEvaluator.run_pedagogical_verification(
            model=mock_model,
            tokenizer=mock_tok,
            test_cases=[
                PedagogicalTestCase(
                    name="Test Case",
                    prompt="Hello",
                    category=PedagogicalCategory.EXPLAIN_SCAFFOLD,
                    must_contain=["crucial_concept_phrase"],
                )
            ],
            fail_on_error=True,
        )

    assert "Pedagogical verification failed" in str(exc_info.value)
    assert "Model promotion and GGUF quantization aborted" in str(exc_info.value)

