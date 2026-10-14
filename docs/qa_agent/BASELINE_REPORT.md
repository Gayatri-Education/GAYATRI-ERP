# Gayatri Repository — Baseline Audit Report

**Date:** 2026-10-07  
**Commit SHA:** `eee87194be0e69fa0f11923d2a59869f0f215816`  
**Branch:** `master` (ahead of origin/master by 13 commits)  
**Document Purpose:** Baseline technical inventory prior to Phase 02+ QA, hardening, and production remediation.

---

## 1. System & Runtime Environment
- **Operating System:** Windows NT / Windows 11 (AMD64)
- **Python Version:** 3.12.10
- **Pytest Path:** `C:\Users\user\AppData\Local\Programs\Python\Python312\Scripts\pytest.exe`
- **Ruff Path:** `C:\Users\user\AppData\Local\Programs\Python\Python312\Scripts\ruff.exe`

---

## 2. Compilation and Code Health
- **Compileall:** `python -m compileall app core central_platform tests scripts`
  - **Result:** **PASSED (0 syntax errors, 0 compilation failures)**
- **Test Suite Discovery:** `pytest --collect-only -q`
  - **Discovered Tests:** **1346 tests** across 84 test modules
- **Test Suite Execution:** `pytest -q --tb=short`
  - **Result:** **1346 passed in 94.06s** (0 failed, 0 errors, 0 skipped)
- **Static Analysis / Lint:** `ruff check .`
  - **Result:** 11,222 diagnostics reported under strict ruleset (`E, W, F, I, B, UP, ANN, S, T20, RUF`), primarily annotations (`ANN`), prints (`T20`), line-lengths (`E501`), and subprocess calls (`S605/S607` in `training/`).

---

## 3. Model Manifest & Physical Model Availability
- **Manifest File:** `model_manifest.json`
  - `model_id`: `gayatri-chem-qwen2.5-0.5b-v4`
  - `local_path`: `models/qwen2.5-0.5b-instruct-q4_k_m.gguf`
  - `checksum`: `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`
- **On-Disk Model Verification:**
  - `models/qwen2.5-0.5b-instruct-q4_k_m.gguf` exists: **FALSE** (Directory / file missing)
- **Defect Identified (QA-001 / QA-003):** Manifest is present, but local model file does not exist on disk. In non-production mode, `LocalGGUFAdapter` quietly falls back to deterministic pedagogical mock content and returns `success=True, status=MODEL_SUCCESS, mock=False`.

---

## 4. High-Risk Code Pattern Inventory
An automated scan across `app/`, `core/`, `central_platform/`, `training/`, and `scripts/` identified:

| Pattern | Count | Primary Locations / Risk |
|---|---:|---|
| `except Exception` | 376 | Broad catch blocks across controllers, adapters, services (QA-016) |
| `pass` (bare) | 61 | Silent exception suppression blocks |
| `TODO` / `FIXME` | 0 | Clean of explicit unaddressed inline tags |
| `os.system(` | 15 | Exclusively in `training/train_slm.py` and `train_colab.py` (QA-012) |
| `subprocess.run/Popen` | 4 | In process supervisors |
| `eval(` / `exec(` | 6 | Dynamic code / AST evaluations in evaluators |
| `pickle` / `yaml.load` | 0 | Unsafe deserialization absent |
| `shell=True` | 0 | Direct shell injection flags absent |
| `.startswith(` | 37 | Unsafe path prefix checks in `central_platform/security/auditor.py:207` (QA-008) |
| `local_user_1` | 10 | Hard-coded user identity in `app/bridge/facade.py`, `core/session.py` (QA-011) |
| `mock` | 110 | Test mocks and adapter fallback modes |
| `fallback` | 135 | Fallback pathways in AI gateway, router, and RAG |
| `legacy` | 62 | References to legacy compatibility paths |

---

## 5. Persistence & Database Baseline
- Authoritative databases: SQLite 3 databases managed under `central_platform/db.py` (`central_platform.db`), `core/db.py`, and `core/session.py`.
- Session persistence utilizes an async thread-pool / queue writer. Durability upon abrupt termination or unhandled crash requires explicit flush verification (QA-010).

---

## 6. Baseline Verification Sign-Off
Baseline metrics and defect mappings established. No code modified during baseline capture.
