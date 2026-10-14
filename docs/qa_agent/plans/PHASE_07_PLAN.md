# Phase 07 Implementation Plan: RAG Ingestion, Retrieval Integrity, Grounding and Health

**Phase:** Phase 07  
**Date:** 2026-10-14  
**Target Defects:**
- `GQA-012` (P1): Tautological RAG health probe derived from first published chunk text without semantic recall verification.
- Parts of `GQA-001`: Genuine RAG subsystem operational readiness verification.
- Parts of `GQA-013`: Indirect prompt injection and untrusted document content sanitization.

---

## 1. Objectives & Scope

1. **Ingestion Lifecycle Hardening**:
   - Explicitly validate uploads by allowed extension (`.pdf`, `.docx`, `.doc`, `.html`, `.htm`, `.md`, `.markdown`, `.txt`, `.json`), MIME/magic byte header checks (`%PDF-`, `PK\x03\x04`), max file size (10 MB), path traversal checks (`..`, `/`, `\`), and prohibition of executable/dangerous scripts.
   - Ensure ingestion fails transparently with structured error reporting whenever parsing, chunking, cleaning, persistence, or validation fails.
   - Enforce that empty or partial indices can never be published or marked healthy.

2. **Remediate Tautological Health Probe (GQA-012)**:
   - In `central_platform/deployment/validator.py`: Retain the operational retrieval liveness check but explicitly label it as an operational smoke test (`probe_type="operational_smoke_test"`, `is_smoke_test=True`).
   - Introduce an independent RAG Golden Query Set and evaluation harness (`central_platform/rag/golden.py` or within `RAGService` and `DeploymentValidator`).
   - The golden set is authored completely independently of stored chunks, covering:
     - Direct keyword matching
     - Paraphrased conceptual queries (non-overlapping vocabulary)
     - Spelling and morphological variations
     - Indirect conceptual questions
     - Subject & course boundary isolation
     - Unsupported/negative out-of-domain questions (must yield empty/unsupported, zero hallucinated citations)

3. **Grounding & Citation Stability**:
   - Verify every returned evidence card contains stable identifiers (`chunk_id`, `source_id`, `chapter`, `page`, `section`, `provenance_type`).
   - Format authoritative citations without inventing citations when evidence is missing.
   - Distinguish corpus origin: `"corpus_source": "DATABASE_PUBLISHED"` vs `"FALLBACK_FILESYSTEM"`.

4. **Multi-Tenant Filter-Before-Ranking & Scope Enforcement**:
   - Enforce that course knowledge queries strictly filter chunks prior to scoring and ranking, preventing cross-tenant and cross-course leaks.
   - For global/unscoped queries, ensure non-public sources from other organizations cannot be accessed.

5. **Retrieval Strategy Transparency**:
   - Expose explicit `retrieval_strategy` (e.g. `HYBRID_LEXICAL_SEMANTIC`, `LEXICAL_BM25`, `VECTOR_DENSE`) and `vector_backend_available` status in every query response.
   - Never claim semantic vector retrieval if only lexical scoring or character n-gram scoring is active.

6. **Stale Index Detection & Cascade Cleanup**:
   - Fix `delete_rag_source` in `PlatformDatabase` to delete corresponding chunks from `rag_chunks` to prevent lingering orphaned/stale chunks.
   - When a source is re-ingested with modified content, transition status to `READY_FOR_REVIEW`/`INGESTED` and invalidate old chunks immediately.

7. **Untrusted Document Sanitization (Indirect Injection Defense)**:
   - Expand `RAGSecuritySanitizer` to detect and neutralize indirect prompt injections embedded in ingested files (e.g., Markdown images for exfiltration, shell/script injection payloads, instructions to disregard previous instructions, fake system prompts).
   - Enforce that all retrieved text is strictly wrapped in non-executable data encapsulation blocks (`<rag_evidence_data ... role="data_only">`).

---

## 2. Implementation Steps

### Step 1: Ingestion & Validation Hardening
- In `central_platform/rag/parsers.py`:
  - Enhance `PDFParser`, `DocxParser`, and `StructuredJSONParser` with explicit validation of magic bytes and structure.
  - Reject corrupt PDFs, invalid DOCX ZIPs, and malformed JSON with clear, typed exceptions (`ValueError` with descriptive reason).
- In `central_platform/rag/service.py`:
  - Hardened file validation: extension, magic bytes, size limit, path traversal.
  - Fail closed on parser errors.
  - Re-indexing workflow: ensure status reverts on content modification.

### Step 2: Database Cascade Cleanup
- In `central_platform/db.py`:
  - Update `delete_rag_source(source_id)` to atomically delete from `rag_chunks` where `source_id = ?` along with `rag_sources`.

### Step 3: Retrieval Strategy & Metadata Transparency
- In `central_platform/rag/service.py`:
  - Expose `retrieval_strategy`, `corpus_source`, and `vector_backend_available` in `RAGService.query` and `_legacy_fallback_query`.
  - Provide strategy breakdown on individual result items (`strategy_used`: `LEXICAL`, `SEMANTIC_NGRAM`, or `HYBRID`).

### Step 4: Golden Query Set & Evaluation Harness
- Create `central_platform/rag/golden.py`:
  - Define `RAGGoldenQuery`, `GoldenQueryCategory`, `RAGEvaluationReport`.
  - Define canonical golden query test cases across categories.
  - Implement `evaluate_rag_golden_set(service, course_id, golden_set=None)` providing precision, recall, grounding rate, and negative rejection rate metrics.

### Step 5: Deployment Validator Hardening (GQA-012)
- In `central_platform/deployment/validator.py`:
  - In `validate_health_checks`, label chunk-derived retrieval probe explicitly as `operational_smoke_test`.
  - Add `validate_rag_integrity(golden_set=None, min_grounding_rate=0.8)` check to `DeploymentValidator`.
  - Enforce production gate: empty corpus or failing golden set marks RAG as DOWN/FAIL in production.

### Step 6: Indirect Injection Hardening
- In `central_platform/rag/security.py`:
  - Expand patterns for indirect injection (Markdown exfiltration, system directives, payload wrapping).

---

## 3. Verification Strategy & Exit Gate

1. **Author Focused Test Suite**: `tests/test_qa_phase07_rag_integrity_grounding.py` covering:
   - Empty corpus in production reporting DOWN.
   - Ingestion failure modes: corrupt PDF/DOCX magic bytes, malformed JSON, dangerous extensions, path traversal.
   - Independent golden query evaluation: paraphrasing, spelling errors, indirect questions, negative unsupported rejection.
   - Multi-tenant cross-course isolation (filter-before-ranking).
   - Cascade deletion of chunks on source deletion.
   - Retrieval strategy transparency (no false claims of vector retrieval).
   - Indirect prompt injection neutralization in document text.
2. **Execute Full Repository Regression**:
   - `pytest -q --tb=short` to guarantee 100% test pass rate across all test suites.
3. **Artifacts & Documentation**:
   - `docs/qa_agent/reports/PHASE_07_REPORT.md`
   - Update `docs/qa_agent/decisions/DECISION_LOG.md` (DEC-019)
   - Update `docs/qa_agent/MASTER_PROGRESS.md`
