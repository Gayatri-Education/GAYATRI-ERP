# Phase 03 Implementation Plan — RAG Correctness, Grounding & Knowledge Integrity

## 1. Context and Objective
Resolve QA-004, QA-006, and QA-007:
1. Prevent silent error suppression in legacy RAG fallback (`_legacy_fallback_query`), ensuring parse/load failures are logged, classified, and associated with source files.
2. Enhance RAG scoring beyond simple token overlap to support semantic n-gram matching, conceptual synonym/stem overlap, and reciprocal reranking while preserving tenant isolation and metadata constraints.
3. Harden the RAG health probe in `DeploymentValidator` so that an empty dictionary (`RAG_EMPTY` with 0 results) cannot masquerade as healthy retrieval in production.
4. Verify end-to-end ingestion robustness (corrupt PDFs, malformed JSON, empty files, duplicate sources).

## 2. Dependencies and Affected Modules
- Service: `central_platform/rag/service.py`
- Ingestion & Parsers: `central_platform/rag/parsers.py`, `central_platform/rag/cleaner.py`
- Security Sanitizer: `central_platform/rag/security.py`
- Validator: `central_platform/deployment/validator.py`
- Tests: `tests/test_phase06_rag_integrity_remediation.py`, `tests/test_phase9_rag.py`, `tests/test_qa_phase03_rag_correctness.py`

## 3. Scope of Tasks
1. **03.1 Trace Ingestion Pipeline & Document Contracts:**
   - Ingestion lifecycle: Upload -> File Validation -> Content Parser -> Smart Chunker -> Metadata Binding -> Platform DB Storage -> Approval & Publishing -> Retrieval.
2. **03.2 Test Ingestion Failures & Corrupt Source Handling:**
   - Test empty files, malformed JSON, corrupt PDFs, oversized files, missing required fields.
3. **03.3 Fix Legacy RAG Silent Fallback Errors (QA-007):**
   - Replace broad `except Exception: continue` in `_legacy_fallback_query`.
   - Log errors with filename, error category, and trace details.
   - Record skipped/corrupt files in diagnostics metadata of return payload.
4. **03.4 Validate Tenant and Metadata Isolation:**
   - Verify course scoping, visibility scopes (`course`, `public`, `institution`, `class`, `private`), and student/tenant boundary enforcement.
5. **03.5 Strengthen Semantic Retrieval Architecture (QA-006):**
   - Incorporate hybrid scoring:
     - Lexical term overlap (BM25-style frequency normalization).
     - Character/word n-gram semantic similarity (fuzzy & conceptual synonym support).
     - Metadata & concept hierarchy matching bonuses.
     - Authority weighting for verified textbooks (NCERT / approved curriculum).
   - Weighted reciprocal reranker.
6. **03.6 Validate Evidence Integrity & Grounding:**
   - Ensure every retrieved item includes complete citation, source_id, chunk_id, provenance_type, section, score, and safe data context.
7. **03.7 Harden Deployment Validator RAG Health Probe (QA-004):**
   - In `DeploymentValidator.validate_health_checks()`:
     - Verify retriever initialization.
     - Verify knowledge asset presence.
     - Execute live probe query and verify `status == "RAG_OK"`, `count > 0`, and provenance exists.
     - In production mode, reject empty results (`RAG_EMPTY`) as `DOWN`.
8. **03.8 Focused Tests & Full Regression Run:**
   - Run focused RAG tests and full repository regression suite.

## 4. Regression Risks & Mitigations
- *Risk:* Existing tests expecting specific score numbers or `_legacy_fallback_query` behavior.
  - *Mitigation:* Preserve existing return schema and confidence thresholds (`confidence_threshold: float = 0.15`). Ensure hybrid scoring scales strictly within `[0.0, 1.0]`.
