# GAYATRI-ERP QA Issue Register

**Status:** Initial seeded register; every item must be re-verified against the current repository before code changes.  
**Canonical tracker:** [`PROGRESS_TRACKER.yaml`](PROGRESS_TRACKER.yaml)  
**Execution guide:** [`../development/DEVELOPMENT_GUIDE.md`](../development/DEVELOPMENT_GUIDE.md)

| ID | Initial target / suspected behavior | Priority | Status | Required proof | Phase |
|---|---|---:|---|---|---|
| ERP-001 | Payment webhook signature verification and trust boundary | P0 | NEEDS_REVALIDATION | Invalid/missing signature cannot mutate financial state; valid signature accepted | 03 |
| ERP-002 | Payment/invoice/order/ledger/event atomicity and idempotency | P0 | NEEDS_REVALIDATION | Transaction rollback and duplicate/concurrency tests | 02–03 |
| ERP-003 | Token revocation persistence may fail open or report false success | P1 | FIXED_VERIFIED | DB failure tests for validation, revoke, logout | 01 |
| ERP-004 | Demo token / synthetic identity production exposure | P1 | FIXED_VERIFIED | Production configuration and unauthorized identity tests | 01 |
| ERP-005 | Independent DB factories / stale module-global services | P1 | NEEDS_REVALIDATION | Dependency graph and separate DB path integration tests | 02 |
| ERP-006 | Health endpoint may report fabricated count or healthy state | P1/P2 | NEEDS_REVALIDATION | DB/dependency failure tests and truthful metrics | 10 |
| ERP-007 | Billing generation UI may be toast-only | P1/P2 | NEEDS_REVALIDATION | Click-to-persisted-billing E2E test | 05 |
| ERP-008 | Outstanding report export may be toast-only | P2 | NEEDS_REVALIDATION | Export content/authorization/error E2E test | 05 |
| ERP-009 | Receipt printing may not fetch/verify persisted receipt | P1/P2 | NEEDS_REVALIDATION | Authorized persisted receipt retrieval test | 03, 05 |
| ERP-010 | Student review action may be toast-only | P1/P2 | NEEDS_REVALIDATION | Review lifecycle and restart persistence test | 06 |
| ERP-011 | Teacher Copilot action may not call backend | P1/P2 | NEEDS_REVALIDATION | Request/result/error E2E test | 05 |
| ERP-012 | AI execution/provider control endpoints may lack effective authorization | P1 | FIXED_VERIFIED | Role and tenant negative tests for all AI routes | 01, 04 |
| ERP-013 | AI failures may be encoded as HTTP 200 | P1/P2 | NEEDS_REVALIDATION | API contract tests for provider failures | 04, 11 |
| ERP-014 | Unknown provider type may silently default to mock | P2 | FIXED_VERIFIED | Invalid enum must reject without provider mutation | 01, 04 |
| ERP-015 | Legacy API endpoints may bypass canonical auth/persistence | P1 | FIXED_VERIFIED | Route inventory, auth matrix, restart tests | 01, 09 |
| ERP-016 | Assessment bank may serve fallback sample questions in empty production state | P1/P2 | NEEDS_REVALIDATION | Empty-bank and explicit demo-mode tests | 07 |
| ERP-017 | Blocked tutor turn may look like a successful completed turn | P2 | NEEDS_REVALIDATION | Status contract and progress non-mutation test | 08 |
| ERP-018 | Dynamic `innerHTML` / inline handler interpolation may enable injection | P2 | NEEDS_REVALIDATION | Contextual escaping and XSS regression tests | 05, 12 |
| ERP-019 | Optional/missing bearer token edge cases | P1 | FIXED_VERIFIED | Route-by-route anonymous/malformed-header tests | 01 |
| ERP-020 | Broad exceptions/defaults may mask failure | P1/P2 | NEEDS_REVALIDATION | Failure injection and log/response assertions | 10–12 |
| ERP-021 | Tests may mutate a developer/shared database | P1/P2 | NEEDS_REVALIDATION | Test DB isolation and safe fixture tests | 00, 02 |
| ERP-022 | Critical features lack sufficient restart, negative-path, or E2E evidence | P1 | NEEDS_REVALIDATION | Feature matrix linked to real E2E evidence | 00, 14 |

## Evidence record template

For each finding, add a subsection or link to a dedicated GitHub issue:

- **Evidence status:** `CONFIRMED`, `REPRODUCED`, `LIKELY`, `NEEDS_RUNTIME_EVIDENCE`, `FIXED_VERIFIED`, `PARTIALLY_FIXED`, `BLOCKED`, or `REGRESSED`
- **Severity and rationale:**
- **Baseline commit:**
- **Affected files / line ranges:**
- **Observed behavior:**
- **Expected behavior / invariant:**
- **Reproduction command and environment:**
- **Before-fix failing test / artifact:**
- **Root cause:**
- **Fix commit / PR:**
- **After-fix tests and results:**
- **Regression coverage:**
- **Residual risk / manual verification:**
- **Verified by / date:**

Do not mark a finding fixed until a regression test proves the prior behavior fails and the corrected behavior passes, with relevant integration evidence. Update status in this file and the YAML tracker in the same PR.
