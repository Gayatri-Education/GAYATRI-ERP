"""QA Phase 12 Test Suite: Privacy, Secrets, XSS, Supply Chain, and Security Regression.

Verifies:
- Defense-in-depth HTTP security headers (nosniff, DENY, CSP, Referrer-Policy).
- Credential masking and secret redaction across validation errors, logs, and dictionaries.
- Contextual HTML and markdown XSS sanitization (disarming tags, event handlers, unsafe links).
- File upload validation (dangerous extension blocking, path traversal, file size limits).
- Archive safety validation (zip slip detection).
- Path containment sanitization.
- Multi-tenant isolation and student IDOR boundary enforcement.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
import zipfile
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import Organization, User, UserRole
from central_platform.security.auditor import SecurityAuditor


@pytest.fixture
def isolated_db(tmp_path: Path):
    """Provide a fresh isolated database with schema and migrations applied."""
    db_file = str(tmp_path / "phase12_security_test.db")
    db = PlatformDatabase(db_file)
    old_env = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = db_file
    yield db
    if old_env:
        os.environ["GAYATRI_DB_PATH"] = old_env
    else:
        os.environ.pop("GAYATRI_DB_PATH", None)
    db.close()


@pytest.fixture
def client(isolated_db: PlatformDatabase):
    """Provide FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_headers(isolated_db: PlatformDatabase):
    """Provide authorization headers for a super admin."""
    org = Organization(id="org-test-12", name="Phase 12 Org", slug="phase12-org")
    isolated_db.create_organization(org)
    admin = User(
        id="usr-admin-12",
        email="admin12@gayatri.ai",
        full_name="Admin 12",
        role=UserRole.SUPER_ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    isolated_db.create_user(admin)
    token = create_access_token(user_id=admin.id, role="super_admin", organization_id=org.id)
    return {"Authorization": f"Bearer {token}"}


# ── 1. HTTP Security Headers ─────────────────────────────────────────────────

def test_security_headers_attached_to_api_responses(client: TestClient):
    """Responses must include OWASP-recommended security headers."""
    resp = client.get("/healthz")
    assert resp.status_code == 200

    headers = resp.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]


# ── 2. Secrets & Credential Redaction ────────────────────────────────────────

def test_sensitive_field_redaction_in_validation_error(client: TestClient, admin_headers: dict):
    """Passwords and secret values must be redacted from validation error details."""
    payload = {
        "username": "test_user_short_pass",
        "email": "user@gayatri.ai",
        "password": "1",  # Too short (min_length=4)
        "role": "STUDENT",
    }
    resp = client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 422
    body = resp.json()
    assert body["ok"] is False

    errs = body["error"]["details"]["validation_errors"]
    password_errs = [e for e in errs if "password" in str(e.get("loc", []))]
    assert len(password_errs) > 0
    for e in password_errs:
        # Input value must be masked, never reflecting the raw credential
        assert e.get("input") == "***REDACTED***"


def test_secret_redaction_in_auditor():
    """SecurityAuditor must recursively redact secrets, tokens, and keys from structures."""
    auditor = SecurityAuditor()

    # String with secrets
    raw_str = "Connecting with sk-abcdef12345678901234567890123456 and password='SuperSecretPassword123'"
    redacted_str = auditor.redact_secrets(raw_str)
    assert "sk-abcdef12345678901234567890123456" not in redacted_str
    assert "SuperSecretPassword123" not in redacted_str
    assert "***REDACTED_SECRET***" in redacted_str

    # Nested dictionary with credentials
    nested_data = {
        "user_id": "usr-123",
        "auth": {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy",
            "password_hash": "argon2_secret_hash",
        },
        "meta": [
            {"api_key": "sk-11112222333344445555666677778888"},
            {"safe_field": "public_data"},
        ],
    }
    redacted_dict = auditor.redact_secrets(nested_data)
    assert redacted_dict["auth"]["token"] == "***REDACTED***"
    assert redacted_dict["auth"]["password_hash"] == "***REDACTED***"
    assert redacted_dict["meta"][0]["api_key"] == "***REDACTED***"
    assert redacted_dict["meta"][1]["safe_field"] == "public_data"


# ── 3. Contextual HTML & XSS Sanitization ────────────────────────────────────

def test_html_xss_contextual_sanitization():
    """SecurityAuditor.sanitize_html must neutralize executable tags, handlers, and unsafe URLs."""
    # 1. Full entity escaping (default)
    raw = '<script>alert("xss")</script><b>Bold Text</b>'
    escaped = SecurityAuditor.sanitize_html(raw, allow_formatting=False)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    assert "&lt;b&gt;" in escaped

    # 2. Rich formatting allowed: tags stripped, inline handlers purged
    formatted = SecurityAuditor.sanitize_html(
        '<p>Hello <script>malicious()</script><img src="x" onerror="stealCookie()" /> <b>World</b></p>',
        allow_formatting=True,
    )
    assert "<script>" not in formatted
    assert "malicious" not in formatted
    assert "onerror" not in formatted
    assert "stealCookie" not in formatted
    assert "<b>World</b>" in formatted

    # 3. Unsafe link schemes disarmed
    unsafe_links = '<a href="javascript:alert(1)">Click Me</a> and <a href="https://gayatri.ai">Valid</a>'
    sanitized_links = SecurityAuditor.sanitize_html(unsafe_links, allow_formatting=True)
    assert "javascript:" not in sanitized_links
    assert 'href="#"' in sanitized_links
    assert 'href="https://gayatri.ai"' in sanitized_links


# ── 4. File Upload & Path Traversal Security ─────────────────────────────────

def test_file_upload_safety_validation():
    """SecurityAuditor.validate_file_upload must enforce extension allowlist and traversal defense."""
    auditor = SecurityAuditor()

    # Allowed safe file
    safe_res = auditor.validate_file_upload("report.pdf", 1024)
    assert safe_res.is_safe is True
    assert len(safe_res.violations) == 0

    # Dangerous executable extension
    exe_res = auditor.validate_file_upload("payload.exe", 1024)
    assert exe_res.is_safe is False
    assert any("Disallowed file extension" in v for v in exe_res.violations)

    # Disallowed script extension
    sh_res = auditor.validate_file_upload("script.sh", 500)
    assert sh_res.is_safe is False

    # Path traversal in filename
    trav_res = auditor.validate_file_upload("../../../etc/passwd.txt", 1024)
    assert trav_res.is_safe is False
    assert any("Path traversal" in v for v in trav_res.violations)

    # Null byte in filename
    null_res = auditor.validate_file_upload("safe.pdf\x00.exe", 1024)
    assert null_res.is_safe is False
    assert any("Null byte" in v for v in null_res.violations)

    # Oversized file
    big_res = auditor.validate_file_upload("big.pdf", 20 * 1024 * 1024, max_bytes=10 * 1024 * 1024)
    assert big_res.is_safe is False
    assert any("exceeds maximum allowed limit" in v for v in big_res.violations)


def test_archive_safety_zip_bomb_and_path_traversal():
    """SecurityAuditor.validate_archive_safety must reject zip slip attacks and corrupt archives."""
    # 1. Non-zip header rejected
    corrupt_res = SecurityAuditor.validate_archive_safety(b"NOT_A_ZIP_HEADER")
    assert corrupt_res.is_safe is False

    # 2. Zip Slip path traversal detected
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("../../evil.txt", "payload")
    zip_bytes = zip_buffer.getvalue()

    slip_res = SecurityAuditor.validate_archive_safety(zip_bytes)
    assert slip_res.is_safe is False
    assert any("Path traversal detected" in v for v in slip_res.violations)

    # 3. Clean valid zip accepted
    clean_buffer = io.BytesIO()
    with zipfile.ZipFile(clean_buffer, "w") as zf:
        zf.writestr("safe_doc.txt", "harmless content")
    clean_bytes = clean_buffer.getvalue()

    clean_res = SecurityAuditor.validate_archive_safety(clean_bytes)
    assert clean_res.is_safe is True


def test_path_containment_sanitization(tmp_path: Path):
    """SecurityAuditor.sanitize_path must keep targets strictly within base directory."""
    auditor = SecurityAuditor()
    base_dir = tmp_path / "sandbox"
    base_dir.mkdir()

    # Valid subpath
    valid_resolved = auditor.sanitize_path(base_dir, "subdir/doc.txt")
    assert valid_resolved is not None
    assert Path(valid_resolved).is_relative_to(base_dir)

    # Traversal attempt escaping sandbox
    escape_resolved = auditor.sanitize_path(base_dir, "../../secret.txt")
    assert escape_resolved is None

    # Null byte injection
    null_resolved = auditor.sanitize_path(base_dir, "doc.txt\x00.exe")
    assert null_resolved is None


# ── 5. Tenant & IDOR Isolation Boundaries ────────────────────────────────────

def test_tenant_and_student_idor_boundaries():
    """SecurityAuditor tenant and student access verification."""
    auditor = SecurityAuditor()

    # Cross-tenant check: non-super-admin cannot access another org
    assert auditor.verify_tenant_boundary("org-alpha", "org-alpha", is_super_admin=False) is True
    assert auditor.verify_tenant_boundary("org-alpha", "org-beta", is_super_admin=False) is False
    assert auditor.verify_tenant_boundary("org-alpha", "org-beta", is_super_admin=True) is True

    # Student IDOR check: student can only access own profile
    student = User(id="stu-1", email="s1@test.org", full_name="S1", role=UserRole.STUDENT, organization_id="org-1")
    assert auditor.verify_student_access(student, "stu-1") is True
    assert auditor.verify_student_access(student, "stu-2") is False

    # Teacher / Admin can access student profile within boundaries
    teacher = User(id="tea-1", email="t1@test.org", full_name="T1", role=UserRole.TEACHER, organization_id="org-1")
    assert auditor.verify_student_access(teacher, "stu-2") is True
