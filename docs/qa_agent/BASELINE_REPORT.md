# Gayatri AI — Baseline Verification Report (Phase 00)

**Date:** 2026-10-14  
**Audit Baseline Git Commit SHA:** `0e83fdacdce905d395c389f53c866db5ede1f67f`  
**Branch:** `master`  
**Python Runtime:** Python 3.12.10 (AMD64)  
**Operating System:** Windows 10.0.22621  
**Target Outcome:** Independent audit reproduction, architecture mapping, and defect-to-phase traceability for GQA-001 through GQA-016.

---

## 1. System Runtime & Toolchain Baseline

| Component | Version / Identifier | Status |
|---|---|---|
| Python Interpreter | 3.12.10 | Verified |
| PySide6 | 6.11.1 | Installed & Verified |
| Pytest | 7.4.4 | Installed & Verified |
| Llama-cpp-python | 0.3.35 | Pinned in lockfile |
| SQLite Runtime | Built-in 3.x | Active |
| Repository Status | Clean working copy prior to plan generation | Verified |

---

## 2. Test Suite & Compilation Baseline

| Check | Command | Exit Code | Result | Evidence File |
|---|---|---|---|---|
| Module Compilation | `python -m compileall app core central_platform scripts training tests -q` | 0 | 100% clean syntax | STDOUT clean |
| Baseline Test Suite | `pytest -q --tb=short` | 0 | 1,409 / 1,409 tests passed | `docs/qa_agent/evidence/logs/phase_00_baseline_test_run.log` |
| Release Gate Suite | `pytest tests/test_qa_phase12_release_gate.py` | 0 | 4 / 4 passed | STDOUT clean |

---

## 3. Architecture Boundary & Deployment Mode Map

Gayatri AI operates across three distinct operational modes, each with distinct security and persistence invariants:

```
[ Desktop Client (PySide6) ] ----(Direct / IPC)----> [ Core Tutor & Session Layer ]
           |                                                      |
           |                                             [ Local SQLite DB ]
           v                                                      |
[ Central Platform API (FastAPI) ]                                 v
   ├── AI Gateway & Router --------> Local GGUF / Cloud Providers
   ├── RAG Service ----------------> Knowledge Base & Vector Index
   ├── Auth & RBAC ----------------> JWT Token & Multi-Worker Revocation
   └── Deployment Validator --------> Health & Configuration Hardening
```

1. **Desktop / Offline Mode:**
   - GUI: PySide6 (`app/main.py`).
   - Inference: Local GGUF (`core/providers/local.py`).
   - Storage: Local SQLite database (`gayatri_local.db`).
   - Authentication: Local user session (`core/session.py`).

2. **Local Single-Process Server:**
   - Server: FastAPI / Uvicorn single worker.
   - Storage: Local SQLite with migration runner.
   - AI Gateway: Routes between local GGUF and configured cloud adapters.

3. **Multi-Tenant Hosted Production Server:**
   - Server: Multi-worker uvicorn / gunicorn.
   - Storage: Shared PostgreSQL / robust persistent store with connection pooling.
   - Authentication: Distributed JWT with shared revocation and rate limiting.
   - Requirement: Must fail closed if production secrets are missing or default.

---

## 4. Defect Traceability Matrix (GQA-001 through GQA-016)

| Defect ID | Priority | Description | Primary Phase | Remediation Strategy |
|---|---|---|---|---|
| **GQA-001** | P0 | AI health/readiness can be false green on file presence alone | Phase 01, 02, 11 | Require true execution probe with timeout; distinguish `LOADABLE` from `EXECUTABLE`. |
| **GQA-002** | P0 | Master test accepts fallback / mock as real model success | Phase 02, 12 | Separate fallback regression test from real-model integration requirement. |
| **GQA-003** | P0 | Fixed canned grading fallback awards full score/credit | Phase 03, 09, 12 | Never award credit or mutate mastery on fallback or unavailable grader. |
| **GQA-004** | P1 | Provider status inferred from config presence rather than runtime check | Phase 04, 11 | Separate configured, reachable, recently-inferred states; track timestamps. |
| **GQA-005** | P1 | Process-local in-memory JWT revocation bypass in multi-worker | Phase 01, 05, 12 | Implement shared/durable token revocation store; test cross-worker invalidation. |
| **GQA-006** | P1 | Shared rate limiter falls back silently to local memory | Phase 05, 12 | Fail fast in cluster/production mode when shared backend is unconfigured. |
| **GQA-007** | P1 | Autouse test fixture mutates root developer database | Phase 01, 06, 10 | Switch test fixture to isolated `tmp_path` database; preserve root database. |
| **GQA-008** | P1 | Configuration divergence (`GAYATRI_ENV` vs `APP_ENV`, secret keys) | Phase 01, 05, 10 | Unify settings into single authoritative configuration model with strict aliases. |
| **GQA-009** | P1 | Single-platform CI does not verify cross-platform matrix | Phase 10, 11 | Configure multi-platform CI matrix (Windows, Ubuntu) for headless checks. |
| **GQA-010** | P1 | Training evaluator ignores `must_contain` criteria | Phase 09, 10, 13 | Fail closed when required criteria are absent; non-zero exit on failure. |
| **GQA-011** | P1 | Async session writer swallows worker exceptions | Phase 06, 12 | Surface write errors to caller, track failed write counters, implement ack. |
| **GQA-012** | P1 | Tautological RAG health probe on first chunk words | Phase 07, 12, 13 | Add golden query evaluation set authored independently of chunk phrases. |
| **GQA-013** | P1 | Regex string matching claimed as complete security proof | Phase 05, 08, 12 | Construct threat-to-test matrix with active payload injection verification. |
| **GQA-014** | P1 | CI installs loose dependencies ignoring lock file | Phase 10, 13 | Pinned installation using `requirements.lock` in CI workflow. |
| **GQA-015** | P2 | Synthetic token metric `daily_spend * 10000` mislabels usage | Phase 04 | Report actual token usage or explicitly label estimates as `estimated`. |
| **GQA-016** | P2 | Latest CI run was incomplete or unverified at audit time | Phase 10, 13 | Ensure final CI verification runs on release SHA with full artifact logging. |

---

## 5. Exit Gate Checklist

- [x] Exact baseline SHA recorded: `0e83fdacdce905d395c389f53c866db5ede1f67f`.
- [x] Full module compilation verified clean.
- [x] Full test suite executed and logged: 1,409 tests collected, 100% passing.
- [x] Every audit finding (GQA-001 through GQA-016) mapped to owner phase and strategy.
- [x] No application source code modified during Phase 00.
