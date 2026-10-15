# GAYATRI-ERP — Remediation Issue Register (QA-001 through QA-015)

**Governing Contract:** [`../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md)  
**Canonical Tracker:** [`REMEDIATION_MASTER_TRACKER.md`](REMEDIATION_MASTER_TRACKER.md)  
**Status:** ACTIVE  

| Issue ID | Category / Target Behavior | Priority | Status | Verification Plan / Invariant | Phase |
|---|---|:---:|:---:|---|:---:|
| **QA-001** | Production config test isolation & missing DB mask | P0 | IN_PROGRESS | Isolate temp DB paths and verify exact reload/debug/checksum assertions | 01 |
| **QA-002** | Synthetic parent metrics & placeholder student data | P1 | NOT_STARTED | Load real data from tenant-scoped DB services; honest empty/error states | 02 |
| **QA-003** | Toast-only fee admin & fabricated invoice counts | P1 | NOT_STARTED | Database-backed atomic billing runs, deduplication, verified receipt prints | 03 |
| **QA-004** | Payment webhook tenant spoofing & org-default fallback | P1 | NOT_STARTED | Gateway-derived tenant binding, constant-time HMAC check, double-entry ledger | 04 |
| **QA-005** | Edge device auth bypass & silent invalid enum conversion | P1 | NOT_STARTED | Registered device credentials, 422 on invalid enum, atomic punch batches | 05 |
| **QA-006** | Ad-hoc role comparison & route-level tenant leaks | P1 | NOT_STARTED | Unified RBAC normalization across all routes, zero cross-tenant IDOR | 06 |
| **QA-007** | Invalid task type conversion & synthetic tutor context | P1/P2 | NOT_STARTED | 422 on invalid task type, real student context, scoped RAG grounding | 07 |
| **QA-008** | Database lifecycle, transactions & singleton isolation | P1 | NOT_STARTED | Explicit instance-scoped DB containers, atomic multi-table rollbacks | 08 |
| **QA-009** | Disconnected UI buttons & unverified success toasts | P1/P2 | NOT_STARTED | Full UI-to-API-to-DB E2E integration with refreshed postcondition | 09 |
| **QA-010** | Inconsistent dependency lock & packaging entrypoints | P2 | NOT_STARTED | Unified lock usage, cross-platform launcher scripts, SHA-256 release manifest | 10 |
| **QA-011** | Unverifiable hardware & cloud provider declarations | P2 | NOT_STARTED | Truthful BLOCKED/SIMULATED hardware labeling, offline local outbox sync | 11 |
| **QA-012** | Competing documentation, trackers & stale claims | P1 | NOT_STARTED | Consolidate single canonical source of truth; reconcile claims vs evidence | 12 |
| **QA-013** | Final forensic review, complete regression & release gate | P0/P1 | NOT_STARTED | 100% CI pass rate across platforms, zero P0/P1 defects, signed release | 13 |
