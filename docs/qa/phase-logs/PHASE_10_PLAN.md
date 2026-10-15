# Phase 10 Plan: Health, Readiness, Observability, and Operational Failure Reporting

**Phase:** PHASE-10  
**Status:** IN_PLANNING  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer  

---

## 1. Goal & Scope
Harden platform health monitoring, readiness probes, failure reporting, and operational observability. Eliminate fabricated metrics and masked failure states (ERP-006, ERP-020). Ensure operational probes (`/healthz`, `/readyz`, `/livez`, `/api/v1/health`, `/api/health`) truthfully distinguish between healthy, degraded, and down states; enforce HTTP 503 on database unavailability; and ensure structured error envelopes carry tracing correlation without leaking secrets or credentials.

---

## 2. Target Findings & Invariants
- **ERP-006: Health endpoint may report fabricated count or healthy state**:
  - `central_platform/api/app.py`: `/api/health` initialized `students_count = 5` and retained it if dashboard queries failed. Non-`UNHEALTHY` statuses (including `DEGRADED`) were collapsed to `HEALTHY`, masking degraded system health. Furthermore, `/api/health` returned HTTP 200 even when the database was down.
- **ERP-020: Broad exceptions/defaults may mask failure**:
  - `central_platform/health/service.py`: `probe_database()` and `check_deep_health()` instantiated fallback `PlatformDatabase()` instead of querying the authoritative `get_db()` connection. `probe_storage()` returned `HEALTHY` without checking directory write permissions (`os.access(..., os.W_OK)`).
- **Liveness vs Readiness vs Health Invariants**:
  - Liveness (`/livez`): Confirms process is executing (HTTP 200).
  - Readiness (`/readyz`): Confirms critical dependencies (authoritative DB) are functional. Must return HTTP 503 with `ready: false` when DB is unavailable; must recover to HTTP 200 when DB is restored.
  - Health (`/healthz`, `/api/v1/health`, `/api/health`):
    - Subsystem states: `HEALTHY`, `DEGRADED`, `UNHEALTHY`.
    - If any critical subsystem is `UNHEALTHY`: Aggregate status is `UNHEALTHY`, returning HTTP 503.
    - If non-critical subsystem is `DEGRADED`: Aggregate status is `DEGRADED`, returning HTTP 200.
    - Truthful metrics: `students_monitored` must never default to fabricated `5`; default is `0` or actual database count.
  - Observability: Request IDs and correlation headers (`X-Request-ID`) must be propagated across responses without leaking secrets.

---

## 3. Implementation Plan
1. **Remediate `central_platform/api/app.py`**:
   - In `legacy_api_health`:
     - Initialize `students_count = 0` (never hardcoded 5).
     - Query actual student count; on exception, set `students_count = 0` and log warning.
     - Extract `health_lvl = h.get("health_level", "HEALTHY")`.
     - When `h["status"] == "UNHEALTHY"` or `health_lvl == "UNHEALTHY"`: return `JSONResponse(status_code=503, content={"status": "UNHEALTHY", "health_level": "UNHEALTHY", ...})`.
     - When `health_lvl == "DEGRADED"`: return `JSONResponse(status_code=200, content={"status": "DEGRADED", "health_level": "DEGRADED", ...})`.
     - Otherwise return HTTP 200 with `"status": "HEALTHY"`.
   - In `HealthStatusResponse` schema (`central_platform/api/schemas.py`): change `students_monitored: int = 5` default to `0`.
2. **Remediate `central_platform/health/service.py`**:
   - In `probe_database` and `check_deep_health`: resolve authoritative DB via `get_db()`.
   - In `probe_storage`: test actual directory write access (`os.access(dir_path, os.W_OK)`).
   - In `check_health`: ensure `overall == "DEGRADED"` sets `status: "DEGRADED"` (or preserve `ONLINE` with explicit `health_level: "DEGRADED"`).
3. **Author Reproduction Suite (`tests/test_qa_phase10_health_observability.py`)**:
   - Test 1: `/api/health` reports true count (0 when empty, not fabricated 5).
   - Test 2: `/api/health` under failure returns 0, never fallback 5.
   - Test 3: `/api/health` reports `DEGRADED` status when a subsystem is degraded.
   - Test 4: `/api/health` returns HTTP 503 and `UNHEALTHY` when database fails.
   - Test 5: `/readyz` returns HTTP 503 and `ready: false` when database fails.
   - Test 6: `/readyz` recovers to HTTP 200 and `ready: true` when failure cleared.
   - Test 7: Deep health probe detects uninitialized or corrupt database.
   - Test 8: Storage probe detects unwritable storage path.
   - Test 9: Structured logs / error responses carry `X-Request-ID` without leaking secrets.
   - Test 10: Dependency failure in `/healthz` reflects `UNHEALTHY` with HTTP 503.
4. **Run targeted tests, debug, and execute full regression suite (`python -m pytest -q -m "not gui"`)**.
5. **Update logs, trackers, issue register, and commit**.
