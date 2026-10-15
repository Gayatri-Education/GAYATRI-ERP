# Phase 01 Plan — Requirements Traceability, Threat Model and Architecture Decisions

**Document:** `docs/erp_agent/plans/PHASE_01_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 01 — Requirements Traceability, Threat Model and Architecture Decisions  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 01 codifies the architectural rules, security boundaries, threat mitigations, and formal requirements disposition for the entire transformation:
1. Reconcile and finalize the full 67-requirement traceability matrix across Sections 5.A through 5.J.
2. Record authoritative architecture decisions in `docs/erp_agent/DECISIONS.md` covering:
   - Tenant/branch hierarchy & server-derived authorization.
   - Authentication, token revocation across multi-worker setups, and session lifetimes.
   - Money precision (paise / exact integer / decimal) and immutable append-only ledger postings.
   - Offline vs online mode truthfulness and external queue outbox guarantees.
   - Sync consistency model (single-writer SQLite vs coordinated sync) and conflict resolution.
   - Hardware adapter boundaries (RFID, biometrics, GPS) with clear isolation of physical dependencies.
   - Local AI guardrails: advisory-only outputs, deterministic validation, and human review gates for sensitive mutations.
   - Privacy, child data protection, and biometric opt-in consent controls.
3. Perform comprehensive STRIDE-based Threat Modeling in `docs/erp_agent/THREAT_MODEL.md` covering:
   - Tenant breakout & header spoofing (`X-Branch-ID`).
   - Insecure Direct Object References (IDOR) across student, fee, mark, and staff records.
   - Malicious file uploads, zip bombs, and path traversal.
   - Private database theft & WAL encryption at rest.
   - Replayed device punches and duplicate payment webhooks.
   - QR code tampering, signature forgery, and certificate reissuance.
   - Sync event replay, out-of-order delivery, and silent overwrites.
   - Child record and personal telemetry leakage.
4. Verify all threat mitigations with existing and targeted security tests.

---

## 2. Artifacts to Generate / Update

- `docs/erp_agent/plans/PHASE_01_PLAN.md` (this file)
- `docs/erp_agent/DECISIONS.md` (complete architectural decisions record)
- `docs/erp_agent/THREAT_MODEL.md` (comprehensive threat analysis)
- `docs/erp_agent/FEATURE_TRACEABILITY.md` (reconciled dispositions)
- `docs/erp_agent/regressions/PHASE_01_REGRESSION.md` (security regression tests evidence)
- `docs/erp_agent/reports/PHASE_01_REPORT.md` (Phase 01 completion report)
- `docs/erp_agent/MASTER_PROGRESS.md` (updated tracker)

---

## 3. Targeted Test Suites for Phase 01

- `tests/test_qa_phase08_security_adversarial.py` (Tenant isolation, IDOR, path traversal, SQL injection)
- `tests/test_qa_phase12_security_privacy_xss.py` (XSS sanitization, upload safety, security headers)
- `tests/test_qa_phase05_auth_revocation_ratelimit.py` (Token revocation, rate limiting)
- `tests/test_qa_phase03_finance_integrity.py` (Webhook signature verification, ledger balance, idempotency)
- `tests/architecture/test_anti_chemistry_coupling.py`, `test_anti_demo_roster.py`, `test_anti_legacy_imports.py` (Architecture invariants)

---

## 4. Exit Criteria (Binary Gate)

- [ ] Every requirement in `docs/erp_agent/FEATURE_TRACEABILITY.md` has an explicit disposition (`VERIFIED_EXISTING`, `IMPLEMENT`, `FIX`, `DEFER_WITH_REASON`, or `BLOCKED`).
- [ ] Comprehensive `docs/erp_agent/DECISIONS.md` entries exist for all 10 architectural domains.
- [ ] Formal `docs/erp_agent/THREAT_MODEL.md` document exists covering the 8 threat vectors with mitigations and test mappings.
- [ ] Security and authorization regression test suites pass with 100% success.
- [ ] `docs/erp_agent/reports/PHASE_01_REPORT.md` links evidence and confirms zero unresolved architectural conflicts.
