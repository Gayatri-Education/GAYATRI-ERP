# Gayatri AI — Release Baseline Audit (2026-10-03)

**Document Reference:** Release Remediation Baseline  
**Audit Date:** 3 October 2026  
**Target Release Date:** 7 October 2026  
**Auditor / Agent:** local-agent (Antigravity)  

---

## 1. Environment & Inventory Baseline

| Attribute | Baseline Value | Notes |
|---|---|---|
| Git Commit SHA | `66dd692` (`66dd6922896ee8c8ad605335d25e0c52bb8e2d42`) | Current head of `master` branch |
| Git Branch | `master` | Clean working tree (untracked: remediation plan) |
| Python Version | `3.12.10` | 64-bit Windows CPython runtime |
| Operating System | `Microsoft Windows NT 10.0.22621.0` (Windows 11) | Standard developer workstation |
| VERSION File | `3.0.1` | **Discrepancy:** `pyproject.toml` lists `5.0.0` |
| pyproject.toml Version | `5.0.0` | Inconsistent with `VERSION` file |
| Dependencies Status | Fully satisfied | Installed per `requirements.txt` / `requirements.lock` |
| PySide6 Version | `6.11.1` (Qt runtime & compiled `6.11.1`) | Functional for desktop shell & WebEngine |
| Local Database | `gayatri_local.db` (SQLite 3, WAL mode) | 8 applied schema migrations verified |

---

## 2. Test Verification Baseline

### Tier 0: Static Compilation Hygiene
Command:
```bash
python -m compileall central_platform app core local_runtime scripts
```
- **Result:** PASSED (0 errors across all 5 directories)

### Database Migration Integrity
Command:
```bash
python scripts/migrate_db.py status --db-path gayatri_local.db
```
- **Total Applied Migrations:** 8 (Versions 001 to 008)
- **Checksum Integrity:** `VERIFIED`

### Architecture Guardrail Suite
Command:
```bash
python -m pytest -v tests/architecture
```
- **Result:** 13 passed in 0.25s (100% pass)

### Tier 4: Comprehensive Headless Regression
Command:
```bash
python -m pytest -q -m "not gui"
```
- **Total Tests Collected:** 1,252
- **Passed:** 1,252
- **Failed:** 0
- **Skipped:** 0
- **Execution Time:** 81.52 seconds

---

## 3. Subsystem Architecture Map

1. **Central Platform API (`central_platform/api`):**
   - Asynchronous FastAPI platform layer.
   - Versioned routes mounted under `/api/v1/*` (auth, users, courses, curricula, tutor, rag, ai, etc.).
   - Legacy route compatibility under `/api/*` and HTML teacher command center at `/`.
   - Tracing & logging middleware (`RequestIDMiddleware`, `StructuredLoggingMiddleware`).

2. **Authentication & Identity (`central_platform/auth`):**
   - JWT token issuance (HMAC-SHA256, access + refresh tokens).
   - PBKDF2 password hashing in database.
   - **Audit finding:** Fallback synthetic user generation active on `/api/v1/auth/login` for non-DB users; insecure email-only password reset bypass on `/api/v1/auth/password-reset`.

3. **AI Execution Subsystem (`central_platform/ai`):**
   - Unified `AIGatewayService`, `ModelRouter`, `PolicyEngine`, and provider adapters (`OpenAIAdapter`, `AnthropicAdapter`, `GeminiAdapter`, `LocalGGUFAdapter`, `MockAIAdapter`).
   - **Audit finding:** Inconsistent model IDs across `model_manifest.json` (Qwen 0.5B), `gateway.py` (v3, SLM, 3B), and `scripts/check_model.py` (3B).
   - Mock adapter has `is_production_mode()` checks, but call graph and fallback routing require verification under production environment flags.

4. **Model Artifacts & Integrity:**
   - Manifest: `model_manifest.json` specifies `gayatri-chem-qwen2.5-0.5b-v4` and path `models/qwen2.5-0.5b-instruct-q4_k_m.gguf`.
   - **Audit finding:** Manifest SHA-256 checksum is `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty string hash), not verified against the actual GGUF artifact.

5. **Retrieval-Augmented Generation (`central_platform/rag`, `core/rag`):**
   - Hybrid retrieval combining vector and BM25 rankers.
   - Ingestion, parser, cleaner, and scoped authorization modules.
   - Must enforce multi-tenant isolation, course version scoping, and prompt injection filtering.

6. **Tutor Orchestrator (`central_platform/tutor`, `core/tutor`):**
   - 16-step canonical orchestrator pipeline.
   - Learning state tracking (BKT / LDG), misconception engine, adaptive action selector, response validator.

7. **Packaging & Clean Installation (`packaging`):**
   - `packaging/gayatri_demo.spec` (PyInstaller) and `packaging/installer.iss` (Inno Setup).
   - **Audit finding:** Spec references obsolete `training/prompts` and outdated module names.

---

## 4. Open Release Blockers (Baseline State)

| ID | Title | Severity | Impacted Phase |
|---|---|---|---|
| **P0-01** | Production login contains mock/integration identity fallback | P0 | Phase 2 |
| **P0-02** | Model manifest checksum is empty hash and unvalidated | P0 | Phase 5 |
| **P0-03** | Production AI failure could fall back to synthetic content | P0 | Phase 4 |
| **P0-04** | Model identity and configuration inconsistent across components | P0 | Phase 1 & 4 |
| **P0-05** | Production CORS configured with wildcard `allow_origins=["*"]` | P0 | Phase 1 |
| **P0-06** | Password reset allows arbitrary email password resets without verified token | P0 | Phase 2 |
| **P0-07** | Packaging spec references nonexistent directories (`training/prompts`) | P0 | Phase 13 |
| **P0-08** | Runtime validation relies solely on synthetic integration fixtures | P0 | Phase 16 |

---

## 5. Phase 0 Gate Certification

- [x] Current commit SHA recorded (`66dd692`)
- [x] Working tree status recorded (clean, untracked remediation plan)
- [x] Test baseline established (1,252/1,252 passing, 0 failures, 81.52s)
- [x] Architecture and subsystems enumerated
- [x] Release blockers cataloged
- [x] Baseline reproducible and documented

**Phase 0 Status: COMPLETE**
