"""Phase 04 QA Test Suite — AI Execution, Provider Config, Kill Switch, and Error Contracts.

Target Findings:
- ERP-012: AI execution/provider control authorization and isolation
- ERP-013: AI failures must never return HTTP 200 (must return machine-detectable HTTP status)
- ERP-014: Unknown provider types must be rejected strictly (HTTP 422)
- Dynamic database injection and lifecycle in AI Gateway
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import Organization, User, UserRole


@pytest.fixture
def qa_ai_env(tmp_path):
    """Fixture providing isolated database, organizations, users, and app dependencies."""
    db_path = tmp_path / "test_qa_phase04.db"
    db = PlatformDatabase(db_path)

    org_id = f"org-ai-{uuid.uuid4().hex[:6]}"
    db.create_organization(Organization(id=org_id, name="AI Test Academy", slug=f"org-ai-{org_id}"))

    student_a = User(
        id=f"stu-a-{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        email="stu.a@ai.edu",
        full_name="Student AI A",
        role=UserRole.STUDENT,
        is_active=True,
    )
    student_b = User(
        id=f"stu-b-{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        email="stu.b@ai.edu",
        full_name="Student AI B",
        role=UserRole.STUDENT,
        is_active=True,
    )
    admin_user = User(
        id=f"admin-ai-{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        email="admin@ai.edu",
        full_name="Admin AI",
        role=UserRole.ORG_ADMIN,
        is_active=True,
    )
    db.create_user(student_a)
    db.create_user(student_b)
    db.create_user(admin_user)

    app.dependency_overrides[get_db] = lambda: db

    yield {
        "db": db,
        "org_id": org_id,
        "student_a": student_a,
        "student_b": student_b,
        "admin_user": admin_user,
    }

    app.dependency_overrides.pop(get_db, None)


def test_ai_execution_failure_under_killswitch_never_returns_http_200(qa_ai_env):
    """ERP-013: When kill switch is active, execution failure must return non-200 (HTTP 503)."""
    client = TestClient(app)

    # 1. Activate kill switch
    token_admin = create_access_token(
        user_id=qa_ai_env["admin_user"].id,
        role="org_admin",
        organization_id=qa_ai_env["org_id"],
    )
    resp_ks = client.post(
        "/api/v1/ai/killswitch",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={"enabled": True, "reason": "Emergency security testing"},
    )
    assert resp_ks.status_code == 200

    try:
        # 2. Attempt AI execution while kill switch is active
        resp_exec = client.post(
            "/api/v1/ai/execute",
            json={"prompt": "Explain photosynthesis", "task_type": "tutoring"},
        )
        # Invariant ERP-013: HTTP 200 must NEVER be returned for execution failure or policy block
        assert resp_exec.status_code != 200, "Execution failure must NOT return HTTP 200 OK"
        assert resp_exec.status_code in (503, 502, 403), f"Expected 503 Service Unavailable, got {resp_exec.status_code}"
        body = resp_exec.json()
        assert body["ok"] is False
        assert body["error"] is not None
    finally:
        # Restore kill switch to disabled
        client.post(
            "/api/v1/ai/killswitch",
            headers={"Authorization": f"Bearer {token_admin}"},
            json={"enabled": False},
        )


def test_ai_execution_all_providers_failed_returns_non_200(qa_ai_env):
    """ERP-013: When all providers are disabled, execution failure must return non-200 (HTTP 503)."""
    client = TestClient(app)

    # Request execution with a non-existent or impossible preferred provider to trigger provider failure
    resp_exec = client.post(
        "/api/v1/ai/execute",
        json={"prompt": "Explain thermodynamics", "preferred_provider": "non_existent_provider_xyz"},
    )
    # If the provider is not available and all providers fail, it must not return HTTP 200
    if not resp_exec.json().get("ok"):
        assert resp_exec.status_code != 200, "Failed AI execution must not return HTTP 200"
        assert resp_exec.status_code in (503, 502, 504, 422)


def test_ai_execution_student_isolation(qa_ai_env):
    """ERP-012: Student A cannot execute generation targeting Student B's account (HTTP 403)."""
    client = TestClient(app)

    token_student_a = create_access_token(
        user_id=qa_ai_env["student_a"].id,
        role="student",
        organization_id=qa_ai_env["org_id"],
    )

    # Student A specifies student_id of Student B
    resp = client.post(
        "/api/v1/ai/execute",
        headers={"Authorization": f"Bearer {token_student_a}"},
        json={
            "prompt": "Help with homework",
            "student_id": qa_ai_env["student_b"].id,  # Other student!
        },
    )
    assert resp.status_code == 403, f"Expected 403 Forbidden for cross-student execution, got {resp.status_code}: {resp.text}"


def test_ai_provider_invalid_type_rejected_with_422(qa_ai_env):
    """ERP-014: Creating provider with invalid type must return HTTP 422."""
    client = TestClient(app)
    token_admin = create_access_token(
        user_id=qa_ai_env["admin_user"].id,
        role="org_admin",
        organization_id=qa_ai_env["org_id"],
    )

    resp = client.post(
        "/api/v1/ai/providers",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={
            "provider_name": "invalid_provider",
            "provider_type": "quantum_neural_net",  # Invalid!
        },
    )
    assert resp.status_code == 422, f"Expected 422 Unprocessable Entity, got {resp.status_code}: {resp.text}"


def test_ai_gateway_dynamic_database_override(qa_ai_env, tmp_path):
    """Verify that AIGatewayService dynamically adopts the injected database."""
    from central_platform.api.routes.ai import get_ai_gateway_service

    # First database
    gw1 = get_ai_gateway_service(db=qa_ai_env["db"])
    assert gw1.db is qa_ai_env["db"]

    # Second database
    db2 = PlatformDatabase(tmp_path / "second_db.db")
    gw2 = get_ai_gateway_service(db=db2)
    assert gw2.db is db2
    assert gw2 is not gw1


def test_ai_execution_production_mode_requires_authentication(qa_ai_env, monkeypatch):
    """ERP-012: In production mode, unauthenticated AI execution must return HTTP 401."""
    monkeypatch.setenv("GAYATRI_ENV", "production")
    client = TestClient(app)

    resp = client.post(
        "/api/v1/ai/execute",
        json={"prompt": "Explain stoichiometry", "task_type": "tutoring"},
    )
    assert resp.status_code == 401, f"Expected 401 Unauthorized in production mode, got {resp.status_code}"


def test_ai_execution_timeout_maps_to_504(qa_ai_env, monkeypatch):
    """ERP-013: AI gateway timeout must map to HTTP 504 Gateway Timeout."""
    from unittest.mock import patch
    from central_platform.ai.schema import AIExecutionResult, ModelExecutionStatus

    client = TestClient(app)

    timeout_result = AIExecutionResult(
        request_id="req-timeout-test",
        content="",
        provider="openai",
        model="gpt-4o",
        success=False,
        status=ModelExecutionStatus.MODEL_TIMEOUT,
        error_class="ProviderTimeout",
        error_message="Gateway connection to provider timed out after 15.0s",
    )

    with patch("central_platform.ai.gateway.AIGatewayService.execute", return_value=timeout_result):
        resp = client.post(
            "/api/v1/ai/execute",
            json={"prompt": "Explain chemical bonding"},
        )
        assert resp.status_code == 504, f"Expected HTTP 504 for timeout, got {resp.status_code}"
        assert resp.json()["ok"] is False
        assert "timed out" in resp.json()["error"]["message"]


def test_ai_execution_rate_limit_maps_to_429(qa_ai_env, monkeypatch):
    """ERP-013: AI rate limit or quota exceeded must map to HTTP 429 Too Many Requests."""
    from unittest.mock import patch
    from central_platform.ai.schema import AIExecutionResult, ModelExecutionStatus

    client = TestClient(app)

    rate_limit_result = AIExecutionResult(
        request_id="req-ratelimit-test",
        content="",
        provider="anthropic",
        model="claude-3-5-sonnet",
        success=False,
        status=ModelExecutionStatus.MODEL_RATE_LIMITED,
        error_class="RateLimitExceeded",
        error_message="Provider rate limit exceeded. Retry after 60s.",
    )

    with patch("central_platform.ai.gateway.AIGatewayService.execute", return_value=rate_limit_result):
        resp = client.post(
            "/api/v1/ai/execute",
            json={"prompt": "Explain thermodynamics"},
        )
        assert resp.status_code == 429, f"Expected HTTP 429 for rate limit, got {resp.status_code}"
        assert resp.json()["ok"] is False
        assert "rate limit" in resp.json()["error"]["message"].lower()

