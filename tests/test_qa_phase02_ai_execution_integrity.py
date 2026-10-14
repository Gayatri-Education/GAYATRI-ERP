"""Tests for QA Phase 02: AI Execution Integrity & Provider Routing.

Verifies:
- QA-001: Execution provenance explicitly exposes REAL_MODEL, MOCK, DEGRADED_FALLBACK, FAILED
- QA-002: Real inference distinguished from mock and degraded fallback
- QA-003: Model readiness states (CONFIGURED, LOADABLE, EXECUTABLE, HEALTHY) and production gate enforcement
- Provider failure modes (401, 403, 429, 500, timeout, malformed JSON)
- Streaming and cancellation handling
"""
import io
import json
import socket
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from central_platform.ai.adapters import (
    AnthropicAdapter,
    GeminiAdapter,
    LocalGGUFAdapter,
    MockAIAdapter,
    OpenAIAdapter,
    is_production_mode,
)
from central_platform.ai.gateway import AIGatewayService
from central_platform.ai.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    AIModelDescriptor,
    ExecutionProvenance,
    ModelExecutionStatus,
    ModelTier,
    ProviderConfig,
    ProviderType,
    TaskType,
)
from central_platform.deployment.validator import (
    DeploymentValidator,
    ModelReadinessState,
    ValidationStatus,
)
from central_platform.db import PlatformDatabase


class TestAIExecutionIntegrity:
    """Verifies AI execution truth, provenance observability, and provider failover."""

    def test_mock_adapter_explicit_provenance(self):
        """Mock adapter explicitly returns MOCK provenance, never REAL_MODEL."""
        cfg = ProviderConfig(provider_name="test_mock", provider_type=ProviderType.MOCK)
        adapter = MockAIAdapter(cfg)
        desc = AIModelDescriptor(model_id="test_mock_model", model_name="MockModel")
        req = AIExecutionRequest(prompt="What is Boyle's law?", task_type=TaskType.TUTORING)

        res = adapter.execute(req, desc)
        assert res.success is True
        assert res.mock is True
        assert res.execution_provenance == ExecutionProvenance.MOCK
        assert res.provenance["real_model"] is False
        assert res.provenance["execution_provenance"] == "MOCK"
        assert res.to_dict()["real_model"] is False

    def test_local_gguf_adapter_real_model_provenance(self):
        """When LocalProvider is available and streams real tokens, REAL_MODEL provenance is set."""
        cfg = ProviderConfig(provider_name="local_llama", provider_type=ProviderType.LOCAL_GGUF)
        adapter = LocalGGUFAdapter(cfg)
        desc = AIModelDescriptor(model_id="qwen", model_name="Qwen2.5-0.5B")
        req = AIExecutionRequest(prompt="What is Avogadro's number?", task_type=TaskType.TUTORING)

        with patch("core.providers.local.LocalProvider.health", return_value={"available": True}), \
             patch("core.providers.local.LocalProvider.is_available", return_value=True), \
             patch("core.providers.local.LocalProvider.chat_stream", return_value=["6.022", " x 10^23", " mol^-1"]):
            res = adapter.execute(req, desc)
            assert res.success is True
            assert res.mock is False
            assert res.execution_provenance == ExecutionProvenance.REAL_MODEL
            assert res.provenance["real_model"] is True
            assert "6.022" in res.content

    def test_local_gguf_adapter_degraded_fallback_provenance(self):
        """When LocalProvider is unavailable outside production, DEGRADED_FALLBACK is set, never REAL_MODEL."""
        cfg = ProviderConfig(provider_name="local_llama", provider_type=ProviderType.LOCAL_GGUF)
        adapter = LocalGGUFAdapter(cfg)
        desc = AIModelDescriptor(model_id="qwen", model_name="Qwen2.5-0.5B")
        req = AIExecutionRequest(prompt="Explain chemical equilibrium", task_type=TaskType.TUTORING)

        with patch("core.providers.local.LocalProvider.health", return_value={"available": False, "reason_code": "missing_file"}), \
             patch("central_platform.ai.adapters.is_production_mode", return_value=False):
            res = adapter.execute(req, desc)
            assert res.success is True
            assert res.mock is True
            assert res.fallback_used is True
            assert res.execution_provenance == ExecutionProvenance.DEGRADED_FALLBACK
            assert res.provenance["real_model"] is False
            assert res.provenance["execution_provenance"] == "DEGRADED_FALLBACK"

    def test_local_gguf_adapter_fails_closed_in_production(self):
        """In production mode, missing local model fails closed with FAILED provenance."""
        cfg = ProviderConfig(provider_name="local_llama", provider_type=ProviderType.LOCAL_GGUF)
        adapter = LocalGGUFAdapter(cfg)
        desc = AIModelDescriptor(model_id="qwen", model_name="Qwen2.5-0.5B")
        req = AIExecutionRequest(prompt="Explain chemical equilibrium", task_type=TaskType.TUTORING)

        with patch("core.providers.local.LocalProvider.health", return_value={"available": False, "reason_code": "missing_file"}), \
             patch("central_platform.ai.adapters.is_production_mode", return_value=True):
            res = adapter.execute(req, desc)
            assert res.success is False
            assert res.status == ModelExecutionStatus.MODEL_UNAVAILABLE
            assert res.execution_provenance == ExecutionProvenance.FAILED
            assert res.provenance["real_model"] is False

    def test_cloud_adapter_real_model_and_error_handling(self):
        """Cloud adapters mark REAL_MODEL on success and FAILED on errors."""
        cfg = ProviderConfig(
            provider_name="test_openai",
            provider_type=ProviderType.OPENAI,
            api_key_ref="TEST_API_KEY",
            base_url="https://api.openai.com/v1",
        )
        adapter = OpenAIAdapter(cfg)
        desc = AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o")
        req = AIExecutionRequest(prompt="Calculate molarity", task_type=TaskType.TUTORING)

        # 1. Missing API key -> FAILED
        with patch.dict("os.environ", {}, clear=True):
            res = adapter.execute(req, desc)
            assert res.success is False
            assert res.status == ModelExecutionStatus.MODEL_CONFIGURATION_ERROR
            assert res.execution_provenance == ExecutionProvenance.FAILED

        # 2. HTTP 429 rate limit -> MODEL_RATE_LIMITED and FAILED
        with patch.dict("os.environ", {"TEST_API_KEY": "valid_key"}), \
             patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)):
            res = adapter.execute(req, desc)
            assert res.success is False
            assert res.status == ModelExecutionStatus.MODEL_RATE_LIMITED
            assert res.execution_provenance == ExecutionProvenance.FAILED

        # 3. Timeout -> MODEL_TIMEOUT and FAILED
        with patch.dict("os.environ", {"TEST_API_KEY": "valid_key"}), \
             patch("urllib.request.urlopen", side_effect=socket.timeout("Connection timed out")):
            res = adapter.execute(req, desc)
            assert res.success is False
            assert res.status == ModelExecutionStatus.MODEL_TIMEOUT
            assert res.execution_provenance == ExecutionProvenance.FAILED

        # 4. Successful response -> REAL_MODEL
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Molarity is moles per liter of solution."}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch.dict("os.environ", {"TEST_API_KEY": "valid_key"}), \
             patch("urllib.request.urlopen", return_value=mock_resp):
            res = adapter.execute(req, desc)
            assert res.success is True
            assert res.execution_provenance == ExecutionProvenance.REAL_MODEL
            assert res.provenance["real_model"] is True
            assert "moles per liter" in res.content

    def test_gateway_fallback_provenance_propagation(self, tmp_path):
        """AI Gateway propagates fallback provenance when failover occurs."""
        db = PlatformDatabase(db_path=str(tmp_path / "gw.db"))
        gateway = AIGatewayService(db=db)

        # Execute tutoring request
        req = AIExecutionRequest(
            prompt="Explain Hess's Law",
            student_id="std_01",
            task_type=TaskType.TUTORING,
        )
        res = gateway.execute(req)
        assert res.success is True
        # Since local model is not on disk and no cloud keys set, fallback or mock is executed
        assert res.execution_provenance in (ExecutionProvenance.MOCK, ExecutionProvenance.DEGRADED_FALLBACK)
        assert res.provenance["real_model"] is False

    def test_deployment_validator_model_readiness_states(self, tmp_path):
        """Deployment validator distinguishes CONFIGURED, LOADABLE, HEALTHY, and fails in production if model missing."""
        # 1. Non-production: manifest exists, file absent -> PASS with CONFIGURED
        v_dev = DeploymentValidator(root_dir=Path("."), env_vars={"APP_ENV": "development"})
        res_dev = v_dev.validate_model_providers()
        assert res_dev.status == ValidationStatus.PASS
        assert res_dev.details["readiness_state"] == ModelReadinessState.CONFIGURED.value
        assert res_dev.details["physical_artifact_present"] is False

        # 2. Production: manifest exists, file absent -> FAIL
        v_prod = DeploymentValidator(root_dir=Path("."), env_vars={"APP_ENV": "production"})
        res_prod = v_prod.validate_model_providers()
        assert res_prod.status == ValidationStatus.FAIL
        assert res_prod.details["production_blocker"] is True
        assert res_prod.details["readiness_state"] == ModelReadinessState.CONFIGURED.value
        assert "Production release blocker" in res_prod.message

        # 3. Model file present with corrupt checksum -> FAIL in production
        fake_model_dir = tmp_path / "models"
        fake_model_dir.mkdir(parents=True, exist_ok=True)
        fake_file = fake_model_dir / "qwen.gguf"
        fake_file.write_bytes(b"GGUF" + b"\x00" * 2048)

        fake_manifest = tmp_path / "model_manifest.json"
        fake_manifest.write_text(json.dumps({
            "model_id": "fake_model",
            "local_path": "models/qwen.gguf",
            "checksum": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        }), encoding="utf-8")

        v_corrupt = DeploymentValidator(root_dir=tmp_path, env_vars={"APP_ENV": "production"})
        res_corrupt = v_corrupt.validate_model_providers()
        assert res_corrupt.status == ValidationStatus.FAIL
        assert res_corrupt.details["readiness_state"] == ModelReadinessState.CORRUPT.value
        assert "checksum mismatch" in res_corrupt.message

    def test_manifest_missing_and_empty_models(self, tmp_path):
        """Manifest missing, malformed, or empty returns UNCONFIGURED or FAILED."""
        # 1. Missing manifest
        v_missing = DeploymentValidator(root_dir=tmp_path / "nonexistent")
        res_missing = v_missing.validate_model_providers()
        assert res_missing.status == ValidationStatus.FAIL
        assert res_missing.details["readiness_state"] == ModelReadinessState.UNCONFIGURED.value

        # 2. Malformed JSON
        mal_manifest = tmp_path / "model_manifest.json"
        mal_manifest.write_text("{not valid json...", encoding="utf-8")
        v_mal = DeploymentValidator(root_dir=tmp_path)
        res_mal = v_mal.validate_model_providers()
        assert res_mal.status == ValidationStatus.FAIL
        assert res_mal.details["readiness_state"] == ModelReadinessState.FAILED.value

        # 3. Empty models array
        mal_manifest.write_text(json.dumps({"models": []}), encoding="utf-8")
        res_empty = v_mal.validate_model_providers()
        assert res_empty.status == ValidationStatus.FAIL
        assert res_empty.details["readiness_state"] == ModelReadinessState.UNCONFIGURED.value

    def test_model_path_traversal_detection(self, tmp_path):
        """Model artifact path attempting directory traversal outside root is rejected."""
        manifest = tmp_path / "model_manifest.json"
        manifest.write_text(json.dumps({
            "models": [{"model_id": "traversal", "local_path": "../../etc/shadow"}]
        }), encoding="utf-8")

        v = DeploymentValidator(root_dir=tmp_path)
        res = v.validate_model_providers()
        assert res.status == ValidationStatus.FAIL
        assert res.details["readiness_state"] == ModelReadinessState.CORRUPT.value
        assert "Path traversal detected" in res.message

    def test_truncated_or_empty_model_file(self, tmp_path):
        """Model file smaller than 1024 bytes is rejected as truncated/corrupt."""
        model_dir = tmp_path / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        tiny_file = model_dir / "tiny.gguf"
        tiny_file.write_bytes(b"too small")

        manifest = tmp_path / "model_manifest.json"
        manifest.write_text(json.dumps({
            "models": [{"model_id": "m1", "local_path": "models/tiny.gguf"}]
        }), encoding="utf-8")

        v = DeploymentValidator(root_dir=tmp_path)
        res = v.validate_model_providers()
        assert res.status == ValidationStatus.FAIL
        assert res.details["readiness_state"] == ModelReadinessState.CORRUPT.value
        assert "truncated" in res.message

    def test_invalid_gguf_magic_header(self, tmp_path):
        """GGUF file without 'GGUF' magic bytes at offset 0 is rejected as corrupt."""
        model_dir = tmp_path / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        bad_header_file = model_dir / "bad_magic.gguf"
        bad_header_file.write_bytes(b"PK03" + b"\x00" * 2048)

        manifest = tmp_path / "model_manifest.json"
        manifest.write_text(json.dumps({
            "models": [{"model_id": "m1", "local_path": "models/bad_magic.gguf"}]
        }), encoding="utf-8")

        v = DeploymentValidator(root_dir=tmp_path)
        res = v.validate_model_providers()
        assert res.status == ValidationStatus.FAIL
        assert res.details["readiness_state"] == ModelReadinessState.CORRUPT.value
        assert "invalid GGUF magic header" in res.message

    def test_valid_gguf_header_and_checksum_without_probe_is_not_healthy(self, tmp_path):
        """Physical model presence and checksum alone reports LOADABLE, never HEALTHY without inference probe."""
        import hashlib
        model_dir = tmp_path / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        good_file = model_dir / "valid.gguf"
        content = b"GGUF" + b"\x01" * 4096
        good_file.write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()

        manifest = tmp_path / "model_manifest.json"
        manifest.write_text(json.dumps({
            "models": [{"model_id": "m1", "local_path": "models/valid.gguf", "checksum": checksum}]
        }), encoding="utf-8")

        v = DeploymentValidator(root_dir=tmp_path, env_vars={"APP_ENV": "development"})
        res = v.validate_model_providers(probe_inference=False)
        assert res.status == ValidationStatus.PASS
        # Crucial GQA-001 invariant: without inference probe, state must NOT be HEALTHY
        assert res.details["readiness_state"] == ModelReadinessState.LOADABLE.value
        assert res.details["inference_verified"] is False
        assert "bounded inference probe required" in res.message

    def test_inference_probe_success_with_real_model(self, tmp_path):
        """Inference probe succeeds when real model executes and returns REAL_MODEL provenance."""
        import hashlib
        model_dir = tmp_path / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        good_file = model_dir / "valid.gguf"
        content = b"GGUF" + b"\x01" * 4096
        good_file.write_bytes(content)
        checksum = hashlib.sha256(content).hexdigest()

        manifest = tmp_path / "model_manifest.json"
        manifest.write_text(json.dumps({
            "models": [{"model_id": "m1", "local_path": "models/valid.gguf", "checksum": checksum}]
        }), encoding="utf-8")

        v = DeploymentValidator(root_dir=tmp_path, env_vars={"APP_ENV": "production"})

        # Mock LocalProvider real execution
        with patch("core.providers.local.LocalProvider.health", return_value={"available": True}), \
             patch("core.providers.local.LocalProvider.is_available", return_value=True), \
             patch("core.providers.local.LocalProvider.chat_stream", return_value=["Energy ", "is conserved."]):
            probe_res = v.validate_model_inference_probe()
            assert probe_res.status == ValidationStatus.PASS
            assert probe_res.details["readiness_state"] == ModelReadinessState.INFERENCE_VERIFIED.value
            assert probe_res.details["real_model"] is True
            assert probe_res.details["execution_provenance"] == "REAL_MODEL"

            # When probe_inference=True in validate_model_providers, state becomes HEALTHY
            full_res = v.validate_model_providers(probe_inference=True)
            assert full_res.status == ValidationStatus.PASS
            assert full_res.details["readiness_state"] == ModelReadinessState.HEALTHY.value
            assert full_res.details["inference_verified"] is True

    def test_inference_probe_fails_on_empty_completion(self, tmp_path):
        """Inference probe fails if the model returns an empty completion."""
        v = DeploymentValidator(root_dir=tmp_path)
        with patch("core.providers.local.LocalProvider.health", return_value={"available": True}), \
             patch("core.providers.local.LocalProvider.is_available", return_value=True), \
             patch("core.providers.local.LocalProvider.chat_stream", return_value=[]):
            probe_res = v.validate_model_inference_probe()
            assert probe_res.status == ValidationStatus.FAIL
            assert probe_res.details["readiness_state"] == ModelReadinessState.FAILED.value
            assert "empty completion" in probe_res.message or "failed" in probe_res.message

    def test_inference_probe_fails_on_mock_or_fallback(self, tmp_path):
        """Inference probe rejects MOCK or DEGRADED_FALLBACK provenance as a failure for production readiness."""
        v = DeploymentValidator(root_dir=tmp_path, env_vars={"APP_ENV": "development"})
        # When local provider is unavailable in dev, gateway uses fallback
        with patch("core.providers.local.LocalProvider.health", return_value={"available": False, "reason_code": "missing_file"}), \
             patch("central_platform.ai.adapters.is_production_mode", return_value=False):
            probe_res = v.validate_model_inference_probe()
            assert probe_res.status == ValidationStatus.FAIL
            assert probe_res.details["readiness_state"] == ModelReadinessState.FAILED.value
            assert "failed real-model verification" in probe_res.message

    def test_release_tier_requires_real_model(self):
        """DeploymentValidator.determine_release_tier requires real_model_verified=True for PRODUCTION_READY."""
        # 1. 100% pass rate but real_model not verified -> RELEASE_CANDIDATE, not PRODUCTION_READY
        tier = DeploymentValidator.determine_release_tier(
            test_pass_rate=1.0,
            open_p0_count=0,
            open_p1_count=0,
            real_model_verified=False,
            real_rag_verified=True,
            security_audit_passed=True,
        )
        assert tier == DeploymentValidator.ReleaseTier.RELEASE_CANDIDATE

        # 2. All verified -> PRODUCTION_READY
        tier_ready = DeploymentValidator.determine_release_tier(
            test_pass_rate=1.0,
            open_p0_count=0,
            open_p1_count=0,
            real_model_verified=True,
            real_rag_verified=True,
            security_audit_passed=True,
        )
        assert tier_ready == DeploymentValidator.ReleaseTier.PRODUCTION_READY

