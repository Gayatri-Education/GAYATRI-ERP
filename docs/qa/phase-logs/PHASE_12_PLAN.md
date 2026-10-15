# Phase 12 Plan: Privacy, Secrets, XSS, Supply Chain, and Security Regression

**Phase:** PHASE-12  
**Status:** IN_PLANNING  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer  

---

## 1. Goal & Scope
Harden the Gayatri AI Platform against privacy violations, secrets leakage, Cross-Site Scripting (XSS), insecure direct object references (IDOR), and supply-chain vulnerabilities. Ensure defense-in-depth HTTP security headers (CSP, nosniff, frame-ancestors, X-Frame-Options) are uniformly attached to responses. Redact sensitive credential inputs (passwords, tokens, API keys) from validation logs and error responses. Verify that HTML injection and XSS payloads in course titles, student names, and error messages are contextually neutralized.

---

## 2. Invariants & Target Behaviors
- **HTTP Security Headers**:
  - `SecurityHeadersMiddleware` attached to FastAPI:
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `X-XSS-Protection: 1; mode=block`
    - `Referrer-Policy: strict-origin-when-cross-origin`
    - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none';`
- **Secrets & PII Redaction**:
  - Validation error handler in `central_platform/api/middleware.py`: Inputs for fields containing `password`, `token`, `secret`, `key` must be redacted (`***REDACTED***`) in error details and log statements.
  - `SecurityAuditor.redact_secrets`: Verify recursive redaction across strings, lists, and dictionaries.
  - Zero real secrets/private keys committed in the repository.
- **XSS and HTML Injection Neutralization**:
  - `SecurityAuditor.sanitize_html`: Strictly neutralizes executable tags (`<script>`, `<iframe>`, `<object>`, `<embed>`, `<svg>`), inline event handlers (`onerror`, `onload`), and unsafe schemes (`javascript:`, `data:`, `vbscript:`).
  - UI portals contextual escaping (re-verify ERP-018 in `components.js`, `fee_admin.js`, `teacher.js`, `student.js`).
- **File Upload & Path Traversal Security**:
  - `SecurityAuditor.validate_file_upload`: Enforce extension allowlist (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.txt`, `.json`, `.md`, `.csv`), reject dangerous extensions (`.exe`, `.bat`, `.sh`, `.php`, `.js`), size limits, and path traversal tokens (`..`, `/`, `\`).
  - `SecurityAuditor.sanitize_path`: Verify canonical directory containment preventing path traversal escapes.
  - `SecurityAuditor.validate_archive_safety`: Prevent zip-slip and decompression bombs.
- **Tenant & Object-Level Access Isolation (IDOR Defense)**:
  - Verify cross-tenant isolation and student self-access boundaries.

---

## 3. Implementation Plan
1. **Implement `SecurityHeadersMiddleware` in `central_platform/api/middleware.py`**:
   - Attach OWASP-recommended security headers on all responses.
2. **Mask Sensitive Fields in `validation_exception_handler` (`middleware.py`)**:
   - Redact `input` for fields matching `password`, `secret`, `token`, `key`.
3. **Register Middleware in `central_platform/api/app.py`**:
   - `app.add_middleware(SecurityHeadersMiddleware)`.
4. **Author Test Suite (`tests/test_qa_phase12_security_privacy_xss.py`)**:
   - Test security headers present on responses.
   - Test password input redaction in validation error responses.
   - Test `SecurityAuditor` secret redaction across nested objects.
   - Test XSS sanitization (tags, inline handlers, dangerous URL schemes).
   - Test path traversal and file upload validation.
   - Test zip bomb / archive safety validation.
   - Test prompt injection and hazardous chemistry precursor blocking.
   - Test multi-tenant isolation and IDOR boundary enforcement.
5. **Execute targeted test suite, related security suites, and full non-GUI regression suite (`python -m pytest -q -m "not gui"`)**.
6. **Update logs, trackers, and commit**.
