# Gayatri AI — Phase-by-Phase Production Fix & Verification Plan

**Repository:** https://github.com/Gayatri-Education/Gayatri  
**Purpose:** Execution specification for a local AI coding agent to remediate defects and validation gaps, then prove production readiness with reproducible evidence.  
**Audit input:** `INDEPENDENT_QA_PRODUCTION_READINESS_AUDIT_2026-10-14.md`  
**Reviewed baseline SHA:** `ea85f29e6f2d9637909bcf2f819853883da29481`  
**Plan created:** 14 October 2026  
**Target outcome:** A release candidate whose core features work under the actual intended deployment configuration, not merely a repository with a large passing unit-test count.

---

## 0. Mission and non-negotiable rules

The agent's mission is to audit the actual code, reproduce defects, implement minimal safe fixes, debug regressions, and create a release evidence pack. **Do not treat the existing QA report, commit messages, README badges, release labels, or test counts as proof.** Re-test all material claims against the checked-out source.

### 0.1 Mandatory workflow for every phase

The agent MUST follow this loop before moving to the next phase:

1. **Inspect.** Read this plan, the independent audit, the current code, callers/dependencies, existing tests, and relevant docs.
2. **Plan before editing.** Create `docs/qa_agent/plans/PHASE_<NN>_PLAN.md` before changing source. Identify files, expected behavior, defect hypothesis, test additions, data/security risks, rollout concerns, and regression risks.
3. **Capture baseline.** Run the focused existing tests and record command, environment, commit SHA, pass/fail/skip count, failures, and logs under `docs/qa_agent/evidence/`.
4. **Implement narrowly.** Fix one logical problem at a time. Do not rewrite unrelated code or refactor without a defect-driven reason.
5. **Test the change.** Add a regression test that fails before the fix; run relevant focused tests. If it fails, debug it before doing the next logical change.
6. **Inspect the diff.** Verify that tests have not been weakened, removed, skipped, converted to mocks, or made less strict to obtain a green run. Review public API/data migrations and unintended behavior changes.
7. **Run repository-wide regression.** At phase end, run compile checks, architecture tests, the complete applicable test suite, and phase-specific integration tests. If a platform-dependent test cannot run, record it as BLOCKED—not PASSED.
8. **Record evidence.** Update `docs/qa_agent/MASTER_PROGRESS.md`, the phase report, regression record, and decision log. Record exact commands and outputs.
9. **Enforce exit gate.** Do not start the next phase until the phase's exit criteria pass or the phase is explicitly marked BLOCKED with a concrete reason and an identified dependency. Never silently waive a P0/P1.

The agent should continue autonomously after writing the required plan unless the environment requires human approval. A plan is an execution artifact, not a reason to stop and ask the user what to do next.

### 0.2 Prohibited shortcuts

The agent MUST NOT:

- Declare readiness because “1,409 tests pass” or because a prior report says an item was fixed.
- Make tests pass by weakening assertions, deleting failing tests, broadly adding `skip`/`xfail`, replacing real execution with mocks, or changing expected results to fit broken behavior.
- Count mock, placeholder, deterministic canned output, stale artifacts, or non-empty strings as evidence of real model execution.
- Use fallback content to award marks, update mastery, diagnose misconceptions, or persist authoritative learning outcomes.
- Make a health endpoint green just because a file, manifest, provider, database connection, or service class exists.
- Swallow exceptions that matter to correctness, security, persistence, payments, or model build/release status.
- Print credentials, JWTs, student messages, private uploaded content, encryption keys, or production database contents into logs or evidence.
- Run destructive migrations, delete model/data files, deploy to production, rotate real credentials, or call paid third-party APIs unless the environment and instructions explicitly authorize it. Use isolated fixtures and provider mocks for ordinary CI; use a controlled test environment for real integration checks.
- Mark a task `PASSED` when it was not executed. Use `BLOCKED` or `NOT_RUN` with a reason.

### 0.3 Severity and status definitions

**P0 / Release blocker:** Can cause incorrect grading/education, fake AI success, data exposure, privilege escalation, core startup/inference failure, learner-state corruption, or false production certification. Must be fixed before production.

**P1 / High:** Can break major workflows, weaken security or durability, make operation/release non-reproducible, cause scale failures, or materially reduce correctness. Must normally be fixed before production.

**P2 / Medium:** Important observability, maintainability, or edge-case issue that does not independently block the release.

**P3 / Low:** Cosmetic or non-critical improvement.

Allowed task statuses: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `FAILED`, `PASSED`, `REOPENED`, `NOT_APPLICABLE`. A phase may be `PASSED` only after its exit gate has evidence.

---

## 1. Required agent artifacts and progress tracking

Create or maintain this structure. If some files already exist, inspect and update them rather than overwriting useful historical evidence.

```text
docs/qa_agent/
├── MASTER_PROGRESS.md
├── BASELINE_REPORT.md
├── plans/
│   ├── PHASE_00_PLAN.md
│   ├── PHASE_01_PLAN.md
│   └── ...
├── reports/
│   ├── PHASE_00_REPORT.md
│   └── ...
├── regressions/
│   ├── PHASE_00_REGRESSION.md
│   └── ...
├── evidence/
│   ├── commands/
│   ├── logs/
│   ├── test-results/
│   ├── model-evaluations/
│   ├── security/
│   └── packaging/
└── decisions/
    └── DECISION_LOG.md
```

`MASTER_PROGRESS.md` must contain, at minimum:

| Phase | Status | Plan written | Baseline captured | Fixes complete | Focused tests | Full regression | Exit gate | Evidence link |
|---|---|---|---|---|---|---|---|---|
| 00 Baseline and project map | NOT_STARTED | No | No | No | No | No | PENDING | |
| 01 Configuration and test isolation | NOT_STARTED | No | No | No | No | No | PENDING | |
| 02 Real AI readiness and provenance | NOT_STARTED | No | No | No | No | No | PENDING | |
| 03 Educational correctness and fallback policy | NOT_STARTED | No | No | No | No | No | PENDING | |
| 04 Gateway observability and metrics | NOT_STARTED | No | No | No | No | No | PENDING | |
| 05 Authentication, revocation and rate limiting | NOT_STARTED | No | No | No | No | No | PENDING | |
| 06 Session persistence and migrations | NOT_STARTED | No | No | No | No | No | PENDING | |
| 07 RAG integrity and grounding | NOT_STARTED | No | No | No | No | No | PENDING | |
| 08 Security and tenant-boundary verification | NOT_STARTED | No | No | No | No | No | PENDING | |
| 09 Training and model-evaluation pipeline | NOT_STARTED | No | No | No | No | No | PENDING | |
| 10 Dependency and CI reproducibility | NOT_STARTED | No | No | No | No | No | PENDING | |
| 11 Cross-platform packaging and operations | NOT_STARTED | No | No | No | No | No | PENDING | |
| 12 Integrated adversarial and load validation | NOT_STARTED | No | No | No | No | No | PENDING | |
| 13 Final evidence pack and release decision | NOT_STARTED | No | No | No | No | No | PENDING | |

For each finding, track: ID, severity, source file/line, reproduction command, expected result, observed result, root cause, code fix, regression test, evidence path, residual risk, and disposition. A finding must not be marked closed without a test demonstrating the corrected invariant.

---

# Phase 00 — Baseline, source map and independent reproduction

**Goal:** Establish exactly what is present on disk and which checks actually pass before modifying code. Do not accept previous claims as baseline evidence.

### Tasks

1. Record branch, commit SHA, uncommitted changes, Python version, OS, installed package versions, active configuration source, and available model/provider environment. Redact secrets.
2. Read the existing `Gayatri_QA_Production_Fix_Plan.md`, independent audit, README, `requirements.txt`, `requirements.lock`, `.github/workflows/ci.yml`, migration scripts, model manifest, and release/packaging docs.
3. Map application entry points and major boundaries: desktop UI, API app, core tutor/session, central platform, AI gateway/adapters, RAG ingest/query, auth/RBAC, sync, fees/payments, training and release artifacts.
4. Determine which paths are intended for desktop/offline, local server, and multi-tenant hosted deployment. Record whether each mode is supported and how it is selected.
5. Inspect test configuration, fixtures, marks, skips, xfails, test selection, and CI commands. Calculate test count using the actual command rather than a commit message.
6. Run current prescribed checks from a clean/isolated checkout. Save full outputs and exit codes. Do not run destructive changes on a user's local database.
7. Re-check the current CI status for the exact SHA. The latest CI result must be distinguished from earlier runs against different SHAs.
8. Convert all findings from the independent audit into a traceability matrix in `docs/qa_agent/BASELINE_REPORT.md`.

### Required outputs

- `BASELINE_REPORT.md` with scope, environment and commands/results.
- `docs/qa_agent/plans/PHASE_00_PLAN.md` written before edits.
- System/module map and intended deployment mode assumptions.
- Initial failing-test list, known skipped tests, and blocked live tests.

### Exit gate

- Exact baseline SHA is recorded.
- Every audit finding has an owner phase and a test/evidence strategy.
- Current failures and skipped checks are listed honestly.
- No code has been changed before the baseline is captured.

---

# Phase 01 — Authoritative configuration, production mode and test isolation

**Maps to:** GQA-007, GQA-008; supports all later phases.  
**Priority:** P1.

**Likely files:** `central_platform/config.py`, `central_platform/deployment/validator.py`, `central_platform/auth/tokens.py`, `central_platform/api/app.py`, `core/config.py`, `tests/conftest.py`, `scripts/migrate_db.py`, configuration tests.

### Problem to solve

The repo has multiple environment and secret-resolution paths. `central_platform/config.py` resolves production mode from `GAYATRI_ENV` or `APP_ENV`; some deployment-validator code uses `APP_ENV` directly. The validator checks `SECRET_KEY` or `JWT_SECRET`, while the authoritative token/config code accepts `GAYATRI_JWT_SECRET` or `JWT_SECRET`. The autouse test fixture applies migrations to repository-root `gayatri_local.db`, risking shared state and unrepeatable runs.

### Tasks

1. Trace every use of production/dev flags, JWT secrets, encryption keys, CORS origins, database path/URL, debug flags and model paths. Produce a configuration matrix before changing code.
2. Build or consolidate one validated settings object/API used consistently by startup validation, auth/token signing, deployment readiness, health checks and service construction. Do not maintain independent validators with contradictory rules.
3. Define and document precedence/aliases. Prefer one canonical secret name; support legacy aliases only if necessary and test conflicts explicitly. In production, fail closed if a required secret is missing, weak, default, or conflicting.
4. Ensure startup uses the same resolved settings that later services use. It must not validate one database or secret while running with another.
5. Check encryption requirements by supported OS/mode. Do not create an unintended security bypass merely because the environment is Windows; if an OS has a documented limitation, explicitly represent the security guarantee and make the deployment decision clear.
6. Change default tests to use temporary databases created by `tmp_path_factory`. Tests specifically exercising upgrade-in-place must build a disposable copy of a fixture DB.
7. Add migration tests for empty schema, supported prior versions, interrupted migrations, rollback, idempotency, and malformed schema.
8. Verify test fixture cleanup closes all connections and background writers. Assert test runs do not mutate a developer database or depend on its pre-existing state.
9. Add safe configuration diagnostics that report selected mode, canonical non-secret setting names and missing requirements without logging values.

### Tests to add

- Each supported production environment alias individually; both flags set consistently; contradictory flags; missing mode.
- Missing/weak/known-default/short JWT secret; valid secret; conflicting aliases.
- Missing encryption key in each supported production OS; weak key; valid key.
- Empty/wildcard/malformed CORS configuration.
- Production debug/reload flag rejection.
- Database config mismatch and missing database.
- Migration from clean temporary DB and rerun idempotency.
- Two independent test DBs cannot see or mutate each other's data.

### Exit gate

- One authoritative configuration result is used for production mode and secrets.
- Invalid production config stops startup before accepting requests.
- Tests use isolated DB state unless intentionally testing a disposable migration fixture.
- Focused tests and full repo regression pass without weakened assertions.

---

# Phase 02 — Real-model execution, AI readiness and execution provenance

**Maps to:** GQA-001, GQA-002; **P0 release blocker**.  
**Likely files:** `central_platform/deployment/validator.py`, `central_platform/ai/gateway.py`, `central_platform/ai/adapters.py`, `central_platform/ai/schema.py`, `core/providers/local.py`, `core/model_fetch/`, AI/deployment tests, `tests/test_phase29_final_platform_audit_master.py`.

### Problem to solve

Some health paths infer AI health from model manifest/model registration and physical file presence. The Phase 29 master AI audit explicitly expects MOCK or DEGRADED_FALLBACK and `real_model == false`; that test checks fallback observability, not the real model. File existence, checksum presence, configured provider, model discovery, model load and real inference are different guarantees and must remain distinct.

### Tasks

1. Trace AI request routing from API/UI through gateway, router, provider adapter, local model loader and returned response. Verify that execution provenance survives every conversion/serialization layer.
2. Define a strict readiness state model such as `UNCONFIGURED`, `CONFIGURED`, `ARTIFACT_VERIFIED`, `LOADABLE`, `INFERENCE_VERIFIED`, `HEALTHY`, `DEGRADED`, `FAILED`. Document transitions and the proof required for each state.
3. Split lightweight liveness checks from a bounded inference readiness probe. Liveness must not load a huge model unnecessarily; release certification must still require actual model execution in the target environment.
4. Validate manifest schema, resolved path containment, file size/header, expected checksum when supplied, configured model ID, loader availability and provider settings. Missing/corrupt/incompatible model must report the right failed state.
5. The target production adapter must execute a controlled, harmless probe with a timeout and bounded tokens. Validate non-empty output, model/provider identity, `REAL_MODEL` provenance and an unambiguous success status. Empty, malformed, timeout, mock, or fallback results must fail the real-inference readiness gate.
6. Keep the current mock/fallback unit test, but rename/document it as fallback-only. Add a separate release integration test that requires real execution. Do not “solve” this by asserting whichever result happens to be returned.
7. Add a real-provider test profile for locally packaged GGUF and each externally supported provider. Provider credentials should be injected via CI secrets/environment; do not write secrets into repo.
8. Ensure errors returned by the gateway preserve normalized status, safe user-facing text and diagnostic context without leaking provider keys or student prompts.
9. Add release evidence metadata: commit SHA, model name/revision, model checksum, provider type, dependency lock hash, execution provenance, latency, and sanitized result metadata.

### Required test cases

- Manifest missing/malformed/empty.
- Registered model but absent file.
- File exists but is truncated or header invalid.
- Checksum absent where required, incorrect checksum and valid checksum.
- Model file passes hash but loader fails.
- Model loads but inference fails, times out, returns blank/malformed output or stream closes early.
- Provider key missing/invalid, quota/rate limit, network outage, HTTP 5xx.
- Mock/fallback response must never satisfy real readiness.
- Real model generates response and provenance is preserved through API response/log/health output.
- Model unload/reload and recovery after failure.

### Exit gate

- Production health cannot be green on manifest/file existence alone.
- Release real-model check demonstrably runs a real model and fails on missing/invalid model.
- Mock/fallback test and real-model test are clearly separated.
- No real-inference tests are silently skipped and then counted as passing for a production tier.

---

# Phase 03 — Educational correctness and safe fallback policy

**Maps to:** GQA-003; **P0 release blocker**.  
**Likely files:** `central_platform/ai/adapters.py`, `central_platform/ai/gateway.py`, `central_platform/ai/schema.py`, `core/tutor_engine.py`, adaptive-learning/scoring services, AI response consumers, student/teacher portal controllers.

### Problem to solve

The deterministic pedagogical response generator includes a grading/evaluation branch that returns a constant `score: 1.0` and `correct: true` without judging the submitted answer. Other canned responses are selected by keyword matching. Explicit fallback provenance is useful but downstream code may still consume the response as authoritative grading, tutor explanation or mastery evidence.

### Tasks

1. Search every call to `generate_dynamic_pedagogical_content`, `MockAIAdapter`, `fallback_used`, `execution_provenance`, and every consumer that updates score, mastery, learning events, misconceptions, progress or teacher analytics.
2. Define a product policy by execution mode:
   - Real local inference counts as real-model execution even when offline.
   - Approved deterministic calculations/rules may be used only for narrow tasks with explicit input validation and tests.
   - Mock/canned fallback is for tests/demo or an explicitly marked non-authoritative degraded UI response only.
   - No non-authoritative response may change grades, correct/incorrect state, mastery, remediation decisions or authoritative learning analytics.
3. Remove the hard-coded full-credit grading result. If the grader/model/rule engine is unavailable, return a typed evaluation-unavailable status and do not mark the answer correct or incorrect by guesswork.
4. Introduce explicit response metadata/enums rather than scattered booleans. Preserve provenance at the API boundary and in learning-event metadata.
5. Make downstream state transitions require a validated assessment object produced by an approved grader—not merely a tutor text response or `success=True`.
6. Keep an offline product usable when local real model inference is available. Do not disable all offline functionality as a shortcut. When the model is missing, show a clear error or a visibly non-authoritative demo message.
7. Add curriculum-independent behavior tests plus domain-specific chemistry and math tests. Include numeric/units/sign convention/reaction equation cases, wrong student answers, ambiguous questions, off-topic prompts, and prompt attempts to influence grading.
8. Review UI/teacher reports to ensure degraded responses cannot be displayed as verified correctness or updated mastery.

### Required test cases

- Incorrect student answer cannot receive automatic full credit.
- Correct answer versus incorrect answer yields expected assessment on a verified grading path.
- Grader unavailable means score/mastery unchanged.
- Mock/fallback response cannot produce `LearningEvent` that asserts `is_correct`, score or mastery delta.
- Duplicate assessment request does not double-update mastery.
- Tutor fallback appears as degraded and is not presented as authoritative NCERT/source-grounded answer.
- Safe recovery when a real model becomes available again.

### Exit gate

- No deterministic fallback can award marks or update mastery.
- All state-changing learning operations require a validated authoritative result.
- A reviewed educational gold set exists, and core cases pass with traceable expected results.

---

# Phase 04 — Gateway status, metrics, logging and degraded-state visibility

**Maps to:** GQA-004, GQA-015.  
**Likely files:** `central_platform/ai/gateway.py`, AI result schemas, logging/middleware, health/analytics routes, admin UI, monitoring tests.

### Tasks

1. Replace status logic that labels the first enabled provider as active/healthy. Separate configured, enabled, reachable, loadable, recently-inferred, degraded and unavailable states.
2. Include last successful inference timestamp; never claim a provider is healthy only because it is configured.
3. Replace synthetic token metric (`daily_spend_usd * 10000`) with actual provider usage fields when available. For local models, report a tokenizer estimate only when clearly labeled `estimated`; use `unknown` when no measurement exists.
4. Define cost and token metric semantics across different providers. Handle usage absent, request failure, retries, fallback and provider failover without double counting.
5. Preserve request IDs/correlation IDs and structured error classes. Ensure logs omit API secrets, bearer tokens, full student content and private source text by default.
6. Expose fallback/degraded state in UI in a way teachers/students can understand. Avoid surfacing internal stack traces or provider credentials.
7. Add tests for counters/metrics reset boundaries, timezone/day boundary, usage missing, provider fallback and log redaction.

### Exit gate

- “Healthy/active” means evidence-based runtime status, not configuration presence.
- Token and cost metrics have defined measurement provenance.
- Monitoring accurately displays degraded responses and does not disclose sensitive values.

---

# Phase 05 — Authentication, revocation, authorization and distributed rate limiting

**Maps to:** GQA-005, GQA-006, parts of GQA-013.  
**Likely files:** `central_platform/auth/tokens.py`, `central_platform/config.py`, `central_platform/security/auditor.py`, `central_platform/rbac/`, API route dependencies and authorization tests.

### Tasks

1. Document the auth/session model for desktop/offline, single-process server and multi-worker/multi-tenant server. Keep guarantees distinct by deployment mode.
2. Replace process-local `_REVOKED_JTIS` as the sole revocation system for multi-worker production. Choose a shared durable registry, session-version mechanism, or a justified access-token/rotating-refresh architecture. The choice must survive the intended restarts/workers.
3. Use strict JWT verification: signature, expiry, issuer/audience if configured, token type, subject, organization, revocation and user active/deleted state. Never accept an unverified payload for authorization.
4. Make production require the authoritative secret settings from Phase 01. Test logout, revocation and refresh semantics including token reuse.
5. For `SharedRateLimiterBackend`, make shared-store configuration explicit. When deployment policy requires global limiting, missing/unhealthy shared storage must cause readiness failure rather than quiet acceptance of per-process limits.
6. Verify atomicity of distributed sliding-window updates. Prevent races where concurrent requests exceed limit. Define separate policies for user ID, anonymous client/IP and endpoint class.
7. Build a comprehensive route/object authorization matrix for student, teacher, org admin, super admin and anonymous actors. Validate object ownership and tenant scope in path, query, body and nested IDs.
8. Verify token revocation checks in every route/service path that accepts an authenticated user; do not rely on frontend hiding controls.

### Required test cases

- Invalid/expired/wrong-type/revoked token; user suspended, deleted or inactive.
- Revoke on process A and use on process B; restart and retry.
- Refresh token rotates; old refresh token reuse fails; logout invalidates expected tokens.
- No shared limiter configured in cluster-required mode fails readiness.
- Same identity distributes requests across two workers and still obeys one global limit.
- Student reads/updates/deletes own object and tries another student's session, learning record, RAG corpus, course and analytics.
- Teacher assigned/unassigned course; org admin same/different tenant; super admin action scoped and audited.
- Auth header missing, malformed, duplicated or excessively long.

### Exit gate

- Revocation and rate limiting meet the stated guarantee in every supported deployment mode.
- No P0/P1 authorization finding remains open.
- Route/object tests cover all protected resource families, not only example endpoints.

---

# Phase 06 — Session persistence, write acknowledgements, data integrity and migrations

**Maps to:** GQA-007, GQA-011.  
**Likely files:** `core/session.py`, `core/db.py`, `scripts/migrate_db.py`, `central_platform/db/`, learning event services, session and concurrency tests.

### Tasks

1. Trace session/message/tutor-context writes, learning event writes and mastery updates end to end. Identify the authoritative store per deployment mode and ensure services do not unintentionally write to divergent SQLite DBs.
2. The asynchronous session writer must expose success/failure to callers or provide a documented durable queue/retry guarantee. A `queue.join()` is not proof the database write succeeded if the worker caught and discarded the exception.
3. Introduce per-write acknowledgement/future or an equivalent reliable mechanism. For APIs that cannot block, return a state that distinguishes pending from durable and provide a way to report failures. Do not falsely confirm persistence.
4. Include failed-write count and structured operation/session ID in logs, without private content. Implement bounded retry only for transient errors and avoid unbounded queue growth.
5. Make shutdown drain queued writes, wait for the writer thread to finish, verify terminal failures, then close the connection. Prevent writes after shutdown begins.
6. Ensure database connection ownership/threading is safe; inspect use of a single SQLite connection across the writer and read paths. Fix race conditions with minimal architectural disruption.
7. Add concurrency tests for updating the same session, separate users, creating/deleting sessions, and context saves alongside messages.
8. Verify deletion semantics across messages, tutor context, events and backups, consistent with retention requirements.
9. Add data migration tests for empty DB, previous supported schema versions, interrupted/partial migrations, rollback and repeated migration.
10. Add idempotency protections for event submissions and mastery updates to prevent retried requests from inflating scores/progress.

### Required fault-injection tests

- `SQLITE_BUSY`, locked DB, read-only directory, disk-full simulation where available, closed connection, serialization failure and worker-thread exception.
- Enqueue write → flush → close → reopen → data exists.
- Enqueue write → injected failure → API/caller sees failure or durable retry/dead-letter evidence.
- Enqueue multiple writes → graceful shutdown → every successful write persisted.
- Abrupt termination/restart behavior explicitly documented and tested to the extent possible.
- Duplicate learning-event request IDs do not create duplicate authoritative effects.

### Exit gate

- User-visible success corresponds to durable persistence or an explicit pending state.
- Write failures are detectable and recoverable; they cannot silently count as completed.
- Tests run against isolated DB instances and do not mutate developer data.

---

# Phase 07 — RAG ingestion, retrieval integrity, grounding and health

**Maps to:** GQA-012, parts of GQA-001 and GQA-013.  
**Likely files:** `central_platform/rag/service.py`, RAG routes/schemas, knowledge asset parsing/chunking/indexing, deployment validator, RAG tests and fixtures.

### Tasks

1. Map upload → extension/MIME/size validation → parse → clean → chunk → metadata → embed/index → validation → publish → retrieval → citation rendering.
2. Ensure ingestion fails transparently when parsing, indexing, embedding, persistence or publication fails. No empty/partial index may be marked published/healthy without a declared policy.
3. Keep the operational retrieval liveness probe, but label it as a smoke test. The current approach derives query words from the first published chunk; that does not establish semantic recall or independent relevance.
4. Add a representative golden query set authored independently of stored chunks. Cover paraphrases, spelling variations, indirect conceptual questions, subject boundaries, course scope, curriculum levels, citation relevance and unsupported questions.
5. Verify citations refer to real retrievable sources with stable identifiers and correct metadata. If no supporting source exists, response must not invent a citation or claim grounded confidence.
6. Ensure production query results cannot leak another tenant's corpus. Verify filter-before-ranking and scope behavior across global/course/org-specific sources.
7. Review lexical and semantic retrieval modes; expose which retrieval strategy is running and whether vector/embedding data is actually available. Do not claim semantic retrieval if only lexical scoring is running.
8. Review legacy JSON fallback: report filename-specific parse errors, avoid quietly treating partial file reads as complete ingestion, and distinguish fallback corpus from published database corpus.
9. Add stale-index detection, source version/checksum tracking and reindex workflow. Ensure updated/deleted source material stops appearing from stale chunks.
10. Sanitize retrieved instructions as untrusted document content. Test malicious instructions inside PDFs/Markdown/text, not only in direct user prompts.

### Required test cases

- Empty corpus in production is not healthy.
- First source/chunk missing/corrupt; invalid parser output; malformed JSON; unsupported MIME/extension; oversized file.
- Upload succeeds but index write fails; database fails; vector/semantic component unavailable.
- Published source returns result with valid citation; citation points to wrong source; no relevance/evidence.
- Golden queries include paraphrase questions that do not share exact source phrasing.
- Cross-course/cross-tenant search cannot return protected content.
- Malicious retrieved text does not override system instructions or trigger tools.
- Update/delete/re-publish cannot surface stale content.

### Exit gate

- Health means the expected corpus/version is retrievable, not merely that some chunk exists.
- RAG golden set has documented metrics, reviewed expected sources and minimum thresholds.
- Retrieval failure, empty evidence and citation errors are explicit and not mislabeled as success.

---

# Phase 08 — Security hardening and independent adversarial verification

**Maps to:** GQA-013; cross-cuts Phases 01, 05, 06 and 07.  
**Likely files:** `central_platform/security/auditor.py`, API middleware/routes, upload handlers, UI rendering/Markdown code, RAG ingest/query, test security suites.

### Tasks

1. Treat `SecurityAuditor` pattern matching as defense-in-depth, not as certification of all threat categories in its docstring.
2. Inventory every route and every place data enters a trust boundary: HTTP body/query/path, local IPC, file upload, RAG corpus, model output, sync payload, payment webhook, admin action and UI Markdown/HTML.
3. Run the full actor/tenant matrix for all route groups; check object-level authorization at the data operation, not only route-level role checks.
4. Use path canonicalization and containment checks for all file access. Test symlink escapes and time-of-check/time-of-use behavior where relevant. Do not trust filename extension alone.
5. Validate uploads by allowed extension, MIME/magic bytes, size and parser constraints; reject path components and dangerous types. Protect against oversized or decompression-bomb documents within practical limits.
6. Test XSS in all browser rendering contexts including Markdown generated from model/provider/user/RAG content. Use proper escaping/sanitization and safe link policy; string substitution alone is not enough.
7. Test prompt injection and indirect injection through documents. The model must treat retrieved text as untrusted; regex misses must not authorize tool calls or secret exposure.
8. Review SQL access patterns for parameter binding, especially filters assembled from query/body parameters. Run targeted injection tests without destructive payloads.
9. Review CSRF/CORS/session/cookie choices for browser-hosted deployment; ensure production CORS configuration aligns with the canonical configuration object.
10. Test secret redaction in errors, traces and audit logs. Ensure no bearer tokens, provider keys or private student contents are logged on failures.
11. Verify rate limiting and abuse protection apply to login, token refresh, AI generation, document upload, search and expensive endpoints.
12. Add security regression tests and produce a threat-to-test matrix. Independent review or external penetration testing remains required for a formal security claim.

### Required test families

- IDOR and cross-tenant access for read/write/delete.
- Authentication bypass/malformed JWT/revocation.
- Prompt injection, encoded/obfuscated instruction, indirect RAG injection and system prompt extraction attempts.
- Markdown/HTML XSS and unsafe URL schemes.
- Path traversal, prefix-collision path, absolute path, null byte, symlink escape.
- SQL injection attempts; oversized and malformed requests; abuse/rate-limit bypass.
- File uploads with mismatched magic bytes, huge input and malformed documents.
- CORS/CSRF behavior in a real browser or browser-level test suite.
- Redaction validation on intentionally induced provider/database errors.

### Exit gate

- No unresolved P0/P1 security issue.
- Each security vector claimed as supported has a specific test and explicit coverage status.
- Security claims are not based only on passing regex tests.

---

# Phase 09 — Training pipeline, dataset integrity and model evaluation

**Maps to:** GQA-010 and model-release reliability.  
**Likely files:** `training/train_slm.py`, `scripts/generate_slm_training_data.py`, dataset preparation scripts/notebooks, model conversion/quantization, artifact manifest/validation, training tests.

### Problem to solve

The current pedagogical verification defines both required and forbidden output strings but increments the pass count based on forbidden-string absence only; it does not check the `must_contain` criteria. A blank or irrelevant response can therefore pass this aspect of the check. A two-prompt verification cannot establish chemistry/math accuracy or robust tutoring behavior.

### Tasks

1. Fix the evaluator so every required criterion is enforced and every forbidden criterion is rejected. Treat empty output, malformed structure, exceptions and missing fields as failures.
2. Ensure failed evaluation exits with non-zero status and prevents model promotion/manifest update/release packaging.
3. Replace fragile shell command concatenation where practical with argument lists passed to `subprocess.run(check=True)`. If `shell=True` is required for a documented reason, validate/quote every variable and do not pass untrusted input.
4. Verify dataset files exist, parse, match the expected schema and contain non-empty train and validation splits. Do not silently generate synthetic data as a production-training substitute unless explicitly opted into a development dataset.
5. Detect exact/near duplicates and train/validation leakage. Record dataset checksums and provenance for approved source material.
6. Pin the base-model revision and tokenizer revision, plus Python/PyTorch/Transformers/PEFT/TRL/datasets/llama.cpp toolchain versions and relevant CUDA/platform assumptions.
7. Track reproducible hyperparameters, seed, quantization config, conversion command, and exact source commit.
8. Validate output artifacts are created where expected, are non-empty, can be loaded, have a valid GGUF header, and match manifest hashes. Do not assume file existence proves artifact integrity.
9. Build a reviewed educational evaluation set: fact checking, chemistry equations/numericals/units/sign conventions, math calculations, Socratic hints, misconception handling, response relevance, answer leakage and prompt injection.
10. Use deterministic programmatic grading for calculable answer keys where possible and blinded expert review for open-ended educational behavior. Model-as-judge may supplement but must not be the only oracle.
11. Compare base model vs fine-tuned model to detect regressions. Store scores and samples securely; redact private training data in logs.
12. Add artifact promotion rules so an unverified artifact cannot overwrite a known-good model or be labelled production-ready.

### Required test cases

- All `must_contain` and `must_not_contain` checks are enforced.
- Empty answer fails; required phrase missing fails; forbidden phrase present fails.
- Failed subprocess stops training and no release artifact is promoted.
- Missing/bad train file, missing validation file, invalid JSON, empty split, duplicate/leaking samples.
- Wrong base model/tokenizer revision cannot be mislabeled as the approved model.
- Converted GGUF passes header/hash checks and successfully loads/infer on target runtime.
- Evaluation report is tied to dataset/model/checkpoint hashes and includes failure cases.

### Exit gate

- Training evaluation is fail-closed and meaningfully measures intended behavior.
- Model build is reproducible enough to identify exact inputs/toolchain.
- Model artifact is load-tested and evaluated before promotion.

---

# Phase 10 — Dependency locking, CI design and release reproducibility

**Maps to:** GQA-009, GQA-014, GQA-016.  
**Likely files:** `.github/workflows/ci.yml`, `requirements.txt`, `requirements.lock`, Python packaging/installer config, CI scripts, test markers.

### Tasks

1. Reconcile dependency intent: identify direct/runtime/dev/training-only dependencies, compare requirements and lock, and document the supported Python matrix.
2. Update CI so the main release verification installs the exact committed lock used for the release build. If a lock generator is used, pin the tool/version and add a check that generated lock is up to date.
3. Consider dependency hashes and vulnerability/licensing checks. Record false positives and approved exceptions; do not automatically upgrade breaking packages without tests.
4. Continue a fast lightweight PR suite, but add a complete release suite that runs real integration tests in an intentionally configured environment. A skipped real-model test must not produce a production-ready result.
5. Run compile checks, architecture guardrails, migration checks and pytest with explicit summaries. Ensure critical test failures cause non-zero exit.
6. Add supported OS/Python matrix for every platform actually promised by the product. Do not add unsupported targets only to make CI look comprehensive; first identify supported targets from product requirements.
7. Add a clean cache install job and cold-cache dependency build. Validate platform wheel availability for `PySide6` and `llama-cpp-python`.
8. Separate GUI tests from headless jobs; run GUI smoke tests with an appropriate runner on supported OS.
9. Check workflow permissions follow least privilege and that PR jobs do not receive unnecessary secrets or write permissions.
10. Re-run CI on the final SHA and record job URLs. A green run on an earlier SHA does not certify the release SHA.
11. Inspect and retain logs for any failure; do not cherry-pick only successful runs or ignore failing required checks.

### Required CI gates

- Locked dependency installation from clean environment.
- Compile/format/static checks and architecture guardrails.
- Temporary database setup and migration suite.
- Full headless tests.
- Supported-platform desktop/package smoke tests.
- Real model/RAG release integration tests in a configured environment.
- Security and dependency scan.
- Build artifacts have version/SHA and checksum metadata.

### Exit gate

- CI tests the same pinned dependency set intended for release.
- All supported target jobs pass on the exact candidate SHA.
- Latest checks have completed; no release-critical job remains in progress or skipped without disposition.

---

# Phase 11 — Clean installation, packaging, upgrade, rollback and operational readiness

**Maps to:** platform release claims and GQA-009.  
**Likely files:** `app/main.py`, `app/windows/`, `packaging/`, installer scripts, database bootstrap/migration, model download/manifest paths, logging/health endpoints, release docs.

### Tasks

1. Identify target release modes: Windows desktop/offline, local server, and/or hosted server. Create a separate acceptance checklist for each; do not assume one mode's tests certify another.
2. On a clean disposable machine/VM, install from the published artifact with no developer Python environment, model cache or database already present.
3. Verify first-run flows, default directories, permissions, database schema creation, missing-model experience, model download/resume/checksum, first actual inference, upgrade and uninstall behavior.
4. Test path resolution with spaces, non-ASCII directory names and standard user permissions; confirm paths do not escape the app data root.
5. Test application startup with bad configuration and missing artifacts; give actionable UI diagnostics without exposing internals.
6. Verify offline mode when the network is disabled and local model exists; verify clear failure when the local model is absent. Do not return canned output as if generated by a model.
7. Test upgrade from each supported prior version with backup/rollback plan. Verify user's messages and learning records survive expected upgrades.
8. Validate backups and restoration with real fixture data; verify integrity checks and document maximum recovery point/time assumptions.
9. Review process management, logs, rotation, disk growth, service restart, graceful shutdown and stale child-process cleanup.
10. Check health endpoints: liveness must be lightweight; readiness includes critical dependencies; AI inference health is distinct and does not mask other failed services.
11. Add post-install smoke test script and a rollback checklist. Never perform a production deployment automatically as part of this code repair plan.

### Exit gate

- Fresh install and upgrade are successful on every supported target.
- The app launches and performs a real inference under the documented mode.
- Failure states are explicit; data is preserved/recoverable according to the release contract.

---

# Phase 12 — Full integration, adversarial, concurrency and load testing

**Maps to:** unresolved cross-cutting risks from all audit findings.  
**Depends on:** Phases 01–11.

### Tasks

1. Build end-to-end student journeys: login → choose course → ask → retrieve source → receive response → answer a question → assessment → mastery update → close/reopen → verify progress persists.
2. Build teacher/admin journeys: add/approve course material → publish RAG → assign course → add instructions → review student progress → manage users/configuration → audit logs.
3. Test error journeys: no internet, model unavailable, RAG empty, provider timeout/rate limit, DB unavailable, async write failure, corrupt session, expired/revoked token and partial sync.
4. Run tenant-isolation attacks across every data-bearing route and UI/API pair. Include guessed object IDs and mismatched tenant identifiers in query/body/path.
5. Run adversarial prompts against user query and retrieved documents; verify no cross-student data exposure, secret leakage, unsafe tool invocation or authoritative grade mutation.
6. Test concurrent requests and sessions, including two workers, rate-limited traffic, long conversations and context-window overflow.
7. Benchmark model latency/memory/token throughput on actual target hardware. Measure startup, first token, total response, memory peak, error rate and recovery. Do not invent expected capacity without target-hardware evidence.
8. Test graceful application shutdown during active request and queued writes; validate no partial state or falsely successful writes.
9. Run browser-level tests for Markdown/rendering, responsive layouts, keyboard operation, route authorization UX and recovery from stale auth/session.
10. Use synthetic/scrubbed data for tests. Never run attacks against live student data or a production system without explicit authorization.

### Exit gate

- All core student/teacher/admin journeys pass with real configured AI and RAG where required.
- Error paths fail visibly and safely; no fake green/success state appears.
- Concurrency and performance satisfy documented acceptance targets on recorded hardware/environment.
- No open P0/P1 issue or unexplained failure/skip remains.

---

# Phase 13 — Final release evidence pack and decision

**Depends on:** All prior phases.

### Tasks

1. Re-run phase-specific tests and the full release suite against the exact release SHA and locked dependency set.
2. Capture test summaries, coverage, known skips, static analysis, dependency scan, route/security matrix, model evaluation, RAG golden set results, migration results, backup restore, packaging, install/upgrade and load-test results.
3. Capture exact model artifact ID/revision/hash and dataset/evaluation identifiers. If a provider integration uses external service credentials, record the provider and sanitized test result; never record secret values.
4. Reconcile every `GQA-*` finding with its remediation commit, regression test, evidence path and residual risk. Re-open any finding that a test contradicts.
5. Complete `docs/qa_agent/MASTER_PROGRESS.md`, decision log and a final `docs/qa_agent/FINAL_RELEASE_READINESS_REPORT.md`.
6. Assign a release tier only from explicit gates:
   - `PRE_PRODUCTION`: any P0 or unresolved security gate; real model/RAG unverified; build/test evidence incomplete.
   - `RELEASE_CANDIDATE`: P0 closed but P1 or target-environment validation remains incomplete.
   - `PRODUCTION_READY`: all mandatory release gates pass, no open P0/P1, the exact SHA's supported-target CI passes, real inference and representative grounded retrieval are proven, and evidence is reproducible.
   - `RELEASED`: production deployment and post-deploy smoke test have actually completed with approval. A code-only agent must not self-assign this tier.
7. Do not say “production-ready” if live provider credentials, target model, supported platform, or representative RAG corpus were not tested. State the gap explicitly.

### Final release acceptance criteria

- [ ] All P0 findings closed with regression tests.
- [ ] All P1 findings closed or a named owner has formally accepted a documented compensating control; no unapproved exception.
- [ ] Latest CI is green for exact release SHA and all supported targets.
- [ ] Exact dependency lock was installed and validated.
- [ ] Real model inference passes in each intended release mode.
- [ ] Mock/degraded fallback cannot mutate grades or learner mastery.
- [ ] Independent RAG golden set meets documented relevance/citation/correctness threshold.
- [ ] Auth, revocation, tenant isolation and rate limiting pass multi-worker tests if multi-worker is supported.
- [ ] Persistence, migration and restore tests pass, including injected errors.
- [ ] Training/evaluation logic fails closed on missing required criteria or failed subprocesses.
- [ ] Security adversarial tests and dependency scans have an evidenced disposition.
- [ ] Clean installation/upgrade and rollback tests pass for target products.
- [ ] Monitoring, logs and user-facing degraded states are accurate.
- [ ] Final evidence pack contains commands, outputs, environment, SHA and artifact hashes.

---

## 2. Finding-to-phase traceability

| Audit finding | Primary phase(s) | Required proof |
|---|---|---|
| GQA-001 AI health/readiness can be false green | 01, 02, 11, 13 | Target-environment real inference readiness test; missing/invalid artifact tests |
| GQA-002 Master test accepts fallback | 02, 12, 13 | Separate fallback test and mandatory real-model integration test |
| GQA-003 Fixed/canned grading fallback | 03, 09, 12 | Incorrect answer cannot receive full marks; no fallback mastery mutation |
| GQA-004 Provider status is config-based | 04, 11 | Provider-down tests and accurate degraded health status |
| GQA-005 Process-local JWT revocation | 01, 05, 12 | Cross-worker and restart revocation tests |
| GQA-006 Shared rate limiter fallback | 05, 12 | Missing shared store fails required mode; concurrent multi-worker limit test |
| GQA-007 Root DB in test fixture | 01, 06, 10 | Isolated DB test and migration fixture suite |
| GQA-008 Configuration divergence | 01, 05, 10 | Consistent settings matrix and fail-fast tests |
| GQA-009 Single-platform CI | 10, 11 | Green CI/build/install evidence for supported target matrix |
| GQA-010 Incomplete training evaluator | 09, 10, 13 | Required and forbidden checks exercised; non-zero exit on bad output |
| GQA-011 Silent async write failure | 06, 12 | Injected DB failure is surfaced/recovered; restart durability proof |
| GQA-012 Narrow RAG health probe | 07, 12, 13 | Golden query/citation/tenant-scoping evaluation |
| GQA-013 Regex is not complete security proof | 05, 07, 08, 12 | Threat-to-test matrix and route/object security results |
| GQA-014 CI ignores lock | 10, 13 | Clean install from locked requirements on release SHA |
| GQA-015 Synthetic token metric | 04 | Metric tests prove actual/estimated/unknown semantics |
| GQA-016 Latest CI incomplete at audit time | 10, 13 | Final completed green workflow linked to the release SHA |

---

## 3. Phase completion report template

Use this template at the end of every phase:

```markdown
# Phase NN — Completion Report

## Summary
- Status: PASSED / FAILED / BLOCKED
- Source SHA before:
- Source SHA after:
- Date/environment:

## Defects addressed
| ID | Root cause | Fix | Regression test | Evidence |
|---|---|---|---|---|

## Commands and results
| Command | Exit code | Passed | Failed | Skipped | Evidence path |
|---|---:|---:|---:|---:|---|

## Diff review
- Files changed:
- Schema/API changes:
- Security/privacy effects:
- Potential regressions:

## Remaining risks and blockers
- ...

## Exit gate
- [ ] Focused tests pass
- [ ] Full applicable regression passes
- [ ] Existing assertions were not weakened
- [ ] Evidence is stored and reproducible
- [ ] No unresolved P0/P1 for this phase

## Decision
- Proceed to next phase: YES / NO
- Reason:
```

## 4. Final instruction to the coding agent

**Plan first. Reproduce before fixing. Implement the smallest correct change. Add a regression test that would have caught the defect. Debug until it passes. Run the full repository regression after each phase. Record the evidence. Only then move to the next phase.**

The objective is not to make the dashboard green or to increase the number of tests. The objective is to make Gayatri behave correctly under real deployment conditions, fail safely when dependencies fail, preserve student data, enforce authorization across tenants, and provide an honest and reproducible production-readiness decision.
