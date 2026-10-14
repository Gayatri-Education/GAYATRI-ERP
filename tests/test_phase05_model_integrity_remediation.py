"""Phase 5 — Model Artifact & Manifest Integrity Remediation Tests (Section 11 / P0-02).

Validates:
1. Manifest and model artifact checksum synchronization.
2. verify_model_manifest() integrity utility and schema output.
3. Production gate rejection of missing, corrupted, or mismatched models.
4. LocalProvider.health() reporting reason_code='corrupt_file' on invalid checksum in production.
5. LocalProvider._load_model() raising LocalModelError on invalid checksum in production.
6. LocalGGUFAdapter returning LocalModelCorrupt error class in production.
7. Backward compatibility for development and test stub workflows.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from core.model_fetch.manifest_validator import (
    ModelIntegrityResult,
    load_and_validate_manifest,
    verify_model_checksum,
    verify_model_manifest,
)
from core.providers.local import LocalModelError, LocalProvider
from central_platform.ai.adapters import LocalGGUFAdapter
from central_platform.ai.schema import (
    AIExecutionRequest,
    AIModelDescriptor,
    ModelExecutionStatus,
    ProviderConfig,
    ProviderType,
)


@pytest.fixture
def dummy_model_file(tmp_path: Path) -> tuple[Path, str]:
    """Creates a temporary model file and returns (file_path, sha256)."""
    p = tmp_path / "test_model.gguf"
    content = b"GGUF_HEADER_MOCK_BYTES_" + b"X" * (1024 * 1024 + 100)
    p.write_bytes(content)
    expected_sha = hashlib.sha256(content).hexdigest()
    return p, expected_sha


@pytest.fixture
def valid_manifest_file(tmp_path: Path, dummy_model_file: tuple[Path, str]) -> Path:
    """Creates a valid manifest file matching the dummy model file."""
    model_p, sha = dummy_model_file
    manifest = {
        "model_id": "gayatri-chem-qwen2.5-0.5b-v4",
        "display_name": "Gayatri Chemistry Tutor (0.5B)",
        "provider": "local",
        "local_path": str(model_p),
        "artifact_path": str(model_p),
        "download_source": "https://example.com/test_model.gguf",
        "quantization": "Q4_K_M",
        "context_length": 8192,
        "architecture": "Qwen2.5",
        "parameter_count": "0.5B",
        "chat_template": "chatml",
        "capabilities": ["text-generation"],
        "hardware_requirements": "1GB RAM, CPU",
        "language_support": ["en"],
        "version": "v4.0",
        "checksum": sha,
        "license": "MIT",
    }
    mpath = tmp_path / "model_manifest.json"
    mpath.write_text(json.dumps(manifest), encoding="utf-8")
    return mpath


def test_root_manifest_authoritative_identity():
    """Verify that root model_manifest.json defines authoritative release identity."""
    manifest = load_and_validate_manifest("model_manifest.json")
    assert manifest["model_id"] == "gayatri-chem-qwen2.5-0.5b-v4"
    assert manifest["context_length"] == 8192
    assert manifest["quantization"] == "Q4_K_M"
    assert manifest["local_path"] == "models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    assert manifest["checksum"] == "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"


def test_verify_model_manifest_output_schema(valid_manifest_file: Path, dummy_model_file: tuple[Path, str]):
    """Verify verify_model_manifest() produces exact Section 11 keys and CLI formatting."""
    model_p, sha = dummy_model_file
    result = verify_model_manifest(manifest_path=valid_manifest_file, model_path=model_p, use_cache=False)

    assert isinstance(result, ModelIntegrityResult)
    assert result.model_id == "gayatri-chem-qwen2.5-0.5b-v4"
    assert result.model_path == str(model_p)
    assert result.expected_sha256 == sha
    assert result.actual_sha256 == sha
    assert result.size == model_p.stat().st_size
    assert result.format == "gguf"
    assert result.valid is True
    assert result.error is None

    # Verify dictionary representation matches Section 11 spec
    d = result.to_dict()
    for req_field in ["MODEL_ID", "MODEL_PATH", "EXPECTED_SHA256", "ACTUAL_SHA256", "SIZE", "FORMAT", "VALID"]:
        assert req_field in d

    # Verify CLI format output
    cli_out = result.format_cli()
    assert f"MODEL_ID: {result.model_id}" in cli_out
    assert f"MODEL_PATH: {result.model_path}" in cli_out
    assert f"EXPECTED_SHA256: {result.expected_sha256}" in cli_out
    assert f"ACTUAL_SHA256: {result.actual_sha256}" in cli_out
    assert f"SIZE: {result.size}" in cli_out
    assert f"FORMAT: {result.format}" in cli_out
    assert "VALID: True" in cli_out


def test_verify_model_manifest_corrupted_artifact(valid_manifest_file: Path, dummy_model_file: tuple[Path, str]):
    """Verify corrupted artifact bytes trigger checksum mismatch and valid=False."""
    model_p, sha = dummy_model_file
    # Tamper with file
    model_p.write_bytes(b"CORRUPTED_BYTES" + b"Y" * (1024 * 1024))

    result = verify_model_manifest(manifest_path=valid_manifest_file, model_path=model_p, use_cache=False)
    assert result.valid is False
    assert result.actual_sha256 != sha
    assert result.error is not None
    assert "Checksum mismatch" in result.error


def test_verify_model_manifest_missing_file(valid_manifest_file: Path, tmp_path: Path):
    """Verify non-existent model file returns valid=False with size 0."""
    non_existent = tmp_path / "does_not_exist.gguf"
    result = verify_model_manifest(manifest_path=valid_manifest_file, model_path=non_existent, use_cache=False)
    assert result.valid is False
    assert result.size == 0
    assert result.actual_sha256 == ""
    assert "not found" in str(result.error).lower()


def test_verify_model_manifest_empty_file(valid_manifest_file: Path, tmp_path: Path):
    """Verify 0-byte file returns valid=False with empty file error."""
    empty_file = tmp_path / "empty.gguf"
    empty_file.write_bytes(b"")
    result = verify_model_manifest(manifest_path=valid_manifest_file, model_path=empty_file, use_cache=False)
    assert result.valid is False
    assert result.size == 0
    assert "empty" in str(result.error).lower()


def test_local_provider_health_production_gate_corrupted(monkeypatch, valid_manifest_file: Path, dummy_model_file: tuple[Path, str]):
    """In production mode, LocalProvider.health() must report corrupt_file if checksum does not match."""
    model_p, sha = dummy_model_file
    # Tamper bytes
    model_p.write_bytes(b"BAD_BYTES" + b"Z" * (1024 * 1024))

    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setattr("core.config.get_active_model_path", lambda: model_p)

    with patch("core.model_fetch.manifest_validator.get_active_manifest", lambda: load_and_validate_manifest(valid_manifest_file)):
        status = LocalProvider.health(force_checksum_verify=True)
        assert status["available"] is False
        assert status["reason_code"] == "corrupt_file"
        assert "Model integrity check failed" in status["message"]


def test_local_provider_load_model_production_gate_rejects(monkeypatch, valid_manifest_file: Path, dummy_model_file: tuple[Path, str]):
    """In production mode, LocalProvider._load_model() must raise LocalModelError on checksum mismatch."""
    model_p, sha = dummy_model_file
    # Tamper bytes
    model_p.write_bytes(b"BAD_BYTES" + b"Z" * (1024 * 1024))

    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setattr("core.config.get_active_model_path", lambda: model_p)

    # Reset any cached model singleton
    LocalProvider.reset()

    with patch("core.model_fetch.manifest_validator.get_active_manifest", lambda: load_and_validate_manifest(valid_manifest_file)):
        with pytest.raises(LocalModelError, match="Production model integrity gate failure"):
            LocalProvider._load_model(force_checksum_verify=True)


def test_local_gguf_adapter_production_corrupt_response(monkeypatch, valid_manifest_file: Path, dummy_model_file: tuple[Path, str]):
    """LocalGGUFAdapter must safely fail with LocalModelCorrupt in production when file fails checksum."""
    model_p, sha = dummy_model_file
    # Tamper bytes
    model_p.write_bytes(b"BAD_BYTES" + b"Z" * (1024 * 1024))

    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setattr("core.config.get_active_model_path", lambda: model_p)

    with patch("core.model_fetch.manifest_validator.get_active_manifest", lambda: load_and_validate_manifest(valid_manifest_file)):
        adapter = LocalGGUFAdapter(ProviderConfig(provider_name="local", provider_type=ProviderType.LOCAL_GGUF))
        req = AIExecutionRequest(prompt="What is dynamic equilibrium?")
        desc = AIModelDescriptor(model_id="gayatri-chem-qwen2.5-0.5b-v4", model_name="local-qwen")

        res = adapter.execute(req, desc)
        assert res.success is False
        assert res.mock is False
        assert res.error_class == "LocalModelCorrupt"
        assert res.status == ModelExecutionStatus.MODEL_UNAVAILABLE


def test_verify_model_checksum_utility(dummy_model_file: tuple[Path, str]):
    """Direct verification of verify_model_checksum helper."""
    model_p, sha = dummy_model_file
    assert verify_model_checksum(model_p, sha) is True
    assert verify_model_checksum(model_p, "0000000000000000000000000000000000000000000000000000000000000000") is False
    assert verify_model_checksum(model_p.with_name("non_existent.gguf"), sha) is False


def test_verify_model_manifest_missing_checksum(valid_manifest_file: Path, dummy_model_file: tuple[Path, str], tmp_path: Path):
    """When manifest has empty checksum, verify_model_manifest returns valid=False."""
    model_p, _ = dummy_model_file
    manifest_data = json.loads(valid_manifest_file.read_text(encoding="utf-8"))
    manifest_data["checksum"] = ""
    no_cs_path = tmp_path / "no_checksum_manifest.json"
    no_cs_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    res = verify_model_manifest(manifest_path=no_cs_path, model_path=model_p, use_cache=False)
    assert res.valid is False
    assert "authoritative checksum" in str(res.error).lower()


def test_local_provider_load_model_non_production_bypasses_checksum(monkeypatch, dummy_model_file: tuple[Path, str]):
    """In development mode, LocalProvider does not enforce checksum unless explicitly forced."""
    model_p, _ = dummy_model_file
    monkeypatch.setenv("GAYATRI_ENV", "development")
    monkeypatch.setattr("core.config.get_active_model_path", lambda: model_p)

    LocalProvider.reset()
    # In development mode, health() should not report corrupt_file if metadata/llama is okay or non-strict
    health = LocalProvider.health(force_checksum_verify=False)
    assert health["reason_code"] != "corrupt_file"


def test_manifest_validator_cli_execution(valid_manifest_file: Path, dummy_model_file: tuple[Path, str]):
    """Manifest validator script can be executed as a CLI tool reporting valid schema."""
    import subprocess
    model_p, _ = dummy_model_file

    proc = subprocess.run(
        [sys.executable, "-m", "core.model_fetch.manifest_validator", str(valid_manifest_file), str(model_p)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "MODEL_ID: gayatri-chem-qwen2.5-0.5b-v4" in proc.stdout
    assert "VALID: True" in proc.stdout

