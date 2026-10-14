# Phase 02 Implementation Plan: Real AI Readiness, Model Execution & Provenance Integrity

**Document:** `docs/qa_agent/plans/PHASE_02_PLAN.md`  
**Phase:** 02  
**Maps to:** GQA-001, GQA-002 (P0 Release Blocker)  
**Status:** IN_PROGRESS  

---

## 1. Architectural Scope & Problem Statement

### 1.1 Root Cause & GQA Findings
- **GQA-001 (P0):** `DeploymentValidator.validate_model_providers()` and related AI health paths infer `HEALTHY` or green readiness from model manifest registration and physical file presence on disk without ever proving that the runtime loader can load the model or that the model can successfully execute inference.
- **GQA-002 (P0):** In `test_phase29_final_platform_audit_master.py`, the AI intelligence audit explicitly asserts `res.execution_provenance in (MOCK, DEGRADED_FALLBACK)` and `real_model == False`. This test verifies fallback observability, but historically masqueraded as a master platform audit without a distinct, mandatory real-model execution test.
- **File presence vs Checksum vs Loader vs Real Inference:** These are fundamentally distinct guarantees. A file may exist on disk, have a valid checksum, yet fail to load due to missing architecture support, invalid GGUF magic header (`GGUF`), out-of-memory errors, library incompatibilities, or generate empty/corrupted/timeout outputs.

---

## 2. Technical Design & Readiness State Model

### 2.1 Formal Readiness State Machine (`ModelReadinessState`)
We expand and strictly enforce the `ModelReadinessState` enum across `central_platform/deployment/validator.py`:
- `UNCONFIGURED`: Manifest missing, empty, or has no model entries.
- `CONFIGURED`: Model registered in manifest, but physical file not yet verified.
- `ARTIFACT_VERIFIED`: Physical artifact exists within resolved root, valid GGUF header/size, and checksum verified (if checksum configured).
- `LOADABLE`: Model binary is loadable by the runtime provider (e.g. `llama-cpp-python` or provider SDK).
- `INFERENCE_VERIFIED`: Model executed controlled probe inference, returning non-empty text with `REAL_MODEL` provenance within bounded timeout.
- `HEALTHY`: Full production readiness confirmed via actual execution.
- `DEGRADED`: Fallback or mock active (strictly prohibited in production tier release gate).
- `MISSING`: Configured local artifact path does not exist on disk.
- `CORRUPT`: File truncated, invalid magic bytes, or checksum mismatch.
- `FAILED`: Loader crash, execution timeout, rate limit, quota exhaustion, or blank/malformed output.

### 2.2 Split Liveness from Bounded Inference Readiness Probe
1. **Lightweight Liveness / Health Check:** Inspects manifest, physical artifact existence, header magic bytes, and checksum without allocating large GPU/CPU tensor buffers unless requested.
2. **Bounded Inference Readiness Probe (`validate_model_inference_probe`):**
   - Controlled, harmless pedagogical test prompt: `"Explain the principle of conservation of energy in one sentence."`
   - Bounded execution: `max_tokens=64`, bounded timeout (default 10.0s).
   - Strict validation:
     - Non-empty completion string.
     - `success == True`.
     - `execution_provenance == ExecutionProvenance.REAL_MODEL`.
     - `mock == False`.
     - Valid latency and token counts.
   - Any empty response, timeout, fallback, mock, or exception immediately fails the probe with `ModelReadinessState.FAILED`.
   - In production mode (`is_production_mode() == True`), `validate_model_providers(probe_inference=True)` is mandatory and fails closed if inference is not verified.

### 2.3 Strict GGUF Header & Path Containment Validation
- Verify path containment to prevent path traversal outside project root.
- Validate file size (> 100 KB) and verify GGUF magic header bytes (`b"GGUF"` at byte 0).
- Truncated files or invalid headers are marked `ModelReadinessState.CORRUPT`.

### 2.4 Separation of Mock/Fallback Observability and Real Model Release Tests
- Document and rename `test_phase29_final_platform_audit_master.py::test_audit_intelligence_ai_gateway_and_resilience` to `test_audit_intelligence_ai_gateway_fallback_observability`.
- Add a dedicated release integration test suite in `tests/test_qa_phase02_ai_execution_integrity.py` exercising:
  - Real model execution probe passes with `INFERENCE_VERIFIED` / `HEALTHY` and `REAL_MODEL`.
  - Missing file, truncated file, invalid GGUF header, and checksum mismatch fail with exact corresponding readiness states.
  - Runtime loader failure and inference timeout fail closed.
  - Gateway error normalization masks secret keys and student prompts.
  - Release evidence metadata includes commit SHA, model name/revision, model checksum, provider type, latency, and provenance.

---

## 3. Implementation Steps

1. **Update `central_platform/deployment/validator.py`:**
   - Add missing states (`UNCONFIGURED`, `ARTIFACT_VERIFIED`, `INFERENCE_VERIFIED`) to `ModelReadinessState`.
   - Add GGUF magic header check (`b"GGUF"`) and path containment validation.
   - Implement `validate_model_inference_probe(self, timeout_seconds: float = 10.0) -> ValidationResult`.
   - Update `validate_model_providers(self, probe_inference: bool = False)`:
     - In production mode, require `probe_inference=True` or verify that file presence alone NEVER yields `HEALTHY`. Mere file presence yields at most `ARTIFACT_VERIFIED` or `LOADABLE`. Only verified inference can yield `INFERENCE_VERIFIED` / `HEALTHY`.
2. **Update `central_platform/ai/adapters.py` & `central_platform/ai/gateway.py`:**
   - Ensure gateway execution and error envelopes never leak API keys or sensitive student data.
   - Preserve `ExecutionProvenance` through every layer and serialization dictionary.
3. **Update `tests/test_phase29_final_platform_audit_master.py`:**
   - Explicitly document the fallback observability contract.
   - Add companion audit test verifying real-model execution requirement for production readiness tier.
4. **Expand `tests/test_qa_phase02_ai_execution_integrity.py`:**
   - Implement all 10 required test cases from Section 186-226 of the master fix plan.
5. **Verify full repository regression (1435+ tests).**
6. **Produce Phase 02 completion report and update tracking.**
