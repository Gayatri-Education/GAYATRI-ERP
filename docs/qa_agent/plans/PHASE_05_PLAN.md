# Phase 05 Implementation Plan — Security Hardening, Path Traversal & Multi-Worker Governance

## 1. Context & Objectives
- **Severity Focus:** P0/P1
- **Key Defects to Remediate:**
  - **QA-008:** Path traversal validation uses unsafe string-prefix containment in `central_platform/security/auditor.py:sanitize_path()`.
  - **QA-009:** Rate limiter in `central_platform/security/auditor.py` is process-local with in-memory timestamp dictionaries and lacks an explicit multi-worker / distributed contract and interface.
  - Multi-tenant boundary isolation, IDOR defenses, upload validation, secret redaction, and token enforcement must be rigorously verified against adversarial tests.

## 2. Requirements & Acceptance Criteria
1. **Canonical Path Traversal Neutralization (QA-008):**
   - Replace string-prefix logic in `SecurityAuditor.sanitize_path()` with canonical path containment using `pathlib.Path.resolve()` and `Path.relative_to()`.
   - Prevent prefix collision exploits (e.g., `/data/uploads_evil/file.pdf` against base `/data/uploads`), parent directory escapes (`../`), root escapes (`/etc/passwd`), Windows drive escapes (`C:\uploads_evil\file.txt`), and null bytes.
   - Return canonical resolved path string if safe; return `None` on any escape attempt or invalid path.
2. **Multi-Worker Rate Limiting Contract & Architecture (QA-009):**
   - Define a formal `RateLimitBackend` interface/protocol supporting sliding window rate limiting.
   - Implement `InMemoryRateLimiterBackend` with thread-safe sliding window logic for local/single-worker desktop deployments.
   - Define `SharedRateLimiterBackend` / multi-worker contract with pluggable architecture for distributed/cluster deployments (e.g. Redis or database-backed).
   - Expose detailed limit status: `allowed`, `remaining`, `reset_seconds`, `backend_type`.
   - Document the exact concurrency guarantee of each backend.
3. **Boundary & Injection Defense Verification:**
   - Multi-tenant organization isolation (Org A cannot access Org B data).
   - IDOR prevention (Student A cannot read Student B records; teachers/admins allowed with valid claims).
   - Prompt injection and toxic chemical synthesis pattern detection.
   - Recursive secret/token redaction across nested JSON structures.

## 3. Targeted Test Suite
Create `tests/test_qa_phase05_security_hardening.py` to test:
- Canonical path traversal test matrix (prefix attacks, `..`, absolute escapes, drive changes, nested valid paths).
- Multi-worker rate limiter contract, in-memory sliding window, and backend pluggability.
- Multi-tenant boundary verification and IDOR prevention.
- Prompt injection & toxic synthesis blocking.
- Deep recursive secret redaction.

## 4. Execution Sequence
1. Write this plan to `docs/qa_agent/plans/PHASE_05_PLAN.md`.
2. Update `central_platform/security/auditor.py` with canonical `sanitize_path()` and modular `RateLimitBackend`.
3. Create `tests/test_qa_phase05_security_hardening.py`.
4. Run focused tests: `pytest tests/test_qa_phase05_security_hardening.py tests/test_phase22_security_hardening_master.py -v`.
5. Run full regression suite: `pytest -q`.
6. Record decision DEC-005 in `docs/qa_agent/decisions/DECISION_LOG.md`.
7. Write `docs/qa_agent/reports/PHASE_05_REPORT.md`.
8. Update `docs/qa_agent/MASTER_PROGRESS.md`.
