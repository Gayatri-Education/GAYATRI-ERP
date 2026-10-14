# Gayatri School OS — Phase-by-Phase Development and Production Readiness Contract

**Document type:** Mandatory execution specification for a local AI coding agent  
**Primary repository:** https://github.com/Gayatri-Education/Gayatri  
**Related product specification:** `GAYATRI_PRODUCT_UNIFICATION_ROADMAP.md`  
**Product direction:** One hybrid, modular platform for schools and coaching/educational institutes  
**Target outcome:** Industry-grade product with a real AI Learning Suite and fully functional School ERP; no demo-only business workflows in a production release  
**Status:** Engineering execution contract. It is not evidence that the current repository is production-ready.

---

## 0. Mission and absolute rules

Your mission is to inspect the actual checked-out repository, understand the complete product and business scope before changing code, plan each phase, implement the smallest coherent changes, test them, debug every failure, run regression checks, record objective evidence, and proceed only when the phase is green. The goal is a reliable production product, not a large diff, impressive test count, green badge, working mock, polished demo, or a collection of endpoints that do not complete real workflows.

The target product contains two coordinated suites:

1. **AI Learning Suite:** curriculum-scoped tutoring, model routing, scoped RAG, learning sessions, assessment, evidence-based mastery, spaced review, teacher interventions and privacy-governed parent visibility.
2. **School Operations / ERP Suite:** institution setup, admissions, student/guardian/staff records, academic calendars, classes and batches, attendance, timetables, examinations, grading/report cards, finance and payments, communications, HR/payroll, transport, hostel, inventory/assets, visitor management, certificates/ID cards and public school CMS.
3. **Shared platform:** identity, tenant isolation, authorization, audited records, course and student identity, document storage, notification jobs, integration contracts, offline synchronization, monitoring, backup/restore, deployment and support operations.

The product must serve both schools and coaching institutes and support hybrid operation: local/offline operation where designed and permitted, with explicit optional synchronization to a central deployment. After the shared platform foundation is stable, AI reliability and core ERP are coordinated parallel workstreams.

### 0.1 Non-negotiable engineering principles

- **Inspect before changing.** Read the product roadmap, this document, current source code, migration history, call sites, route registrations, relevant tests, deployment scripts and docs before touching a feature.
- **Understand the full business workflow before implementing any ERP feature.** Never build a page or endpoint from a one-line feature name. Map users, permissions, states, exceptions, data ownership, external dependencies, audit needs, privacy, offline behavior, acceptance criteria and failure recovery first.
- **Plan every phase before editing source.** Write the phase plan and test strategy first. A plan is not approval to stop; continue execution autonomously unless a real external approval, credential, hardware device, product decision or destructive operation is required.
- **One canonical service per business domain.** Avoid duplicate sources of truth, duplicate APIs with different behavior, hidden state stores and route-local business logic.
- **A successful response means the requested operation actually succeeded.** No silent exception swallowing, false `ok: true`, synthetic success, fake payment status, fabricated attendance, fictitious grades or success-shaped fallback data in production.
- **Mocks are test tools, never production substitutes.** Mock, stub, fixture, sample and canned behavior must be clearly isolated and impossible to select accidentally in production.
- **Tests must be meaningful.** Add a regression test that fails before each defect fix. Never make a suite green by deleting tests, loosening assertions, broad `skip`/`xfail`, replacing real execution with mocks, or changing correct expected values to fit broken behavior.
- **No phase hopping.** A phase may be passed only after all its exit criteria are evidenced. Unresolved P0/P1 findings block progression and release.
- **No false certainty.** Use `BLOCKED`, `NOT_RUN` or `NOT_APPLICABLE` accurately. Never claim that real-model inference, real payments, hardware, PostgreSQL, security, performance or cross-platform packaging passed when it was not actually tested.
- **Keep the main branch runnable.** Implement small coherent slices, run focused tests and regression tests frequently, and do not leave the repository indefinitely broken.
- **No unapproved destructive action.** Do not run destructive production migrations, delete customer files/data, rotate real secrets, deploy publicly, send real messages, make real payments or incur paid API/GPU costs without explicit authorization.
- **Privacy before convenience.** Data must not cross tenant, user, course, guardian, provider or privacy-policy boundaries simply because a UI or model request is convenient.
- **Industry-grade means operationally supportable.** Include observability, configuration validation, migrations, backup/restore, upgrade/rollback, security review, runbooks and realistic load tests—not just feature code.

### 0.2 What “no dead ends” means

Every visible feature must reach a defined outcome and every failure must offer a safe, intelligible next step. Avoid:

- Buttons that do nothing; forms that cannot submit; routes with no client integration; client actions with no persisted server operation.
- Workflow records stuck forever in `PENDING`, `PROCESSING`, `IN_REVIEW` or `SENDING` without retry, failure, cancellation or reconciliation paths.
- Wizards that create half-finished records with no resume, discard or support path.
- Uploads that silently fail parsing/indexing; long jobs without status/progress; retrying jobs that duplicate results.
- Payment attempts with no status reconciliation, refund trail or support reference.
- Attendance corrections, mark approval, payroll approval or admission decisions without an auditable review path.
- Offline writes that disappear, duplicate, overwrite important records without conflict visibility or remain indefinitely unacknowledged.
- Fallbacks that make an unavailable capability appear to work.

For every workflow, define terminal states, transition rules, retry rules, cancellation rules, authorization, timeouts, idempotency, recovery steps and user-visible errors before implementation.

### 0.3 What “no silent fails” means

A failure is silent when the system hides it, misreports it as success, discards the evidence, or leaves the user believing a consequential action completed when it did not. Every failure that affects correctness, security, persistence, payments, AI outcome, sync or delivery must:

1. Be caught at a boundary where it can be handled meaningfully.
2. Produce a structured error or explicit degraded/failure status.
3. Include a correlation/request ID in logs and, when useful, user-facing support details.
4. Preserve a safe retry/recovery path when possible.
5. Avoid exposing credentials, tokens, private student content or internal stack traces to an unauthorized client.
6. Prevent partial writes or record them as an explicit durable workflow state with reconciliation semantics.
7. Be testable through injected faults or controlled failure tests.

Do not put bare `except: pass` around persistence, security, payment, model execution, migration, queue acknowledgement, audit logging or sync. If an exception is intentionally non-fatal, log a structured warning/error, increment an observable metric, document why continuing is safe and test that behavior.

---

## 1. Source-of-truth and repository discovery protocol

### 1.1 Read and reconcile inputs

At the start, locate and read:

- `GAYATRI_PRODUCT_UNIFICATION_ROADMAP.md` (or the exact supplied roadmap file if the repository does not yet contain it).
- This `DEVELOPMENT.md`.
- `README.md`, `CHANGELOG.md`, `pyproject.toml`, dependency files/lock file and CI workflow.
- `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/DEPLOYMENT.md`, `docs/SECURITY_MODEL.md`, `docs/PRIVACY_CONTRACT.md`, `docs/TESTING_STRATEGY.md` and relevant API/operations docs.
- `GAYATRI_PHASE_BY_PHASE_PRODUCTION_FIX_PLAN.md` and `Gayatri_QA_Production_Fix_Plan.md` without assuming their findings are correct.
- All SQL migrations and down migrations.
- `central_platform/api/app.py`, router modules, auth dependencies, RBAC, configuration, domain services, database abstraction, sync engine, local runtime and UI/bridge integration.
- The attached/source document titled **“Comprehensive Feature Gap Analysis Report: EduJet ERP/LMS vs. Gayatri AI Platform”** if available in the workspace.
- All tests and current Git state.

If a named document is absent, search for a supplied equivalent and record what is missing. Continue using this execution contract and the scope in Section 3; do not stop merely because an optional report is absent. If the product roadmap is absent, reconstruct no new product decisions: use Section 3 as the minimum accepted scope and record this deviation in the decision log.

### 1.2 Build a source map before editing

Produce `docs/development/REPOSITORY_MAP.md` with:

- Actual package/entrypoint map and startup commands.
- Actual route registry and API version prefixes.
- Auth identity resolution, token validation/revocation, RBAC and tenant-scope flow.
- Database connection creation, migration runner, transaction semantics and environment selection.
- Domain ownership map: canonical models, services, tables, route handlers, UI clients and events.
- AI invocation path from UI/API to model provider and response validation.
- RAG ingestion path from upload to parse, chunk, embed/index, retrieve, cite and delete/re-index.
- Learning lifecycle from student action through evaluation, durable event, mastery projection and UI update.
- Payment path from invoice/order through provider callback/webhook, ledger, receipt and reconciliation.
- Sync path from local mutation/outbox through transport, central idempotency, conflict handling and acknowledgement.
- Jobs, notifications, document/object storage, file uploads, report generation, packaging and deployment paths.
- Existing dead paths, duplicate services, legacy endpoints, mock/sample fallbacks and unknowns.

For each finding, link to file and line or symbol names. Use `CODE_OBSERVED`, `REPO_DOCUMENTED`, `RUNTIME_VERIFIED`, `PROPOSED`, `BLOCKED`, `NOT_RUN` or `NOT_APPLICABLE` labels from the start.

### 1.3 Confirm the baseline independently

Capture the exact Git commit SHA, Python/OS version, environment variables' **names only** (never values of secrets), installed dependency versions, model availability/checksum if applicable, database engine/schema version and current working-tree diff.

Run existing tests and validation commands as-is first. Record exact commands, exit code, stdout/stderr artifacts and failures. Separate failures caused by environment from reproducible product defects. Do not accept a README's test count or a CI badge as evidence of a local pass.

Minimum baseline tasks:

- `git status --short`, `git rev-parse HEAD`, inspect recent commits.
- Inspect CI commands and run the canonical test command from the repository.
- Python syntax/compile checks and lint/type/security checks that the project actually configures.
- Migration from a fresh empty database and upgrade from the last supported schema.
- API startup/readiness/health checks under development and production-like configuration.
- Test whether a missing/invalid local model is reported as degraded/unavailable, not as real inference success.
- Inspect the actual test suite for mocks, fixture shortcuts and coverage gaps in critical workflows.

Do not modify the product merely to obtain a cleaner baseline report. Fix baseline problems in the relevant planned phase, with regression tests.

---

## 2. Execution control system

### 2.1 Mandatory lifecycle for every phase

Repeat this exact lifecycle for every phase in Section 7. Save evidence after each step. Do not skip directly from planning to implementation or from a focused test pass to phase completion.

1. **Read scope:** Read all relevant roadmap sections, source modules, models, migrations, caller paths, UI integration, support docs and tests.
2. **Map impact:** Identify affected features, domain ownership, data paths, role/tenant boundaries, external systems, offline behavior, migrations, compatibility contracts and downstream phases.
3. **Clarify only true blockers:** First use the requirements and safe defaults in this document. Ask the owner only when a product decision cannot be safely resolved from approved scope or the action needs explicit external authorization. Record assumptions rather than repeatedly asking questions already answered.
4. **Write the phase plan before code:** Create `docs/development/plans/PHASE_<NN>_PLAN.md`, including scope, exclusions, file map, requirements, state transitions, migration plan, API contract, threat scenarios, test plan, feature flags, rollback, observability and exit criteria.
5. **Create test cases before implementation:** At minimum, list happy path, invalid inputs, permission denials, tenant crossing, duplicate requests, concurrent updates, dependency failure, timeout, process restart, partial failure, offline/retry behavior, audit coverage and user-visible state for each affected workflow.
6. **Capture a baseline:** Run focused tests and any existing test around changed behavior. Save output under `docs/development/evidence/`. Note pre-existing failures distinctly.
7. **Implement minimal coherent slices:** Change one logical behavior at a time. For complex features, build vertical slices from persistence to API to UI and recovery; avoid weeks of disconnected scaffolding.
8. **Debug immediately:** For each new failure, reproduce it, isolate cause, fix root cause, add regression coverage and rerun until green or mark as blocked with the exact external dependency. Do not accumulate known failures until phase end.
9. **Review correctness and security:** Inspect the diff manually. Check authorization in service boundaries, transaction integrity, exception propagation, logs, secrets, data retention, migration reversibility/forward safety and backward compatibility.
10. **Run focused tests:** Unit, service, database, API, UI/client contract and integration tests for the changed slice.
11. **Run phase-specific end-to-end paths:** Exercise persisted state through real application paths, not only mocks or direct helper calls.
12. **Run full applicable regression:** Full non-GUI suite, GUI/platform-specific tests when possible, type/lint/security checks, migrations, packaging/build smoke checks and architecture/static checks.
13. **Run adversarial/fault tests:** Inject provider timeouts, malformed responses, database exceptions, duplicate webhook/event delivery, lost acknowledgement, permission denial, stale version and restart where relevant.
14. **Record objective evidence:** Update phase report, regression record, issue ledger, decision log and master progress table. Record command, SHA, environment, result, counts, skipped/blocked tests and links to evidence.
15. **Apply exit gate:** Mark `PASSED` only when all required acceptance criteria pass. Any unmet criterion must remain `FAILED`, `BLOCKED` or `NOT_RUN`; do not start dependent phases on false green.
16. **Reconcile the repository:** Ensure tests, documentation, migrations, schemas, UI, API contracts, feature flags and deployment configuration agree. Check uncommitted changes and finish with a clean, understandable phase commit or checkpoint.
17. **Then move forward:** Continue to the next phase autonomously once the gate is green. For parallel streams, integration still follows the dependency contract in Section 8.

### 2.2 Valid status meanings

Use only these statuses, consistently:

- `NOT_STARTED` — no work has begun.
- `IN_PROGRESS` — plan approved and execution underway.
- `PASSED` — every applicable gate passed with evidence.
- `FAILED` — executed and failed; defects remain.
- `BLOCKED` — a material dependency prevents execution, with the exact blocker and owner/next action recorded.
- `NOT_RUN` — not executed. Never count as passing.
- `NOT_APPLICABLE` — explicitly excluded with written rationale and approval.
- `REOPENED` — a passed item failed during later integration/regression and is back in scope.

A phase summary may not be `PASSED` when a required subtask is `FAILED`, `BLOCKED`, `NOT_RUN` or `REOPENED`. If a P0/P1 appears later, reopen the affected phase and release gate.

### 2.3 Severity rules

- **P0 — Critical blocker:** unauthorized data access, tenant leakage, authentication bypass, fabricated successful payment, incorrect official marks/payroll, corrupted/lost durable records, real secret exposure, false AI execution status, critical production startup/inference failure, unrecoverable upgrade or backup/restore failure.
- **P1 — High blocker for production:** major workflow dead-end, incorrect fees/balances, duplicate financial/attendance events, invalid report cards, missing authorization on sensitive actions, unsafe fallback, serious sync loss, unbounded job/resource use, non-reproducible release or major unhandled failure.
- **P2 — Important:** material usability or maintainability issue, noncritical workflow edge case, incomplete observability/analytics or unsupported configuration not required for the release target.
- **P3 — Low:** cosmetic issue or low-impact refinement.

P0 and P1 must be fixed before the affected phase can pass. P2 can be deferred only with an owner, documented impact, workaround and explicit product/release approval. Do not silently downgrade severity to meet a deadline.

---

## 3. Accepted product scope and non-negotiable product contract

### 3.1 Product commitments

- **Market:** both K–12 schools and coaching/educational institutes.
- **Deployment:** hybrid. Local/offline operation must be explicitly designed and verified; central hosting must have an explicit secure data model and synchronization policy.
- **ERP:** full scope, delivered in gates. Full target includes school core, HR/payroll, transport, hostel, inventory/assets, visitor management, certificates/ID cards, messaging and public CMS.
- **Delivery priority:** parallel AI Learning Suite reliability and core ERP development after the common foundations are green.
- **Architecture:** one platform, one identity and permission model, shared student/course/institution records, two coordinated suites, optional modules with explicit entitlements.

### 3.2 First integrated pilot scope

The first integrated pilot should prove a complete vertical workflow across the AI and ERP suites, not every edge feature. It must include:

- Institution setup and roles/permissions.
- Academic year/term configuration appropriate to tenant type.
- Student and guardian records, staff/teacher membership, class/section or coaching-batch membership, course offering and enrollment.
- Admission-to-active-enrollment journey (minimal functional admissions lifecycle).
- Daily attendance, correction request and audit.
- Timetable creation and conflict detection for applicable tenants.
- Assessment, authorized grading/review, printable report card or appropriate coaching result report.
- Fee structures/invoices/payment status with real configured provider path or controlled manual-payment reconciliation; mocks are never production success.
- Real-model AI tutoring and scoped RAG on an approved course pack, durable session/learning records and teacher visibility.
- Basic notifications and visible delivery status for approved channels.
- Offline-safe local usage and tested synchronization for the explicitly supported data entities.
- Production-grade auth, tenant isolation, logs, backup, restore and operational runbooks.

### 3.3 Full ERP target modules

All following modules are in product scope. A module may be feature-flagged/entitlement-disabled for a tenant, but must never be advertised as available if its backend, permissions, failure handling or support workflow is incomplete.

1. Admissions and inquiry CRM.
2. Student information system and guardian management.
3. Academic calendars, classes, batches, courses, cohorts and enrollment.
4. Attendance: manual, classroom, late arrival, absence, correction, import and eventual hardware.
5. Timetable and substitution management.
6. Examinations, question bank, marks, grade scales, moderation, report cards and transcripts where applicable.
7. Fees, invoices, payment provider integrations, manual payment reconciliation, receipts, concessions, refunds, arrears and financial exports.
8. Staff directory, leave, staff attendance and payroll preparation/approvals. Actual salary disbursement is not implemented without explicit provider/legal requirements and authorization.
9. Transport: routes, stops, vehicles, drivers, student allocation and optional GPS provider integration.
10. Hostel/boarding: allocation, capacity, check-in/out, leave, warden log and mess fees as configured.
11. Inventory/assets: vendors, purchase requests/orders, receipt, issue/return, stock adjustments and audit.
12. Visitor management and gate pass/pickup authorization.
13. Certificates/ID cards: versioned templates, controlled personal data fields, preview, batch generation, reissue and print/download audit.
14. Communications: in-app, email, SMS, WhatsApp or other channels through approved providers; templates, consent/preferences, retries and delivery receipts.
15. Public school CMS: public announcements, events, admission notices, media uploads and accessibility/security safeguards.
16. Institution/cross-suite analytics and exportable reports.
17. Hardware edge daemon/connectors for supported attendance devices, isolated from UI/model process.
18. Platform operations: tenant provisioning, module entitlements, audit, retention, backup/restore, sync management, logs, alerts, support diagnostics and release/update processes.

### 3.4 No demo-only functionality in production

The following are prohibited as production behavior:

- Seeded fake users, default admin identities, pre-canned notifications or sample question banks returned as if they were a real tenant's data.
- Model mocks or canned replies labeled as real AI answers.
- Fake payment order IDs, invented captured status, fabricated refunds or receipts.
- Static dashboards with illustrative values presented as live institution metrics.
- Frontend-only state changes for admission, marks, fees, attendance, timetable or staff records.
- “Export succeeded” when the file was not generated/stored; “notification sent” when provider delivery was not accepted; “sync succeeded” when server acknowledgement did not arrive.
- Catching errors and returning `200 OK`, `ok: true`, zero values or stale data without a visible degraded indicator and documented policy.
- Empty placeholders sold as implemented modules.

A test/demo mode is allowed only when clearly labeled, isolated from production data and credentials, and impossible to enable accidentally in production configuration. Startup must fail if production configuration would activate unsafe mock/sample behavior.

---

## 4. Universal feature-development protocol — mandatory before every ERP feature

An ERP feature cannot enter implementation until its full scope has been understood and written down. Repeat this protocol for every module and meaningful feature slice, not just once for the entire project.

### 4.1 Discover the actual scope

Create `docs/development/features/<FEATURE_ID>_<slug>/SCOPE.md` and include:

1. **Purpose and beneficiaries:** Which user problem is solved? Which institution types use it? Which roles act on it?
2. **In-scope and out-of-scope behavior:** Explicitly list both. A narrow first slice is acceptable; an undefined feature is not.
3. **Business glossary:** Define terms, statuses, financial or academic meaning, identifiers, units/currency/timezone and institution-specific variants.
4. **Workflow maps:** Every happy path plus alternative, rejected, cancelled, expired, duplicate, failed, reopened and recovery path.
5. **State machine:** Allowed states, transition guards, terminal states, who may transition, transaction boundaries and invalid transitions.
6. **Data ownership:** Canonical owner service/table for every record. Identify relationships to student, guardian, staff, class, course, tenant and audit trail.
7. **Permission matrix:** Roles/permission codes, organization scope, record scope, field-level restrictions and negative cases.
8. **Validation:** Required fields, formats, ranges, business-rule validation, uniqueness, foreign keys, date rules and cross-record invariants.
9. **Privacy and retention:** Sensitive fields, lawful/product purpose, visibility, export/delete/anonymize constraints, retention and audit requirements; do not invent legal conclusions.
10. **External dependencies:** Payment, messaging, storage, biometric, GPS, payroll or document engine; provider sandbox availability and failure conditions.
11. **Offline and synchronization:** Which actions may be offline, which are prohibited offline, conflict policy, idempotency strategy and user visibility of pending operations.
12. **Notifications and side effects:** What triggers them, recipient eligibility, consent/preferences, retries, deduplication and delivery states.
13. **User experience:** Entry point, empty/loading/error/permission-denied/offline states, progress, confirmation, edit/cancel, retry, support reference and accessibility.
14. **Reporting:** Source-of-truth query, filters, time ranges, pagination, exports, reconciliation and whether data is eventually consistent.
15. **Operational support:** Logs, metrics, health status, retry/reconciliation tools, manual support actions and runbooks.
16. **Migration/import/backfill:** Legacy data behavior, default values, data quality report, duplicates, rollback/forward recovery and tenant separation.
17. **Acceptance criteria:** Given/when/then criteria for real persisted behavior and failures.
18. **Traceability:** Requirement IDs link to design elements, implementation files, API contracts, test IDs and evidence.
19. **Open questions/assumptions:** What remains unknown, how it was handled, owner and whether it blocks implementation.

### 4.2 Define the business acceptance matrix

Before code, prepare a test matrix that includes at least:

| Scenario class | Required question |
|---|---|
| Happy path | Does an authorized user complete the complete workflow and observe durable state? |
| Validation | Are malformed, incomplete, duplicate and out-of-range values rejected clearly? |
| Authorization | Are unauthenticated, wrong-role, wrong-tenant and wrong-resource requests rejected? |
| State machine | Are all illegal transitions rejected and all allowed transitions auditable? |
| Concurrency | What happens when two users update the same record simultaneously? |
| Idempotency | Does a client retry create exactly one business effect? |
| Persistence | Does data survive request completion, process restart and application restart? |
| External service | What happens on timeout, provider rejection, invalid signature, rate limit and malformed response? |
| Partial failure | Can the workflow recover when the main write succeeds but notification/export/secondary action fails? |
| Offline | Is the operation supported offline? If not, is it explicitly blocked rather than falsely accepted? |
| Conflict | Is the conflict resolved according to the domain policy and visible to the responsible user? |
| Audit | Can an auditor identify who did what, when, from which state, and how a correction was made? |
| UX | Does each failure produce an understandable message and safe next action? |
| Observability | Can operators find failure using request/job/provider reference without sensitive payload logging? |
| Upgrade | Does existing data migrate safely and remain accessible? |
| Accessibility | Can core workflows be used by keyboard, screen readers and supported display sizes? |
| Performance | Does the workflow meet measured latency/capacity goals for the target pilot? |
| Recovery | Can a stuck or failed workflow be retried, cancelled, reconciled or escalated? |

### 4.3 Define the operational contract

For each stateful workflow, write explicit contracts:

- **Command contract:** required input, authenticated actor, authorization, idempotency key, request ID, validation and expected result.
- **Persistence contract:** tables changed, transaction boundary, constraints and expected durable status after each outcome.
- **Event contract:** event ID, schema version, tenant, entity ID/version, timestamp, actor, correlation ID and privacy classification.
- **Side-effect contract:** queue/job ID, retryable/non-retryable classification, deduplication key and final delivery state.
- **Error contract:** stable error code, safe user message, retry recommendation and diagnostic correlation reference.
- **Recovery contract:** operator/client action to resume, retry, cancel, reconcile or escalate without duplicate effects.

### 4.4 Build a vertical slice, not a disconnected layer

Implement and test the feature through its entire path in small slices:

1. Validated domain rules and unit tests.
2. Schema/migration and repository persistence.
3. Domain service with transaction and error semantics.
4. API contract and route authorization.
5. Client/UI integration.
6. Empty/loading/success/error/offline/permission UX.
7. Audit, logs, metrics and recovery/admin support.
8. E2E regression and acceptance evidence.

Do not add a large table model with no workflow, or a screen with static values, and declare the feature implemented.

---

## 5. Architecture and implementation standards

### 5.1 Single source of truth

For every entity, document the canonical service and storage authority. Avoid independent in-memory caches or module-level database instances as authoritative owners. Caches may accelerate reads but must have clear invalidation, TTL and stale-data semantics.

Use application lifespan/dependency injection for connection pools and service construction. Do not create database connections, AI model runtimes or network clients unexpectedly at import time. Resource creation, startup health checks, shutdown cleanup and test isolation must be explicit.

### 5.2 Domain boundaries

Recommended conceptual domains:

- Identity, tenant, roles and entitlements.
- Institution configuration and academic calendar.
- Person directory and relationships (students, guardians, staff).
- Admissions.
- Class/section/batch, course, curriculum and enrollment.
- Attendance.
- Timetable and resource scheduling.
- Assessment/exam/grading/reporting.
- AI tutor/RAG/learning state/mastery.
- Fees/payments/accounting/reconciliation.
- HR/leave/payroll preparation.
- Transport/fleet/hostel/inventory/visitors.
- Communications/notification jobs.
- Documents/certificates/public CMS.
- Sync/outbox/conflict reconciliation.
- Audit/analytics/operations.

A domain service owns business invariants. Route handlers parse requests, authenticate/authorize, call services, translate results to versioned DTOs and return appropriate statuses. UI controllers handle interaction/display and should not reimplement authoritative business rules.

### 5.3 API standards

- Maintain an explicit API version prefix and OpenAPI contract.
- Use stable request/response schemas; do not expose database row shapes or internal exceptions directly.
- Validate input at both boundary and domain invariant levels.
- Use consistent pagination, sorting, filtering, timestamp and error formats.
- Use appropriate HTTP status codes; no blanket 200 for failures.
- For mutating operations, define idempotency and concurrency semantics where retries or duplicate effects are possible.
- Protect against object-level authorization issues on every ID-addressed endpoint.
- Add rate limits and request-size limits to login, public forms, uploads, AI calls and other abuse-prone paths.
- Keep legacy endpoints only with an explicit migration/retirement plan; they must call the same domain service and authorization policy as canonical endpoints.
- Generate/update route contract tests and consumer/client compatibility checks when API contracts change.
- Never leak stack traces, SQL, secrets or private content to clients.

### 5.4 Database and migrations

- Inspect actual existing migrations before proposing schema changes. Do not infer table shape from docs alone.
- Add forward, tested migrations; add down scripts where safely possible. Some data migrations are not genuinely reversible—document forward recovery instead of pretending they are.
- Enforce foreign keys, unique constraints, check constraints and indexes where they protect invariants.
- Use explicit transactions for multi-row business changes.
- Use decimal/integer minor units for money; never use floating point as the authoritative financial amount.
- Store timestamps in UTC and render in configured institution/user timezone; model the local business date separately where needed.
- Version important business records. Use optimistic concurrency or explicit locking for competing edits.
- Do not hard-delete financial ledgers, approved marks, attendance correction histories or audit trails to hide past actions.
- Migrations must be tested from fresh database, previous supported version, populated representative fixture and interrupted/failed migration scenario.
- Backups and restore must be verified on an isolated target, not inferred from a successful backup command.

### 5.5 Database deployment decision gate

The roadmap targets local SQLite and central PostgreSQL. The inspected repository has SQLite-based implementation code in the current database abstraction while docs mention PostgreSQL. Do not claim cross-engine support until it is demonstrated.

Before supporting PostgreSQL:

1. Identify all direct `sqlite3` usage, dialect-specific SQL and assumptions.
2. Select and document a real multi-engine repository/ORM strategy.
3. Remove accidental database construction scattered through routes/services.
4. Port migrations and transaction semantics deliberately.
5. Add dedicated PostgreSQL integration CI, concurrency tests and migration tests.
6. Prove tenant isolation under concurrent requests.
7. If not completed, make the supported deployment claim explicit: local SQLite and only the central database engine that has actually passed the full suite.

A changed `DATABASE_URL` or config variable is not an implementation.

### 5.6 Hybrid/offline contract

Offline capability must be specified per feature, not assumed for the entire ERP.

- Store supported local writes durably in a local database/outbox before reporting “saved locally.”
- Mark state honestly: `PENDING_SYNC`, `SYNCED`, `CONFLICT`, `FAILED_RETRYABLE`, `FAILED_FINAL` or equivalent documented states.
- Use globally unique operation IDs/idempotency keys and a server-side deduplication ledger.
- Validate device binding and authorized user/tenant ownership when syncing.
- Protect local data at rest where required by the deployment threat model.
- Never perform irreversible or highly consequential actions offline unless the domain contract explicitly supports safe queued approval semantics.
- Do not last-write-wins official marks, payments/refunds, payroll, admission decisions or attendance corrections without entity-specific conflict rules.
- Expose pending queue, last successful sync, failures, conflict resolution and retry/cancel actions to authorized users/support staff.
- Test loss of connectivity during upload, during acknowledgement, after server commit, before local acknowledgement and during conflict resolution.

### 5.7 UI/UX requirements

For each actionable screen, support loading, empty, success, validation error, permission denied, unavailable service, offline mode, unsaved edits, retry and destructive-action confirmation where relevant. All labels, dates, currency and grading output must derive from tenant/user configuration rather than assumptions. Avoid hard-coded student names, IDs, courses, fee amounts or dashboard metrics.

Core workflows must be responsive and accessible, handle keyboard navigation/focus/errors, and not leak information through hidden page state. If the product retains a desktop shell and adds a web portal, document the shared UI contract and ensure they use the same backend authority.

---

## 6. Data model checklist

The following is a target domain inventory, not a declaration that these tables already exist. Before adding anything, compare this list against actual migrations and entities to reuse or extend existing structures without duplicating them.

### 6.1 Shared platform and tenant

- `organizations` / institution: tenant identity, status, configuration, timezone, locale, type and settings.
- `users`, `user_credentials`, `roles`, `permissions`, `role_permissions`, `user_role_assignments` or the equivalent existing model.
- Institution membership, role scope, class/course assignment and guardian link tables as needed.
- `academic_years`, `terms`, `school_calendar_events`, working days/holidays, configurable periods and academic policy versions.
- `audit_events`/audit ledger with actor, tenant, action, entity, entity ID/version, before/after digest or allowed structured diff, timestamp and correlation ID.
- `idempotency_records`, `outbox_events`, job queue state and webhook/event deduplication records as required by existing architecture.
- Feature entitlements, module flags and provider configuration (secrets stored in secret manager/environment, not plain database fields).

### 6.2 Student and relationships

- Student identity/profile and lifecycle status.
- Guardian/person records and many-to-many student-guardian relationship, including relationship, authorized pickup/communication flags and visibility rules.
- Staff/teacher profile linked to user identity, institution employment status and assigned memberships.
- Student/class/batch/course membership with start/end dates and historical transitions.
- Admission conversion references; avoid creating duplicate student users upon retry.
- Document metadata with owner, scope, file hash, content type, encrypted storage location, scan/index status and retention.

### 6.3 Admissions

Candidate entities: `admission_inquiries`, `applications`, `application_documents`, `application_stage_history`, `admission_decisions`, `admission_offers` or equivalent. Enforce public-form abuse controls, tenant scope, consent/retention, document security, duplicate-applicant detection and idempotent conversion into a student profile.

### 6.4 Attendance

Candidate entities: `attendance_sessions`/class date records, `attendance_records`, `attendance_corrections`, `attendance_events`, `device_registry`, `device_bindings` and import batches. Define attendance statuses, timezone/date semantics, duplicate punch behavior, late arrival and approved correction history. A derived daily rollup must trace back to its source records.

### 6.5 Timetable/resources

Candidate entities: `timetable_versions`, `timetable_slots`, `periods`, `rooms/resources`, teacher assignments, class/batch assignments, effective date ranges and substitutions. Define conflict constraints for teacher, room, group, period and effective range. Publish/version schedules so edits do not silently rewrite historical timetables.

### 6.6 Examination and grading

Candidate entities: `exam_sessions`, `assessment_blueprints`, `grade_scales`, `mark_entries`, `moderation/review events`, `grade_approvals`, `report_cards`, `report_card_versions` and generated artifact metadata. Track grading scheme version, rubric, absent/exempt statuses, max marks, rounding rules, aggregation/weighting, approval actor and publication time. Keep draft results distinct from official published outcomes.

### 6.7 Finance

Reuse and validate the existing fee domain where appropriate. Candidate entities include fee structures/plans, accounts, invoices, invoice line items, payments, payment attempts, provider events/webhooks, receipts, discounts/concessions, refunds, refund attempts, manual reconciliation entries and ledger audit events. Use an immutable or correction-aware financial ledger. Money must be stored as integer minor units or exact decimal values under a single documented convention.

### 6.8 HR and payroll

Candidate entities: staff records, contracts or compensation profiles where applicable, leave balances/requests, staff attendance inputs, payroll periods, payroll runs, payroll line items, approvals and external disbursement/reconciliation references. Separate preparation from approval and provider disbursement. Record calculation-rule/version inputs and protect compensation data with field-level permission checks.

### 6.9 Transport, hostel, inventory and visitors

- Transport routes, stops, vehicles, driver/staff assignments, student route allocations, trip/check events and optional GPS snapshots from an explicit provider.
- Hostel/building/room/bed capacity, allocations, check-in/out, leave approvals, warden notes, and configurable mess-charge references.
- Vendors, purchase requests, purchase orders, received items, stock locations, movements, issue/return, adjustments and audits.
- Visitor records, purpose, host, check-in/out, pass expiry, pickup authorizations, privacy retention and incident/audit history.

### 6.10 Certificates, notifications and CMS

- Versioned templates, allowed field mappings, generated artifact metadata, issuer, batch job, reissue/revocation reasons and access log.
- Notification templates, consent/preferences, jobs, attempts, provider IDs, retries, final outcome and deduplication keys. Do not store provider secrets alongside job payloads.
- Public CMS pages/posts/events/media metadata, publication approval, visibility, URL slug constraints, media scanning and audit; separate public views from authenticated admin APIs.

### 6.11 Schema rules before migration

For each new table, document primary key, tenant scope, foreign keys, uniqueness, state checks, indexes, timestamps, soft-delete/archive policy, audit treatment, privacy classification and migration/rollback behavior. Do not create generic JSON blobs for fields that need relational integrity, permissions, reporting or reconciliation. JSON may be appropriate for versioned provider payloads/configuration with schema validation and careful privacy controls.

---

## 7. Phase-by-phase execution plan and gates

Phases below define the mandatory execution sequence. They can be split into smaller implementation increments, but acceptance gates cannot be weakened. For each phase, create the plan file before editing and update master progress. The AI and ERP tracks can proceed in parallel only after Phase 1 establishes their shared contracts.

### PHASE 00 — Independent baseline and product contract

**Purpose:** Understand reality before implementation; reconcile roadmap scope and existing code.

**Tasks**

- [ ] Read this document, product roadmap and referenced source docs.
- [ ] Confirm repository SHA, branch, dirty state and untracked files.
- [ ] Create the repository map and identify all live entrypoints.
- [ ] Map every registered API route, middleware, auth dependency and legacy compatibility route.
- [ ] Build an actual data dictionary from applied migrations and database introspection; compare against docs.
- [ ] Trace AI path end to end, including mock provider, real model loading, RAG, output validation, learning commit and persistence.
- [ ] Trace payment lifecycle and identify mock/demo adapters and hard-coded statuses.
- [ ] Trace sync behavior and entity coverage; identify operations currently synced versus only documented.
- [ ] Inventory admissions, attendance, timetable, report-card, HR/payroll, transport, hostel, inventory, visitor, certificates, notification delivery and CMS implementation; mark each as real/partial/mock/absent based on evidence.
- [ ] Inspect actual tests: determine what is unit, integration, E2E, mocked, skipped or platform-blocked.
- [ ] Run baseline suite and capture all failures without altering test expectations.
- [ ] Create requirements traceability matrix and phase dependency map.
- [ ] Open a prioritized defect ledger with P0–P3, reproduction, expected/actual behavior, owner/phase and status.

**Required artifacts**

- `docs/development/MASTER_PROGRESS.md`
- `docs/development/REPOSITORY_MAP.md`
- `docs/development/BASELINE_REPORT.md`
- `docs/development/REQUIREMENTS_TRACEABILITY.md`
- `docs/development/DEFECT_LEDGER.md`
- `docs/development/decisions/DECISION_LOG.md`
- `docs/development/evidence/baseline/`

**Exit gate**

- [ ] Baseline commands and outcomes are reproducible.
- [ ] Every product module is labeled `RUNTIME_VERIFIED`, `CODE_OBSERVED`, `REPO_DOCUMENTED`, `PROPOSED`, `BLOCKED` or `NOT_RUN`—never guessed complete.
- [ ] The agent can describe the live request/data flow for auth, AI, RAG, learning state, fees/payments, sync and startup.
- [ ] Known release blockers have severity and reproduction or explicitly stated verification plan.
- [ ] No source code has been changed solely to improve the baseline score.

### PHASE 01 — Shared platform foundation and safe execution boundary

**Purpose:** Establish the stable base on which the AI and ERP workstreams can develop without contradictory state or security shortcuts.

**Tasks**

- [ ] Consolidate configuration sources; detect conflicting values; validate production secrets/configuration at startup.
- [ ] Decide canonical app lifespan and dependency-injection pattern for database, model runtime, provider clients, queues and domain services.
- [ ] Remove duplicate authoritative instances and unexpected module-import resource creation where confirmed by baseline.
- [ ] Define canonical domain-service map and route ownership. Legacy paths must delegate to canonical services or be retired with a documented compatibility plan.
- [ ] Review every route for authentication, object-level authorization, tenant scope and role/permission rules.
- [ ] Ensure development synthetic identities and sample fallback code are unreachable in production mode; assert this at startup and test.
- [ ] Add structured error schema, request/correlation IDs and safe logging conventions.
- [ ] Establish canonical migration lifecycle, transaction boundaries, connection lifecycle and test isolation.
- [ ] Choose and prove central database strategy. If PostgreSQL is in target scope, implement and CI-test it fully; otherwise record a scoped release limitation until support is real.
- [ ] Define shared person/student/guardian/staff identity and institution ownership model before ERP schema work.
- [ ] Define domain event and outbox conventions, idempotency convention and schema versioning.
- [ ] Establish feature entitlement/flag behavior: disabled feature returns a clear unavailability/upgrade message, not a mock success.
- [ ] Add startup validation preventing unsafe mock adapters and weak/default secrets in production.

**Exit gate**

- [ ] Full API authorization matrix passes, including negative tests.
- [ ] Every sensitive route has a tested auth dependency or equivalent provable centralized enforcement.
- [ ] Database ownership is deterministic in API and tests; no unintentional separate authoritative database instances remain.
- [ ] Startup fails fast on invalid production settings and clearly identifies non-secret configuration errors.
- [ ] Legacy routes either share the canonical authorization/domain behavior or are disabled with explicit migration documentation.
- [ ] A fresh database and an existing supported database migrate successfully; failed migration behavior is known and recoverable.
- [ ] Full regression green; remaining P0/P1 foundation defects are zero.

### PHASE 02A — AI Learning Suite correctness and reliability (parallel track A)

**Dependency:** Phase 1 green and shared student/course/tenant/API contracts frozen for this increment.

**Purpose:** Prove real AI behavior and authoritative learning state.

**Tasks**

- [ ] Verify real local model resolution, checksum/manifest validation, load errors, inference cancellation/timeouts and memory constraints.
- [ ] Make adapter identity and execution provenance explicit: real provider/model, mock, unavailable, degraded or failed.
- [ ] Ensure mock replies cannot be counted as real tutoring or mastery events.
- [ ] Test the tutor orchestrator's full step lifecycle and cancellation/error paths.
- [ ] Validate course/version/tenant scope throughout document ingest and retrieval.
- [ ] Test parse failure, empty/unreadable PDFs, malformed DOCX/JSON, oversized uploads, malicious file content and duplicate ingestion.
- [ ] Test chunk/index job lifecycle, failure/retry, index versioning, stale source invalidation and deletion.
- [ ] Add retrieval golden set and evaluate relevance, source attribution, unsupported-answer abstention and retrieval isolation.
- [ ] Test prompt injection, answer leakage, unsafe or unsupported response, malformed provider output and timeout/circuit-breaker behavior.
- [ ] Verify evaluation of learner answers and deterministic mastery update; model text alone must not directly set authoritative mastery.
- [ ] Test duplicate/replayed turns, interruption mid-turn, database rollback and recovery.
- [ ] Verify saved conversations, sessions and learning events survive restart and are accessible only to authorized users.
- [ ] Verify teacher instructions and parent visibility policy cascade exactly as defined.
- [ ] Measure latency/RAM/CPU on the minimum supported target hardware; distinguish real model from mocks.
- [ ] Validate prompt/model/version records sufficient to reproduce a reported issue without logging private prompts unnecessarily.

**Exit gate**

- [ ] Real model test has actual inference evidence and explicit model/version checksum.
- [ ] Mock/unavailable mode is labeled and cannot mutate authoritative learning state as if real learning occurred.
- [ ] RAG golden tests meet thresholds established from baseline and approved evaluation set; unsupported evidence results in abstention/qualification.
- [ ] Cross-tenant and cross-course retrieval attacks return no unauthorized chunks.
- [ ] Interrupted and replayed turns do not produce duplicate or invalid mastery writes.
- [ ] UI/API reports accurate states for model missing, provider timeout, RAG failure and persistence failure.
- [ ] Full AI-related regression green and evaluation report archived.

### PHASE 02B — Core ERP foundation and Student Information System (parallel track B)

**Dependency:** Phase 1 green; AI and ERP tracks agree on canonical identity/course/enrollment contracts.

**Purpose:** Build durable institutional records and admissions-to-enrollment workflow.

**Tasks**

- [ ] Complete tenant profile and configurable institution type (school or coaching/institute), locale/timezone and academic structure.
- [ ] Implement academic year/term/calendar structures where applicable.
- [ ] Establish student, guardian, staff and teacher relationships, preserving the existing user identity system.
- [ ] Implement class/section/cohort/batch and course offering membership with effective dates and history.
- [ ] Implement admissions inquiry, application, document checklist, stage history, decision and conversion.
- [ ] Public inquiry forms: validate input, rate-limit, prevent abuse, protect uploaded documents and keep tenant boundaries explicit.
- [ ] Detect possible duplicate applicants/students and provide safe merge/review rather than automatic destructive overwrite.
- [ ] Make admission conversion idempotent and transactional so retries cannot create duplicate student accounts/enrollments.
- [ ] Add search/filter/pagination, import validation and error report where those functions are included in the first release.
- [ ] Add audit trails for changes to identity, guardian relationships, status, enrollments and admissions decisions.
- [ ] Connect student records to existing course enrollment, learning sessions and permitted dashboards.
- [ ] Implement lifecycle actions: deactivate, transfer, withdraw, archive and reenroll with defined access/data-retention behavior.

**Exit gate**

- [ ] A real persisted application can complete the admission-to-student-to-class/course journey end to end.
- [ ] Duplicate submit/retry is idempotent; partial failure can resume or roll back safely.
- [ ] Guardian permissions and student relationship boundaries pass positive and negative tests.
- [ ] Student and class rosters reconcile across admin, teacher, student, parent and learning screens.
- [ ] School-only concepts are not mandatory for coaching institute tenants unless configured.
- [ ] Data import failures are itemized; invalid rows are not silently discarded.

### PHASE 03 — Attendance, timetable and communications foundation

**Purpose:** Deliver daily operational workflows with auditability and recoverability.

**Tasks: Attendance**

- [ ] Define attendance statuses, sessions, school/business date, timezone, check-in rules, grace periods and correction policy.
- [ ] Support authorized teacher/admin manual attendance and class/batch roll calls.
- [ ] Prevent duplicate records by attendance session/student and idempotency key.
- [ ] Record late arrival, absence, excused/approved status and corrections as auditable transitions.
- [ ] Define whether students/parents can submit requests or only view records.
- [ ] Implement authorized roster, daily/class reports and safe bulk operations.
- [ ] Queue absence notifications only after attendance commit and appropriate policy checks.

**Tasks: Timetable**

- [ ] Define calendars, period lengths, rooms/resources, teacher availability, class/batch capacity and effective versions.
- [ ] Detect teacher, room, class/batch and required-subject conflicts on draft creation and publication.
- [ ] Support draft, validate, publish, supersede and archive states.
- [ ] Support substitutions/reschedules with notifications and audit.
- [ ] Keep historical timetables stable and define behavior for cancelled/moved sessions.
- [ ] Permit simpler batch schedules for coaching institutes without forcing school-style periods.

**Tasks: Communications**

- [ ] Define notification provider abstraction and durable job/attempt records.
- [ ] Implement in-app delivery and at least the provider channels explicitly selected for the pilot.
- [ ] Respect consent/preferences, recipient status, quiet hours where configured and parent/guardian links.
- [ ] Use retry/backoff for transient failures and dead-letter/review state for permanent failures.
- [ ] Verify provider acknowledgement vs actual delivery receipt semantics; do not state “delivered” on mere enqueue.
- [ ] Provide authorized job status, retry and audit view.

**Exit gate**

- [ ] Attendance persists and survives restart; duplicate and correction cases are deterministic and auditable.
- [ ] Timetable conflict tests catch each supported resource conflict before publish.
- [ ] No publication can result in an unvalidated timetable being represented as conflict-free.
- [ ] Notification outages do not roll back core attendance/timetable records; they surface as recoverable pending/failure states.
- [ ] Queue jobs cannot become silently stuck; retry limits and final state are tested.

### PHASE 04 — Examinations, official grading and report cards

**Purpose:** Provide an official academic outcome workflow distinct from AI formative feedback.

**Tasks**

- [ ] Scope tenant-configurable exam terms, assessment types, subject/group rules and mark/grade scales.
- [ ] Define max marks, weighting, aggregation, absent/exempt/withdrawn behavior, rounding and grade-band boundaries.
- [ ] Version grading policies; each result references the policy/version used to calculate it.
- [ ] Support question/exam setup, schedule, teacher allocation, submission/marks entry and review.
- [ ] Validate marks and rubric outputs; reject negative, over-maximum, invalid or missing values according to the scheme.
- [ ] Separate draft marks, reviewed marks, approved results and published reports.
- [ ] Require permissioned review for changes to finalized results and preserve prior version/change rationale.
- [ ] Generate report cards from approved persisted results only, with deterministic totals and a record of PDF/artifact version.
- [ ] Use escaped/validated template fields, page-break handling, fonts, locale and accessibility/readability checks.
- [ ] Make generation jobs idempotent and expose generation failures/retry.
- [ ] Test report cards against independently calculated expected marks and sample cases, not only snapshot images.
- [ ] Prohibit AI from silently mutating official grades or publishing results.

**Exit gate**

- [ ] Grading engine passes table-driven tests for every supported grading boundary and exception case.
- [ ] Approved report cards reconcile to independently calculated results.
- [ ] Draft/unapproved marks are never visible as official published results.
- [ ] Changes to final results are versioned, permissioned and audited.
- [ ] Failed PDF generation cannot be displayed/downloaded as success and has recoverable job state.
- [ ] Report output verified at supported print sizes, locale, Unicode and target fonts.

### PHASE 05 — Finance, real payment integrations and reconciliation

**Purpose:** Make finance authoritative and safe; a fee screen alone is insufficient.

**Tasks**

- [ ] Map existing fee tables/services and inspect actual amount types before changes.
- [ ] Define currency convention, minor units/decimal precision, rounding, tax/discount policy if in scope, invoice numbering and fiscal/business date.
- [ ] Implement/version fee structures and plans, accounts, invoices/line items, concessions/discounts and adjustment approvals.
- [ ] Model payment intent/order, attempt, provider event, settlement, receipt, refund and reconciliation separately where needed.
- [ ] Integrate the official provider SDK/API in a controlled sandbox; use real provider order creation and server-side status verification.
- [ ] Verify webhook signatures against raw request bytes and correct secret; validate timestamp/replay policy where supported.
- [ ] Deduplicate provider events by provider event/order/payment identifiers and idempotency key.
- [ ] Do not mark a payment captured based only on client input or a locally generated payment ID.
- [ ] Store append-only payment events/ledger movements; apply explicit corrections rather than rewriting history.
- [ ] Define pending, created, authorized, captured/settled, failed, cancelled, partially refunded, refunded and reconciliation-required transitions appropriate to provider semantics.
- [ ] Reconcile local payment records against provider state and manual offline/cash transfers; show unexplained discrepancies.
- [ ] Implement receipts generated only for confirmed/reconciled qualifying payments.
- [ ] Implement refunds with permission, balance checks, partial/full amount rules, provider response capture and failure recovery.
- [ ] Prevent sensitive payment secrets/card data from entering logs or general app storage.
- [ ] Provide statements, arrears and finance exports that reconcile to the underlying ledger.
- [ ] Separate test/mock adapter registration from production; startup fails if a mock is configured as the production provider.

**Exit gate**

- [ ] Sandbox integration creates real provider-side test orders; payment verification is server-authoritative.
- [ ] Duplicate and out-of-order webhooks do not double-post the ledger or issue duplicate receipts.
- [ ] Failed/ambiguous payments enter reconciliation rather than fabricated success/failure.
- [ ] Refund lifecycle, partial refunds and provider outages are tested.
- [ ] Invoice/account balances reconcile from ledger data; report is checked by independent calculation.
- [ ] The app clearly separates `MOCK`, `SANDBOX`, `LIVE` provider modes; production cannot use mock status responses.
- [ ] Finance logs and evidence contain no secrets or unnecessary student financial details.

### PHASE 06 — Full ERP expansion: staff, payroll, transport, hostel, inventory, visitors, certificates and CMS

**Dependency:** Shared platform, tenant/auth/audit model green; each feature must complete Section 4 before code.

**General rule:** Every submodule gets its own scope and exit gate; no “ERP completed” claim is allowed because a shared CRUD API exists.

**6A. Staff and HR**

- [ ] Define staff profile lifecycle and employment status, effective dates and authorization.
- [ ] Link teacher/staff accounts without duplicate users.
- [ ] Implement leave policy, request, approval/rejection, withdrawal and overlapping-date validation.
- [ ] Support staff attendance where included, with correction/audit.
- [ ] Restrict sensitive personnel and compensation fields by permission.

**6B. Payroll preparation and approval**

- [ ] Document supported country/jurisdiction and payroll requirements before claiming statutory compliance.
- [ ] Store compensation/allowance/deduction components using exact amounts and rule versions.
- [ ] Define payroll period, eligibility, proration, absence/leave inputs, calculation formula and rounding.
- [ ] Separate draft calculation, validation, approval, export/disbursement and reconciliation states.
- [ ] Recalculate deterministically and retain calculation inputs/result digest for audit.
- [ ] Require dual approval or configurable maker-checker for sensitive payroll release where the policy specifies it.
- [ ] Do not automatically transfer salary unless real provider integration, authorization, sanctions/validation, reconciliation and required legal scope are explicitly established.

**6C. Transport**

- [ ] Implement routes/stops, vehicles, driver assignments, student allocation, effective dates and capacity checks.
- [ ] Validate vehicle/driver availability and conflicts.
- [ ] Keep GPS integration optional and provider-specific; distinguish stale location from current tracking.
- [ ] Protect location/pickup information and limit access to authorized roles/guardians.
- [ ] Define offline behavior, data retention and device-provider failure behavior.

**6D. Hostel and boarding**

- [ ] Implement buildings/rooms/beds, occupancy/capacity, allocation, check-in/out and transfer.
- [ ] Prevent double allocation and invalid capacity.
- [ ] Implement leave/outpass request and approval, warden log and incident audit as configured.
- [ ] Link hostel/mess fees to the canonical financial service; do not maintain a parallel balance ledger.
- [ ] Restrict sensitive location and incident notes.

**6E. Inventory and assets**

- [ ] Define stock items, units, warehouses/locations, vendors, purchase requisition/order, receipt and issuance lifecycle.
- [ ] Keep movements append-only or correction-aware; stock balance must reconcile from movements.
- [ ] Handle partial deliveries, damaged/returned items, adjustments, serial numbers and fixed assets if in scope.
- [ ] Use authorization and thresholds for procurement/adjustments; audit overrides.
- [ ] Report negative stock, mismatches and pending deliveries explicitly.

**6F. Visitor, gate pass and pickup authorization**

- [ ] Define visitor check-in/out, host, purpose, identity data handling, pass expiry and emergency scenarios.
- [ ] Implement revocation/cancellation and prevent reuse of expired passes.
- [ ] Validate guardian pickup authorization against current guardian/student records and policy.
- [ ] Restrict record access and schedule retention/deletion according to documented policy.

**6G. Certificate and ID card designer**

- [ ] Define approved templates, field allowlist, versioning, preview, issue/reissue/revoke and batch job.
- [ ] Escape user content and protect template engines against code injection/path traversal.
- [ ] Avoid exposing unrelated PII through template fields.
- [ ] Test long names, Unicode, missing photos, corrupted images, font fallback, pagination and print dimensions.
- [ ] Store artifact checksum, generation metadata, issuer, template version and access history.

**6H. Public CMS and admissions website**

- [ ] Separate public endpoints/content from authenticated admin endpoints.
- [ ] Add draft/review/publish/unpublish/archive states and publication audit.
- [ ] Validate URL slug uniqueness, media upload type/size, scanning, metadata and safe rendering.
- [ ] Apply rate limiting and anti-abuse protection to forms.
- [ ] Prevent private student/guardian records from appearing in public search, media and analytics.
- [ ] Include responsive/accessibility/SEO basics only after secure publish workflow is functional.

**Exit gate for each submodule**

- [ ] `SCOPE.md` complete and acceptance matrix approved before code.
- [ ] Real workflow persists, obeys authorization and survives restart.
- [ ] Every state transition and failure path tested.
- [ ] Audit, reporting, import/export and recovery are complete for that module.
- [ ] External provider behavior is real in sandbox or the feature is explicitly labelled unavailable—not faked.
- [ ] All P0/P1 submodule findings closed and module is correctly feature-gated until complete.

### PHASE 07 — Offline sync hardening and hardware edge integrations

**Purpose:** Extend offline capability from learning events to explicitly supported operations without risking the main UI/model runtime.

**Tasks**

- [ ] Publish an entity-by-entity offline support matrix.
- [ ] Separate edge/device daemon process from desktop UI and model inference. Hardware I/O must not block UI or tutor generation.
- [ ] Define secure local REST/message ingress, device identity, device secret/certificate lifecycle, payload validation and rate limits.
- [ ] Support only explicitly tested device protocols/drivers. Do not claim generic biometric compatibility.
- [ ] Use idempotent operation keys and durable local outbox/central processed-event ledger.
- [ ] Verify batch partial success and per-item acknowledgement semantics; never discard failed items when a batch partially succeeds.
- [ ] Define entity-specific conflict handling: auto-merge safe fields, reject stale writes where needed, route consequential conflicts for human review.
- [ ] Add sync health dashboard with pending queue age, retries, dead-letter count, conflict count, last success and safe device diagnostics.
- [ ] Test network loss before/after central commit, replay, duplicated device punches, out-of-order events, clock skew, corrupt payload and device revocation.
- [ ] Encrypt credentials and sensitive local records under documented threat model; support secure updates and credential rotation.
- [ ] Ensure edge service has least privilege and can be restarted independently.

**Exit gate**

- [ ] Supported offline entities are documented, not implied.
- [ ] Replayed events create no duplicate consequential business effect.
- [ ] All queue items end in acknowledged, retryable, terminal-failed or conflict state; no silent drop.
- [ ] Conflict decisions are deterministic/auditable and high-impact records cannot be silently overwritten.
- [ ] A hardware/device failure cannot crash the UI or AI runtime.
- [ ] Driver/protocol integration is tested against simulator and real approved device when hardware is part of the release; otherwise hardware is `BLOCKED`/not offered.

### PHASE 08 — Unified analytics, quality, accessibility and institution pilot

**Purpose:** Connect suites without allowing analytics to become an independent or misleading source of truth.

**Tasks**

- [ ] Define each KPI, source table/event, time window, tenant scope, freshness and denominator in a data dictionary.
- [ ] Reconcile dashboard counts against SQL/source-of-truth records in test fixtures.
- [ ] Use evidence-based learning insights; make explanations and data freshness visible.
- [ ] Enforce parent privacy levels and school policy before generating summary data.
- [ ] Test institution setup end to end for both a school and a coaching/institute tenant.
- [ ] Run usability testing on the real UI and typical/edge workflows; fix dead ends rather than training users to work around them.
- [ ] Perform accessibility checks on key student, guardian, teacher, admin, finance and admission journeys.
- [ ] Establish performance baselines and load profiles using realistic institution sizes and request patterns.
- [ ] Test exports/reports for filters, pagination, timezone, data leakage and large data sets.
- [ ] Validate backup/restore, release update and support diagnostic workflows.

**Exit gate**

- [ ] Dashboard outputs reconcile to canonical source records within the documented consistency window.
- [ ] School and coaching configurations both pass critical journeys without code forks or invalid required fields.
- [ ] Core journeys have no known dead-end or false success.
- [ ] Accessibility and performance issues exceeding agreed severity are fixed or release-blocking exceptions are explicitly approved.
- [ ] Pilot feedback, defects, mitigations and owner decisions are captured.

### PHASE 09 — Production release gate and controlled rollout

**Purpose:** Prove deployability, safety, maintainability and operational recovery under the actual release configuration.

**Tasks**

- [ ] Create a release-candidate checklist tied to commit SHA and build artifact checksum.
- [ ] Run the full test suite, required real-model suite, database tests, API E2E, security suite, load tests and packaging smoke tests.
- [ ] Run dependency vulnerability and license checks where tooling exists; inspect newly added dependencies and pin supported versions.
- [ ] Perform code review for critical paths: auth/RBAC, tenant isolation, payments, grading, AI state commits, sync, upload/document handling, logs and secrets.
- [ ] Test fresh installation, in-place upgrade, interrupted upgrade recovery and rollback/forward-fix path.
- [ ] Restore a backup into an isolated environment and verify business-level integrity.
- [ ] Confirm production configuration does not enable dev auth, mock providers, synthetic data, debug/reload, public API docs unless intentionally approved, wildcard CORS or hard-coded secrets.
- [ ] Confirm TLS, secure cookie/token settings, rate limits, request-size caps, retention settings, logs and alert routes.
- [ ] Test external providers in their sandbox; live transactions/messages are separately authorized and not required for routine CI.
- [ ] Produce operations runbooks, incident response, support access procedure, data export/retention policy and rollback procedure.
- [ ] Obtain explicit product-owner and pilot-institution acceptance for release scope and known P2 issues.

**Hard release blockers**

- [ ] Any unresolved P0/P1.
- [ ] Missing negative authorization tests for sensitive routes.
- [ ] Any mock/demo adapter reachable in production for a critical business flow.
- [ ] Real-model inference not distinguished from mock/unavailable execution.
- [ ] Payment, marks, attendance or payroll record can report success without durable authoritative confirmation.
- [ ] Untested database upgrade/backup restore for target deployment.
- [ ] Data leakage, secret exposure or cross-tenant access.
- [ ] Critical workflow failure can be swallowed, left stuck indefinitely or cannot be recovered.
- [ ] Release artifact cannot be reproduced or the version/commit cannot be identified.

**Exit gate**

The release decision must be a signed, evidence-linked `GO`, `NO-GO` or `GO_WITH_APPROVED_P2_EXCEPTIONS`. Never issue `GO` merely because CI is green.

---

## 8. Parallel workstream coordination

### 8.1 Dependency rule

AI Learning Suite Phase 02A and ERP Phase 02B may start in parallel only after Phase 1 stabilizes shared foundations. They must agree on a written contract for:

- Organization/tenant identifiers and scope.
- User/student/guardian/teacher identity.
- Classes/batches, courses, offerings, enrollment and academic term linkage.
- Canonical database/repository transaction handling.
- Authorization and privacy policy.
- API error shape, request IDs and audit events.
- Learning events and offline sync envelope.
- Module entitlements and deployment configuration.

A contract change affecting both tracks must be recorded in `DECISION_LOG.md`, communicated via a compatibility issue and tested by both workstreams before merge.

### 8.2 Ownership and branches

Use separate branches or isolated worktrees for parallel development. Assign one integration owner for shared models, migrations, config and API contracts. Never let both agents independently invent the same student/guardian/class table or migrate the same schema domain without coordination.

Every workstream must publish:

- Plan and changed-file map.
- API/data contract changes.
- Migration identifiers/checksums.
- Focused test command/results.
- Full regression result after integration.
- Remaining defects/assumptions.

### 8.3 Integration order

1. Shared identity and platform contracts merge first.
2. ERP core and AI reliability changes rebase onto the contract.
3. Run combined integration test against one clean database and one representative upgraded database.
4. Run student admission/enrollment/tutoring/assessment/teacher-intervention journey across both suites.
5. Run authorization, tenant-isolation and sync conflict tests against integrated code.
6. Merge only when CI and integration gate are green; otherwise isolate the failing change and fix it before adding more work.

---

## 9. Testing strategy — correctness over test count

### 9.1 Required layers

1. **Static checks:** formatting, lint, type checks, import graph, dependency and secret scans as configured.
2. **Unit tests:** state transition, grading, permissions, schedule conflict, fees and deterministic learning logic.
3. **Repository/database tests:** constraints, transactions, rollback, migrations, concurrency and persistence after reopen.
4. **API contract tests:** schema validation, status codes, authentication, role/resource access, pagination and errors.
5. **Provider contract tests:** real SDK/request shape with sandbox or controlled test doubles; provider doubles must not substitute for end-to-end sandbox evidence.
6. **Integration tests:** multiple services + database + outbox/jobs + test provider.
7. **End-to-end tests:** complete user journeys through public API/UI to persisted records and visible result.
8. **Adversarial/security tests:** cross-tenant IDs, token revocation, role downgrade, stale session, IDOR, prompt injection, malicious uploads, oversized payloads, CSRF/CORS where relevant, SSRF/path traversal and brute force/rate limits.
9. **Fault injection:** provider timeout, database unavailable, corrupted model, malformed model reply, queue outage, lost acknowledgment, disk full, expired credentials, invalid webhook signature and process restart.
10. **Performance/capacity:** expected concurrent users, AI latency/queueing, large roster/report exports, job backlogs and sync batch size.
11. **Packaging/deployment:** clean machine install, upgrade, configuration, shutdown, restore and smoke test for every supported OS/deployment target.
12. **Human acceptance:** teacher, student, parent, admin, admissions and finance review of real workflows on the target pilot configuration.

### 9.2 Required negative test coverage

Every privileged endpoint should be tested for anonymous access, expired/revoked token, inactive account, wrong role, wrong tenant, wrong assigned class/course, unauthorized target ID and unexpected/missing resource. Do not infer route security from one route's tests.

Every critical data mutation should include invalid input, concurrent conflict, duplicate retry, mid-transaction exception and audit assertion.

Every asynchronous job should include enqueue failure, worker crash, retry, max retries, dead-letter/final failure, duplicate execution and restart recovery.

Every external integration should include timeout, authentication failure, rate limit, malformed response, signature/replay failure and reconciliation after ambiguous outcome.

### 9.3 Testing real AI, not mock AI

- Name and checksum the model used for each real-model result.
- Validate output and provider errors, not only nonempty text.
- Maintain golden academic/RAG cases with expected sources, allowed answer envelope and scoring rubric.
- Evaluate unsupported answer/abstention behavior and answer leakage.
- Measure quality on separate validation sets; do not tune against the exact release test questions.
- Test that mock output is never recorded as verified real model execution, official grade or mastery gain.
- If local hardware/model is unavailable in CI, label real-model evaluation `BLOCKED`/`NOT_RUN`; retain separately passing mock-based unit tests, but do not declare AI release gate complete.

### 9.4 Contract/property tests for ERP invariants

Examples of invariants that should be encoded as tests:

- Admission conversion retry creates at most one canonical student and one intended enrollment.
- One student cannot have two conflicting active enrollments in the same constrained class/offering unless the institution policy permits it.
- Attendance uniqueness holds at the configured attendance-session/student grain.
- A published timetable cannot violate the supported teacher/room/class conflict rules.
- A mark cannot exceed the configured maximum or change after publication without a permitted revision workflow.
- A report card is generated only from approved results and references a grading-policy version.
- An invoice's balance equals the documented calculation over authoritative ledger events.
- One provider payment event affects a ledger no more than once.
- Refund total cannot exceed eligible captured/settled funds under provider rules.
- Payroll release cannot occur before required approval(s).
- Inventory balance reconciles to movements; adjustment action is audited.
- An offline event replay never creates duplicate attendance/payment/learning business effects.
- No tenant query returns another tenant's record even when a caller supplies a guessed identifier.

### 9.5 Avoid vacuous tests

Review for tests that:

- Only assert status code 200 or non-empty output.
- Mock the function under test or bypass core logic.
- Ignore database state after the request.
- Disable auth/security behavior instead of configuring a realistic signed identity.
- Assert fake provider responses without separate sandbox evidence.
- Pass even when the feature is not implemented.
- Use broad exception expectation that accepts the wrong failure.
- Are skipped because the implementation is hard to test without a documented blocker.

A test should assert the actual business invariant, not implementation trivia alone.

### 9.6 Regression discipline

Whenever a defect is found:

1. Save reproduction steps and failing output.
2. Write a test that fails on the current code for the right reason.
3. Fix the root cause.
4. Run the new test, related tests and full applicable regression.
5. Inspect whether the fix changes a contract or schema.
6. Re-test all previously passed adjacent behaviors.
7. Update the defect ledger with evidence and status.

If a previously passing test starts failing, do not edit its expected result automatically. Determine whether the intended contract changed through an approved decision; otherwise treat it as a regression.

---

## 10. Security and privacy acceptance standards

### 10.1 Identity and authorization

- Validate token signature, issuer/audience where applicable, expiry, revocation and account status.
- Never trust a role or tenant ID supplied by an untrusted client without resolving/validating it against server-side identity and membership records.
- Enforce authorization at route and domain-service boundaries for sensitive operations.
- Apply object-level permissions to every ID-based read/update/delete/export/download.
- Use least privilege and explicit policy for Super Admin and support impersonation.
- Log privileged actions with actor, target, reason where appropriate and correlation ID.
- Disable insecure dev identity fallback in production and fail startup if production policy is ambiguous.

### 10.2 Tenant isolation

Every tenant-owned read/write must bind to the authenticated tenant scope. Never rely on UI filtering. Test list, search, counts, exports, download URLs, RAG chunks, background jobs, analytics, notifications, sync and logs. Jobs must persist tenant context and re-authorize before processing. Cache keys must include every relevant scope/version component.

### 10.3 Student privacy and AI

- Define which student data may enter local model context, external model provider, analytics, logs or support tooling.
- `LOCAL_ONLY` must disable network transmission of prompts/documents/student content for model inference and analytics as specified by product policy.
- Cloud fallback requires explicit policy permission and should be visible/configurable, not silently invoked after local failure.
- Keep parent summary/restricted/blocked privacy levels authoritative throughout backend queries and generated output.
- Do not use student chat history for training unless a separate approved data governance and consent policy explicitly enables it.
- Treat retrieved curriculum content as untrusted input; defend against prompt injection and malicious uploaded documents.
- Do not let AI decide access rights, official grades, fees, attendance corrections or employment/payroll action.

### 10.4 Financial and official records

- Use provider-side verification and signature validation for payment events.
- Use idempotency, append-only/correction-aware history and reconciliation.
- Use maker-checker approvals where required for consequential operations.
- Restrict exports and include access audit trails.
- Separate business state changes from notification attempts so provider outage cannot falsify the core ledger.

### 10.5 Uploads and generated files

- Restrict allowed file types and sizes; validate file contents, not just extension/MIME header.
- Use malware scanning where available and isolate parsers/converters for untrusted content.
- Store outside executable/public paths; use opaque IDs and authorized downloads or expiring URLs.
- Prevent path traversal, archive bombs, XSS/template injection and unsafe rendering.
- Scope each upload to tenant, course/record and permission; deletion must invalidate related indexes/cache where required.
- PDF/report generation must be reproducible, safely templated and not falsely successful after renderer errors.

### 10.6 Logs and secrets

- Never log passwords, tokens, API keys, payment secrets, raw credentials or unnecessary full student prompts/content.
- Use redaction and structured fields; include correlation IDs and safe identifiers.
- Store secrets in environment/secret manager. Do not commit `.env` or live secrets.
- Use explicit log retention/rotation and safe diagnostics packages.
- Ensure error traces available to operators do not leak to end users.

---

## 11. Silent-failure prevention and workflow reliability

### 11.1 Error taxonomy

Use stable machine-readable error/failure categories, for example:

- `VALIDATION_ERROR`
- `AUTHENTICATION_REQUIRED`
- `PERMISSION_DENIED`
- `RESOURCE_NOT_FOUND`
- `CONFLICT`
- `IDEMPOTENCY_REPLAY`
- `DEPENDENCY_UNAVAILABLE`
- `DEPENDENCY_TIMEOUT`
- `MODEL_UNAVAILABLE`
- `MODEL_OUTPUT_INVALID`
- `RAG_INGESTION_FAILED`
- `RAG_EVIDENCE_INSUFFICIENT`
- `PERSISTENCE_FAILED`
- `MIGRATION_FAILED`
- `PAYMENT_PENDING_VERIFICATION`
- `PAYMENT_RECONCILIATION_REQUIRED`
- `NOTIFICATION_DELIVERY_FAILED`
- `SYNC_CONFLICT`
- `JOB_RETRY_EXHAUSTED`
- `EXPORT_GENERATION_FAILED`

Choose a concise stable set that fits existing conventions rather than duplicating error systems. Map each category to retryability, user-safe text, support steps and observability.

### 11.2 Standard outcome contract

Every critical operation should return or persist enough information to distinguish:

- Completed successfully with authoritative confirmation.
- Accepted and queued but not yet completed.
- Saved locally and pending synchronization.
- Completed with partial/noncritical side effect failure.
- Recoverably failed and eligible for retry.
- Terminally failed and requiring user/operator action.
- Rejected before mutation due to validation/permission/conflict.

A boolean `ok` alone is insufficient for long-running, external or multi-step operations. Include stable status, operation/job ID when applicable, safe message, correlation ID and next action. Do not return internal stack traces.

### 11.3 Long-running jobs

For ingestion, report generation, bulk import, notification batch, payroll processing, export and sync:

- Persist job state and progress checkpoints.
- Set deadlines/timeouts, retry policy and maximum attempts.
- Make task execution idempotent.
- Have worker-heartbeat/lease or stale-job recovery.
- Define cancellation behavior and whether partial outputs are deleted, retained or marked failed.
- Store input/output summary and error classification without retaining excessive sensitive payload.
- Expose authorized status/progress UI or API.
- Support retry only where retry cannot duplicate business effects.

### 11.4 Observability

Provide structured logs, metrics and actionable alerts for:

- API error/latency and request IDs.
- Database connection/transaction/migration state.
- Model load/inference latency, model identity, timeouts and failure categories.
- RAG ingestion/index freshness/retrieval quality diagnostics.
- Queue length, oldest pending age, retries, dead-letter count and job execution time.
- Payment callback verification, unmatched provider events and reconciliation differences.
- Sync pending operations, conflicts, replay rate and last success.
- Backup status, restore verification, disk space and release version.

Health endpoints must reflect actual service readiness, not merely importable classes or existence of a config file. Liveness should be lightweight; readiness must check dependencies required to serve the chosen mode. Do not leak private data in monitoring labels.

---

## 12. Progress tracking and required working artifacts

### 12.1 Required directory structure

Create/update this structure in the repository. Do not overwrite useful existing QA history; merge the plan and evidence.

```text
docs/development/
├── MASTER_PROGRESS.md
├── REPOSITORY_MAP.md
├── BASELINE_REPORT.md
├── REQUIREMENTS_TRACEABILITY.md
├── DEFECT_LEDGER.md
├── RELEASE_READINESS.md
├── plans/
│   ├── PHASE_00_PLAN.md
│   ├── PHASE_01_PLAN.md
│   └── ...
├── features/
│   └── <FEATURE_ID>_<slug>/
│       ├── SCOPE.md
│       ├── ACCEPTANCE_MATRIX.md
│       ├── API_CONTRACT.md
│       ├── DATA_MODEL.md
│       ├── TEST_PLAN.md
│       └── RUNBOOK.md
├── reports/
│   └── PHASE_<NN>_REPORT.md
├── regressions/
│   └── PHASE_<NN>_REGRESSION.md
├── evidence/
│   ├── baseline/
│   ├── commands/
│   ├── logs/
│   ├── test-results/
│   ├── model-evaluations/
│   ├── security/
│   ├── integrations/
│   ├── migrations/
│   ├── performance/
│   ├── packaging/
│   └── restore-drills/
└── decisions/
    └── DECISION_LOG.md
```

### 12.2 Master progress table template

Keep one row per phase and important feature. Update it at the start, after each meaningful milestone and at phase close.

| Phase / Feature | Status | Scope read | Plan before code | Baseline captured | Implementation | Focused tests | Fault/security tests | Full regression | Exit gate | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| 00 Baseline | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 01 Platform foundations | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 02A AI reliability | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 02B Core ERP/SIS | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 03 Attendance/timetable/comms | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 04 Exams/report cards | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 05 Finance/payment | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 06 Full ERP extensions | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 07 Offline sync/hardware | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 08 Pilot/integration | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |
| 09 Production release | NOT_STARTED | No | No | No | No | No | No | No | PENDING | |

### 12.3 Feature work record

For each feature, record:

- Feature ID, title, owner/agent and related phase.
- User/business problem and approved scope.
- Files inspected and current implementation status.
- Data/API/UI/provider impact.
- Plan approval date and baseline commit.
- Acceptance/test IDs.
- Changed files and migration IDs.
- Commands and results.
- Known limitations, external blockers and risks.
- Evidence links and final gate status.

### 12.4 Decision log

Every nontrivial change to product behavior, architecture, data model, API contract, security policy, supported deployment, feature scope or test acceptance must be logged with date, context, options, chosen decision, rationale, affected files/contracts, migration/backfill needs and approval owner where required. Never silently change scope to make a failing test pass.

---

## 13. Phase-plan template — required before source edits

The agent must create `docs/development/plans/PHASE_<NN>_PLAN.md` from this template before making any source change in a phase.

```markdown
# Phase <NN>: <Title>

## Status
- Current status: IN_PROGRESS
- Baseline commit SHA:
- Agent/workstream:
- Start date:
- Dependencies/preceding phase gates:

## 1. Objective and user value
Describe the business outcome—not just classes/endpoints to be written.

## 2. Scope
### In scope
### Explicitly out of scope
### Required tenant/deployment modes

## 3. Repository discovery
- Source files and symbols read:
- Existing behavior confirmed:
- Existing tests and gaps:
- Related docs/migrations/API callers/UI clients:
- Unknowns and verification status labels:

## 4. Requirements and traceability
| Requirement ID | Expected behavior | API/UI/service/data touchpoints | Test ID | Severity if violated |
|---|---|---|---|---|

## 5. Business workflow and state machine
Document happy paths, transitions, alternate paths, cancellation, retries, conflict and terminal failure.

## 6. Data and migration plan
Tables/entities, constraints, transaction boundary, migration forward/rollback/restore plan and compatibility.

## 7. API/client contract
Request/response, authorization, error categories, idempotency, pagination, versioning and UI states.

## 8. Threat model and privacy
Assets, actors, trust boundaries, tenant scope, abuse cases, PII, logging/retention and mitigations.

## 9. Implementation sequence
Small vertical slices, files to change, dependencies and checkpoints.

## 10. Test plan written before implementation
Unit, repository, API, integration, E2E, negative, concurrency, fault injection, accessibility, performance and upgrade tests.

## 11. Observability and support
Metrics, structured logs, alerts, job recovery, user-facing support references and runbook changes.

## 12. Rollout and rollback
Feature flags, migration order, staged enablement, data backfill, rollback/forward repair and compatibility.

## 13. Exit criteria
List objective criteria and exact commands. Define what blocks the phase.

## 14. Execution evidence
Update with baseline, implementation, test, regression and review evidence.

## 15. Final result
PASSED / FAILED / BLOCKED / NOT_RUN. Never use PASSED without evidence links.
```

---

## 14. Feature scope and acceptance template

Every ERP feature gets `SCOPE.md` and `ACCEPTANCE_MATRIX.md` before implementation. Use this format.

```markdown
# Feature <ID>: <Name>

## Business purpose
## Personas and access matrix
## Institution types and configuration
## Scope / non-scope
## Terms and canonical records
## User journey diagrams
## State machine and allowed transitions
## Data ownership / constraints / migration
## API contract and error taxonomy
## External provider contract
## Offline/sync policy by operation
## Privacy, retention and audit
## Loading/empty/success/error/offline UX
## Reporting/export requirements
## Long-running jobs and recovery
## Support/admin intervention path
## Acceptance criteria
## Threat/fault cases
## Test IDs and evidence plan
## Rollout, feature flag and rollback
## Open assumptions / BLOCKED items
```

Acceptance cases should use Given/When/Then statements. For example:

```gherkin
Feature: Admission conversion is idempotent
  Scenario: Repeated conversion request does not create duplicate student records
    Given an approved application in tenant A with no student linked
    And the caller has permission to convert admissions for tenant A
    When the conversion command is submitted twice with the same idempotency key
    Then one canonical student record is linked to the application
    And exactly one intended enrollment is created
    And both responses refer to the same durable result
    And one logical audit event chain identifies the actor and operation

  Scenario: A caller from tenant B cannot convert tenant A application
    Given an application owned by tenant A
    And an authenticated caller belonging only to tenant B
    When the caller attempts conversion by guessing the application ID
    Then the request is rejected without mutating tenant A data
    And no sensitive application information is returned
    And the security event is logged without exposing application PII
```

---

## 15. ERP feature-specific completeness checklist

Use this checklist at every submodule gate. Mark `N/A` only with a documented reason and approval.

### 15.1 Admissions

- [ ] Inquiry/applicant can be created, updated, stage-transitioned, rejected, withdrawn or archived as permitted.
- [ ] Public form is rate-limited and resistant to invalid/oversized input and duplicate spam.
- [ ] Document upload is validated, isolated, scanned if supported and authorized for download.
- [ ] Stage history and admission decisions are auditable.
- [ ] Duplicate applicant/student review is available.
- [ ] Conversion to student/guardian/enrollment is transactional and idempotent.
- [ ] Applicant receives only allowed status and communication.
- [ ] Reports reconcile to persisted applications by stage/date/campus.
- [ ] Imports provide per-row accepted/rejected results.
- [ ] Failed emails/docs do not silently lose the application or admission record.

### 15.2 Student information and guardian relationships

- [ ] Canonical identity and tenant membership are explicit.
- [ ] Duplicate profiles can be reviewed/merged safely with history.
- [ ] Guardian relationships support appropriate multiple guardians and permissions.
- [ ] Student class/course transfers and status changes are history-preserving.
- [ ] Parent/student portal access obeys current linkage and privacy policy.
- [ ] Student export, archival and retention behavior are defined.
- [ ] No profile change implicitly grants unrelated access.

### 15.3 Attendance

- [ ] Teacher sees only assigned classes/groups unless explicit broader permission exists.
- [ ] Session roster is based on the configured membership effective at the attendance date.
- [ ] Present/absent/late/excused/other statuses are tenant-configurable where needed.
- [ ] Duplicate punches and repeated submission are handled deterministically.
- [ ] Correction preserves original event, approver, reason and timestamp.
- [ ] Attendance report reconciles to raw attendance records.
- [ ] Guardian notification follows commit, preference, guardian linkage and retry rules.
- [ ] Device timestamps, timezone, offline queue and clock-skew handling are explicit.
- [ ] No attendance event is marked synced before central acknowledgement.

### 15.4 Timetable

- [ ] Timetable is configurable for school periods or coaching sessions/batches.
- [ ] Teacher, room, cohort/class, equipment and availability conflicts are checked.
- [ ] Draft validation and publish are distinct.
- [ ] Edits to published timetable create a controlled new version or audited revision.
- [ ] Substitution, cancellation and reschedule are supported according to scope.
- [ ] Notifications are queued with delivery outcome status.
- [ ] Views respect permissions and show the correct effective timetable.

### 15.5 Examinations and report cards

- [ ] Assessment/exam lifecycle is defined and authorized.
- [ ] Marks entry has range/type validations and draft/review/approval states.
- [ ] Grading formula, weighting, rounding and absent/exempt behavior are versioned and tested.
- [ ] AI feedback remains separate from official grades.
- [ ] Published results are immutable except through approved revision workflow.
- [ ] Report card includes only approved records and correct student/term identity.
- [ ] PDF generation handles Unicode, fonts, page breaks, logos/photos and long content.
- [ ] Generated file is persisted with checksum/version and authorized access.
- [ ] Failed generation is surfaced and retryable without duplicate publication.
- [ ] Totals are independently recalculated in tests and match source marks.

### 15.6 Fees and payments

- [ ] Fee plans, invoices and adjustments are tenant-scoped and auditable.
- [ ] Currency precision, due date, discount and rounding policies are explicit.
- [ ] Payment provider mode is explicit (`MOCK`, `SANDBOX`, `LIVE`); mock is forbidden in production.
- [ ] Orders and statuses come from provider truth or controlled manual reconciliation.
- [ ] Webhook signature, replay, deduplication and retry are tested.
- [ ] A pending/ambiguous payment remains pending/reconciliation-required, not assumed successful.
- [ ] Receipts are issued only for the policy-defined confirmed state.
- [ ] Partial/full refunds, failed refunds and reconciliation are covered.
- [ ] Ledger, invoice, account and finance reports reconcile.
- [ ] No sensitive provider data is logged or sent to the browser unnecessarily.

### 15.7 HR, leave and payroll

- [ ] Staff status, department/role, effective dates and permission scopes are correct.
- [ ] Leave conflicts, balances, approval and cancellation are tested.
- [ ] Compensation data is field-restricted.
- [ ] Payroll rules are documented, versioned and independently verified.
- [ ] Draft, calculation, review, approval, export/disbursement and reconciliation states are separate.
- [ ] Changes after approval require audited correction/reopen path.
- [ ] Payroll cannot release without required approvals.
- [ ] External disbursement is not simulated as successful.
- [ ] Legal/statutory scope is explicitly limited or reviewed by qualified owner before claims are made.

### 15.8 Transport and GPS

- [ ] Route, stop, vehicle and driver assignments validate capacity and conflicts.
- [ ] Student allocation effective dates and guardian visibility are correct.
- [ ] Trip change/cancellation and incident paths are defined.
- [ ] GPS provider outage/stale data is clearly labeled.
- [ ] Location information is restricted, retained only as required and not published broadly.
- [ ] Offline event idempotency and driver-device access are tested.

### 15.9 Hostel/boarding

- [ ] Room/bed occupancy and allocation constraints prevent overbooking.
- [ ] Check-in/out and room transfer have history.
- [ ] Leave/outpass approval and guardian/warden access are scoped.
- [ ] Mess/hostel charges use the canonical finance ledger.
- [ ] Sensitive incident notes are protected.
- [ ] Availability and occupancy reports reconcile to allocations.

### 15.10 Inventory/assets

- [ ] Purchasing workflow has request, approval (if configured), order and receipt states.
- [ ] Partial delivery, returns, damaged goods and adjustments are represented.
- [ ] Every stock movement is traceable to source and actor.
- [ ] Concurrent issue/receipt cannot create invalid balances.
- [ ] Stock on hand reconciles to movements and inventory reports.
- [ ] Vendor/item import errors are reported row-by-row.

### 15.11 Visitors and gate passes

- [ ] Check-in/out, expiration, cancellation and host validation work.
- [ ] Pickup authorization is checked against current guardian permissions.
- [ ] Expired/revoked pass cannot be reused.
- [ ] Access logs are retrievable by authorized users without unnecessary PII exposure.
- [ ] Retention and deletion follow documented policy.

### 15.12 Certificates and IDs

- [ ] Template version and allowed field mappings are explicit.
- [ ] Only authorized, correct records populate output.
- [ ] Batch jobs show per-record success/failure and can be resumed safely.
- [ ] Reissue/revoke flows retain audit evidence.
- [ ] PDF/print output is readable, correctly sized and robust to Unicode/long text/missing image.
- [ ] Template injection and untrusted image risks are mitigated.

### 15.13 Notifications and messaging

- [ ] Enqueue, provider acceptance, delivery, failure and unknown status are not conflated.
- [ ] Channel preferences, guardian linkage and recipient eligibility are verified.
- [ ] Template variables are validated/escaped.
- [ ] Retry is bounded and idempotent; terminal failures are visible.
- [ ] Provider rate limits, outage and credentials expiration are handled.
- [ ] No message includes private data beyond approved purpose/recipient policy.
- [ ] Bulk sends support preview/recipient count and safe cancellation before dispatch.

### 15.14 Public CMS

- [ ] Public content is read-only to anonymous users; authoring requires role authorization.
- [ ] Draft/review/publish/unpublish/archive transitions are tested.
- [ ] Uploads, rendered content and slugs are secured.
- [ ] Private data cannot be reached through guessing media URLs or search APIs.
- [ ] Rate limit and spam control cover public forms.
- [ ] Accessible/responsive pages and safe preview/publish path exist.

### 15.15 Hardware/edge daemon

- [ ] Driver/process is separate from desktop event loop and AI inference runtime.
- [ ] Device pairing, authentication, revocation and least privilege are tested.
- [ ] Messages are validated, deduplicated and durably persisted before acknowledgement.
- [ ] Outage/restart/clock skew/duplicate punch behavior is tested.
- [ ] Device failure does not crash the rest of the application.
- [ ] Supported devices/protocols are stated explicitly; no generic compatibility claim without testing.

---

## 16. Release evidence and definition of done

A phase, ERP feature or release is done only when all applicable items below pass.

### Product behavior

- [ ] Scope and state machine agreed before implementation.
- [ ] Every accepted requirement maps to code and at least one appropriate test.
- [ ] Real end-to-end workflow works with persisted data.
- [ ] Empty/error/loading/offline/permission states are implemented.
- [ ] No dead-end buttons, abandoned states or silent fallback behavior remain in scope.
- [ ] Feature is truly available or clearly disabled; no UI advertises nonexistent capability.

### Engineering quality

- [ ] Code follows domain boundaries and existing conventions unless an approved migration says otherwise.
- [ ] Input validation, transactions and concurrency/idempotency are correctly implemented.
- [ ] Errors are meaningful, structured and observable.
- [ ] Logs redact secrets and unnecessary PII.
- [ ] Migration forward/upgrade behavior is tested; rollback/forward recovery documented.
- [ ] API/UI/data docs are updated.
- [ ] New dependencies are justified, pinned and checked.
- [ ] Changes are reviewed for unintended side effects and tests are not weakened.

### Verification

- [ ] Focused unit/service/repository/API tests pass.
- [ ] Relevant E2E workflow passes.
- [ ] Negative authorization/tenant tests pass.
- [ ] Duplicate/retry/concurrency/fault-injection tests pass where relevant.
- [ ] Full applicable regression suite passes.
- [ ] Test skips/blocks are documented; no unexecuted required tests counted as passing.
- [ ] Real integration evidence exists for each production-critical provider/model/DB claim.

### Operations

- [ ] Metrics, logs, alerts and support correlation are available.
- [ ] Backup and restore validated for target deployment.
- [ ] Startup/readiness correctly detects required dependencies.
- [ ] Deployment/update/rollback/runbooks exist.
- [ ] Feature flag/entitlement rollout and rollback are safe.
- [ ] Release version, commit SHA and artifact checksums are captured.

---

## 17. Release measurements and sign-off

Numeric product thresholds must be agreed from a measured baseline, target hardware, institution scale and test data. Do not invent “excellent” performance numbers without measuring the actual environment.

At minimum record:

- Critical workflow E2E pass rate and all unmet cases.
- P0/P1 open count: must be zero for GO.
- Tenant/authorization negative-test results.
- AI model identity, latency distribution, memory/CPU, error rate and evaluation quality.
- RAG retrieval/grounding metrics against approved golden set.
- API p50/p95/p99 latency and error rate under representative load.
- Queue/job oldest age, retry/dead-letter count and recovery results.
- Sync replay/dedup/conflict/loss test results.
- Payment reconciliation results and duplicate-event tests.
- Report card grading reconciliation results.
- Backup/restore verification and measured recovery times.
- Packaging/install/upgrade success on each supported target.
- Accessibility checks and pilot user acceptance.

### Release decision template

```markdown
# Gayatri Release Decision
- Release/version:
- Commit SHA:
- Artifact checksum:
- Target deployment mode(s):
- Supported OS/database/model/provider versions:
- Decision: GO / NO-GO / GO_WITH_APPROVED_P2_EXCEPTIONS
- P0 open:
- P1 open:
- P2 exceptions and approvers:
- Required test command/results:
- Real model evaluation evidence:
- Provider sandbox/integration evidence:
- Tenant/security evidence:
- Upgrade/backup/restore evidence:
- Known limitations:
- Rollback trigger and procedure:
- Operations owner:
- Product owner approval:
- Pilot institution acceptance:
- Date:
```

Only the explicitly authorized product/release owner can approve scope exceptions. The coding agent must not self-approve a P0/P1 waiver.

---

## 18. Mandatory coding-agent operating prompt

The following operating prompt can be used as the top-level instruction for the local AI agent. This file remains the detailed governing contract.

> You are the implementation engineer for Gayatri School OS. Read `DEVELOPMENT.md`, `GAYATRI_PRODUCT_UNIFICATION_ROADMAP.md` and the current repository before making edits. Follow the phase order. Start by writing the repository map and baseline evidence. For every phase, inspect the full relevant scope, write a plan and test matrix before code, then implement small vertical slices, debug immediately, run focused tests, run negative/fault tests, execute full applicable regression and record evidence. Move to the next phase only when the current phase gate is fully green. For every ERP feature, fully understand users, business process, states, authorization, tenant ownership, data constraints, exceptions, external dependencies, offline behavior, reporting, audit, support, recovery and acceptance before coding. Production paths must use real persistence and real configured provider behavior. Mocks and demo data may only be used in clearly labeled development/test configurations and must be unreachable in production. Never swallow critical exceptions, fabricate success, return static metrics, weaken tests or mark unrun work as passed. Maintain `MASTER_PROGRESS.md`, feature scope docs, defect ledger, decision log and evidence. If blocked by missing secret/hardware/provider approval, record the exact blocker and continue on independent work; do not fake the result. Treat new P0/P1 findings as stop-the-line defects. Be honest about what is runtime-verified, code-observed, documented, blocked or not run. Optimize for correctness, maintainability, recoverability, privacy, security and production operations—not code volume.

---

## 19. Immediate first actions (do these now, in order)

1. [ ] Confirm repository root and working-tree status; do not overwrite user edits.
2. [ ] Read this full `DEVELOPMENT.md` and the full product unification roadmap supplied with it.
3. [ ] Read the production fix plans and relevant architecture, data, security, privacy and deployment docs; treat claims as hypotheses.
4. [ ] Create `docs/development/MASTER_PROGRESS.md`, `REPOSITORY_MAP.md`, `BASELINE_REPORT.md`, `REQUIREMENTS_TRACEABILITY.md` and `DEFECT_LEDGER.md` from actual source observations.
5. [ ] Capture baseline SHA and run existing tests and validation commands without modifying tests.
6. [ ] Trace and verify the highest-risk paths: auth/tenant isolation, database lifecycle/migrations, real AI execution, RAG grounding, learning state commit, fee/payment provider behavior and sync idempotency.
7. [ ] Write `PHASE_00_PLAN.md`, implement baseline artifacts, validate them, and pass Phase 00 gate.
8. [ ] Write `PHASE_01_PLAN.md` before source edits. Fix shared foundations and prove Phase 01 green.
9. [ ] Only after Phase 01 is green, start Phase 02A and Phase 02B with a frozen shared data/API contract.
10. [ ] Continue phase by phase without skipping gates. Each phase ends with evidence, a clear status and regression report.

If an essential dependency is unavailable, mark the specific test or subtask `BLOCKED`/`NOT_RUN`, describe the external action required, and continue tasks that do not depend on it. Do not claim production readiness while a mandatory release gate remains blocked.

---

## 20. Final rule

**Do not build the appearance of an ERP. Build the complete business capability.** A feature is functional only when authorized users can finish the real workflow, state is stored in the authoritative database, reporting reconciles, failures are surfaced, recovery is possible, audit evidence exists, tenant/privacy boundaries hold, tests prove the behavior, and deployment/operations can support it. A phase is green only when these conditions are evidenced. A release is production-ready only after all required release gates have passed on the target deployment configuration.
