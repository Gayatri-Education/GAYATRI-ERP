# Gayatri School OS — Architecture and Engineering Decision Log

This log permanently records all formal architectural, engineering, security, and governance decisions made during the development and production readiness lifecycle of Gayatri School OS (`Gayatri-Education/GAYATRI-ERP`).

---

## Decision Record Index

| Decision ID | Date | Status | Phase | Title |
|---|---|---|---|---|
| **DEC-P00-01** | 2026-10-14 | ACCEPTED | Phase 00 | Transition to Dedicated Repository `Gayatri-Education/GAYATRI-ERP` |
| **DEC-P00-02** | 2026-10-14 | ACCEPTED | Phase 00 | Adoption of `DEVELOPMENT.md` as Mandatory Execution Contract |
| **DEC-P00-03** | 2026-10-14 | ACCEPTED | Phase 00 | Preservation of Certified Platform Baseline and Sandbox Test Isolation |

---

## DEC-P00-01: Transition to Dedicated Repository `Gayatri-Education/GAYATRI-ERP`

- **Date:** 2026-10-14  
- **Status:** ACCEPTED  
- **Context:**  
  The project is expanding from the core Gayatri AI tutoring platform into the complete **Gayatri School OS** (unifying the AI Learning Suite and the School Operations / ERP Suite). A dedicated repository was established at `https://github.com/Gayatri-Education/GAYATRI-ERP` to maintain this integrated platform, while retaining `https://github.com/Gayatri-Education/Gayatri` as the upstream reference repository.
- **Decision:**  
  Configure git remotes in the workspace with `origin` pointing to `https://github.com/Gayatri-Education/GAYATRI-ERP.git` and `upstream` pointing to `https://github.com/Gayatri-Education/Gayatri.git`. All ERP feature development, documentation, and phase-by-phase releases will be maintained directly on `GAYATRI-ERP`.
- **Consequences:**  
  Clean isolation of the ERP expansion while maintaining complete commit history and synchronization capability with upstream platform improvements.

---

## DEC-P00-02: Adoption of `DEVELOPMENT.md` as Mandatory Execution Contract

- **Date:** 2026-10-14  
- **Status:** ACCEPTED  
- **Context:**  
  `DEVELOPMENT.md` specifies strict non-negotiable engineering principles for Gayatri School OS:
  1. No demo-only / mock business workflows in production.
  2. Universal feature development protocol (every ERP feature must have a full `SCOPE.md` including state machines, permissions, offline policy, and idempotency before code edits).
  3. Strict phase execution gate sequence from Phase 00 to Phase 09.
  4. Single source of truth for all domain entities.
- **Decision:**  
  Formally adopt `DEVELOPMENT.md` as the binding product, engineering, and QA contract governing all development. Every phase requires written plans, focused tests, full regression runs, and auditable evidence packs before exit gates can pass.
- **Consequences:**  
  Zero phase-hopping or false green status. High architectural rigor and durability across both schools and coaching institutes.

---

## DEC-P00-03: Preservation of Certified Platform Baseline and Sandbox Test Isolation

- **Date:** 2026-10-14  
- **Status:** ACCEPTED  
- **Context:**  
  The repository enters this expansion with 1,562 tests created during prior hardening phases. Prior defects (such as autouse fixtures mutating root databases, weak secret fallbacks, and process-local token revocation) were resolved in those suites.
- **Decision:**  
  Maintain all existing test suites and fixtures (`ensure_isolated_test_database`) intact. New ERP domain models, routes, and services must integrate with canonical platform configuration, database abstractions, and authentication dependencies without weakening existing security or educational assertions.
- **Consequences:**  
  Regression safety is preserved across all AI tutoring, RAG, auth, and persistence domains as ERP tables and services are incrementally introduced.
