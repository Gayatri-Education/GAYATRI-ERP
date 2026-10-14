"""Centralized Security Auditor and Threat Defense Engine for Gayatri AI Platform (Phase 22).

CRITICAL ARCHITECTURAL PRINCIPLE (GQA-013):
Pattern matching in SecurityAuditor provides defensive heuristics and defense-in-depth filtering,
NOT absolute mathematical certification of immunity against all dynamic adversarial variants.
Primary security guarantees must be enforced by structural boundaries across the platform:
- Authentication & JWT Revocation: cryptographically verified tokens with durable JTI tracking.
- Authorization & Multi-Tenancy: object-level isolation enforced at the database and service layer.
- SQL Injection: 100% parameterized queries via SQLite / PostgreSQL parameter binding.
- Path Traversal: canonical path resolution (Path.resolve().relative_to()) and symlink containment.
- File Uploads: magic byte verification, strict extension allowlists, and parser limits.
- XSS: contextual HTML entity escaping and strict sanitization before DOM rendering.
- RAG Injection: wrapping retrieved content as untrusted read-only data blocks.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union

from central_platform.auth.tokens import decode_and_verify_token, is_token_revoked
from central_platform.models.schema import User, UserRole


class RateLimitBackend:
    """Abstract contract for sliding window rate limiting across deployment tiers (QA-009)."""

    def is_allowed(self, key: str, limit: Optional[int] = None, window_seconds: float = 60.0) -> bool:
        raise NotImplementedError

    def get_status(self, key: str, limit: Optional[int] = None, window_seconds: float = 60.0, record: bool = False) -> Dict[str, Any]:
        raise NotImplementedError


class InMemoryRateLimiterBackend(RateLimitBackend):
    """In-memory sliding window rate limiter for single-process / desktop environments.

    Concurrency Guarantee:
        Guarantees strict sliding-window enforcement within the local Python process.
        Thread-safe using internal RLock. For multi-worker cluster deployments, use
        SharedRateLimiterBackend or an external distributed cache backend.
    """

    def __init__(self, rate_limit_per_minute: int = 60):
        self.default_limit = rate_limit_per_minute
        self._timestamps: Dict[str, List[float]] = {}
        self._lock = threading.RLock()

    def is_allowed(self, key: str, limit: Optional[int] = None, window_seconds: float = 60.0) -> bool:
        status = self.get_status(key, limit=limit, window_seconds=window_seconds, record=True)
        return status["allowed"]

    def get_status(self, key: str, limit: Optional[int] = None, window_seconds: float = 60.0, record: bool = False) -> Dict[str, Any]:
        lim = limit or self.default_limit
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._timestamps.setdefault(key, [])
            valid_timestamps = [t for t in timestamps if t > cutoff]
            self._timestamps[key] = valid_timestamps

            allowed = len(valid_timestamps) < lim
            if allowed and record:
                valid_timestamps.append(now)

            remaining = max(0, lim - len(valid_timestamps))
            reset_seconds = max(0.0, valid_timestamps[0] + window_seconds - now) if valid_timestamps else 0.0

            return {
                "allowed": allowed,
                "current_count": len(valid_timestamps),
                "limit": lim,
                "remaining": remaining,
                "reset_seconds": round(reset_seconds, 2),
                "backend": "in_memory_sliding_window",
                "guarantee": "process_local",
            }


class DatabaseRateLimiterStore:
    """Multi-process / worker-safe sliding window rate limiter backed by PlatformDatabase (GQA-006)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_db(self):
        from central_platform.db import PlatformDatabase
        path = self.db_path or os.environ.get("GAYATRI_DB_PATH")
        return PlatformDatabase(path)

    def is_allowed(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        stat = self.get_status(key, limit=limit, window_seconds=window_seconds, record=True)
        return stat["allowed"]

    def get_status(
        self,
        key: str,
        limit: int,
        window_seconds: float = 60.0,
        record: bool = False,
    ) -> Dict[str, Any]:
        db = self._get_db()
        return db.check_rate_limit_atomic(key, limit, window_seconds, record=record)

    def check_health(self) -> bool:
        try:
            db = self._get_db()
            return db.check_rate_limit_atomic("__health__", limit=1000, record=False)["allowed"]
        except Exception:
            return False


class SharedRateLimiterBackend(RateLimitBackend):
    """Shared/Distributed rate limiter contract for multi-worker production deployments.

    Concurrency Guarantee:
        Supports multi-worker processes (e.g. Gunicorn / Uvicorn worker pools).
        When an external store (such as DatabaseRateLimiterStore, Redis, or platform DB) is configured,
        rate limits are coordinated globally across all workers.
        When cluster_required is True (or GAYATRI_RATE_LIMITER_CLUSTER_REQUIRED is set),
        missing shared store causes readiness failure and fails closed rather than silently
        falling back to local memory (GQA-006).
    """

    def __init__(
        self,
        rate_limit_per_minute: int = 60,
        shared_store: Optional[Any] = None,
        cluster_required: Optional[bool] = None,
    ):
        self.default_limit = rate_limit_per_minute
        self.shared_store = shared_store
        if cluster_required is None:
            cluster_required = os.environ.get("GAYATRI_RATE_LIMITER_CLUSTER_REQUIRED", "0").lower() in ("1", "true", "yes")
        self.cluster_required = cluster_required
        self._fallback = InMemoryRateLimiterBackend(rate_limit_per_minute=rate_limit_per_minute)

    def check_readiness(self) -> tuple[bool, str]:
        """Verify shared rate limiter backend readiness for cluster operation."""
        if self.cluster_required:
            if self.shared_store is None:
                return False, "Shared rate limiter backend required in cluster mode, but no shared store is configured"
            if hasattr(self.shared_store, "check_health"):
                try:
                    ok = self.shared_store.check_health()
                    if not ok:
                        return False, "Shared rate limiter store health check failed"
                except Exception as exc:
                    return False, f"Shared rate limiter store health error: {exc}"
        return True, "Ready"

    def is_allowed(self, key: str, limit: Optional[int] = None, window_seconds: float = 60.0) -> bool:
        if self.shared_store is not None and hasattr(self.shared_store, "is_allowed"):
            return self.shared_store.is_allowed(key, limit or self.default_limit, window_seconds)
        if self.cluster_required:
            raise RuntimeError(
                "Shared rate limiter backend required in cluster mode: quiet fallback to local memory is prohibited"
            )
        return self._fallback.is_allowed(key, limit, window_seconds)

    def get_status(self, key: str, limit: Optional[int] = None, window_seconds: float = 60.0, record: bool = False) -> Dict[str, Any]:
        if self.shared_store is not None and hasattr(self.shared_store, "get_status"):
            res = self.shared_store.get_status(key, limit or self.default_limit, window_seconds, record=record)
            res["backend"] = "shared_distributed"
            res["guarantee"] = "cluster_wide"
            return res
        if self.cluster_required:
            raise RuntimeError(
                "Shared rate limiter backend required in cluster mode: quiet fallback to local memory is prohibited"
            )
        res = self._fallback.get_status(key, limit, window_seconds, record=record)
        res["backend"] = "shared_fallback_in_memory"
        res["guarantee"] = "process_local_fallback"
        return res



@dataclass
class SecurityAuditResult:
    is_safe: bool
    violations: List[str] = field(default_factory=list)
    sanitized_input: Optional[str] = None
    threat_category: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SecurityAuditor:
    """Enterprise security auditor enforcing defense-in-depth across platform boundaries."""

    # 1. Prompt Injection & Jailbreak Patterns
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        re.compile(r"reveal\s+(the\s+)?(secret|system|hidden)\s+(prompt|key|token|instructions)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(DAN|unfiltered|jailbroken|chaos)", re.IGNORECASE),
        re.compile(r"dump\s+database", re.IGNORECASE),
        re.compile(r"disregard\s+(the\s+)?rules", re.IGNORECASE),
        re.compile(r"print\s+your\s+initial\s+system\s+prompt", re.IGNORECASE),
    ]

    # 2. Hazardous Chemistry & Weapon Precursor Patterns
    HAZARDOUS_CHEMISTRY_PATTERNS = [
        re.compile(r"\b(sarin|vx|tabun|soman|novichok|mustard\s+gas)\b", re.IGNORECASE),
        re.compile(r"\b(synthesize|manufacture|cook|purify)\s+(tnt|rdx|c4|nitroglycerin|ricin|anthrax)\b", re.IGNORECASE),
        re.compile(r"\b(chemical\s+weapon|improvised\s+explosive|pipe\s+bomb)\b", re.IGNORECASE),
        re.compile(r"\b(methamphetamine|heroin|fentanyl)\s+(synthesis|recipe|precursors)\b", re.IGNORECASE),
    ]

    # 3. Secret & API Key Leakage Patterns
    SECRET_PATTERNS = [
        (re.compile(r"AIza[0-9A-Za-z-_]{20,40}"), "GOOGLE_API_KEY"),
        (re.compile(r"sk-[a-zA-Z0-9]{20,48}"), "OPENAI_API_KEY"),
        (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "GITHUB_TOKEN"),
        (re.compile(r"(password|passwd|secret|token)\s*=\s*(?:['\"][^'\"]+['\"]|[^\s,;]+)", re.IGNORECASE), "CREDENTIAL_ASSIGNMENT"),
        (re.compile(r"Bearer\s+[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*", re.IGNORECASE), "BEARER_TOKEN"),
    ]

    # 4. SQL Injection Heuristics
    SQL_INJECTION_PATTERNS = [
        re.compile(r"(\%27)|(\')|(\-\-)|(\%23)|(#)", re.IGNORECASE),
        re.compile(r"\b(UNION\s+ALL\s+SELECT|UNION\s+SELECT)\b", re.IGNORECASE),
        re.compile(r"\b(DROP\s+TABLE|ALTER\s+TABLE|DELETE\s+FROM)\b", re.IGNORECASE),
        re.compile(r"(\'\s*OR\s*\'1\'\s*=\s*\'1)|(1\s*=\s*1)", re.IGNORECASE),
    ]

    # 5. XSS Script Patterns
    XSS_PATTERNS = [
        re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"onerror\s*=\s*['\"].*?['\"]", re.IGNORECASE),
        re.compile(r"onload\s*=\s*['\"].*?['\"]", re.IGNORECASE),
    ]

    # 6. File Upload Safety Constants
    ALLOWED_FILE_EXTENSIONS: Set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".json", ".md", ".csv"}
    DANGEROUS_EXTENSIONS: Set[str] = {".exe", ".bat", ".sh", ".cmd", ".vbs", ".js", ".php", ".py", ".dll", ".so"}

    def __init__(
        self,
        rate_limit_per_minute: int = 60,
        rate_limit_backend: Optional[RateLimitBackend] = None,
    ):
        if rate_limit_backend is not None and hasattr(rate_limit_backend, "default_limit") and rate_limit_per_minute == 60:
            rate_limit_per_minute = rate_limit_backend.default_limit
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_backend = rate_limit_backend or InMemoryRateLimiterBackend(
            rate_limit_per_minute=rate_limit_per_minute
        )

    # ── Rate Limiting (QA-009 / GQA-006) ──────────────────────────────────────

    DEFAULT_POLICIES = {
        "anonymous": 20,       # 20 req/min for anonymous client IP
        "user": 60,            # 60 req/min for standard authenticated user
        "auth_sensitive": 10,  # 10 req/min for login / password reset / auth token issuance
        "bulk_read": 120,      # 120 req/min for telemetry / high throughput queries
    }

    def check_rate_limit(self, user_id: str, max_requests: Optional[int] = None) -> bool:
        """Sliding window rate limiter enforcing request throttling."""
        return self.rate_limit_backend.is_allowed(user_id, limit=max_requests or self.rate_limit_per_minute)

    def check_rate_limit_detailed(
        self, user_id: str, max_requests: Optional[int] = None
    ) -> Dict[str, Any]:
        """Sliding window rate limit status with diagnostic telemetry."""
        return self.rate_limit_backend.get_status(
            user_id, limit=max_requests or self.rate_limit_per_minute, record=True
        )

    def check_rate_limit_for_identity(
        self,
        identity: str,
        category: str = "user",
        max_requests: Optional[int] = None,
        window_seconds: float = 60.0,
    ) -> bool:
        """Enforce differentiated rate limit policy based on actor category and endpoint class."""
        limit = max_requests or self.DEFAULT_POLICIES.get(category, self.rate_limit_per_minute)
        return self.rate_limit_backend.is_allowed(f"{category}:{identity}", limit=limit, window_seconds=window_seconds)

    def check_rate_limit_detailed_for_identity(
        self,
        identity: str,
        category: str = "user",
        max_requests: Optional[int] = None,
        window_seconds: float = 60.0,
    ) -> Dict[str, Any]:
        """Detailed status query with policy-scoped keys."""
        limit = max_requests or self.DEFAULT_POLICIES.get(category, self.rate_limit_per_minute)
        res = self.rate_limit_backend.get_status(
            f"{category}:{identity}", limit=limit, window_seconds=window_seconds, record=True
        )
        res["policy_category"] = category
        return res


    # ── Prompt Injection & Safety ─────────────────────────────────────────────

    def sanitize_prompt(self, prompt: str) -> SecurityAuditResult:
        """Audit prompts for prompt injections, system prompt extraction, and unsafe chemistry synthesis."""
        violations: List[str] = []

        # Check prompt injection
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(prompt):
                violations.append(f"Prompt injection pattern detected: {pattern.pattern}")

        # Check hazardous chemistry synthesis
        for pattern in self.HAZARDOUS_CHEMISTRY_PATTERNS:
            if pattern.search(prompt):
                violations.append("Hazardous materials or prohibited chemical synthesis request blocked")

        is_safe = len(violations) == 0
        sanitized = prompt
        for pattern in self.XSS_PATTERNS:
            sanitized = pattern.sub("", sanitized)

        return SecurityAuditResult(
            is_safe=is_safe,
            violations=violations,
            sanitized_input=sanitized if is_safe else None,
            threat_category="PROMPT_INJECTION" if not is_safe else None,
        )

    # ── Contextual HTML & Markdown XSS Sanitization (GQA-013) ─────────────────

    @classmethod
    def is_safe_url(cls, url: str) -> bool:
        """Verify that a URL scheme is safe for rendering (http, https, mailto, tel, relative)."""
        if not url:
            return False
        clean_url = url.strip().lower()
        for dangerous_prefix in ("javascript:", "data:", "vbscript:", "file:", "about:"):
            if clean_url.startswith(dangerous_prefix):
                return False
        if clean_url.startswith(("/", "./", "../", "#", "?")):
            return True
        if "://" in clean_url:
            scheme = clean_url.split("://", 1)[0]
            return scheme in ("http", "https")
        if clean_url.startswith(("mailto:", "tel:")):
            return True
        return ":" not in clean_url

    @classmethod
    def sanitize_html(cls, text: str, allow_formatting: bool = False) -> str:
        """Contextual HTML/Markdown sanitizer with strict tag, event handler, and URL filtering.

        If allow_formatting is False: escapes all characters to HTML entities via html.escape().
        If allow_formatting is True: strips active executable tags (<script>, <iframe>, <style>,
        <object>, <embed>, <svg>, <form>, <input>, <base>, <meta>), removes inline on* event
        handlers, and neutralizes unsafe link schemes.
        """
        import html
        if not text:
            return ""

        if not allow_formatting:
            return html.escape(text)

        # 1. Strip active executable tags completely
        clean = re.sub(
            r"(?i)<(script|style|iframe|object|embed|svg|math|form|input|button|base|meta|link)\b[^>]*>.*?</\1>",
            "",
            text,
            flags=re.DOTALL,
        )
        clean = re.sub(
            r"(?i)<(script|style|iframe|object|embed|svg|math|form|input|button|base|meta|link)\b[^>]*>",
            "",
            clean,
        )

        # 2. Strip all inline on* event handlers
        clean = re.sub(r"(?i)\s+on[a-z]+\s*=\s*(?:'[^']*'|\"[^\"]*\"|[^\s>]+)", "", clean)

        # 3. Disallow dangerous URL schemes in href and src attributes
        def _sanitize_link_scheme(match: re.Match) -> str:
            attr = match.group(1)
            quote = match.group(2)
            url = match.group(3)
            if not cls.is_safe_url(url):
                return f'{attr}={quote}#{quote}'
            return match.group(0)

        clean = re.sub(
            r'(?i)\b(href|src)\s*=\s*(["\'])(.*?)\2',
            _sanitize_link_scheme,
            clean,
        )

        return clean

    # ── RAG Context Sanitization ──────────────────────────────────────────────

    def sanitize_rag_chunk(self, content: str) -> SecurityAuditResult:
        """Sanitize retrieved RAG documents to prevent indirect context hijacking."""
        violations: List[str] = []
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(content):
                violations.append("Indirect RAG prompt injection detected in retrieved text")

        is_safe = len(violations) == 0
        # Neutralize potential command sequences
        clean_content = content.replace("System:", "Document:").replace("Assistant:", "Document:")
        return SecurityAuditResult(
            is_safe=is_safe,
            violations=violations,
            sanitized_input=clean_content if is_safe else None,
            threat_category="RAG_INJECTION" if not is_safe else None,
        )

    # ── File Upload & Path Traversal ──────────────────────────────────────────

    @classmethod
    def validate_archive_safety(
        cls,
        content_bytes: bytes,
        max_extracted_bytes: int = 25 * 1024 * 1024,
        max_ratio: float = 100.0,
    ) -> SecurityAuditResult:
        """Decompression bomb and archive path traversal validation for uploaded ZIP/DOCX packages."""
        import zipfile
        import io

        if not content_bytes.startswith(b"PK\x03\x04"):
            return SecurityAuditResult(is_safe=False, violations=["Not a valid ZIP/DOCX package header."])

        violations = []
        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
                total_uncompressed = 0
                total_compressed = max(1, len(content_bytes))
                for zinfo in zf.infolist():
                    if ".." in zinfo.filename or zinfo.filename.startswith(("/", "\\")):
                        violations.append(f"Path traversal detected in archive entry: {zinfo.filename}")
                    total_uncompressed += zinfo.file_size
                    if total_uncompressed > max_extracted_bytes:
                        violations.append(f"Decompression size exceeds maximum limit of {max_extracted_bytes} bytes.")
                        break

                ratio = total_uncompressed / total_compressed
                if ratio > max_ratio and total_uncompressed > 1024 * 1024:
                    violations.append(f"Suspected decompression bomb: compression ratio {ratio:.1f} exceeds threshold {max_ratio}.")

        except zipfile.BadZipFile as exc:
            violations.append(f"Corrupt archive: {exc}")

        return SecurityAuditResult(
            is_safe=len(violations) == 0,
            violations=violations,
            threat_category="DECOMPRESSION_BOMB" if violations else None,
        )

    def validate_file_upload(
        self, filename: str, file_size_bytes: int, max_bytes: int = 10 * 1024 * 1024
    ) -> SecurityAuditResult:
        """Enforce extension allowlists, dangerous extension blocks, size limits, and path traversal defense."""
        violations: List[str] = []

        # 1. Path traversal checks
        if ".." in filename or "/" in filename or "\\" in filename:
            violations.append("Path traversal characters ('..', '/', '\\') detected in filename")

        if "\x00" in filename:
            violations.append("Null byte detected in filename")

        # 2. Extension validation
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in self.DANGEROUS_EXTENSIONS:
            violations.append(f"Disallowed file extension: Executable/dangerous extension '{ext}' strictly prohibited")
        elif ext not in self.ALLOWED_FILE_EXTENSIONS:
            violations.append(f"Disallowed file extension '{ext}'. Allowed: {self.ALLOWED_FILE_EXTENSIONS}")

        # 3. File size limit
        if file_size_bytes > max_bytes:
            violations.append(f"File size {file_size_bytes} exceeds maximum allowed limit of {max_bytes} bytes")

        return SecurityAuditResult(
            is_safe=len(violations) == 0,
            violations=violations,
            threat_category="FILE_UPLOAD_ABUSE" if violations else None,
        )

    def sanitize_path(
        self, base_dir: Union[str, Path], requested_path: Union[str, Path]
    ) -> Optional[str]:
        """Safely resolve requested path ensuring it stays strictly within base directory (QA-008).

        Uses canonical path comparison via pathlib.Path.resolve() and relative_to() to prevent:
        - Prefix containment collisions (e.g. /data/uploads_evil against /data/uploads)
        - Directory traversal escapes (../)
        - Absolute path overrides (/etc/passwd, C:\\Windows)
        - Null bytes and malformed characters
        """
        if not base_dir or not requested_path:
            return None

        req_str = str(requested_path)
        if "\x00" in req_str:
            return None

        try:
            base = Path(base_dir).resolve()
            p_req = Path(req_str)
            if p_req.is_absolute():
                target = p_req.resolve()
            else:
                target = (base / p_req).resolve()

            # Enforce that target is strictly equal to base or a subpath within base
            target.relative_to(base)
            return str(target)
        except (ValueError, RuntimeError, OSError):
            return None

    # ── Tenant & IDOR Isolation ───────────────────────────────────────────────

    def verify_tenant_boundary(self, user_org_id: str, target_org_id: str, is_super_admin: bool = False) -> bool:
        """Verify cross-tenant organization isolation."""
        if is_super_admin:
            return True
        return user_org_id == target_org_id

    def verify_student_access(self, requesting_user: User, target_student_id: str) -> bool:
        """Verify IDOR protection for student records."""
        if requesting_user.role in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.TEACHER):
            return True
        return requesting_user.id == target_student_id

    # ── Secret Redaction & Log Sanitization ───────────────────────────────────

    def redact_secrets(self, text_or_dict: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
        """Recursively redact API keys, tokens, and passwords from logs and messages."""
        if isinstance(text_or_dict, str):
            redacted = text_or_dict
            for pattern, _ in self.SECRET_PATTERNS:
                redacted = pattern.sub("***REDACTED_SECRET***", redacted)
            return redacted
        elif isinstance(text_or_dict, dict):
            clean_dict = {}
            for k, v in text_or_dict.items():
                if any(sec in k.lower() for sec in ("password", "passwd", "token", "secret", "api_key", "authorization")):
                    clean_dict[k] = "***REDACTED***"
                elif isinstance(v, (dict, list)):
                    clean_dict[k] = self.redact_secrets(v)
                elif isinstance(v, str):
                    clean_dict[k] = self.redact_secrets(v)
                else:
                    clean_dict[k] = v
            return clean_dict
        elif isinstance(text_or_dict, list):
            return [self.redact_secrets(item) for item in text_or_dict]
        return text_or_dict
