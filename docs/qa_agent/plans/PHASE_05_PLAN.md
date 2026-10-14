# Phase 05 Plan: Authentication, Revocation, Authorization & Distributed Rate Limiting

**Phase Goal:** Remediate audit findings `GQA-005`, `GQA-006`, and `GQA-013` by establishing a durable multi-worker JWT revocation registry, fail-closed cluster-wide sliding-window rate limiting, refresh token rotation, and comprehensive multi-tenant/role authorization proofs.

---

## 1. Architectural Scope & Target Findings

### GQA-005: Process-Local In-Memory JWT Revocation Bypass
- **Problem:** `central_platform/auth/tokens.py` tracks revoked tokens via a process-local `_REVOKED_JTIS: Set[str] = set()`. In multi-worker environments (Gunicorn/Uvicorn worker pools, horizontal replicas) or across server restarts, revocation in one worker is completely bypassed by others.
- **Remediation:**
  1. Define pluggable `TokenRevocationStore` interface with `is_revoked()`, `revoke()`, and `cleanup()`.
  2. Implement `DatabaseRevocationStore` backed by `PlatformDatabase`'s `revoked_tokens` table `(jti PRIMARY KEY, user_id, revoked_at, expires_at, reason)`.
  3. Ensure thread-safety and write-through persistence to durable storage, preserving fast in-memory cache for repeated lookups while querying the database on cache miss.
  4. Ensure revocation survives process restart and replicates instantly across independent worker processes sharing the database.

### GQA-006: Shared Rate Limiter Silent Fallback to Local Memory
- **Problem:** `central_platform/security/auditor.py:SharedRateLimiterBackend` falls back silently to `InMemoryRateLimiterBackend` when `shared_store is None`. In cluster/multi-worker deployments where global throttling is required, this quietly permits per-process bursts, defeating cluster-wide DDoS and brute force protection.
- **Remediation:**
  1. Add `cluster_required: bool = False` flag (configurable via code or `GAYATRI_RATE_LIMITER_CLUSTER_REQUIRED`).
  2. In cluster-required mode, missing or unhealthy shared storage raises a readiness/runtime error (`RuntimeError`) or fails closed rather than silently falling back to local memory.
  3. Implement `DatabaseRateLimiterStore`: a durable SQLite/database-backed sliding-window store that guarantees atomic sliding-window operations across multiple worker processes (`rate_limit_events` table).
  4. Define differentiated rate limit policies across actor categories: anonymous client IP (20/min), authenticated user ID (60/min), auth-sensitive endpoints (10/min), and bulk/telemetry endpoints (120/min).

### GQA-013: Security Proofs & Role/Object Authorization Matrix
- **Problem:** Need end-to-end verification of route and object ownership boundaries across Student, Teacher, Org Admin, Super Admin, and Anonymous callers.
- **Remediation:**
  1. Implement refresh token rotation: `/auth/refresh` revokes the exchanged refresh token, issues both a new access token and new rotated refresh token, and blocks token reuse with 401 Unauthorized.
  2. Strengthen Authorization header parser: reject missing, malformed, or excessively long headers (> 8192 bytes) with 400/401.
  3. Validate negative security boundaries:
     - Student cannot access another student's sessions, learning events, analytics, or query RAG on another student's behalf.
     - Teacher cannot access students outside assigned cohorts or outside their organization.
     - Org Admin cannot view or manipulate records belonging to another organization.
     - Super Admin actions are audited and authorized across tenants.

---

## 2. Implementation Steps

1. **Database Schema Extension (`central_platform/db.py`):**
   - Add `revoked_tokens` table in `PlatformDatabase._init_db()`:
     - `jti TEXT PRIMARY KEY`, `user_id TEXT`, `revoked_at TEXT NOT NULL`, `expires_at INTEGER`, `reason TEXT`.
     - Index on `idx_revoked_tokens_expires (expires_at)`.
   - Add `rate_limit_events` table in `PlatformDatabase._init_db()`:
     - `id INTEGER PRIMARY KEY AUTOINCREMENT`, `key TEXT NOT NULL`, `timestamp REAL NOT NULL`.
     - Index on `idx_rate_limit_events (key, timestamp)`.
   - Add database helper methods: `revoke_token`, `is_token_revoked`, `cleanup_expired_revocations`, `record_rate_limit_hit`, `check_rate_limit_atomic`.

2. **Durable Token Revocation (`central_platform/auth/tokens.py`):**
   - Implement `TokenRevocationStore` abstract base, `DatabaseRevocationStore`, and `InMemoryRevocationStore`.
   - Provide `get_revocation_store()` and `set_revocation_store()`.
   - Wire `revoke_token()` and `is_token_revoked()` through the active revocation store.
   - Enforce revocation check in `decode_and_verify_token()`.

3. **Shared Rate Limiting Engine (`central_platform/security/auditor.py`):**
   - Implement `DatabaseRateLimiterStore` supporting multi-process sliding-window enforcement.
   - Update `SharedRateLimiterBackend`:
     - Add `cluster_required` flag and `check_readiness()` probe.
     - Fail closed / raise error if cluster mode is required and no healthy shared store is present.
   - Add identity/category rate limiting policies in `SecurityAuditor`.

4. **Auth Route Hardening (`central_platform/api/routes/auth.py` and `dependencies.py`):**
   - Implement refresh token rotation: old refresh token revoked upon use; reuse of revoked refresh token returns 401.
   - Hardened `extract_bearer_token`: length checks, malformed header handling.
   - Logout revokes both access token and supplied refresh token.

5. **Test Authoring & Execution:**
   - Author `tests/test_qa_phase05_auth_revocation_ratelimit.py` covering all required test cases.
   - Execute focused test suite.
   - Run full regression suite (`pytest -q --tb=short`).

6. **Reporting & Master Progress:**
   - Document decisions in `docs/qa_agent/decisions/DECISION_LOG.md` (DEC-017).
   - Produce `docs/qa_agent/reports/PHASE_05_REPORT.md`.
   - Update `docs/qa_agent/MASTER_PROGRESS.md`.
