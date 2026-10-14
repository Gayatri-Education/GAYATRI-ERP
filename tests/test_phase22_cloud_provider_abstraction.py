"""Tests for Phase 22 — Cloud Provider Abstraction.

Verifies normalized adapter execution for:
- BaseAIProviderAdapter interface & get_api_key handling
- OpenAICompatibleAdapter & OpenAIAdapter
- AnthropicAdapter
- GeminiAdapter
- OpenRouterAdapter
- MockAIAdapter & LocalGGUFAdapter fallback behaviors
"""
import pytest
from unittest.mock import patch, MagicMock
import io
import json

from central_platform.ai.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    AIModelDescriptor,
    ProviderConfig,
    ProviderType,
    TaskType,
)
from central_platform.ai.adapters import (
    BaseAIProviderAdapter,
    MockAIAdapter,
    LocalGGUFAdapter,
    OpenAICompatibleAdapter,
    OpenAIAdapter,
    AnthropicAdapter,
    GeminiAdapter,
    OpenRouterAdapter,
    generate_dynamic_pedagogical_content,
)


@pytest.fixture
def sample_model_descriptor():
    return AIModelDescriptor(
        model_id="test-model",
        model_name="gpt-4o",
        cost_per_1k_input_usd=0.005,
        cost_per_1k_output_usd=0.015,
        latency_p50_ms=250.0,
        supports_tools=True,
        supports_json=True,
        capabilities=["socratic_tutoring", "reasoning"],
    )


@pytest.fixture
def sample_provider_config():
    return ProviderConfig(
        provider_name="test_openai",
        provider_type=ProviderType.OPENAI,
        api_key_ref="TEST_OPENAI_KEY",
        base_url="https://api.openai.com/v1",
        timeout_seconds=30.0,
    )


@pytest.fixture
def sample_request():
    return AIExecutionRequest(
        request_id="req-test-22",
        prompt="Explain Hess's Law in chemical thermodynamics.",
        system_prompt="You are a Socratic tutor.",
        task_type=TaskType.TUTORING,
        max_tokens=256,
        temperature=0.7,
    )


def test_base_provider_adapter_key_resolution(sample_provider_config, monkeypatch):
    adapter = BaseAIProviderAdapter(sample_provider_config)
    assert adapter.get_api_key() == ""

    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-fake-secret-key")
    assert adapter.get_api_key() == "sk-fake-secret-key"


def test_base_provider_adapter_not_implemented(sample_provider_config, sample_request, sample_model_descriptor):
    adapter = BaseAIProviderAdapter(sample_provider_config)
    with pytest.raises(NotImplementedError):
        adapter.execute(sample_request, sample_model_descriptor)


def test_mock_adapter_execution(sample_provider_config, sample_request, sample_model_descriptor):
    adapter = MockAIAdapter(sample_provider_config)
    res = adapter.execute(sample_request, sample_model_descriptor)

    assert isinstance(res, AIExecutionResult)
    assert res.success is True
    assert res.provider == "test_openai"
    assert res.model == "gpt-4o"
    assert len(res.content) > 0
    assert res.prompt_tokens > 0
    assert res.completion_tokens > 0
    assert res.total_tokens == res.prompt_tokens + res.completion_tokens
    assert res.estimated_cost_usd >= 0.0


def test_openai_compatible_adapter_error_when_no_api_key(sample_provider_config, sample_request, sample_model_descriptor, monkeypatch):
    monkeypatch.delenv("TEST_OPENAI_KEY", raising=False)
    adapter = OpenAICompatibleAdapter(sample_provider_config)
    res = adapter.execute(sample_request, sample_model_descriptor)

    assert res.success is False
    assert res.provider == "test_openai"
    assert res.content == ""
    assert res.mock is False
    assert res.status == "MODEL_CONFIGURATION_ERROR" or res.error_class == "MissingAPIKeyError"



def test_openai_compatible_adapter_mocked_http_success(sample_provider_config, sample_request, sample_model_descriptor, monkeypatch):
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-fake-key")

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "Hess's Law states that total enthalpy change is state-independent."}}],
        "usage": {"prompt_tokens": 15, "completion_tokens": 12, "total_tokens": 27}
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        adapter = OpenAIAdapter(sample_provider_config)
        res = adapter.execute(sample_request, sample_model_descriptor)

    assert res.success is True
    assert "Hess's Law states" in res.content
    assert res.prompt_tokens == 15
    assert res.completion_tokens == 12
    assert res.total_tokens == 27


def test_anthropic_adapter_mocked_http_success(sample_request, sample_model_descriptor, monkeypatch):
    config = ProviderConfig(
        provider_name="test_anthropic",
        provider_type=ProviderType.ANTHROPIC,
        api_key_ref="TEST_ANTHROPIC_KEY",
    )
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "sk-ant-key")

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "content": [{"text": "Claude explanation of Hess's Law."}],
        "usage": {"input_tokens": 20, "output_tokens": 15}
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        adapter = AnthropicAdapter(config)
        res = adapter.execute(sample_request, sample_model_descriptor)

    assert res.success is True
    assert res.content == "Claude explanation of Hess's Law."
    assert res.prompt_tokens == 20
    assert res.completion_tokens == 15


def test_gemini_adapter_mocked_http_success(sample_request, sample_model_descriptor, monkeypatch):
    config = ProviderConfig(
        provider_name="test_gemini",
        provider_type=ProviderType.GEMINI,
        api_key_ref="TEST_GEMINI_KEY",
    )
    monkeypatch.setenv("TEST_GEMINI_KEY", "gem-key")

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "candidates": [{
            "content": {
                "parts": [{"text": "Gemini explanation of Hess's Law."}]
            }
        }]
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        adapter = GeminiAdapter(config)
        res = adapter.execute(sample_request, sample_model_descriptor)

    assert res.success is True
    assert res.content == "Gemini explanation of Hess's Law."


def test_openrouter_adapter_subclass(sample_provider_config, sample_request, sample_model_descriptor, monkeypatch):
    config = ProviderConfig(
        provider_name="test_openrouter",
        provider_type=ProviderType.OPENROUTER,
        api_key_ref="TEST_OPENROUTER_KEY",
    )
    monkeypatch.setenv("TEST_OPENROUTER_KEY", "or-key")

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "OpenRouter response text"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
    }).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        adapter = OpenRouterAdapter(config)
        res = adapter.execute(sample_request, sample_model_descriptor)

    assert res.success is True
    assert res.content == "OpenRouter response text"


def test_dynamic_pedagogical_content_variations():
    req1 = AIExecutionRequest(prompt="Grading problem", task_type=TaskType.ASSESSMENT_GRADING)
    c1 = generate_dynamic_pedagogical_content(req1)
    grade_data = json.loads(c1)
    assert grade_data["status"] == "EVALUATION_UNAVAILABLE"
    assert grade_data["score"] is None
    assert grade_data["correct"] is None
    assert grade_data["authoritative"] is False

    req2 = AIExecutionRequest(prompt="Show copilot overview", task_type=TaskType.COPILOT_SUMMARY)
    c2 = generate_dynamic_pedagogical_content(req2)
    assert "Diagnostic Summary" in c2

    req3 = AIExecutionRequest(prompt="I don't understand, confused", task_type=TaskType.TUTORING)
    c3 = generate_dynamic_pedagogical_content(req3)
    assert "balance scale" in c3
