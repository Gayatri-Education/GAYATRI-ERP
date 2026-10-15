# Phase 15 Regression Evidence Log

**Document:** `docs/erp_agent/regressions/PHASE_15_REGRESSION.md`  
**Execution Phase:** Phase 15 — Local SLM and RAG Operational Assistant  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Test Execution Commands & Outputs

- **Command:** `pytest tests/test_qa_phase02_ai_execution_integrity.py tests/test_qa_phase04_ai_contracts.py tests/test_qa_phase07_rag_integrity_grounding.py tests/test_phase06_scoped_rag_authorization.py tests/test_phase14_ai_governance.py`
- **Exit Code:** `0`
- **Result:** 58 passed, 0 failures, 0 errors, 0 skipped, 1 warning in 10.32s

---

## 2. Test Verification Matrix

| Area | Assertion Details | Result |
|---|---|---|
| Model Provenance & Integrity | GGUF magic header validation, corrupt file rejection, checksum verification | PASSED |
| Production Release Safety | Release tier requires real models; mock fallbacks fail closed in production | PASSED |
| AI Gateway & Kill Switch | Kill switch returns HTTP 503; provider timeouts map to 504; rate limits map to 429 | PASSED |
| Ingestion & Input Safety | Rejection of unsupported extensions, path traversal, decompression bombs, and corrupt files | PASSED |
| Citation Grounding & Stability | Stable chunk IDs, chapter/page citations, zero hallucinations on empty corpus | PASSED |
| Scoped RAG Isolation | Multi-tenant org isolation, cross-course isolation, class-level notes, and remedial targeting | PASSED |
| Prompt Injection Defense | Neutralization of indirect prompt injection in RAG docs; non-executable data encapsulation | PASSED |
| Model Governance & Telemetry | Request routing, automatic fallback upon primary killed, telemetry aggregation | PASSED |
