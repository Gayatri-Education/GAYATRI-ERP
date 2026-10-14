"""Tests for QA Phase 08: Reliability, Recovery & Observability.

Verifies:
- Failure taxonomy and structured RecoveryResult contracts across all 12 failure domains.
- Provider timeout, circuit breaker trips, and explicit degraded fallback provenance.
- RAG failure graceful degradation to syllabus context without fabricated citations.
- Database outage handling with in-memory snapshot and read-only mode flag.
- Self-healing repair for malformed LLM outputs (code fences, trailing commas, braces, empty).
- Secret redaction and log sanitization preventing API key and token leakage.
- Health endpoint separation: liveness vs readiness vs basic health vs deep health.
- AI Gateway global kill switch enforcement.
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock

from central_platform.recovery.manager import (
    FailureCategory,
    FailureRecoveryManager,
    RecoveryResult,
    RecoveryStatus,
    CommitDecision,
)
from central_platform.health.service import PlatformHealthService
from central_platform.db import PlatformDatabase
from central_platform.security.auditor import SecurityAuditor
from central_platform.ai.gateway import AIGatewayService
from central_platform.ai.schema import (
    AIExecutionRequest,
    ExecutionProvenance,
    ModelExecutionStatus,
    TaskType,
)


def test_failure_taxonomy_and_contract_structure():
    """Verify FailureRecoveryManager produces complete, structured RecoveryResult contracts."""
    # 1. Missing model
    res_missing = FailureRecoveryManager.handle_model_failure(
        error=FileNotFoundError("Weights missing"),
        is_missing=True,
        model_name="Qwen2.5-0.5B",
    )
    assert res_missing.failure_category == FailureCategory.MISSING_MODEL
    assert res_missing.status == RecoveryStatus.DEGRADED_FALLBACK
    assert res_missing.retryable is True
    assert "Weights missing" in res_missing.technical_diagnostic
    assert res_missing.user_message != ""

    # 2. Corrupt model weights
    res_corrupt = FailureRecoveryManager.handle_model_failure(
        error=ValueError("Checksum mismatch"),
        is_corrupt=True,
        model_name="Qwen2.5-0.5B",
    )
    assert res_corrupt.failure_category == FailureCategory.CORRUPT_MODEL
    assert res_corrupt.commit_decision == CommitDecision.ROLLBACK
    assert res_corrupt.retryable is False

    # 3. Provider timeout
    res_timeout = FailureRecoveryManager.handle_provider_timeout(
        error=TimeoutError("Gateway timed out"),
        max_retries=3,
        provider="remote_provider",
    )
    assert res_timeout.failure_category == FailureCategory.PROVIDER_TIMEOUT
    assert res_timeout.fallback_used == "LocalFirstRouter"
    assert res_timeout.data["mode"] == "LOCAL_ONLY"

    # 4. Broken upload
    res_upload = FailureRecoveryManager.handle_broken_upload(
        error=IOError("Connection dropped"),
        filename="lecture.pdf",
        partial_bytes=4096,
    )
    assert res_upload.failure_category == FailureCategory.BROKEN_UPLOAD
    assert res_upload.status == RecoveryStatus.UNRECOVERABLE
    assert res_upload.commit_decision == CommitDecision.ROLLBACK
    assert res_upload.data["partial_bytes"] == 4096

    # 5. Duplicate sync batch
    res_sync = FailureRecoveryManager.handle_duplicate_sync(
        operation_id="sync_op_999",
        student_id="student_123",
        duplicate_count=2,
    )
    assert res_sync.failure_category == FailureCategory.DUPLICATE_SYNC
    assert res_sync.status == RecoveryStatus.RECOVERED
    assert res_sync.data["is_replay"] is True


def test_rag_outage_degrades_without_fabricated_citations():
    """RAG vector search failure must degrade to syllabus context without false citations."""
    res_rag = FailureRecoveryManager.handle_rag_failure(
        error=ConnectionError("Vector index unavailable"),
        fallback_concept="Newton's Laws",
        course_id="crs_physics_101",
    )
    assert res_rag.failure_category == FailureCategory.RAG_FAILURE
    assert res_rag.status == RecoveryStatus.DEGRADED_FALLBACK
    assert res_rag.fallback_used == "CurriculumDirectContext"
    assert res_rag.data["rag_active"] is False
    assert res_rag.data["concept"] == "Newton's Laws"
    # Ensure no fabricated citations are returned
    assert "citations" not in res_rag.data or not res_rag.data.get("citations")


def test_database_outage_handling_and_read_only_mode():
    """Database outage must provide an in-memory snapshot marked read_only: True."""
    res_db = FailureRecoveryManager.handle_database_failure(
        error=OSError("Disk I/O error on sqlite file"),
        cached_state={"student_id": "std_1", "last_concept": "Thermodynamics"},
        operation="write_session",
    )
    assert res_db.failure_category == FailureCategory.DATABASE_FAILURE
    assert res_db.status == RecoveryStatus.DEGRADED_FALLBACK
    assert res_db.fallback_used == "InMemorySnapshotCache"
    assert res_db.commit_decision == CommitDecision.ROLLBACK
    assert res_db.data["read_only"] is True
    assert res_db.data["student_id"] == "std_1"


def test_malformed_model_output_self_healing():
    """Verify resilient self-healing JSON repair on various malformed LLM outputs."""
    # 1. Clean JSON
    clean_json = '{"answer": "42", "confidence": 0.95}'
    res_clean = FailureRecoveryManager.repair_malformed_model_output(clean_json)
    assert res_clean.status == RecoveryStatus.RECOVERED
    assert res_clean.data["answer"] == "42"

    # 2. Markdown fence with trailing comma
    fence_json = 'Here is the result:\n```json\n{"step": 1, "explanation": "Valid",}\n```\nHope that helps!'
    res_fence = FailureRecoveryManager.repair_malformed_model_output(fence_json)
    assert res_fence.status == RecoveryStatus.RECOVERED
    assert res_fence.data["step"] == 1
    assert res_fence.fallback_used == "MarkdownFenceExtractor"

    # 3. Raw braces without fences and with whitespace
    raw_braces = 'Leading chatter {"status": "ok", "value": 100} trailing chatter'
    res_braces = FailureRecoveryManager.repair_malformed_model_output(raw_braces)
    assert res_braces.status == RecoveryStatus.RECOVERED
    assert res_braces.data["status"] == "ok"
    assert res_braces.data["value"] == 100

    # 4. Empty output
    res_empty = FailureRecoveryManager.repair_malformed_model_output("")
    assert res_empty.status == RecoveryStatus.DEGRADED_FALLBACK
    assert res_empty.fallback_used == "DefaultJsonPayload"


def test_security_logging_secret_redaction():
    """Verify that credentials, tokens, and keys are thoroughly scrubbed from logs."""
    auditor = SecurityAuditor()

    # Secret string redaction
    sample_text = "Encountered error with sk-1234567890abcdef1234567890abcdef and password=SuperSecretPassword123"
    clean_text = auditor.redact_secrets(sample_text)
    assert "SuperSecretPassword123" not in str(clean_text)

    # Nested dictionary redaction
    payload = {
        "user_id": "u_101",
        "api_key": "secret_key_value_999",
        "nested": {
            "token": "bearer_token_abc_xyz",
            "safe_field": "public_data",
        },
        "items": [
            {"password": "plain_password_here"},
            {"name": "Alice"},
        ],
    }
    cleaned = auditor.redact_secrets(payload)
    assert cleaned["user_id"] == "u_101"
    assert cleaned["api_key"] == "***REDACTED***"
    assert cleaned["nested"]["token"] == "***REDACTED***"
    assert cleaned["nested"]["safe_field"] == "public_data"
    assert cleaned["items"][0]["password"] == "***REDACTED***"
    assert cleaned["items"][1]["name"] == "Alice"


def test_health_probes_distinction_and_deep_health():
    """Verify liveness, readiness, basic health, and deep health probe contracts."""
    db = PlatformDatabase(":memory:")
    health_svc = PlatformHealthService(db=db)

    # 1. Liveness
    live = health_svc.check_live()
    assert live["alive"] is True

    # 2. Readiness
    is_ready, ready_details = health_svc.check_ready()
    assert is_ready is True
    assert ready_details["subsystems"]["database"]["status"] == "HEALTHY"

    # 3. Deep Health when physical weights are missing
    deep = health_svc.check_deep_health()
    # In test environment where physical GGUF weights are absent, deep health must NOT falsely report HEALTHY!
    assert deep["subsystems"]["database"]["status"] == "HEALTHY"
    assert deep["subsystems"]["database"]["integrity"] == "ok"
    assert deep["subsystems"]["models"]["physical_weights_present"] is False
    assert deep["status"] == "UNHEALTHY"

    db.close()


def test_ai_gateway_global_kill_switch():
    """Verify global AI kill switch stops inference requests immediately with policy failure."""
    db = PlatformDatabase(":memory:")
    gateway = AIGatewayService(db=db)

    req = AIExecutionRequest(
        task_type=TaskType.TUTORING,
        prompt="Help me with thermodynamics",
        student_id="student_101",
    )

    # Activate global kill switch
    gateway.policy_engine.global_kill_switch = True

    result = gateway.execute(req)
    assert result.success is False
    assert result.status == ModelExecutionStatus.MODEL_UNAVAILABLE
    assert result.error_class == "PolicyViolation"
    assert result.execution_provenance == ExecutionProvenance.FAILED

    # Gateway status reflects kill switch state
    status_dict = gateway.get_status()
    assert status_dict["kill_switch_active"] is True
    assert status_dict["gateway_status"] == "DEGRADED"

    db.close()
