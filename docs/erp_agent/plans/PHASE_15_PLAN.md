# Phase 15 Plan — Local SLM and RAG Operational Assistant

**Document:** `docs/erp_agent/plans/PHASE_15_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 15 — Local SLM and RAG Operational Assistant  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 15 verifies the local-first AI and RAG architecture:
1. **Model Identity, Integrity & Checksums:** GGUF magic header validation, checksum verification, truncated/corrupt file rejection, and path traversal detection.
2. **Explicit Execution Provenance:** Distinguish real model execution from mocks or degraded fallbacks. In production release tier, mock adapters fail closed.
3. **Local-Only Provider Enforcement:** Fail-closed when providers are unavailable; outbound network leaks prohibited; kill-switch returns explicit HTTP 503 rather than silent mock fallback.
4. **Scoped Knowledge Retrieval (RAG):** Multi-tenant organization and course isolation. Private courses are strictly shielded; class-scoped and student-targeted remedial material isolation verified.
5. **Grounding & Provenance:** Stable chunk citations with source ID, chapter, and page number. Zero hallucinations on empty retrieval corpora.
6. **Indirect Prompt Injection Neutralization:** Dangerous executable markers inside ingested RAG documents neutralized; non-executable data encapsulation blocks enforced.
7. **Advisory Role Safety Invariant:** AI produces suggestions requiring human review; cannot execute unapproved financial, payroll, or academic mutations.

---

## 2. Likely Files & Scope Boundary

- `central_platform/ai/gateway.py` (`AIGatewayService`)
- `central_platform/ai/adapters/` (`LocalGGUFAdapter`, `CloudAdapter`, `MockAdapter`)
- `central_platform/rag/` (`RAGPipeline`, `ScopedRAGRetriever`, `DocumentIngestion`)
- `central_platform/models/schema.py` (`AIModel`, `AIProvider`, `ExecutionLog`)
- `tests/test_qa_phase02_ai_execution_integrity.py`
- `tests/test_qa_phase04_ai_contracts.py`
- `tests/test_qa_phase07_rag_integrity_grounding.py`
- `tests/test_phase06_scoped_rag_authorization.py`
- `tests/test_phase14_ai_governance.py`

---

## 3. Targeted Test Scenarios

1. Verify GGUF header validation and corrupt model rejection (`test_invalid_gguf_magic_header`).
2. Verify production mode fails closed on missing models or mock fallbacks (`test_local_gguf_adapter_fails_closed_in_production`).
3. Verify kill-switch returns HTTP 503 instead of 200 (`test_ai_execution_failure_under_killswitch_never_returns_http_200`).
4. Verify empty corpus in production is unhealthy (`test_empty_corpus_in_production_is_not_healthy`).
5. Verify cross-tenant and cross-course RAG isolation (`test_cross_course_isolation`, `test_multi_tenant_organization_isolation`).
6. Verify indirect prompt injection neutralization in uploaded documents (`test_indirect_prompt_injection_neutralization_in_documents`).
7. Verify course offering grants partner organization RAG access without global leaks (`test_active_offering_grants_access_to_partner_org`).

---

## 4. Exit Criteria (Binary Gate)

- [ ] Real model execution distinguished from mocks with immutable provenance.
- [ ] Emergency kill-switch and provider fallback fail-closed behavior verified.
- [ ] Multi-tenant RAG isolation and citation grounding verified.
- [ ] Anti-prompt injection defense and data encapsulation verified.
- [ ] `docs/erp_agent/reports/PHASE_15_REPORT.md` and `docs/erp_agent/regressions/PHASE_15_REGRESSION.md` generated with passing evidence.
