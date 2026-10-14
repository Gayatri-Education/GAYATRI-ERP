"""Tests for QA Phase 05: Security Hardening, Path Traversal & Multi-Worker Governance.

Verifies:
- QA-008: Canonical path containment against prefix collision attacks, traversal, and escapes.
- QA-009: Multi-worker rate limiter contract, sliding window backend, and diagnostic telemetry.
- Multi-tenant organization isolation and IDOR access validation.
- Recursive secret redaction across nested configurations.
"""

import os
from pathlib import Path
import pytest

from central_platform.models.schema import User, UserRole
from central_platform.security.auditor import (
    InMemoryRateLimiterBackend,
    RateLimitBackend,
    SecurityAuditor,
    SharedRateLimiterBackend,
)


def test_canonical_path_traversal_prefix_collision(tmp_path: Path):
    """QA-008: Prevent prefix containment collisions and traversal escapes."""
    auditor = SecurityAuditor()
    base_dir = tmp_path / "safe_storage"
    base_dir.mkdir(parents=True, exist_ok=True)
    evil_dir = tmp_path / "safe_storage_evil"
    evil_dir.mkdir(parents=True, exist_ok=True)

    # 1. Normal safe file within base_dir
    safe_target = auditor.sanitize_path(base_dir, "notes/chapter1.pdf")
    assert safe_target is not None
    assert str(base_dir.resolve()) in safe_target

    # 2. Prefix collision exploit: target begins with base string as a prefix, but is outside base directory
    prefix_exploit = auditor.sanitize_path(base_dir, "../safe_storage_evil/payload.pdf")
    assert prefix_exploit is None

    # 3. Standard directory traversal escape
    traversal_escape = auditor.sanitize_path(base_dir, "../../system_file.txt")
    assert traversal_escape is None

    # 4. Null byte injection
    null_byte_path = auditor.sanitize_path(base_dir, "file.pdf\x00.exe")
    assert null_byte_path is None

    # 5. Empty inputs
    assert auditor.sanitize_path("", "file.pdf") is None
    assert auditor.sanitize_path(base_dir, "") is None


def test_in_memory_rate_limiter_sliding_window():
    """QA-009: Test in-memory rate limiter sliding window and detailed telemetry."""
    backend = InMemoryRateLimiterBackend(rate_limit_per_minute=3)
    user_id = "test_user_throttle"

    # First 3 requests should be allowed
    assert backend.is_allowed(user_id) is True
    assert backend.is_allowed(user_id) is True
    assert backend.is_allowed(user_id) is True

    # 4th request must be rejected
    assert backend.is_allowed(user_id) is False

    # Detailed status inspection
    status = backend.get_status(user_id, limit=3, record=False)
    assert status["allowed"] is False
    assert status["current_count"] == 3
    assert status["remaining"] == 0
    assert status["backend"] == "in_memory_sliding_window"
    assert status["guarantee"] == "process_local"


def test_shared_rate_limiter_contract_and_fallback():
    """QA-009: Test shared rate limiter contract delegation and fallback behavior."""
    # When shared store is None, fallback backend is used
    shared_limiter = SharedRateLimiterBackend(rate_limit_per_minute=2)
    assert shared_limiter.is_allowed("worker_user") is True
    assert shared_limiter.is_allowed("worker_user") is True
    assert shared_limiter.is_allowed("worker_user") is False

    status = shared_limiter.get_status("worker_user", limit=2)
    assert status["backend"] == "shared_fallback_in_memory"

    # When custom external store is provided, operations are delegated
    class MockClusterStore:
        def __init__(self):
            self.calls = 0

        def is_allowed(self, key: str, limit: int, window_seconds: float) -> bool:
            self.calls += 1
            return True

        def get_status(self, key: str, limit: int, window_seconds: float, record: bool = False) -> dict:
            return {"allowed": True, "limit": limit, "cluster_id": "redis_node_1"}

    mock_cluster = MockClusterStore()
    cluster_limiter = SharedRateLimiterBackend(rate_limit_per_minute=10, shared_store=mock_cluster)
    assert cluster_limiter.is_allowed("cluster_user") is True
    assert mock_cluster.calls == 1

    status_cluster = cluster_limiter.get_status("cluster_user")
    assert status_cluster["backend"] == "shared_distributed"
    assert status_cluster["guarantee"] == "cluster_wide"


def test_security_auditor_pluggable_backend_and_detailed_probe():
    """Verify SecurityAuditor integrates with pluggable backend and detailed probe."""
    backend = InMemoryRateLimiterBackend(rate_limit_per_minute=2)
    auditor = SecurityAuditor(rate_limit_backend=backend)

    stat1 = auditor.check_rate_limit_detailed("user_probe")
    assert stat1["allowed"] is True
    assert stat1["remaining"] == 1

    stat2 = auditor.check_rate_limit_detailed("user_probe")
    assert stat2["allowed"] is True
    assert stat2["remaining"] == 0

    stat3 = auditor.check_rate_limit_detailed("user_probe")
    assert stat3["allowed"] is False
    assert stat3["remaining"] == 0


def test_multi_tenant_and_idor_boundaries():
    """Verify tenant isolation and student IDOR access boundaries."""
    auditor = SecurityAuditor()

    # Tenant boundary
    assert auditor.verify_tenant_boundary("org_alpha", "org_alpha") is True
    assert auditor.verify_tenant_boundary("org_alpha", "org_beta") is False
    assert auditor.verify_tenant_boundary("org_alpha", "org_beta", is_super_admin=True) is True

    # Student IDOR
    student_a = User(id="student_1", email="s1@test.org", full_name="S1", role=UserRole.STUDENT, organization_id="org_a")
    teacher = User(id="teacher_1", email="t1@test.org", full_name="T1", role=UserRole.TEACHER, organization_id="org_a")

    assert auditor.verify_student_access(student_a, "student_1") is True
    assert auditor.verify_student_access(student_a, "student_2") is False
    assert auditor.verify_student_access(teacher, "student_2") is True


def test_recursive_secret_redaction():
    """Verify recursive redaction for sensitive keys in nested payloads."""
    auditor = SecurityAuditor()
    payload = {
        "user": "student_alpha",
        "api_key": "sk-123456789012345678901234",
        "nested": {
            "token": "secret_session_token",
            "safe_data": "mathematics",
            "list_items": [{"password": "secret_pass"}, "normal_string"],
        },
    }
    redacted = auditor.redact_secrets(payload)
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["token"] == "***REDACTED***"
    assert redacted["nested"]["safe_data"] == "mathematics"
    assert redacted["nested"]["list_items"][0]["password"] == "***REDACTED***"
    assert redacted["nested"]["list_items"][1] == "normal_string"
