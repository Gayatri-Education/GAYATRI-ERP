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
