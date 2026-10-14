# Phase 08 Plan — Reliability, Recovery & Observability

**Objective:** Ensure system failures are detectable, recoverable, and diagnosable across all failure domains, verifying automated fallback policies, degraded execution modes, deep health probing, and observability sanitization.

---

## 1. Scope & Targeted Subsystems

1. **Failure Taxonomy (`central_platform/recovery/manager.py`):**
   - Authoritative failure categories: `MISSING_MODEL`, `CORRUPT_MODEL`, `PROVIDER_TIMEOUT`, `PROVIDER_MALFORMED`, `RAG_UNAVAILABLE`, `DATABASE_UNAVAILABLE`, `BROKEN_MIGRATION`, `BROKEN_UPLOAD`, `INTERRUPTED_PUBLISH`, `EXPIRED_INSTRUCTION`, `DUPLICATE_SYNC`, `APP_CRASH_MID_TURN`.
   - Recovery status: `RECOVERED`, `DEGRADED_FALLBACK`, `UNRECOVERABLE`.
   - Commit decisions: `COMMIT`, `ROLLBACK`, `NOOP`, `RETRY`.

2. **Provider Failures & Circuit Breaking:**
   - Fallback routing on provider timeout or exhaustion.
   - Circuit breaker transition (`CLOSED` -> `OPEN` -> `HALF_OPEN`).
   - Explicit `DEGRADED_FALLBACK` execution provenance.

3. **RAG Retrieval Outage & Graceful Degradation:**
   - Degrade to structured syllabus context when vector store fails.
   - Anti-hallucination guarantee: No fake citations or false-grounding claims during outage.

4. **Database Outages & Read-Only Snapshots:**
   - Database connection failure -> in-memory cached state with explicit `read_only: True` flag.

5. **Malformed Model Output Self-Healing:**
   - Markdown code fence JSON extraction.
   - Regex balanced brace extraction and trailing comma cleanup.
   - Empty/corrupt output handling with default pedagogical payload.

6. **Deep Health Probe & Liveness/Readiness Separation:**
   - Liveness: Process up.
   - Readiness: Database connection and critical dependencies responsive.
   - Deep Health: Verifies database schema/read-write, physical model artifact on disk (not just manifest json), and storage accessibility. Does not return green if physical artifacts are absent.

7. **Kill Switch & Security Sanitization:**
   - Global and targeted kill switch in `AIGatewayService` and `PolicyEngine`.
   - Sanitized logging: Zero API key, password, or bearer token leakage.

---

## 2. Dev Loop Steps

1. **Plan Authoring:** Commit `docs/qa_agent/plans/PHASE_08_PLAN.md`.
2. **Implementation Enhancements:**
   - Enhance `PlatformHealthService` in `central_platform/health/service.py` to add `probe_deep_health()` that checks real physical model file presence and database schema viability.
   - Verify `FailureRecoveryManager` contracts and self-healing output repair in `central_platform/recovery/manager.py`.
   - Verify log sanitization helper ensuring sensitive credentials cannot be leaked in logs or error diagnostics.
3. **Focused Tests:**
   - Author `tests/test_qa_phase08_reliability_observability.py`.
   - Run focused suite covering Phase 08 and previous recovery tests (`test_phase24_failure_recovery_master.py`, `test_phase38_failure_recovery.py`, `test_phase23_reliability_failure_injection_recovery.py`).
4. **Full Regression:**
   - Run `pytest -q` across the entire codebase.
5. **Decisions & Reporting:**
   - Log `DEC-008` in `docs/qa_agent/decisions/DECISION_LOG.md`.
   - Write `docs/qa_agent/reports/PHASE_08_REPORT.md`.
   - Update `docs/qa_agent/MASTER_PROGRESS.md`.
