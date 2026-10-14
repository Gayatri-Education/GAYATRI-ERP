# Phase 07 Implementation Plan — Portals & Cross-Component Contracts

## 1. Context & Objectives
- **Severity Focus:** P1/P2
- **Objective:** Validate end-to-end data contracts and security boundaries across Student, Teacher, Parent, Admin, and Payment portals.
- **Key Target Areas:**
  - Student Contract: student views enrolled courses, launches session, submits response, accesses curriculum roadmap, and inspects session history without data leakage.
  - Teacher Contract: cohort overview, student mastery inspection, alert resolution, custom instructional directive publishing, and verification that published directives integrate into student RAG and tutor prompt contexts.
  - Parent Contract: strict boundary enforcement (only linked children accessible; private student conversational raw text withheld; high-level mastery summaries exposed according to privacy settings).
  - Admin & RBAC Contract: organizational boundary checks, user provisioning, course governance, knowledge asset publishing, and system kill switch operation.
  - Payment & Fee Contract: fee invoice creation, provider abstraction (Mock/Razorpay/UPI), idempotent completion, and failure rollback semantics.

## 2. Requirements & Acceptance Criteria
1. **Student & Teacher Cross-Portal Sync:**
   - Teacher issues instructional directive for a concept (e.g. emphasize sign convention).
   - Student session on that concept retrieves and honors the active teacher directive in tutor guidance.
2. **Parent Privacy Enforcement:**
   - Parent linked to Child A cannot query Child B.
   - Visibility filtering: `BLOCKED` hides data; `SUMMARY` shows aggregated progress; `DETAILED` shows topics; raw private student chat is never leaked to parent without explicit opt-in.
3. **Admin & Governance Invariants:**
   - Role boundaries: STUDENT role cannot access teacher alerts or fee admin endpoints.
   - TEACHER role cannot manage organizations or trigger platform kill switch.
   - SUPER_ADMIN can manage cross-organization settings.
4. **Payment Abstraction & Durability:**
   - Idempotent transaction processing: duplicate transaction IDs do not double-credit fees.
   - Rollback on provider failure.

## 3. Targeted Test Suite
Create `tests/test_qa_phase07_portal_contracts.py` testing:
- Teacher-to-student instructional directive propagation and tutor integration.
- Parent portal privacy boundaries (child isolation and visibility filtering).
- Role-based contract boundaries (Student vs. Teacher vs. Admin).
- End-to-end fee payment processing, idempotency, and failure rollback.

## 4. Execution Sequence
1. Write this plan to `docs/qa_agent/plans/PHASE_07_PLAN.md`.
2. Verify cross-portal contracts and implement any necessary glue/hardening.
3. Create `tests/test_qa_phase07_portal_contracts.py`.
4. Run focused tests: `pytest tests/test_qa_phase07_portal_contracts.py tests/test_phase27_* tests/test_phase28_* tests/test_phase29_* tests/test_phase30_* tests/test_phase31_* tests/test_phase32_* tests/test_phase34_* -v`.
5. Run full regression suite: `pytest -q`.
6. Record decision DEC-007 in `docs/qa_agent/decisions/DECISION_LOG.md`.
7. Write `docs/qa_agent/reports/PHASE_07_REPORT.md`.
8. Update `docs/qa_agent/MASTER_PROGRESS.md`.
