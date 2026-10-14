# Phase 08 Implementation Plan: Security Hardening & Independent Adversarial Verification

**Phase:** Phase 08  
**Date:** 2026-10-14  
**Target Defects:**
- `GQA-013` (P1): Regex string matching claimed as complete security proof; cross-cuts Phases 01, 05, 06, and 07.

---

## 1. Objectives & Scope

1. **Clarify SecurityAuditor Architectural Principle (GQA-013)**:
   - Formally document that regex/pattern matching in `SecurityAuditor` represents defense-in-depth heuristics, not formal certification of threat immunity.
   - Primary security guarantees must be backed by structural enforcement:
     - 100% Parameterized queries for SQL injection prevention.
     - Canonical path resolution (`Path.resolve().relative_to(base)`) and symlink containment for path traversal.
     - Strict object-level authorization across tenant and identity boundaries.
     - Cryptographic verification with durable revocation tracking for JWTs.
     - Contextual HTML entity escaping and strict sanitization for XSS prevention.
     - Strict extension and magic byte verification for file uploads.

2. **CORS & Trust Boundary Hardening**:
   - In `central_platform/api/app.py`, synchronize CORS configuration directly with authoritative `PlatformSettings.allowed_origins`.
   - Ensure wildcard origins (`"*"`) are strictly prohibited in production mode.

3. **Contextual HTML/Markdown XSS Sanitization & Safe Link Policy**:
   - Enhance `SecurityAuditor` with robust `sanitize_html(text: str, allow_formatting: bool = True) -> str` and `is_safe_url(url: str) -> bool`.
   - Disallow script, iframe, style, svg, object, embed, form, input tags.
   - Strip all inline event handlers (`onload`, `onerror`, `onclick`, etc.).
   - Disallow dangerous URL schemes (`javascript:`, `vbscript:`, `data:`, `file:`).

4. **Object-Level Authorization Matrix**:
   - Verify that data access checks verify both role and object ownership / tenant boundaries across all route groups (Student, Teacher, Org Admin, Super Admin, Anonymous).
   - Test IDOR boundaries for student records, class notes, course offerings, and user profiles.

5. **SQL Injection Defense-in-Depth Verification**:
   - Verify that SQL queries across `PlatformDatabase` use parameterized bindings (`?`).
   - Run adversarial non-destructive SQL injection payloads across search, filters, and ID lookups to prove parameterization immunity.

6. **Decompression Bomb & Upload Constraints**:
   - In file upload validation, add decompression bomb safeguards (e.g., compressed ratio limits, max uncompressed byte checks) for archive and DOCX/PDF uploads.

7. **Threat-to-Test Matrix**:
   - Produce a comprehensive Threat-to-Test Matrix mapping every claimed security vector to explicit automated tests with coverage status.

---

## 2. Implementation Steps

### Step 1: SecurityAuditor Clarification & HTML/XSS Sanitizer
- In `central_platform/security/auditor.py`:
  - Update module docstring to state defense-in-depth nature of regex heuristics (GQA-013).
  - Add `sanitize_html(text: str, allow_formatting: bool = False) -> str`.
  - Add `is_safe_url(url: str) -> bool`.
  - Enhance `sanitize_prompt()` to utilize `sanitize_html()`.
  - Add `validate_archive_safety(content_bytes: bytes, max_extracted_bytes: int = 20 * 1024 * 1024) -> SecurityAuditResult`.

### Step 2: Canonical CORS in FastAPI App
- In `central_platform/api/app.py`:
  - Update CORS middleware registration to source `allow_origins` strictly from `get_authoritative_settings().allowed_origins`.

### Step 3: Author Focused Security Test Suite
- Author `tests/test_qa_phase08_security_adversarial.py` covering:
  - Threat vector 1: IDOR and cross-tenant access.
  - Threat vector 2: Authentication bypass, malformed tokens, and revoked tokens.
  - Threat vector 3: Prompt injection, encoded/obfuscated instructions, and indirect RAG injection.
  - Threat vector 4: Markdown/HTML XSS, SVG payloads, event handlers, and unsafe URL schemes (`javascript:`, `data:`).
  - Threat vector 5: Path traversal, prefix collisions, and symlink escape attempts.
  - Threat vector 6: SQL injection parameter binding resilience.
  - Threat vector 7: File upload size limits, disallowed dangerous extensions, and decompression bomb protection.
  - Threat vector 8: Production CORS configuration enforcing authoritative origins.
  - Threat vector 9: Recursive secret redaction in nested logs and error payloads.
  - Threat vector 10: Multi-worker distributed rate limiting fail-closed policy.

### Step 4: Verification & Regression Run
- Run focused suite and full repository regression (`pytest -q --tb=short`).

### Step 5: Finalize Documentation & Advance
- Update `docs/qa_agent/decisions/DECISION_LOG.md` (DEC-020).
- Generate `docs/qa_agent/reports/PHASE_08_REPORT.md` including the Threat-to-Test Matrix.
- Update `docs/qa_agent/MASTER_PROGRESS.md` marking Phase 08 PASSED and GQA-013 RESOLVED.
