# GAYATRI-ERP — QA Remediation Goal for an Autonomous Coding Agent

**Repository:** https://github.com/Gayatri-Education/GAYATRI-ERP  
**Target branch:** `main` (work on a dedicated remediation branch)  
**Goal owner:** Gayatri-ERP maintainers  
**Document type:** Executable development objective and quality contract  
**Priority:** P0/P1 defects first; no release approval until mandatory gates pass  
**Source audit:** `GAYATRI_ERP_QA_AUDIT_REPORT.md` (independent source/CI audit, 15 October 2026)

---

## 1. Mission

Bring GAYATRI-ERP to a state where its **implemented behavior, data persistence, security boundaries, tests, documentation, release metadata, and product claims agree**. Fix the audit findings and systematically search for the same defect patterns elsewhere in the repository. Do not merely patch the listed examples if equivalent defects remain in other modules.

The final result must be a verifiable, maintainable, production-quality system—not a demonstration that passes because assertions were weakened, tests were skipped, mocks were accepted as real integrations, or reports were edited to say “passed.”

### Required outcome

1. The latest CI run is green on every supported CI platform.
2. Critical user journeys work from UI action through authorized API/service logic to durable database state and back to the UI.
3. Production workflows never report that an operation completed unless the required durable state change and integrity checks succeeded.
4. Demo/sample data is available only in an explicit, visibly identified demo/test mode and can never masquerade as live school data.
5. Tenant boundaries, role/permission checks, object ownership, payment provider trust, and edge-device identity are tested as negative as well as positive cases.
6. Database transactions, retries, duplicate events, app restarts, independent app instances, and failures do not cause data loss, duplication, cross-tenant access, or false success.
7. Release/version/migration/test evidence is generated from the code actually tested. Stale QA claims are corrected.
8. GitHub progress records, tests, plans, phase logs, and commits are maintained as the work proceeds.
9. Hardware or third-party integration behavior that cannot be physically exercised is labelled **BLOCKED / NOT VERIFIED / SIMULATED** with a documented evidence plan. Do not falsely claim it is fully fixed or production-certified.

---

## 2. Non-negotiable agent rules

### 2.1 The phase loop is mandatory

For **every phase**, follow this cycle in order:

1. **Inspect:** read the relevant source, configuration, migrations, existing tests, architecture decisions, and issue history. Confirm the finding still exists on the current commit.
2. **Plan:** create/update `docs/qa/plans/PHASE_NN_PLAN.md` (or the repository's verified canonical equivalent) before editing implementation code. State the hypothesis, files likely affected, risks, tests, rollback strategy, and exit criteria.
3. **Reproduce:** create or run a focused regression test demonstrating the defect. Record the actual failing assertion/output. If it is not reproducible, investigate whether the branch or behavior changed; do not invent a failure.
4. **Implement:** make the smallest coherent code change that fixes the root cause and any equivalent patterns found elsewhere.
5. **Test:** run the focused tests, the related module tests, architecture checks, static/compile checks, and any required integration/E2E test.
6. **Debug:** when any check fails, inspect the cause, fix code or test setup appropriately, then rerun. Do not suppress output, add broad `xfail`, skip tests, loosen assertions, or replace a failing assertion with a weaker one to obtain green results.
7. **Review:** inspect the full diff, security implications, logs, error paths, compatibility, migrations, and unintentional changes. Search for adjacent use cases and regressions.
8. **Record:** update the issue register, progress tracker, phase log, evidence links, commit SHA, and residual risks.
9. **Commit:** commit a logically complete phase or small reviewable unit on the remediation branch. Never make a “completed” tracker entry before evidence exists.
10. **Advance:** proceed only when all exit criteria pass. If blocked by credentials, real hardware, external provider access, or an unavailable environment, mark the exact work `BLOCKED` and proceed only with independent work that does not rely on pretending the blocked requirement passed.

### 2.2 Safety and integrity rules

- Start by checking `git status`, branch, HEAD SHA, latest CI, and uncommitted files. **Never overwrite, reset, clean, or discard user changes.** If the working tree is dirty, preserve the changes and coordinate around them.
- Do not work directly on `main`; create a descriptive branch such as `qa/production-readiness-remediation`.
- No secrets, access tokens, actual child/student PII, gateway credentials, or live database backups may be committed.
- Do not delete files simply because they are large, duplicated-looking, old, or inconvenient. Prove there are no static/dynamic imports, runtime path uses, packaging references, migration dependencies, or documentation links first.
- Do not call mock/simulated execution “real.” Mock adapters must be explicit, named, observable, and prohibited in production.
- Do not use fallback values that turn invalid input into a valid but different request (e.g. invalid device type → biometric terminal; unknown AI task → general task).
- Do not hide failures with empty `except` blocks or debug-only logs when the UI/user/operator needs to know the operation failed.
- A toast, HTTP 200, object returned in memory, passing unit test, folder, table, or endpoint does **not** prove a business workflow is complete.
- For every mutation, prove postconditions by reading persisted state from a fresh DB connection (and after reopen/restart where relevant).
- Preserve correct tests. If a test specification is wrong, document why and update it transparently; do not change it merely to match the implementation.
- Keep tests hermetic: unique temporary DBs, isolated environment variables, no reliance on a developer database, and deterministic provider fixtures.
- Use current test results only. Never carry a historical pass count forward as the status of a later commit.

---

## 3. Baseline and repository setup — Phase 00

### Actions

1. Inspect `README.md`, `DEVELOPMENT.md`, `ERP_TRANSFORMATION_DEVELOPMENT.md`, `GAYATRI_ERP_DEVELOPMENT_GUIDE.md`, `GAYATRI_ERP_ISSUE_REGISTER.md`, all candidate QA trackers, the release handover, CI workflow, and current release manifest.
2. Record `git rev-parse HEAD`, branch, dirty status, Python version, OS, lockfile verification result, migration status, test discovery count, CI run ID/URL, and the exact failing tests for the current HEAD.
3. Confirm current names/paths for the canonical progress tracker, issue register, phase log directory, and release documentation. Resolve conflicts between root-level and `docs/` copies deliberately; do not assume the audit's branch SHA is still HEAD.
4. Generate a repository map based on imports, registered routes, entry points, migrations, launch/setup scripts, package manifests, UI-to-bridge references, and dynamic runtime file paths.
5. Create a feature traceability matrix: `claim/feature → UI action → API/bridge → service → persistence → authorization → test → status`.
6. Capture the baseline without changing business logic.

### Exit criteria

- Baseline commit and environment captured.
- All CI failures and test commands listed exactly.
- Canonical tracking/documentation files identified.
- Feature traceability matrix distinguishes `IMPLEMENTED_VERIFIED`, `IMPLEMENTED_UNVERIFIED`, `PARTIAL`, `SIMULATED`, `BLOCKED`, `NOT_IMPLEMENTED`.
- No claim of production readiness is made just because a previous local report says tests passed.

---

## 4. Phase 01 — Restore trustworthy CI and production configuration tests (P0 / release blocker)

### Known defect to verify

The audit inspected a CI run where both Ubuntu and Windows failed these five tests, with 1,557 passes and 5 failures on each runner:

- `tests/test_phase01_production_config_hardening.py::test_production_debug_mode_rejected`
- `tests/test_phase01_production_config_hardening.py::test_production_reload_mode_rejected`
- `tests/test_phase01_production_config_hardening.py::test_production_model_checksum_verification`
- `tests/test_phase01_production_config_hardening.py::test_create_app_in_production_mode`
- `tests/test_phase12_final_forensic_certification.py::test_layer1_demo_tokens_disabled_in_production`

The observed error was: `Production startup aborted: Configured production database does not exist: gayatri_local.db`. This masks the assertion each test is meant to verify. Re-check the latest CI and current source before changing anything.

### Actions

1. Make production-configuration tests set their complete intended environment explicitly, including a unique temporary DB path where the tested path requires a valid DB.
2. Create/migrate a temporary database where needed. For tests specifically checking invalid/missing DB behavior, keep the DB missing intentionally and assert the relevant error.
3. Isolate environment variables (`GAYATRI_ENV`, `APP_ENV`, `GAYATRI_DB_PATH`, `DATABASE_URL`, secrets, encryption key, CORS origins, model path/checksum, `DEBUG`, `RELOAD`, `FASTAPI_DEBUG`). Restore them after every test.
4. Ensure assertion order tests the targeted invariant; the debug/reload tests must reach the debug/reload branch and checksum tests must reach checksum verification.
5. Fix any genuine application bug exposed after test isolation is repaired. Do not stop at test fixture changes if the production config is actually wrong.
6. Run each of the five tests individually, then the complete related test files, `pytest -v tests/architecture`, and the full headless suite.
7. Confirm Windows and Ubuntu runners both use the same intended test contract.

### Exit criteria

- All five tests pass for the intended reason.
- No test assertion was weakened and no tests were skipped or xfailed to mask the issue.
- Full headless regression succeeds locally and CI passes on all supported OS jobs.
- CI log URL, SHA, test counts, elapsed time, and commit are recorded in the phase log.

---

## 5. Phase 02 — Eliminate synthetic parent data and fake dashboard completeness (P1)

### Known location

`app/portals/parent/controller.py`, `ParentPortalController.get_dashboard_context()` returns hard-coded values such as mastery 84%, attendance 96.5%, and 2 pending assignments, with placeholder identities `parent_001` and `child_001`. It attempts only simple name lookups and catches exceptions at debug level. There is no visible guardian-child relationship check in that context builder.

### Required implementation

1. Trace the real authenticated parent identity and guardian-child relationship model in the backend.
2. Derive the parent from trusted auth/session state, not a caller-supplied identity or placeholder.
3. Authorize selected children through a persisted parent/guardian-to-student relationship and the active tenant/organization. Reject unrelated, disabled, or cross-tenant children.
4. Load mastery, attendance, pending work, assessments, teacher messages, fees, and notifications from authoritative domain services, each with correct tenant and child scope.
5. Remove fixed values from production code. If demo data remains, gate it behind an explicit demo mode, mark the UI visibly as DEMO, and forbid it in production configuration.
6. Implement honest empty, unavailable, and error states. A dependency exception must not silently fall back to plausible operational numbers; emit appropriate structured logs and a user-visible recoverable state.
7. Add tests for: real values; empty DB; missing student; unrelated parent/child; cross-tenant child; expired/revoked/disabled parent; DB/service exception; partially available domains; demo mode; production mode forbidding sample content.
8. Test parent UI rendering and ensure it cannot display stale previous-child data during a failed child switch.

### Exit criteria

- No synthetic operational parent metrics are present in production execution paths.
- No parent can obtain another family’s child data.
- The UI differentiates zero from missing data and actual errors.
- Data is verified from the database/service layer, including a restart/read-back test.

---

## 6. Phase 03 — Make fee administration and receipt handling financially trustworthy (P1)

### Known locations

- `central_platform/portals/fee_admin.py`
- `app/ui/design_system/fee_admin.js`
- `central_platform/fees/service.py`
- `central_platform/finance/service.py`
- `central_platform/api/routes/finance.py` and fee routes

The audit found fixed fee-admin summary numbers and sample outstanding-report rows. `generate_monthly_billing()` can report three invoices and INR 45,000 when the DB is unavailable or the returned student list is empty; with students, the visible path increments an in-memory count/amount without creating each invoice in the shown loop. The JavaScript trusts the counts and displays a completion toast. `printReceipt()` falls back to `window.print()` if the receipt fetch/JSON path throws.

### Required implementation

1. Route the summary and outstanding report through database-backed tenant-scoped queries. Remove sample names, fixed totals and fabricated counts from production mode.
2. Design monthly billing as an idempotent operation with a persisted batch/run record, exact billing period, eligible student set, invoice IDs, totals, status and actor/audit information.
3. Validate that the period is legal, student enrollment/account is active, the fee plan/structure is valid, discounts/waivers are applied by policy, and duplicate invoice generation is prevented by DB constraints/idempotency—not only process memory.
4. Generate invoice records and fee-account/ledger updates in an explicit atomic transaction. If any required row fails, roll back all related changes and return a failure response.
5. Empty eligible student set must result in zero created invoices and an honest `NO_ELIGIBLE_STUDENTS`/zero-result state, never a fabricated success.
6. Return `COMPLETED` only after durable rows exist and totals reconcile. The UI must display server-confirmed counts and make partial failures explicit.
7. Review money types and rounding, currency, overpayment, duplicate payment, discount exceeding balance, refund lifecycle, negative/zero inputs, invoice status transitions and ledger balance invariants. Prefer integer minor currency units or a defined decimal strategy over floating-point arithmetic for authoritative financial records.
8. Ensure audit trail captures actor, reason, timestamp, before/after state where policy requires it. Do not mutate posted ledger entries in place if the intended accounting model requires append-only correction entries.
9. For receipts, create a dedicated verified-print view/template populated only by the successful authorized API response. Printing by receipt ID must stop on network failure, malformed response, 401, 403, 404, cross-tenant mismatch or missing required receipt fields. Keep “print current page” as a separate, clearly named action if still needed.
10. Test billing retry/deduplication, two concurrent identical runs, injected failure half-way through a batch, process restart, exact counts, persisted invoice/receipt read-back and tenant scoping.

### Exit criteria

- No production fee summary or export contains seeded sample data.
- Monthly billing creates durable invoices or reports a clear zero/failure status; counts match read-back rows.
- Repeated requests do not create duplicates.
- Finance ledger/invoice/account values reconcile in all success and rollback tests.
- Receipt verification failure never triggers receipt printing.

---

## 7. Phase 04 — Payment webhook verification, tenant binding, and accounting invariants (P1)

### Known location

`central_platform/api/routes/finance.py`, `ingest_webhook()` accepts signed webhook payloads, but the visible route can infer organization from caller-controlled header/query/body fields and ultimately fall back to `org-default`. Signature verification exists; retain it and strengthen the mapping from event to the actual payment order.

### Required implementation

1. Model the trusted merchant/provider configuration per organization. Identify the provider account/merchant before using the webhook to mutate records.
2. Derive organization and expected payment data from a unique existing payment order and trusted gateway response fields. Do not treat `X-Organization-ID`, query params or payload `organization_id` as proof of a tenant.
3. Remove the `org-default` fallback. Unknown, ambiguous, unmatched or untrusted events must be rejected/quarantined without changing financial state.
4. Validate provider, merchant identity, provider order ID, persisted invoice/order, organization, amount, currency and valid state transition. For partial/captured/refunded/failed events, define explicit state transitions.
5. Verify signature over the exact raw bytes using constant-time comparison and the correct provider-specific canonicalization. Do not mark an event verified based on an untrusted caller boolean.
6. Persist provider event IDs/idempotency keys with database uniqueness constraints. Handle retries and concurrent duplicate webhooks safely.
7. Atomically persist webhook receipt, payment status, invoice/account changes, double-entry ledger records, and receipt creation. A partial transaction must not be visible.
8. Use stable error contracts; never return a successful response for an unmatched or rejected payment event.
9. Add tests for missing/invalid signature, altered body, wrong provider secret, wrong merchant, unknown order, duplicate event, replay, amount/currency mismatch, wrong tenant, ambiguous IDs, out-of-order events, DB failure and concurrent delivery.
10. Ensure logs never contain raw secrets, signature values or unnecessary student/bank/PII details.

### Exit criteria

- No caller-supplied tenant field can establish the tenant for a payment mutation.
- Unknown provider/order/tenant and amount/currency mismatch have no side effects.
- Duplicate and concurrent deliveries are idempotent.
- Invoice, payment, ledger, receipt and webhook event remain consistent after failures and restart.

---

## 8. Phase 05 — Edge devices, attendance punches, and invalid-enum behavior (P1)

### Known location

`central_platform/api/routes/edge_sync.py`:
- `register_device()` defaults invalid `device_type` values to `BIOMETRIC_TERMINAL`.
- `heartbeat()` accepts a device ID and metadata without a visible caller/device-authentication dependency and responds `ACK` after a service call.
- `ingest_punches()` accepts optional user auth and can use `X-Organization-ID` as organization identity if no user is authenticated.

The service may include further checks, so inspect it fully before classifying exploitability. The final route contract must still make the trust boundary explicit.

### Required implementation

1. Review `central_platform/sync/edge_service.py` and all device registration, revoke, heartbeat, punch, conflict and sync services.
2. Define explicit device authentication: registered device ID plus secret/token or HMAC signature over a canonical body, timestamp and nonce/idempotency key. Store secrets hashed/encrypted as appropriate and support revocation/rotation.
3. Verify the device is registered, active, not revoked, and bound to the organization that owns the target users before accepting heartbeat/punches.
4. Treat headers as scope hints only, not authorization. Reject tenant mismatch, device/organization mismatch, unknown device, invalid student/user, replay, stale timestamp and invalid punch state.
5. Do not return `ACK` until the authenticated update is durably persisted. Failures must be explicit and auditable.
6. Reject unrecognized `device_type`, `punch_type`, `verification_type`, and sync resolution strategies with 422/400. A legitimate omitted field may receive a documented default, but a supplied invalid value must never be silently changed into a different valid one.
7. Make batch ingestion atomic or document precise per-item partial-success semantics; return accepted/rejected IDs and reasons, with idempotency guarantees.
8. Rate-limit device endpoints and record security events without logging raw device credentials.
9. Test valid credential, no credential, bad signature, expired timestamp, replay/duplicate, revoked/unknown device, wrong tenant, wrong student, malformed enum, partially invalid batch, crash mid-batch, retry after timeout, and read-back after restart.
10. Real terminal/GPS testing must be marked `BLOCKED` until actual devices are available; contract tests and simulation are not equivalent to hardware acceptance.

### Exit criteria

- Every edge mutation is authorized using a registered identity/device credential and server-side tenant mapping.
- No invalid enum silently changes the device type or operation.
- Health, ACK and acceptance counts reflect actual persisted facts.

---

## 9. Phase 06 — Central authorization and tenant-isolation audit across every route (P1)

### Known areas

- `central_platform/api/routes/ops_gate.py` directly compares `current_user.role` to string values instead of consistently using centralized role normalization.
- Similar logic may exist across legacy and versioned endpoints; the agent must inventory the full route set rather than fix one file only.

### Required implementation

1. Build an automated route inventory, including modern API routers, legacy routes, server-mounted static/UI paths and mutating endpoints.
2. For each endpoint, record: anonymous allowed? accepted roles/permissions? tenant derivation? object ownership rule? CSRF/browser concerns where applicable? audit event? rate limit? failure status? required tests?
3. Use central role normalization and a shared permission policy for all routes. Do not mix ad-hoc string comparisons, enum comparison, role names or route-specific assumptions.
4. Check authorization at the service/data boundary for sensitive operations as defense in depth; route authentication alone is not enough if object tenant/ownership is not checked.
5. Validate student and guardian relationships, teacher assignments/course scope, fee account/receipt ownership, branch grants, organization admins and super-admin exceptions.
6. Verify legacy endpoints do not bypass the canonical identity, authorization, persistence or failure contract. Remove or safely deprecate duplicate routes only after compatibility review.
7. Test anonymous, malformed token, expired/revoked token, inactive user, every allowed/denied role, cross-tenant IDs, spoofed org/branch header, guessed object ID, unlinked parent-child, and authorized success.
8. Review CORS, CSRF, content security policy, security headers, rate limits, open redirects, upload size/type/path checks, error detail leakage, debug/docs exposure and PII logging.
9. Enforce production startup rejection of weak/default secrets and unintended wildcard CORS; confirm docs disabled by default if that remains the policy.
10. Create a security regression test per discovered route-level gap.

### Exit criteria

- Complete route authorization matrix checked into `docs/qa/`.
- Each sensitive endpoint is covered by positive and negative automated tests.
- Central role policy is consistently used and cross-tenant access fails closed.
- Any unresolved route is recorded with severity and release-blocking status; no silent closure.

---

## 10. Phase 07 — AI task validation, tutor context, RAG trust, and honest degraded states (P1/P2)

### Known location

`central_platform/api/routes/ai.py` maps unrecognized `task_type` to `TaskType.GENERAL`. `app/ui/design_system/student.js` uses placeholder values such as `'current'` and `'crs-chem-101'` when student/course arguments are missing. These patterns can route an invalid request to a different task/course and can break real-user learning workflows.

### Required implementation

1. Reject supplied but invalid task types via schema validation (422) instead of silently converting them to general work. Omitted and invalid values must have distinct semantics.
2. Remove magic user/course IDs from production flows. Obtain authenticated student, enrollment, active course/version and session context from trusted app/API state.
3. Verify RAG upload, chunking, source lifecycle, indexing, retrieval filters and citations end to end. Confirm that empty indexes, all-filtered documents, corrupt documents and failed embeddings are reported as degraded/unavailable, not fabricated as grounded success.
4. Verify every retrieved source is scoped to authorized organization/course/class/student, including cache keys and vector/BM25 hybrid paths. Test cross-tenant retrieval, deleted/unpublished/expired sources, retrieval failure and prompt injection.
5. Ensure tutor turn status differentiates successful completion, blocked turn, validation failure, provider unavailable, timeout and offline fallback. Failed/blocked turns must not award mastery/assessment credit or claim that learning state was committed.
6. Test provider error contracts (HTTP status and stable response shape), kill switch, budget/rate limits, timeout, malformed model output, missing local model, low-memory/load failure and recovery.
7. Do not use a mock provider in production or silently fall back to a cloud service if privacy claims say all student data stays on campus. Require an explicit approved policy for any external provider.
8. Validate tool execution boundaries (math/chemistry/code tools), input bounds, timeout/resource limits, prompt-defense, output sanitization and any subprocess/network isolation.
9. Ensure session/review queue writes are durable, idempotent where relevant, and loaded again from the API after a successful action.
10. Add tests proving no model/provider execution, budget change, or student progress update occurs on invalid task type or unauthorized course context.

### Exit criteria

- Invalid task/course context is rejected with an actionable error.
- RAG grounding and tenant scoping are verified through source-level citations and negative tests.
- Degraded/blocked results never appear as completed successful turns or inflate mastery.

---

## 11. Phase 08 — Database/app lifecycle, transactions, migration safety, and service isolation (P1)

### Required implementation

1. Review `central_platform/db.py`, all domain services, migration runner, all constructors/default DB behavior and module-level singleton services.
2. Establish one explicit database/service container per application instance. Make dependency injection consistent between FastAPI, desktop portals, UI bridge and tests. Remove/rework global service caches where they capture stale DB path/config or leak across tests/app instances.
3. Prove two app instances using separate temporary DB paths never share records, user identity, provider config, current tenant, singleton service, or cached state.
4. Review every critical multi-table business mutation for an explicit transaction and rollback semantics. Pay particular attention to admissions conversion, fee invoice/billing, payment/webhook/ledger/receipt, assessment completion/mastery, sync batches and device punches.
5. Verify SQLite connection lifecycle, WAL configuration, foreign keys, busy timeout, nested transaction/savepoint behavior, lock errors, closed-connection behavior and concurrent access. If PostgreSQL is claimed as supported, test actual PostgreSQL behavior or mark support as unverified rather than describing the SQLite implementation as dual-engine production-ready.
6. Test migration from an empty DB to latest schema, each supported prior version, checksum mismatch, interruption, rollback, repeated `up`, backup and restore, foreign-key checks and fresh-connection read-back.
7. Do not mutate a developer/shared DB in tests. All automated tests must use tmp paths or an explicitly isolated disposable service.
8. Audit schema/table counts and manifest metadata against the actual migration registry, not hand-maintained numbers.
9. Ensure migration down scripts are reversible where claimed; document non-reversible data changes explicitly and require backup/approval if rollback could destroy data.
10. Add database integrity and recovery tests with injected exceptions and concurrent requests.

### Exit criteria

- Independent DB isolation test passes.
- Transaction and restart tests cover all critical mutations.
- Migrations are repeatable, checksummed and verified from clean and supported-upgrade states.
- No unexplained auto-created default DB/service causes production data to land in the wrong path.

---

## 12. Phase 09 — Complete genuine UI-to-API-to-database E2E workflows (P1/P2)

### Required implementation

Build and maintain a feature matrix covering all advertised modules. For each important workflow, start from the actual user-facing control and prove every layer is connected.

Minimum workflows:

1. **Identity:** create/provision organization → create user → login → role-based access → logout/revocation.
2. **Admissions/SIS:** inquiry → duplicate detection → application/documents → admission decision → student profile → enrollment/class/fee account.
3. **Attendance:** create session → mark roll call or signed edge punch → retrieve list → correction with reason/audit → parent reads only linked child data.
4. **Fees/payments:** fee plan/structure → billing batch → persisted invoice → payment order → valid webhook → receipt → ledger and balance → outstanding export/reconciliation.
5. **Academics/exams:** academic year/class/subject → timetable with collision prevention → exam schedule → marks validation/moderation → grading → persisted report card → correct parent/student view.
6. **Teacher:** course/assignment/instruction → teacher copilot request → authorized response → student-facing result and audit history.
7. **Student learning:** enroll/course version → tutor/RAG session → assessment → grading → mastery/review queue → close/reopen application → same durable state.
8. **Parent:** parent login → switch among only linked children → attendance/progress/fees/notifications → verify no stale or fabricated data.
9. **HR/payroll:** staff record → leave/attendance → payroll calculation → approval/locked pay run → payslip. Check legal/tax figures with domain owner before claiming statutory correctness.
10. **Campus facilities:** visitor registration → gate pass → checkout; transport/hostel/library/inventory critical create-update-report lifecycle.
11. **Notifications/CMS/certificates:** draft → approval/publish/delivery → status and failure/retry; generated document and QR verification must resolve to the persisted certificate.
12. **Offline sync:** locally queued change → disconnect → conflicting update from another client → reconnect/retry → resolution, audit and durable final state.

### UI contract requirements

- Every button/tab/menu that represents a business action must do one of: a real supported action, a clearly disabled/not-yet-available state, or a named demo-only action with visible labels. No cosmetic success toast as a substitute for backend work.
- Show loading state, success state only after server confirmation, clear empty state, validation errors and recoverable server/network failures.
- On a mutation timeout, query operation status/idempotency result before offering a blind retry that could duplicate the action.
- Refresh or re-fetch authoritative UI state after the mutation. Do not rely only on client-side incrementing or stale cached numbers.
- Sanitize dynamic HTML, avoid inline handler interpolation, and test XSS payloads in every relevant render function.
- Test screen sizes, keyboard navigation, focus management, accessible error messages, contrast and receipt/report print layouts.

### Exit criteria

- Every advertised “implemented” core workflow has an E2E evidence link and persisted postcondition.
- Unimplemented or simulated features are visible and accurately labelled in UI/docs.
- No critical action remains a dead end, cosmetic tab, placeholder-ID request or success toast without backend confirmation.

---

## 13. Phase 10 — Install, dependency lock, packaging and model-readiness correctness (P2)

### Known locations

- `setup.bat` installs from `requirements.txt` while CI uses `requirements.lock`.
- `launch.bat`, `launch.sh`, `run.bat`, setup instructions and repository docs may have different assumptions about Python, the database, the server and local model path.
- The audit observed inconsistent version declarations in README, `pyproject.toml`, controller responses and release manifest; current values must be rechecked before editing.

### Required implementation

1. Pick an authoritative dependency workflow. Ensure local setup, CI, smoke tests and release package use the same validated lock when deterministic install is the goal. Keep the lock verifier meaningful and test it.
2. Verify lock generation is reproducible, platform-aware where needed, and installs successfully on documented Windows/Linux versions. Address heavy native dependencies (Qt/WebEngine, `llama-cpp-python`, PyTorch/transformers, PostgreSQL driver) explicitly rather than relying on accidental host setup.
3. Make setup/launch scripts fail clearly on Python incompatibility, dependency failure, migration failure, bad permissions, missing model and API startup errors. Do not swallow the error or report setup success if a critical stage failed.
4. Provide a supported model download/installation path or an honest “model not installed” mode. Verify download checksum, storage location, disk space, cancellation/resume, missing/corrupt weights and a real inference smoke test. No fake model response is permitted as successful inference.
5. Test packaged desktop launch from a clean machine/user profile, with no dev-only paths and no pre-existing local database. Verify `--help`, `--version`, `--check-startup`, `smoke` and server mode commands.
6. Align product version across `VERSION`, `pyproject.toml`, README badges, UI about/version, changelog, release manifest and release handover. Decide the real intended version from repository/release history; don't guess a new version to make files agree.
7. Generate `RELEASE_MANIFEST.json` during the release/CI process from the exact checked-out commit and actual migrations/artifacts. Validate hash, SHA, branch/tag, schema version, build timestamp and dirty-tree semantics. CI should fail if the committed manifest claims a different source SHA or stale migration inventory when that is prohibited by policy.
8. Keep reproducible install, smoke test, packaging test and migration test as CI gates.

### Exit criteria

- Fresh Windows and Linux setup/launch succeeds on documented supported environments, or the support claim is narrowed honestly.
- Missing model and missing provider show explicit states, not fake AI success.
- Dependency, version and release-manifest evidence is consistent with the tested artifact.

---

## 14. Phase 11 — Offline mode, sync recovery, hardware and third-party integrations (P2; explicit blocked-state rules)

### Required implementation

1. Trace the entire outbox/inbox sync lifecycle: create operation → durable queue → send → server acknowledgment → dedupe → conflict selection → client acknowledgment → retry/recovery after crash.
2. Run two independent clients and a server against representative concurrent edits; test duplicate deliveries, reordered operations, partial response, connectivity interruption, process kill/restart, clock skew, revoked credentials, unsupported schema version and retry storms.
3. Verify sync conflict resolution is deterministic and audited; no default strategy may unexpectedly overwrite student/finance/attendance records without a documented policy.
4. Test backup/restore while SQLite WAL is active using the supported backup mechanism, verify integrity and application-level record counts after restore, and run a restore drill in a clean environment.
5. Verify local AI can be used without internet if that is a product promise. Test DNS/network removed, model available, empty/corrupt RAG index, queue recovery and absence of unwanted remote calls.
6. Exercise actual RFID/biometric and GPS hardware if available. If not available, provide device contract tests/simulators but mark hardware acceptance `BLOCKED` with needed model, protocol, firmware, credentials and test procedure. Never re-label simulated tests as physical-device acceptance.
7. Exercise real payment provider sandbox, actual notification providers and email/SMS/WhatsApp delivery only with authorized credentials. Validate retry, delivery receipts, provider outage, rate limit and dead-letter paths. Keep provider access blocked when credentials are not supplied and never add secrets to GitHub.
8. Ensure privacy claims match behavior: identify every outbound request and external provider. Document where data is stored, transmitted, retained and deleted. No external AI fallback for student information unless explicitly configured and approved by policy.

### Exit criteria

- Sync/outbox behavior is proven under retry, concurrency and restart with no duplicate or lost critical mutations.
- Backup restore is verified.
- External hardware/providers are `VERIFIED` only if exercised in a suitable environment; otherwise their exact release impact is recorded as `BLOCKED` or `SIMULATED`.

---

## 15. Phase 12 — Consolidate documentation, tracker, issue status and release claims (P1)

### Required implementation

1. Search the whole repository for the competing development guides, issue registers, progress trackers, duplicate cleanup reports, release handovers and outdated feature claims.
2. Select one canonical development goal, one canonical issue register, one canonical progress tracker and one canonical release handover after checking all cross-links. Keep older QA evidence as dated history; do not delete it blindly.
3. Make other root-level copies short pointers to canonical docs, or archive them in a clearly marked historical directory after references are migrated and link validation passes.
4. Correct claims such as “all 1,775 tests pass,” “production-ready,” “100% offline,” “unbreakable,” or “all features complete” unless the current evidence supports the exact statement. Document release limitations clearly.
5. Maintain a status per issue: `CONFIRMED`, `IN_PROGRESS`, `FIXED_PENDING_VERIFICATION`, `FIXED_VERIFIED`, `BLOCKED`, `NOT_REPRODUCED`, or `REOPENED`.
6. A finding becomes `FIXED_VERIFIED` only after: root-cause fix, regression test reproducing old behavior/failing and new behavior/passing, related suite pass, persistence/security/E2E evidence when relevant, commit SHA and verification run URL.
7. Validate links, YAML, JSON, migrations manifest, command examples and version references in CI.
8. Keep a “claims vs evidence” table with `CLAIM`, `EVIDENCE`, `STATUS`, `LIMITATION`. The product README must not overstate hardware, provider, offline or statutory compliance support.
9. Any feature needing credentials or physical devices gets an owner/action to unblock and must remain blocked until verified.

### Exit criteria

- One canonical live tracker and issue register are named in all active docs.
- No stale green-test or production-ready claim contradicts current CI/evidence.
- Release manifest matches the tested commit and current schema metadata.
- Link checks and documentation consistency checks pass.

---

## 16. Phase 13 — Final forensic review, regression and release decision (P0/P1 gate)

Do not start this phase until all prior code phases are complete or every blocked requirement is explicitly documented with release impact.

### Final checks

1. Rebase/merge the remediation branch as allowed by the repository workflow and record the exact candidate SHA. Do not force-push or rewrite shared history without explicit owner approval.
2. Run the complete CI pipeline on all supported platforms from the candidate SHA.
3. Run:
   - `python -m compileall app core central_platform tests scripts`
   - `python scripts/verify_dependency_lock.py`
   - `python scripts/migrate_db.py up --db-path <fresh-temporary-db>`
   - `python scripts/migrate_db.py status --db-path <fresh-temporary-db>` (or verified equivalent)
   - `pytest -v tests/architecture`
   - `pytest -v -m "not gui"`
   - GUI/desktop tests in an environment where Qt/WebEngine is supported
   - all new focused tests and E2E journeys
   - packaging/install/smoke and release-manifest validation
4. Check that no tests are skipped unexpectedly, weakened, xfailed to hide defects, order-dependent, using shared database files, or dependent on live internet/gateway without declared integration markers.
5. Review `git diff --check`, the complete change set, secret/PII scanning, TODO/mock/demo search, suspicious broad exception handling, placeholder IDs, hard-coded operational figures and success toasts.
6. Search for analogous bug patterns in all modules, not only listed files:
   - hard-coded counts, default student names, fallback amounts, `org-default`, placeholder IDs
   - `except Exception` followed by success/default value/empty list/printing
   - invalid enum converted to another enum
   - HTTP 200 on a failure result
   - “success” toast before persistence confirmation
   - unscoped DB queries or caller-controlled tenant IDs
   - optional auth for sensitive mutations
   - missing idempotency/transaction around multi-table writes
   - test assertions that only inspect response shape rather than durable state
7. Generate a final report including what passed, what failed, blocked external prerequisites, remaining defects, current SHA, CI URLs and a GO/NO-GO decision.

### GO criteria

**GO** only when:

- All P0/P1 issues are resolved and `FIXED_VERIFIED` with evidence.
- All CI jobs for the candidate SHA are green.
- Core identity, parent-child isolation, admissions/student lifecycle, attendance, fee/payments, tutor/assessment, report and sync workflows pass required persistence + negative-path/E2E tests.
- No known production success response is generated by fake operational data or a placeholder mutation.
- Production config and route security tests reach their intended assertions and fail closed.
- Release/version/schema evidence matches the exact candidate.
- All unverified hardware/external integrations are truthfully declared, and the owner has accepted whether the release scope can ship without them.

If a core advertised claim is unavailable or unverified, do not declare full-product production readiness. Narrow the release scope and documentation or keep the release **NO-GO**.

---

## 17. Mandatory test strategy and evidence format

For every finding/phase, add tests as appropriate from the following list:

- **Happy path:** valid authorized operation succeeds.
- **Validation:** missing/malformed/invalid enum/bounds rejected with stable status and message.
- **Authorization:** anonymous, wrong role, inactive/revoked identity, cross-tenant, wrong owner and spoofed headers rejected.
- **Persistence:** read back from a fresh DB connection; re-open DB/process and verify again.
- **Failure injection:** DB write failure, provider timeout, malformed response, service exception, file/model missing.
- **Atomicity:** no partial writes when one step fails.
- **Idempotency/replay:** repeated request/event has no duplicate financial/attendance/learning effect.
- **Concurrency:** concurrent identical requests and competing writes preserve invariants.
- **UI contract:** success toast only after success; explicit error/empty/degraded state; refresh reflects server state.
- **Security:** XSS, path traversal, upload limits, secret redaction, prompt injection, CORS/auth boundary as relevant.
- **Install/operations:** clean setup, migration, backup/restore, missing model, offline condition and startup failure.

Record each verification with this template in a phase log:

```text
Phase / issue ID:
Finding and root cause:
Current source SHA:
Plan link:
Files changed:
Before-fix reproduction (command + result):
Fix summary:
Focused tests (command + pass/fail count):
Related regression tests:
Full CI run URL / OS / Python / SHA:
E2E persisted-state evidence:
Security/negative-path evidence:
Migration/restore evidence (if applicable):
Remaining risk or blocker:
Status: IN_PROGRESS | FIXED_PENDING_VERIFICATION | FIXED_VERIFIED | BLOCKED
Commit SHA:
Reviewer notes:
```

**Evidence must be real output from the current commit.** Summarized numbers without a command/run/commit reference do not qualify.

---

## 18. GitHub progress and commit policy

1. Before implementation, create a plan document for the phase and assign issue IDs (retain `QA-001` through `QA-015` for the broad audit actions or map them into the canonical register). Add sub-IDs for newly found defects.
2. Update the canonical progress tracker at the start and end of every phase. It must identify status, owner/agent, source files, tests, evidence links, commit SHA, blockers and next action.
3. Commit the phase plan before code changes when practical; then commit tests and fixes in small understandable batches.
4. Keep new tests with the code fix. Do not submit a phase with source changes but no regression tests for a confirmed bug, except where explicitly blocked and approved.
5. Push the branch and open/update a GitHub PR if repository authentication/workflow permits. The PR must include issue IDs, problem, root cause, test evidence, migration impact and residual risks. If push/PR cannot be performed, provide the exact local commit SHA and state what remains to publish—do not claim it was pushed.
6. Keep one current summary of phase completion, but preserve dated evidence history. Never overwrite prior logs; add a new run log when results change.
7. Add a GitHub CI check that rejects a stale release manifest or a tracker claiming current green CI when the actual required workflow has failed, if technically feasible within the repo’s workflow.
8. The issue register and tracker must be updated in the same PR as the fix or in the immediately linked documentation commit.

---

## 19. Required completion summary to the maintainer

When done (or blocked), provide a summary with:

1. Candidate branch and HEAD SHA.
2. GitHub PR URL (if created) and latest CI run URLs by platform.
3. Findings fixed, each mapped to issue ID, commit and regression test.
4. Full test results with exact totals and skipped count.
5. Fresh database/migration/install/restore results.
6. Confirmed E2E journeys and which state was read back from persistence.
7. Any remaining `BLOCKED`, `SIMULATED`, `NOT_VERIFIED` or `NOT_IMPLEMENTED` feature, why it is blocked, and what would unblock it.
8. Release decision: `GO`, `NO-GO`, or `GO WITH EXPLICITLY LIMITED SCOPE`.

Do not finish with “all fixed” unless every GO criterion is proven. Where an environment prevents confirmation, state that limitation plainly and leave the item open.

---

## 20. Source areas to begin with

Use the findings as entry points, then expand the search across the codebase:

- CI: `.github/workflows/ci.yml`
- Production configuration: `central_platform/config.py`, `tests/test_phase01_production_config_hardening.py`, `tests/test_phase12_final_forensic_certification.py`
- Parent portal: `app/portals/parent/controller.py`, `app/ui/design_system/parent.js`
- Fee UI/service: `central_platform/portals/fee_admin.py`, `central_platform/fees/service.py`, `central_platform/finance/service.py`, `app/ui/design_system/fee_admin.js`
- Finance webhook/receipts: `central_platform/api/routes/finance.py`
- Edge devices: `central_platform/api/routes/edge_sync.py`, `central_platform/sync/edge_service.py`
- AI: `central_platform/api/routes/ai.py`, `central_platform/tutor/`, `central_platform/rag/`, `app/ui/design_system/student.js`
- Authorization/release gate: `central_platform/api/routes/ops_gate.py`, `central_platform/auth/`, `central_platform/rbac/`, all `central_platform/api/routes/`
- DB/migrations: `central_platform/db.py`, `scripts/migrate_db.py`, `migrations/`
- Desktop/lifecycle: `app/main.py`, `app/windows/main_window.py`, `app/bridge/facade.py`, `app/portals/`
- Setup/package: `setup.bat`, `launch.bat`, `launch.sh`, `run.bat`, `requirements.txt`, `requirements.lock`, `pyproject.toml`, `VERSION`, `RELEASE_MANIFEST.json`
- QA/docs: `README.md`, `DEVELOPMENT.md`, `ERP_TRANSFORMATION_DEVELOPMENT.md`, `docs/qa/`, `docs/erp_agent/`, root-level QA/development files.

---

## Final instruction to the AI agent

**Start with Phase 00 and proceed strictly phase by phase.** For each phase, inspect the current repository, write the plan, reproduce the defect, fix the root cause, test, debug, rerun regressions, review the diff, and update GitHub progress. Stop advancement on a failed gate. Search for sibling defects instead of fixing only visible examples. Do not fabricate test results, use hard-coded demo outputs in production, weaken assertions, silently convert errors to success, or state that production readiness has been achieved without the required evidence. The deliverable is a reliable product and an auditable proof trail—not merely changed code.
