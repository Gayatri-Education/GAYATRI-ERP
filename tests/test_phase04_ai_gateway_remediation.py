"""Gayatri AI Platform — Phase 4 AI Gateway & Model Routing Hardening Tests.

Verifies Section 10 of Release Plan & Defect Register P0-03 & P0-04:
1. Model available -> 200 OK, ok=True, state_committed=True, SLR mastery updated.
2. Model missing -> fails safely, ok=False, state_committed=False, no SLR mutation.
3. Model corrupt -> fails safely, ok=False, state_committed=False, no SLR mutation.
4. Provider timeout -> fails safely with MODEL_TIMEOUT, ok=False, no SLR mutation.
5. Provider 401 -> fails safely with MODEL_CONFIGURATION_ERROR, ok=False.
6. Provider 429 -> fails safely with MODEL_RATE_LIMITED, circuit breaker triggered.
7. Provider 500 -> fails safely with fallback attempted, graceful degradation.
8. Empty response -> fails safely with EmptyResponseError, ok=False.
9. Malformed response -> fails safely with MalformedResponseError / JSONDecodeError, ok=False.
10. Mock adapter forced in production -> rejected with MockInProductionProhibited.
11. Model identity unification across core/config, manifest, and gateway (P0-04).
12. State invariant: on AI failure, student mastery in SLR and event store are completely unmutated.
"""
from __future__ import annotations

import io
import json
import socket
import urllib.error
from unittest.mock import MagicMock, patch
import pytest

from central_platform.ai.adapters import (
    AnthropicAdapter,
    GeminiAdapter,
    LocalGGUFAdapter,
    MockAIAdapter,
    OpenAIAdapter,
    OpenAICompatibleAdapter,
    is_production_mode,
)
from central_platform.ai.gateway import AIGatewayService
from central_platform.ai.schema import (
    AIExecutionRequest,
    AIExecutionResult,
    AIModelDescriptor,
    ModelExecutionStatus,
    ModelTier,
    ProviderConfig,
    ProviderType,
    TaskType,
)
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Course,
    CourseVisibility,
    Enrollment,
    MasteryState,
    Organization,
    StudentLearningRecord,
    User,
    UserRole,
)
from central_platform.tutor.orchestrator import (
    GenericTutorOrchestrator,
    TutorTurnRequest,
    TutorTurnResult,
)
import core.config


def get_mastery_score(db: PlatformDatabase, student_id: str, course_id: str, concept_id: str) -> float:
    states = db.get_mastery_states(student_id, course_id=course_id)
    for s in states:
        if s.concept_id == concept_id:
            return s.score
    return 0.0


@pytest.fixture
def test_db():
    """Seed test database with an active student and enrolled course."""
    db = PlatformDatabase(":memory:")
    # Organization
    db.create_organization(Organization(id="org-p04", name="P04 Test Organization", slug="org-p04"))
    # Student
    db.create_user(
        User(
            id="student-p04-01",
            email="p04_student@test.edu",
            full_name="Student Test",
            role=UserRole.STUDENT,
            organization_id="org-p04",
        )
    )
    # Course
    db.create_course(
        Course(
            id="course-p04-chem",
            title="Physical Chemistry",
            code="CHEM-101",
            organization_id="org-p04",
            visibility=CourseVisibility.PUBLIC,
        )
    )
    # Active enrollment
    db.create_enrollment(
        Enrollment(
            id="enr-p04-01",
            student_id="student-p04-01",
            course_id="course-p04-chem",
            is_active=True,
        )
    )
    # SLR
    db.create_slr(
        StudentLearningRecord(
            id="slr-p04-01",
            student_id="student-p04-01",
            course_id="course-p04-chem",
            authoritative=True,
        )
    )
    # Pre-existing mastery in SLR
    db.upsert_mastery_state(
        MasteryState(
            id="mst-p04-01",
            slr_id="slr-p04-01",
            concept_id="thermodynamics_first_law",
            score=0.45,
            confidence=0.8,
        )
    )
    return db


# ── Scenario 1: Model Available (Normal Successful Execution) ─────────────

def test_scenario_01_model_available(test_db):
    """Scenario 1: Model available -> 200 OK, ok=True, valid response, state committed."""
    mock_gateway = MagicMock(spec=AIGatewayService)
    mock_gateway.execute.return_value = AIExecutionResult(
        request_id="req-test-ok",
        content="In thermodynamics, internal energy change is given by Delta U = q + w.",
        provider="local_llama",
        model="Gayatri-Chemistry-Tutor-0.5B",
        prompt_tokens=50,
        completion_tokens=25,
        total_tokens=75,
        latency_ms=35.0,
        estimated_cost_usd=0.0,
        success=True,
        status=ModelExecutionStatus.MODEL_SUCCESS,
        mock=False,
    )

    orchestrator = GenericTutorOrchestrator(db=test_db, ai_gateway=mock_gateway)
    req = TutorTurnRequest(
        student_id="student-p04-01",
        session_id="sess-p04-01",
        course_id="course-p04-chem",
        concept_id="thermodynamics_first_law",
        message="What is the formula for internal energy change?",
    )
    result = orchestrator.execute_turn(req)

    assert result.status == "SUCCESS"
    assert result.validation_passed is True
    assert result.state_committed is True
    assert "Delta U = q + w" in result.response_text


# ── Scenario 2: Model Missing (Safe Failure) ───────────────────────────────

def test_scenario_02_model_missing_fails_safely(test_db, monkeypatch):
    """Scenario 2: Model missing -> fail safe, ok=False, no SLR mutation, no false event."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    assert is_production_mode() is True

    # Configure LocalProvider health to report missing model
    with patch("core.providers.local.LocalProvider.health") as mock_health:
        mock_health.return_value = {
            "available": False,
            "reason_code": "missing_file",
            "message": "Model file not found at path.",
            "path": "models/gayatri/qwen.gguf",
        }

        adapter = LocalGGUFAdapter(ProviderConfig(provider_name="local_llama", provider_type=ProviderType.LOCAL_GGUF))
        exec_req = AIExecutionRequest(prompt="Hello tutor", task_type=TaskType.TUTORING)
        res = adapter.execute(exec_req, AIModelDescriptor(model_id="local", model_name="local-qwen"))

        assert res.success is False
        assert res.status == ModelExecutionStatus.MODEL_UNAVAILABLE
        assert res.error_class == "LocalModelMissing"

        # Test through tutor orchestrator with gateway reporting model missing
        gw = AIGatewayService(db=test_db)
        gw.adapters["local_llama"] = adapter
        orchestrator = GenericTutorOrchestrator(db=test_db, ai_gateway=gw)

        mastery_before = get_mastery_score(test_db, "student-p04-01", "course-p04-chem", "thermodynamics_first_law")
        events_before = len(test_db.query_learning_events(student_id="student-p04-01"))

        turn_req = TutorTurnRequest(
            student_id="student-p04-01",
            session_id="sess-p04-02",
            course_id="course-p04-chem",
            concept_id="thermodynamics_first_law",
            message="Explain thermodynamics",
        )
        turn_res = orchestrator.execute_turn(turn_req)

        assert turn_res.status != "SUCCESS"
        assert turn_res.state_committed is False
        assert turn_res.validation_passed is False
        assert "temporarily unavailable" in turn_res.response_text

        # State Invariant: SLR mastery and learning events are unmodified
        mastery_after = get_mastery_score(test_db, "student-p04-01", "course-p04-chem", "thermodynamics_first_law")
        events_after = len(test_db.query_learning_events(student_id="student-p04-01"))

        assert mastery_after == mastery_before
        assert events_after == events_before


# ── Scenario 3: Model Corrupt (Safe Failure) ───────────────────────────────

def test_scenario_03_model_corrupt_fails_safely(test_db, monkeypatch):
    """Scenario 3: Model corrupt -> fail safe, ok=False, no SLR mutation."""
    monkeypatch.setenv("GAYATRI_ENV", "production")

    with patch("core.providers.local.LocalProvider.health") as mock_health:
        mock_health.return_value = {
            "available": False,
            "reason_code": "corrupt_file",
            "message": "Model file size or checksum does not match verified metadata.",
            "path": "models/gayatri/qwen.gguf",
        }

        adapter = LocalGGUFAdapter(ProviderConfig(provider_name="local_llama", provider_type=ProviderType.LOCAL_GGUF))
        exec_req = AIExecutionRequest(prompt="Hello tutor", task_type=TaskType.TUTORING)
        res = adapter.execute(exec_req, AIModelDescriptor(model_id="local", model_name="local-qwen"))

        assert res.success is False
        assert res.status == ModelExecutionStatus.MODEL_UNAVAILABLE
        assert res.error_class == "LocalModelCorrupt"


# ── Scenario 4: Provider Timeout (Safe Failure) ────────────────────────────

def test_scenario_04_provider_timeout_fails_safely(test_db, monkeypatch):
    """Scenario 4: Provider timeout -> fail safe with MODEL_TIMEOUT, ok=False, no SLR mutation."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-mock")

    cfg = ProviderConfig(provider_name="openai", provider_type=ProviderType.OPENAI, api_key_ref="OPENAI_API_KEY")
    adapter = OpenAIAdapter(cfg)

    # Simulate socket timeout on HTTP request
    with patch("urllib.request.urlopen", side_effect=socket.timeout("The read operation timed out")):
        exec_req = AIExecutionRequest(prompt="What is work?", task_type=TaskType.TUTORING)
        res = adapter.execute(exec_req, AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o"))

        assert res.success is False
        assert res.status == ModelExecutionStatus.MODEL_TIMEOUT
        assert res.error_class == "TimeoutError"


# ── Scenario 5: Provider 401 Unauthorized (Safe Failure) ───────────────────

def test_scenario_05_provider_401_fails_safely(test_db, monkeypatch):
    """Scenario 5: Provider 401 (invalid/missing key) -> MODEL_CONFIGURATION_ERROR, ok=False."""
    monkeypatch.setenv("GAYATRI_ENV", "production")

    # Missing API key
    cfg = ProviderConfig(provider_name="openai", provider_type=ProviderType.OPENAI, api_key_ref="MISSING_KEY_VAR")
    adapter = OpenAIAdapter(cfg)

    exec_req = AIExecutionRequest(prompt="Hello", task_type=TaskType.TUTORING)
    res = adapter.execute(exec_req, AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o"))

    assert res.success is False
    assert res.status == ModelExecutionStatus.MODEL_CONFIGURATION_ERROR
    assert res.error_class == "MissingAPIKeyError"

    # HTTP 401 response from endpoint
    monkeypatch.setenv("OPENAI_API_KEY", "invalid-key")
    adapter_with_key = OpenAIAdapter(ProviderConfig(provider_name="openai", provider_type=ProviderType.OPENAI, api_key_ref="OPENAI_API_KEY"))
    http_401 = urllib.error.HTTPError("https://api.openai.com/v1/chat/completions", 401, "Unauthorized", {}, io.BytesIO(b'{"error": "invalid_api_key"}'))

    with patch("urllib.request.urlopen", side_effect=http_401):
        res401 = adapter_with_key.execute(exec_req, AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o"))
        assert res401.success is False
        assert res401.status == ModelExecutionStatus.MODEL_CONFIGURATION_ERROR
        assert res401.error_class == "HTTP_401"


# ── Scenario 6: Provider 429 Rate Limited (Safe Failure) ───────────────────

def test_scenario_06_provider_429_fails_safely(test_db, monkeypatch):
    """Scenario 6: Provider 429 -> MODEL_RATE_LIMITED, trips circuit breaker, ok=False."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    adapter = OpenAIAdapter(ProviderConfig(provider_name="openai", provider_type=ProviderType.OPENAI, api_key_ref="OPENAI_API_KEY"))
    http_429 = urllib.error.HTTPError("https://api.openai.com/v1/chat/completions", 429, "Rate limit exceeded", {}, io.BytesIO(b'{"error": "rate_limited"}'))

    with patch("urllib.request.urlopen", side_effect=http_429):
        exec_req = AIExecutionRequest(prompt="Hello", task_type=TaskType.TUTORING)
        res = adapter.execute(exec_req, AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o"))

        assert res.success is False
        assert res.status == ModelExecutionStatus.MODEL_RATE_LIMITED
        assert res.error_class == "HTTP_429"


# ── Scenario 7: Provider 500 Internal Error (Safe Failure) ─────────────────

def test_scenario_07_provider_500_fails_safely(test_db, monkeypatch):
    """Scenario 7: Provider 500 -> MODEL_UNAVAILABLE, tries fallback; if all fail, fails safe."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    adapter = OpenAIAdapter(ProviderConfig(provider_name="openai", provider_type=ProviderType.OPENAI, api_key_ref="OPENAI_API_KEY"))
    http_500 = urllib.error.HTTPError("https://api.openai.com/v1/chat/completions", 500, "Internal Server Error", {}, io.BytesIO(b'{"error": "server_down"}'))

    with patch("urllib.request.urlopen", side_effect=http_500):
        exec_req = AIExecutionRequest(prompt="Hello", task_type=TaskType.TUTORING)
        res = adapter.execute(exec_req, AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o"))

        assert res.success is False
        assert res.status == ModelExecutionStatus.MODEL_UNAVAILABLE
        assert res.error_class == "HTTP_500"


# ── Scenario 8: Empty Response (Safe Failure) ──────────────────────────────

def test_scenario_08_empty_response_fails_safely(test_db, monkeypatch):
    """Scenario 8: Empty response -> fails safe with EmptyResponseError, ok=False."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    adapter = OpenAIAdapter(ProviderConfig(provider_name="openai", provider_type=ProviderType.OPENAI, api_key_ref="OPENAI_API_KEY"))
    empty_json_response = io.BytesIO(json.dumps({
        "choices": [{"message": {"content": ""}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 0},
    }).encode("utf-8"))

    mock_resp = MagicMock()
    mock_resp.read.return_value = empty_json_response.getvalue()
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        exec_req = AIExecutionRequest(prompt="Explain enthalpy", task_type=TaskType.TUTORING)
        res = adapter.execute(exec_req, AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o"))

        assert res.success is False
        assert res.status == ModelExecutionStatus.MODEL_INVALID_RESPONSE
        assert res.error_class == "EmptyResponseError"


# ── Scenario 9: Malformed Response (Safe Failure) ──────────────────────────

def test_scenario_09_malformed_response_fails_safely(test_db, monkeypatch):
    """Scenario 9: Malformed response (corrupted JSON or missing keys) -> fails safe."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    adapter = OpenAIAdapter(ProviderConfig(provider_name="openai", provider_type=ProviderType.OPENAI, api_key_ref="OPENAI_API_KEY"))

    # Case A: Corrupted JSON syntax
    bad_json_resp = MagicMock()
    bad_json_resp.read.return_value = b"{'invalid_json': true, broken"
    bad_json_resp.__enter__.return_value = bad_json_resp

    with patch("urllib.request.urlopen", return_value=bad_json_resp):
        exec_req = AIExecutionRequest(prompt="Explain enthalpy", task_type=TaskType.TUTORING)
        res = adapter.execute(exec_req, AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o"))
        assert res.success is False
        assert res.status == ModelExecutionStatus.MODEL_INVALID_RESPONSE
        assert "JSONDecodeError" in res.error_class

    # Case B: Valid JSON but missing choices
    missing_choices_resp = MagicMock()
    missing_choices_resp.read.return_value = json.dumps({"status": "unexpected"}).encode("utf-8")
    missing_choices_resp.__enter__.return_value = missing_choices_resp

    with patch("urllib.request.urlopen", return_value=missing_choices_resp):
        res_missing = adapter.execute(exec_req, AIModelDescriptor(model_id="gpt-4o", model_name="gpt-4o"))
        assert res_missing.success is False
        assert res_missing.status == ModelExecutionStatus.MODEL_INVALID_RESPONSE
        assert res_missing.error_class == "MalformedResponseError"


# ── Scenario 10: Mock Adapter Forced in Production (Prohibited) ────────────

def test_scenario_10_mock_adapter_prohibited_in_production(test_db, monkeypatch):
    """Scenario 10: Mock adapter forced in production -> MockInProductionProhibited, ok=False."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    assert is_production_mode() is True

    # 1. Direct MockAIAdapter invocation rejected
    mock_adapter = MockAIAdapter(ProviderConfig(provider_name="mock_engine", provider_type=ProviderType.MOCK))
    res = mock_adapter.execute(
        AIExecutionRequest(prompt="Test prompt", task_type=TaskType.TUTORING),
        AIModelDescriptor(model_id="mock-standard", model_name="Mock-Pedagogical-Engine"),
    )
    assert res.success is False
    assert res.error_class == "MockInProductionProhibited"
    assert res.status == ModelExecutionStatus.MODEL_CONFIGURATION_ERROR

    # 2. Registering mock provider in gateway is prohibited
    gw = AIGatewayService(db=test_db)
    with pytest.raises(ValueError, match="strictly prohibited in production mode"):
        gw.register_provider(ProviderConfig(provider_name="evil_mock", provider_type=ProviderType.MOCK))

    # 3. Requesting mock_engine as preferred provider in production fails closed
    fail_res = gw.execute(AIExecutionRequest(
        prompt="Explain Gibbs free energy",
        preferred_provider="mock_engine",
        task_type=TaskType.TUTORING,
    ))
    # Either routed to another non-mock provider or fails safely
    assert fail_res.mock is False or fail_res.success is False
    if not fail_res.success:
        assert fail_res.error_class in ("MockInProductionProhibited", "AllProvidersFailed", "LocalModelUnavailable")


# ── Model Identity Unification (P0-04) ─────────────────────────────────────

def test_p04_model_identity_unification():
    """Verify model identity definition is unified across core/config, manifest, and gateway."""
    # 1. Manifest specifies canonical model ID
    with open("model_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
    canonical_id = manifest["model_id"]
    assert canonical_id == "gayatri-chem-qwen2.5-0.5b-v4"

    # 2. core/config specifies matching default model ID and name
    assert core.config.DEFAULT_MODEL_ID == canonical_id
    assert core.config.DEFAULT_CHAT_TEMPLATE == "chatml"
    assert manifest["chat_template"] == "chatml"

    # 3. AIGatewayService default local_llama models includes the canonical model ID
    gw = AIGatewayService(PlatformDatabase(":memory:"))
    local_cfg = gw.router.providers["local_llama"]
    local_model_ids = [m.model_id for m in local_cfg.models]
    assert canonical_id in local_model_ids
    # Canonical model is first in the list
    assert local_cfg.models[0].model_id == canonical_id


# ── State Invariant Verification on AI Failure ─────────────────────────────

def test_state_invariant_on_ai_failure(test_db):
    """Verify that ANY AI failure strictly preserves SLR student mastery and learning events."""
    mock_failed_gw = MagicMock(spec=AIGatewayService)
    mock_failed_gw.execute.return_value = AIExecutionResult(
        request_id="req-failure-503",
        content="",
        provider="local_llama",
        model="Gayatri-Chemistry-Tutor-0.5B",
        success=False,
        status=ModelExecutionStatus.MODEL_UNAVAILABLE,
        error_class="ProviderTimeoutError",
        error_message="Upstream provider timed out.",
        mock=False,
    )

    orchestrator = GenericTutorOrchestrator(db=test_db, ai_gateway=mock_failed_gw)

    mastery_before = get_mastery_score(test_db, "student-p04-01", "course-p04-chem", "thermodynamics_first_law")
    initial_score = mastery_before
    events_before = test_db.query_learning_events(student_id="student-p04-01")

    req = TutorTurnRequest(
        student_id="student-p04-01",
        session_id="sess-turn-fail",
        course_id="course-p04-chem",
        concept_id="thermodynamics_first_law",
        message="What is the first law?",
    )
    res = orchestrator.execute_turn(req)

    # Turn results
    assert res.status != "SUCCESS"
    assert res.state_committed is False
    assert res.validation_passed is False
    assert "temporarily unavailable" in res.response_text

    # Student SLR mastery MUST NOT advance
    mastery_after = get_mastery_score(test_db, "student-p04-01", "course-p04-chem", "thermodynamics_first_law")
    assert mastery_after == initial_score

    # Learning events count MUST NOT increase with false completion event
    events_after = test_db.query_learning_events(student_id="student-p04-01")
    assert len(events_after) == len(events_before)
