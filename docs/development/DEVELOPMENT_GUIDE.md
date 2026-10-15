# GAYATRI-ERP — Phase-by-Phase Development, QA, Repository Cleanup & GitHub Progress Guide

**Repository:** `https://github.com/Gayatri-Education/GAYATRI-ERP`  
**Default branch:** `main`  
**Purpose:** Give a local AI coding agent a controlled, evidence-driven execution contract for making the ERP production-ready.  
**Mode:** Diagnose, plan, implement, test, debug, verify, document, and checkpoint one phase at a time.  
**Important:** This guide is not proof that any feature works. The agent must independently inspect the checked-out code and reproduce findings.

---

## 0. Non-negotiable execution contract

The agent must follow this loop for **every phase**, without exception:

1. **Read the current state** — inspect the current branch, working tree, latest commit, progress tracker, issue register, README, phase notes, relevant code, migrations, configuration, and tests. Do not trust a prior agent's completion statement without evidence.
2. **Map the scope** — trace UI → API/client → authorization → service/domain logic → database/event/side effect → response/UI state. Identify callers, consumers, dependencies, and regressions likely to occur.
3. **Plan before coding** — write the phase plan, files expected to change, acceptance criteria, targeted tests, negative tests, security/privacy checks, migration/rollback concerns, and rollback strategy into the phase log and GitHub issue/PR. Wait for human approval if the repository owner or task explicitly requires approval. Do not silently skip approval.
4. **Reproduce first** — add or run a failing test that demonstrates each in-scope defect. If reproduction is impossible, record the exact reason and mark it `BLOCKED` or `NEEDS_RUNTIME_EVIDENCE`; do not invent a reproduction.
5. **Implement the smallest safe change** — no unrelated refactors, broad rewrites, feature removals, API contract changes, dependency upgrades, schema changes, or file deletion unless included in the approved plan.
6. **Test the changed behavior** — run focused unit, integration, API, UI, authorization, persistence, and failure-path tests as applicable. Test both success and failure paths.
7. **Debug until green or blocked** — inspect real stack traces, logs, HTTP status/body, database rows, emitted events, browser/desktop console output, and side effects. Fix root causes, not just assertions. Never weaken, skip, xfail, mock away, or delete a failing test merely to make the suite green.
8. **Run risk-based regression tests** — test the direct callers and shared dependencies. Run the broad suite at phase milestones and mandatory release gates. Record exact commands, exit codes, counts, skipped tests, and environment.
9. **Verify independently** — re-run the reproduction test, inspect the final diff, scan for security/data-integrity regressions, and confirm the behavior from the actual user-visible path. A mocked unit test alone is not proof of end-to-end behavior.
10. **Update records** — update `docs/qa/PROGRESS_TRACKER.yaml`, `docs/qa/ISSUE_REGISTER.md`, the phase log, and README when user-facing setup/architecture/status changes. Mark a finding fixed only with linked test evidence.
11. **Commit and publish** — use a dedicated branch, small reviewable commits, push to GitHub, and open/update a pull request. Put phase ID, issue IDs, test commands/results, and known limitations in commit/PR notes. Never commit secrets, private data, model weights, generated databases, credentials, or local environment files.
12. **Gate the phase** — move to the next phase only when every required exit criterion is met, evidence is stored, GitHub progress is updated, and the working tree is clean. Otherwise keep the phase open and record the blocker.

**Never:** claim “fixed” because code compiles; claim “production-ready” because unit tests pass; infer that a toast means an operation happened; treat HTTP 200 as business success; treat an empty/fallback dataset as real data; or treat GitHub Actions green as proof that all important workflows work.

## 1. Safety, scope and repository governance

### 1.1 Start with a safe workspace

- Record `git status --short --branch`, `git rev-parse HEAD`, `git log -5 --oneline`, and the remote URL.
- Confirm the remote is `Gayatri-Education/GAYATRI-ERP`.
- Do not work directly on `main`. Create a branch such as `qa/erp-001-payment-webhook-integrity` or `dev/phase-00-baseline`.
- Preserve all user changes. If the working tree is not clean, inspect and save the state before proceeding; never overwrite changes.
- Do not run destructive migrations, cleanup scripts, data resets, or deletion commands against production or a database whose environment is not proven to be test-only.
- Use synthetic fixtures and isolated temporary test databases for tests.
- Before any cleanup, make a tracked inventory and verify whether each candidate is referenced by code, packaging, CI, docs, deployment, runtime imports, tests, or external consumers.

### 1.2 Evidence labels

Use these labels in every audit/progress record:

- `CONFIRMED` — source or runtime evidence directly demonstrates the behavior.
- `REPRODUCED` — a test or controlled runtime procedure reliably reproduces it.
- `LIKELY` — strong code-path evidence, but runtime path not yet reproduced.
- `NEEDS_RUNTIME_EVIDENCE` — cannot be resolved from source/tests alone.
- `NOT_REPRODUCIBLE` — attempted with recorded commands/environment and not reproduced.
- `FIXED_VERIFIED` — regression test fails before and passes after the change, with relevant integration evidence.
- `PARTIALLY_FIXED` — some paths fixed, other paths remain.
- `BLOCKED` — external dependency, access, environment, or decision prevents safe progress.
- `REGRESSED` — previously verified behavior now fails.

Severity:
- `P0` — exploitable security issue, payment/data corruption, cross-tenant disclosure, or release-stopping integrity failure.
- `P1` — major feature failure, auth/privacy weakness, loss of durable state, or business workflow unusable.
- `P2` — significant functional defect, silent no-op, misleading success, accessibility/reliability issue.
- `P3` — minor defect, usability/documentation gap, or low-risk cleanup.

### 1.3 Required durable files in GitHub

Keep only files that actively help development, operations, QA, security, or users. The following are required and must not be deleted during cleanup:

- `README.md` — truthful product overview, verified setup, configuration, tests, security/reporting status.
- `docs/development/DEVELOPMENT_GUIDE.md` — this phase-by-phase execution contract.
- `docs/qa/PROGRESS_TRACKER.yaml` — machine-readable source of truth for phase state.
- `docs/qa/ISSUE_REGISTER.md` — finding-level status and evidence.
- `docs/qa/FILE_CLEANUP_REPORT.md` — inventory and deletion decisions with proof.
- `docs/qa/phase-logs/` — concise logs for completed/in-progress phases; one log per phase or an equivalent append-only log.
- CI workflow files, dependency manifests/lockfiles, tests, migrations, security policy, license, packaging/deployment files, and all runtime files that are actually required.

Do not create duplicate trackers or multiple conflicting roadmaps. If equivalent files already exist, reconcile and use the canonical one rather than creating duplicates.

---

## 2. GitHub progress model

### 2.1 Status values

Use only these phase statuses:

`NOT_STARTED`, `DISCOVERY`, `PLANNED`, `AWAITING_APPROVAL`, `IMPLEMENTING`, `TESTING`, `DEBUGGING`, `VERIFYING`, `BLOCKED`, `DONE`, `REOPENED`.

A phase is `DONE` only when:
- all acceptance criteria pass;
- all required tests pass, or a documented exception is explicitly approved;
- regression checks are complete;
- no P0/P1 issue from the phase remains unresolved;
- documentation and cleanup records are updated;
- evidence is linked;
- a commit is pushed to the phase branch and included in a PR;
- the PR has been reviewed and merged, unless the owner explicitly chooses another release process.

### 2.2 Progress tracker schema

Maintain `docs/qa/PROGRESS_TRACKER.yaml` in every phase commit. Minimum fields:

```yaml
project: GAYATRI-ERP
baseline:
  branch: main
  commit: "<SHA inspected at start>"
  inspected_at_utc: "<ISO-8601>"
overall_status: IN_PROGRESS
current_phase: PHASE-00
last_updated_utc: "<ISO-8601>"
phases:
  - id: PHASE-00
    title: Baseline and reproducibility
    status: DISCOVERY
    owner: local-ai-agent
    branch: dev/phase-00-baseline
    issue_url: null
    pull_request_url: null
    started_at_utc: null
    completed_at_utc: null
    findings: []
    files_changed: []
    tests:
      commands: []
      passed: 0
      failed: 0
      skipped: 0
      exit_codes: []
      evidence_urls: []
    acceptance:
      - id: A1
        description: "Baseline and environment recorded"
        status: NOT_VERIFIED
        evidence: null
    blockers: []
    commit_shas: []
```

Keep this schema accurate; do not fabricate timestamps, results, URLs, test counts, or commits. Update status at start, after planning, after implementation, after testing, when blocked, and at completion. Commit tracker changes alongside code or phase evidence. Use UTC ISO-8601 timestamps.

### 2.3 GitHub issue / PR / commit protocol

For each phase:
1. Open or update a GitHub issue with objective, findings, in-scope files, out-of-scope items, acceptance criteria, tests, risks, and cleanup considerations.
2. Create a phase branch from the latest reviewed `main`.
3. Commit the plan before implementation when feasible.
4. Commit focused changes with messages such as:
   - `docs(qa): record PHASE-00 baseline`
   - `fix(finance): verify and atomically process payment webhooks`
   - `test(auth): cover revocation-store failure behavior`
5. Push the branch and open a PR. PR body must contain:
   - Phase ID and issue links
   - Before/after behavior
   - Test commands and actual outcomes
   - Migration/security/privacy impact
   - Files deleted and evidence supporting deletion
   - Rollback instructions
   - Remaining risks and manual checks
6. Update tracker with real issue/PR/commit URLs and SHA.
7. Do not merge a phase with failing required checks or unresolved review comments affecting correctness/security.
8. If GitHub write access fails, preserve the local branch and logs, record the exact failure in the tracker, and mark `BLOCKED`. Never claim GitHub progress is maintained until the remote write is confirmed.

### 2.4 Session handoff protocol

At the end of every working session, update:
- current phase and exact status;
- latest commit SHA and branch;
- files modified and files still uncommitted;
- tests run with exact results;
- failures remaining and next debugging action;
- decisions needing human approval;
- next three concrete actions.

The next session must read this handoff before touching code.

---

## 3. Mandatory phase workflow template

Every phase log must include:

```markdown
# PHASE-XX — <title>
## Current status
## Baseline commit / branch
## 1. Discovery and dependency map
## 2. Reproduction steps and evidence
## 3. Plan and acceptance criteria
## 4. Human approval (if required)
## 5. Implementation summary
## 6. Tests run (commands, environment, exit codes)
## 7. Debugging and root cause
## 8. Regression results
## 9. Security / privacy / data-integrity review
## 10. Documentation and cleanup impact
## 11. GitHub issue / PR / commit links
## 12. Residual risks / blockers
## 13. Gate decision: PASS / FAIL / BLOCKED
```

A gate decision must be one of `PASS`, `FAIL`, or `BLOCKED`. `PASS` requires evidence for every criterion. A skipped test is not a pass. If a criterion does not apply, explain why and obtain review rather than deleting the criterion.

---

# 4. Phased development roadmap

The phases are deliberately ordered so that security and data integrity are addressed before UI polish or destructive cleanup. Reorder only with a written rationale and approval.

## PHASE-00 — Repository baseline, inventory, and reproducibility

**Goal:** Establish what exists and what actually works before modifying behavior.

**Plan / inspect**
- Record branch, SHA, tree status, Python/runtime versions, OS, environment variables by name only (never values), dependency manifests, CI workflows, packaging, migrations, API routers, front-end portals, services, data files, and docs.
- Build a route inventory: method/path, auth dependency, role/tenant requirements, service, DB, side effects, response contract, tests.
- Build a feature matrix for finance/payments, identity/auth, student, teacher, academic, attendance, assessment, tutor/AI, notifications, sync, admin, health/readiness, and desktop UI.
- Inventory current tests without trusting stated test counts or green badges.
- Capture a clean baseline of test commands, collection errors, failures, skipped/xfail tests, lint/type checks, and CI state.

**Implement**
- Documentation and inventory only. Do not change product behavior yet.
- Create/reconcile tracker, issue register, cleanup report, and phase log.

**Test/debug**
- Re-run baseline commands in a clean environment.
- Verify commands documented in README are real and paths exist.
- Identify flaky tests and tests that mutate shared or developer databases.

**Exit gate**
- Every major module and public route is inventoried.
- Baseline failures are recorded with logs and reproduction status.
- No claim of feature completeness is made without end-to-end evidence.
- Tracker and logs are pushed to GitHub.

## PHASE-01 — Authentication, authorization, tenant isolation, and revocation (P0/P1)

**Known audit targets to re-verify**
- `central_platform/auth/tokens.py`: revocation-store error handling may fail open; `is_revoked()` may return false on DB failure and `revoke()` may report success when persistence fails.
- `central_platform/auth/dependencies.py`: optional auth and missing/malformed bearer token handling.
- `central_platform/api/routes/auth.py`: synthetic identity/demo-token behavior and production guardrails.
- `central_platform/api/routes/ai.py`: confirm authentication/authorization for execution, provider configuration, toggles, and kill switch.
- Legacy handlers in `central_platform/api/app.py`: confirm no auth/RBAC/tenant bypass.
- Any route that accepts student, teacher, organization, invoice, class, course, or session IDs from a client.

**Plan**
- Trace token creation → validation → user lookup → role and tenant checks → revocation check → route dependency.
- Enumerate every public, protected, optional-auth, admin-only, and service-to-service route.
- Define fail-closed behavior and migration/compatibility impact before coding.

**Implement**
- Fix confirmed bypasses and fail-open behavior.
- Remove or strictly gate synthetic users/demo tokens in production; never let unknown identities acquire a real user context.
- Ensure authorization is checked server-side at the resource query and mutation boundary, not only in the UI.
- Make revocation persistence outcomes truthful; fail closed for protected requests when revocation state cannot be safely checked.
- Ensure route dependencies share the intended database/service configuration.

**Test/debug**
- Missing, malformed, expired, revoked, wrong-audience, wrong-role, and wrong-tenant tokens.
- DB unavailable during validation, revoke, logout, and user lookup.
- Cross-student, cross-teacher, cross-organization and IDOR probes.
- Production environment with demo endpoints and synthetic identities.
- Legacy and versioned API routes side by side.
- Confirm expected HTTP status and no protected side effect.

**Exit gate**
- No known P0/P1 auth bypass remains.
- Failure of revocation persistence cannot silently authorize a request or falsely report logout success.
- Negative tests assert no database mutation or data disclosure.
- Security review and route matrix are updated.

## PHASE-02 — Database lifecycle, dependency injection, transactions, and durable state

**Known audit targets to re-verify**
- Independent `get_db() -> PlatformDatabase()` functions in route modules and module-global service/database instances.
- In-memory services/legacy engines that may not share the canonical persistence layer.
- Transaction boundaries around payment, invoice, order, ledger, webhook, attendance, academic, assessment, and tutor events.
- Any SQLite/test fixtures that mutate `gayatri_local.db`; verify current implementation before acting.

**Plan**
- Map each feature's write/read path, transaction scope, uniqueness constraints, foreign keys, connection lifecycle, and recovery path.
- Establish the canonical database factory and transaction ownership.
- Identify all persistence claims in README and operations docs.

**Implement**
- Unify DB configuration/connection injection where confirmed necessary.
- Use explicit transactions for multi-record business operations.
- Add constraints and idempotency keys where required, with safe migration and rollback plans.
- Ensure services return explicit failure when persistence fails; never return success after rollback or failed commit.
- Prevent test fixtures from mutating developer/production databases.

**Test/debug**
- Process restart and re-read tests for every durable workflow.
- Inject connection loss, constraint violation, timeout, commit failure, duplicate request, and concurrent write.
- Verify rollback leaves no partial invoice/ledger/order/event state.
- Verify migrations from a clean DB and supported prior schema.
- Test data isolation between two independent DB paths.

**Exit gate**
- Every production-critical write has documented transaction and idempotency semantics.
- Repeated requests and restart tests demonstrate correct durable state.
- Migration/rollback and backup/restore behavior are documented.

## PHASE-03 — Finance, payments, webhook integrity, invoices, ledger, and receipts (P0)

**Known audit target to re-verify**
- `central_platform/api/routes/finance.py` and `central_platform/finance/service.py`: webhook processing may not call signature verification, may persist `signature_verified=1` without actual verification, and may update payment, receipt, invoice, order, ledger, and webhook event through separate transaction contexts. Duplicate detection and event creation may not be atomic.

**Plan**
- Map provider signature verification, raw-body handling, event ID, payment state transitions, invoice state, order state, ledger posting, receipt generation, refunds, retries, and reconciliation.
- Define invariants before implementation: unverified webhook cannot mutate financial state; a provider event is applied at most once; all related records commit atomically; ledger entries balance; transitions are legal.

**Implement**
- Verify provider signatures using the provider's official algorithm and exact raw payload rules; compare signatures safely.
- Reject unknown providers and malformed/unsigned events; never mark an event verified before successful verification.
- Implement idempotent event processing with durable unique keys and atomic transaction semantics.
- Enforce legal payment/invoice/order transitions and safe retry behavior.
- Make receipt retrieval/printing tied to an authenticated, persisted receipt and correct invoice/payment.
- Add reconciliation and auditable error states; never use fake success.

**Test/debug**
- Valid/invalid/missing signature; wrong secret; altered payload; unknown provider; duplicate event; out-of-order event; concurrent duplicate delivery; DB failure mid-transaction; already-paid invoice; amount/currency mismatch; refund; retry after partial failure.
- Assert no financial side effect for invalid events.
- Assert exactly one ledger posting and consistent invoice/order/receipt state for duplicates.
- Use test provider credentials only; never real money in tests.

**Exit gate**
- Finance invariants pass under success, retry, duplicate, concurrency, and failure injection.
- No unverified event can mutate financial records.
- P0 financial findings are `FIXED_VERIFIED` with evidence.

## PHASE-04 — AI execution, provider configuration, kill switch, and error contracts

**Known audit targets to re-verify**
- `central_platform/api/routes/ai.py`: AI execution/provider control routes may not visibly enforce auth in individual handlers; execution failures may be returned inside `ApiResponse(ok=False)` with HTTP 200; unknown provider types may silently default to `MOCK`; module-global gateway service may capture stale DB/config.

**Plan**
- Trace API request → auth → provider selection → policy/limits → execution → timeout/retry → audit event → response.
- Define consistent HTTP/business error semantics and allowed provider types.
- Determine how kill switch is propagated to already-running and new requests.

**Implement**
- Enforce role checks for execution and provider administration.
- Reject invalid provider types rather than silently substituting a mock provider.
- Make failures machine-detectable using consistent HTTP statuses and structured error codes.
- Make provider configuration refresh behavior explicit and auditable.
- Ensure kill switch blocks new execution and handles in-flight work according to documented policy.
- Avoid logging API keys, prompts containing sensitive data, or student identifiers beyond policy.

**Test/debug**
- Unauthorized provider create/update/toggle, invalid provider enum, provider timeout, rate limit, missing credentials, stale configuration, kill-switch activation during requests, audit write failure.
- Assert clients can distinguish success, degraded operation, and failure.
- Verify provider selection cannot bypass privacy or tenant policies.

**Exit gate**
- All provider-control endpoints are protected.
- No invalid configuration is silently converted to a successful mock response.
- Failure contracts are documented and tested.

## PHASE-05 — Student, teacher, admin, and fee UI-to-API wiring (no toast-only success)

**Known audit targets to re-verify**
- `app/ui/design_system/fee_admin.js`: `generateMonthlyBilling()` and `exportOutstandingReport()` may only show a toast; `printReceipt()` may open print without fetching/verifying a persisted receipt.
- `app/ui/design_system/student.js`: `startReview(conceptId)` may only show a toast without creating a review/session or saving progress.
- `app/ui/design_system/teacher.js`: `triggerCopilotAnalysis()` may only show a toast without calling the backend or rendering results.
- `innerHTML` and inline handler interpolation in student UI may create injection and fragile event wiring risks.

**Plan**
- For every visible control, trace click → validated request → auth → server action → durable state → response → visible success/error/loading state.
- Classify controls as functional, intentionally disabled with reason, or nonfunctional.
- Define empty, loading, success, partial, error, retry, offline, and permission-denied states.

**Implement**
- Wire only to canonical backend endpoints and durable services.
- Replace toast-only placeholders with real behavior or clearly disabled controls with truthful explanation.
- Prevent duplicate submissions and stale responses.
- Escape/sanitize user-controlled content; use safe DOM APIs and event listeners instead of interpolated inline handlers where applicable.
- Ensure exported reports and receipts reflect authorized, persisted data.

**Test/debug**
- Browser/desktop UI tests for every critical control.
- Network failure, 401/403, 404, 409, 422, 429, 500, timeout, malformed JSON, empty dataset, and duplicate click.
- Verify successful toast/notification appears only after backend confirms the operation.
- Test keyboard navigation, focus, screen sizes, and error accessibility for key workflows.

**Exit gate**
- Every visible critical action is implemented end-to-end or explicitly disabled.
- No false-success toast remains for an operation that did not happen.
- UI and API contract tests agree.

## PHASE-06 — Student learning, review lifecycle, and persistence

**Plan**
- Map concept, enrollment, session, review queue, attempt, mastery/progress, and event lifecycles.
- Verify that student-facing progress is scoped to the authenticated student and tenant.

**Implement**
- Make review creation, completion, and rescheduling durable and idempotent.
- Ensure progress changes only after a validated attempt/result and required event persistence.
- Make empty review queues and missing concepts explicit states, not silent no-ops.

**Test/debug**
- Start review → answer/complete → refresh/restart → verify state.
- Two students, same concept; tenant isolation; repeated completion; invalid concept; concurrent updates; offline/retry if supported.
- Verify mastery and review state agree across API, UI, and DB.

**Exit gate**
- Review lifecycle and progress persist and are correctly student-scoped.
- No UI claims completion without persisted state.

## PHASE-07 — Assessment, question bank, grading, and anti-fallback behavior

**Known audit target to re-verify**
- `central_platform/api/routes/assessments.py`: list/question-bank behavior may return sample fallback questions when DB is empty, disguising missing/unconfigured content as real data.

**Plan**
- Trace question source, curriculum/tenant/course scope, randomization, answer key protection, attempt lifecycle, grading, scoring, and results.
- Establish whether sample content is allowed only in explicit demo/test mode.

**Implement**
- Remove implicit production fallback content; empty bank should return a clear empty/configuration state.
- Validate question/course/tenant ownership and attempt state.
- Protect answer keys and grading logic from client-side manipulation.
- Make scoring deterministic and auditable.

**Test/debug**
- Empty bank, unknown course, cross-tenant question ID, tampered score, repeated submission, expired attempt, malformed answer, duplicate question, randomized variants.
- Verify API response, DB state, and student-visible score.

**Exit gate**
- Production data cannot be replaced by hidden demo fallback.
- Assessment integrity and ownership tests pass.

## PHASE-08 — Tutor orchestration, RAG grounding, and blocked-turn semantics

**Known audit target to re-verify**
- `central_platform/api/routes/tutor.py`: blocked tutoring path may return a `turn-blocked-*` ID and safe response that clients could mistake for a completed tutoring turn.

**Plan**
- Trace user input → auth/course scope → retrieval → policy → model → evaluator → event/progress persistence → response.
- Identify fallback to ungrounded model answers, stale course versions, missing retrieval, model/provider failures, and partial turn writes.

**Implement**
- Make blocked, incomplete, failed, and successful turns distinguishable in status and response contract.
- Ensure RAG scope respects tenant/course/version/permissions.
- Do not fabricate sources or claim grounding when retrieval returns no valid evidence.
- Persist turn events and learning outcomes consistently; ensure retries do not duplicate state.
- Ensure prompt injection and answer-leakage safeguards are enforced server-side.

**Test/debug**
- Empty index, wrong tenant/course, stale version, retrieval timeout, model timeout, blocked request, injection attempt, answer leakage probe, evaluator failure, DB event failure.
- Verify a blocked turn does not increment success metrics or mastery.
- Compare citations/snippets to actual indexed sources.

**Exit gate**
- Tutor states are explicit and durable; groundedness and scope tests pass.
- No silent fallback produces an apparently successful but unsupported answer.

## PHASE-09 — Attendance, academic workflows, instructions, notifications, and sync

**Plan**
- Map every legacy and versioned endpoint, state transition, notification trigger, sync event, conflict strategy, and tenant boundary.
- Find in-memory state that disappears on restart and paths that bypass the canonical service.

**Implement**
- Route all supported workflows through canonical services and persistence.
- Validate state transitions and actor permissions.
- Add idempotency and conflict handling for sync where applicable.
- Make notification delivery failure observable and retryable without duplicate notifications.

**Test/debug**
- Restart persistence; duplicate and out-of-order events; invalid transition; unauthorized instruction; sync conflict; notification provider outage; event replay.
- Verify server and desktop views converge on the same state.

**Exit gate**
- Supported workflows have clear source of truth and tested restart/retry behavior.
- Legacy endpoints are secured, migrated, or explicitly retired with a compatibility plan.

## PHASE-10 — Health, readiness, observability, and operational failure reporting

**Known audit target to re-verify**
- `central_platform/api/app.py` `/api/health` may initialize a nonzero students count and retain it after a dashboard query fails; non-`UNHEALTHY` statuses may be mapped to `HEALTHY`, masking degraded state.

**Plan**
- Distinguish liveness (process is running) from readiness (dependencies are usable) and degraded health.
- Inventory exception handlers, logging, metrics, request IDs, audit events, and fallback/default values.

**Implement**
- Return real measurements or explicit `unknown/unavailable`; never substitute fabricated business counts.
- Make readiness reflect required dependencies; do not expose secrets or sensitive internals.
- Standardize structured logs and error IDs for critical flows.
- Ensure exceptions cannot become false-green status.

**Test/debug**
- DB down, AI provider down, migration missing, disk full, bad config, audit store down, partial dependency failure.
- Assert health/readiness changes correctly and recovers.
- Verify logs contain correlation IDs but no secrets.

**Exit gate**
- Monitoring distinguishes healthy, degraded, and unhealthy states accurately.
- No fabricated default metric is presented as real.

## PHASE-11 — API contracts, validation, rate limits, and idempotency

**Plan**
- Inventory request/response schemas, status codes, pagination, error envelopes, limits, idempotency, and backward compatibility.

**Implement**
- Add strict request validation, bounded pagination, safe file/input limits, idempotency for retry-prone operations, and consistent error contracts.
- Reject invalid states at the API boundary; avoid permissive defaults that hide bad input.
- Document compatibility/deprecation strategy for legacy routes.

**Test/debug**
- Boundary values, oversized payloads, malformed types, unknown enum values, replay, concurrent duplicate, rate-limit exhaustion, retry-after behavior.
- Contract tests across frontend and backend.

**Exit gate**
- API behavior is predictable, documented, and covered by contract/negative tests.

## PHASE-12 — Privacy, secrets, XSS, supply chain, and security regression

**Plan**
- Scan tracked files and history where permitted for secrets; inspect environment/config defaults, dependencies, CORS, CSP, HTML injection, file uploads, logs, and sensitive data retention.
- Do not print secret values in logs or audit output. If a credential is exposed, treat it as compromised and follow owner-approved rotation steps.

**Implement**
- Fix confirmed vulnerabilities with minimal changes.
- Use secure defaults, secret-free examples, restrictive permissions, output encoding, and safe file handling.
- Review dependencies for known vulnerabilities and pin/lock according to the project's dependency policy.
- Avoid weakening CSP or adding unsafe inline script exceptions as a shortcut.

**Test/debug**
- Static security scans and targeted exploit tests.
- XSS payloads in names, labels, course titles, reports, and API error messages.
- Verify tenant and role checks at both route and object levels.
- Confirm no tokens/keys/student data in logs or artifacts.

**Exit gate**
- No known P0/P1 security issue remains unresolved.
- Security exceptions are explicit, reviewed, and time-bounded.

## PHASE-13 — Performance, concurrency, reliability, and recovery

**Plan**
- Define supported hardware, expected users/concurrency, latency targets, memory/disk limits, and critical workload budgets from actual product requirements.
- Profile before optimizing.

**Implement**
- Address demonstrated bottlenecks; add bounded queues/timeouts/retries and graceful cancellation where needed.
- Prevent retries from duplicating payments, events, notifications, or learning progress.
- Document capacity limitations honestly.

**Test/debug**
- Concurrent login and API requests; webhook duplicate races; large course/index; provider timeout; slow DB; restart during work; resource exhaustion.
- Record latency percentiles, error rates, memory, and CPU with reproducible setup.

**Exit gate**
- Critical workflows meet agreed targets or have explicit documented limits and mitigation.

## PHASE-14 — End-to-end product acceptance and release gate

**Plan**
- Build role-based user journeys from sign-in to key workflows: student learning/review/assessment, teacher instructions/copilot, admin course/identity/finance, payment/receipt, health and recovery.
- Include fresh install, upgrade, restart, and rollback scenarios.

**Implement**
- Fix only issues required for accepted workflows and their regressions.
- Update installation, configuration, troubleshooting, architecture, security, and release docs from verified behavior.

**Test/debug**
- Run targeted suite, integration suite, UI E2E, security tests, migration tests, and the complete non-GUI suite where feasible.
- Test clean installation and supported upgrade path.
- Check that tests are not skipped or weakened to achieve green status.
- Perform a release-candidate smoke test on a clean machine/environment.

**Exit gate**
- All P0/P1 findings resolved or explicitly release-blocked.
- Critical workflows pass end-to-end using real persistence and realistic dependencies.
- README instructions have been executed successfully.
- Release approval is explicit; no agent may self-certify a production release solely from tests.

## PHASE-15 — Repository cleanup and documentation consolidation

**Do not start destructive cleanup until PHASE-00 inventory and relevant functional phases are complete.** A file being old, large, duplicated-looking, or unused by grep is not sufficient evidence for deletion.

**Classify each candidate**
- `KEEP_RUNTIME`: imported, dynamically loaded, packaged, deployed, or used at runtime.
- `KEEP_TEST`: needed for regression, fixtures, contract tests, or CI.
- `KEEP_OPS`: needed for migration, deployment, backup, recovery, monitoring, or support.
- `KEEP_DOCS`: canonical user/developer/security/operations documentation.
- `CONSOLIDATE`: duplicate documentation or obsolete scripts with a verified canonical replacement.
- `REMOVE_CANDIDATE`: only after all checks below pass.
- `UNKNOWN_BLOCKED`: unclear ownership/reference; retain until resolved.

**Required deletion proof**
1. Search direct imports/references and dynamic/plugin/entry-point loading.
2. Search packaging, CI, installer, shell/batch files, deployment, docs, and external links.
3. Check git history, callers, runtime-generated path conventions, and configuration references.
4. Run import/route/packaging/tests before and after deletion.
5. Confirm no migration/data file is needed for existing installations or rollback.
6. Record exact path, reason, reference searches, tests, reviewer, and replacement path (if any) in `docs/qa/FILE_CLEANUP_REPORT.md`.
7. Delete in small batches on a dedicated branch; review the diff and test after each batch.
8. Never delete user data, secrets, migrations, licenses, CI configuration, tests, dependency locks, or operational recovery material without explicit owner approval.

**README.md must be accurate**
- Remove claims that cannot be verified; do not state exact test counts, router counts, database table counts, supported model requirements, offline guarantees, security guarantees, or payment support unless measured and current.
- Correct repository clone URL and directory name.
- Clearly separate implemented/verified, experimental, planned, and unsupported functionality.
- Include prerequisites, safe installation/configuration, migration, run commands, test commands, health endpoints, architecture, security notes, reporting instructions, and known limitations.
- Do not expose secrets or encourage unsafe production defaults.

**Exit gate**
- Every deleted file has documented evidence and no missing runtime dependency.
- All essential user, developer, QA, operations, security, and CI files remain.
- Clean clone/install/tests pass.
- README is accurate and points to canonical docs only.

## PHASE-16 — Final audit, handover, and maintenance

- Re-run all release-gate checks from a clean clone.
- Review every issue register entry and verify evidence links still work.
- Verify tracker phase statuses match merged GitHub history.
- Produce a release handover with architecture, configuration, deployment, backup/restore, monitoring, incident response, known limitations, and rollback.
- Tag a release only after human approval and repository policy checks.
- Keep unresolved P0/P1 items visible; never bury them in a “known issues” paragraph.

---

## 5. Seed findings from the initial QA review

These are **targets to re-check**, not automatic proof that the current code still contains the defects. The agent must re-read the exact file and line on its current baseline and add a regression test before changing it.

| ID | Initial target | Priority | First relevant phase |
|---|---|---:|---|
| ERP-001 | Payment webhook signature verification and trust boundary | P0 | 03 |
| ERP-002 | Payment/invoice/order/ledger/event atomicity and idempotency | P0 | 02–03 |
| ERP-003 | Token revocation persistence may fail open / false-success | P1 | 01 |
| ERP-004 | Demo token and synthetic identity production exposure | P1 | 01 |
| ERP-005 | Independent DB factories / stale module-global services | P1 | 02 |
| ERP-006 | Health endpoint may report fabricated count/healthy state | P1/P2 | 10 |
| ERP-007 | Billing generation UI may be toast-only | P1/P2 | 05 |
| ERP-008 | Outstanding report export may be toast-only | P2 | 05 |
| ERP-009 | Receipt print may not fetch/verify persisted receipt | P1/P2 | 03, 05 |
| ERP-010 | Student review action may be toast-only | P1/P2 | 06 |
| ERP-011 | Teacher Copilot analysis may be toast-only | P1/P2 | 05 |
| ERP-012 | AI execution/provider routes may lack effective authorization | P1 | 01, 04 |
| ERP-013 | AI failure may be represented as HTTP 200 | P1/P2 | 04, 11 |
| ERP-014 | Unknown provider type may silently default to mock | P2 | 04 |
| ERP-015 | Legacy API endpoints may bypass canonical auth/persistence | P1 | 01, 09 |
| ERP-016 | Assessment bank may return sample fallback data in empty production state | P1/P2 | 07 |
| ERP-017 | Blocked tutor turn may look like a successful completed turn | P2 | 08 |
| ERP-018 | Dynamic `innerHTML`/inline handler interpolation in student UI | P2 | 05, 12 |
| ERP-019 | Optional/missing bearer token edge cases | P1 | 01 |
| ERP-020 | Broad exception handlers/default values may mask failures | P1/P2 | 10–12 |
| ERP-021 | Test fixtures may mutate a developer database | P1/P2 | 00, 02 |
| ERP-022 | Feature-level restart, negative-path, and E2E coverage gaps | P1 | 00, 14 |

Create one canonical register entry per finding with: evidence, confidence, severity, affected paths, reproduction, root cause, fix commit/PR, regression test, residual risk, and verification date. Split findings if one item contains independent root causes.

---

## 6. Required testing policy

### For every code change
- Focused regression test for the bug.
- At least one negative/failure-path test where applicable.
- Tests for direct callers and shared dependencies.
- Formatting/lint/type checks applicable to changed files.
- Verify no test was skipped, weakened, or rewritten to hide the defect.

### At every phase gate
- Run all tests for the affected subsystem.
- Run API/contract tests for changed interfaces.
- Run authorization and tenant-isolation tests for protected resources.
- Run persistence/restart tests for durable workflows.
- Run UI smoke tests for changed visible actions.
- Review logs for silent exceptions and false success.
- Inspect the diff for unrelated changes, secrets, generated artifacts, and accidental deletions.

### Milestone / release gates
Run the broadest feasible suite at baseline, after phases 03, 04–05, 08–10, after cleanup, and before release. Use actual commands discovered in the repo; do not blindly copy commands from stale README text. Record environment, command, exit code, passed/failed/skipped counts, and artifact links.

### Test-quality rules
- A test is valuable only if it can fail when the defect returns.
- Do not rely solely on mocks for payment integrity, authorization, tenant isolation, persistence, or E2E UI behavior.
- Never lower assertions or loosen security checks to make a test pass.
- For nondeterministic tests, record the flake, isolate the cause, and keep it visible until resolved.
- If a full suite cannot run, document the exact limitation and do not mark the release gate green.

---

## 7. Definition of done for every feature

A feature is complete only when all applicable conditions hold:

- UI entry point exists and is reachable by the intended role.
- Request validation and authorization are enforced server-side.
- Correct domain service and canonical persistence are used.
- Success response is returned only after the operation actually succeeds.
- Failures are visible, actionable, and do not leave partial state.
- Retry/duplicate behavior is safe and idempotent where needed.
- Tenant and user boundaries are verified.
- Loading, empty, error, retry, and success states are implemented.
- Logs/audit trail are adequate without leaking secrets or private data.
- Unit + integration + negative-path + regression tests exist.
- Restart/re-read behavior is verified for durable state.
- Documentation and API contracts are current.
- Progress tracker, issue register, phase log, and GitHub PR are updated.

---

## 8. Standard progress report template

Append this to the phase log after each work session:

```markdown
### Session YYYY-MM-DD — PHASE-XX
- Status before:
- Baseline SHA:
- Branch:
- Plan approved by / approval status:
- Files inspected:
- Files changed:
- Findings confirmed:
- Tests run:
  - `command` — exit code — passed/failed/skipped — evidence link
- Bugs reproduced:
- Root causes found:
- Fixes implemented:
- Regressions checked:
- GitHub issue:
- Pull request:
- Commit SHA(s):
- Blockers / decisions:
- Exact next actions:
- Status after:
```

## 9. Final agent instructions

1. Start at PHASE-00, not at the most convenient bug.
2. Re-read current source and this tracker before each phase.
3. Make a written plan before coding and request approval wherever the project owner requires it.
4. Fix the root cause and add a regression test before calling a defect fixed.
5. Keep each PR small enough to review; avoid bundling unrelated cleanup with functional fixes.
6. Never delete files based only on intuition, age, size, naming, or an incomplete text search.
7. Never trust test summaries without rerunning the relevant commands.
8. Never report GitHub progress unless the issue/branch/commit/PR is actually visible remotely.
9. Never advance a phase with unresolved acceptance criteria; mark `BLOCKED` or `REOPENED`.
10. Never claim production readiness while P0/P1 issues, missing evidence, or unverified critical workflows remain.
