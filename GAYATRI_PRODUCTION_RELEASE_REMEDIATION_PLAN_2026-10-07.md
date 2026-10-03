# GAYATRI — Production Release Remediation & Phase-by-Phase Execution Plan

**Repository:** `https://github.com/Gayatri-Education/Gayatri`  
**Target release date:** **7 October 2026**  
**Audit baseline:** **3 October 2026**  
**Primary goal:** Make the current Gayatri repository releasable without breaking previously working functionality.

---

## 0. Mission

This document is the authoritative execution guide for the local AI coding agent working on the Gayatri repository.

The agent must **not** treat this as a greenfield rewrite.

The agent must:

1. Inspect the current repository state before every phase.
2. Understand existing architecture and contracts before changing code.
3. Fix only the defects necessary for the production release unless a dependency is required to make a fix safe.
4. Preserve existing public APIs and working behavior wherever possible.
5. Make the smallest safe change that solves the identified problem.
6. Run targeted regression tests after every change.
7. Run broader regression tests before completing a phase.
8. Record evidence for every completed phase.
9. Never mark a phase complete because code was written; phase completion requires verification.
10. Stop and report when a proposed change introduces a regression, violates a security invariant, or changes an API contract unexpectedly.

### Hard release principle

> **Passing existing tests is necessary but not sufficient. Real product flows, packaged runtime behavior, configuration correctness, security boundaries, and production-mode behavior must also be verified.**

---

# 1. Non-Negotiable Agent Rules

## 1.1 Never code before reconnaissance

Before modifying any file:

```text
1. Read relevant source files.
2. Trace callers and callees.
3. Identify tests covering the affected behavior.
4. Identify configuration/environment dependencies.
5. Identify public API/UI contracts.
6. Identify persistence effects.
7. Identify security/tenant/role implications.
8. Identify packaging/runtime implications.
```

Create a short phase-local impact note before editing.

Required format:

```text
Phase:
Problem:
Root cause:
Files inspected:
Files expected to change:
Files that must NOT change:
Call graph:
Persistence impact:
API/UI contract impact:
Security impact:
Packaging impact:
Tests to run before change:
Tests to run after change:
Rollback strategy:
```

---

## 1.2 No speculative refactoring

Do not:

- rewrite working services merely to improve style;
- rename large groups of files during bug fixing;
- replace architecture because another framework seems better;
- delete compatibility APIs during release hardening;
- introduce a new database technology during the final release window;
- replace the AI stack unless the current stack is proven unusable.

Any refactor that is not necessary for the release blocker should be moved to `POST_RELEASE_BACKLOG.md`.

---

## 1.3 No production use of mock/demo behavior

Production must never silently use:

- mock users;
- synthetic identities;
- mock AI;
- deterministic fake pedagogical answers;
- demo tokens;
- test fixtures;
- fake telemetry;
- test-only curriculum;
- hard-coded student records.

A test path may continue to use mocks, but production execution must be explicitly prevented from doing so.

---

## 1.4 Preserve contracts

Before changing an API, identify:

```text
HTTP method
path
request schema
response schema
status codes
authentication requirements
role requirements
tenant requirements
side effects
error behavior
```

If compatibility is required:

```text
old endpoint
    -> compatibility wrapper
        -> canonical service implementation
```

Do not duplicate business logic.

---

## 1.5 Every bug fix must have regression protection

Every fix must add or update at least one test, unless the issue is purely packaging/documentation.

Preferred order:

```text
1. Reproduce bug.
2. Capture failing test.
3. Implement minimal fix.
4. Run focused test.
5. Run affected subsystem regression.
6. Run release smoke tests.
```

---

## 1.6 Never weaken a test to make it pass

Forbidden:

```text
- changing assertions merely to match broken behavior
- skipping failing tests without root-cause analysis
- converting errors into success responses
- making production code return test fixtures
- increasing timeouts indefinitely to hide performance regressions
- deleting tests because implementation changed
```

Tests may change only when the **intended contract** changed and the new contract is documented and verified.

---

## 1.7 Environment separation is mandatory

Use explicit modes:

```text
development
test
production
```

The agent must verify that production cannot accidentally inherit development behavior.

Minimum production checks:

```text
GAYATRI_ENV=production
APP_ENV=production
```

and all production-sensitive subsystems must derive their behavior from the same authoritative environment decision.

---

## 1.8 Do not expose secrets in logs

Never log:

- passwords;
- JWTs;
- refresh tokens;
- API keys;
- encryption keys;
- password reset tokens;
- unnecessary full student records;
- unnecessary full prompt contents.

Use identifiers such as:

```text
request_id
turn_id
user_id
organization_id
course_id
session_id
```

where appropriate.

---

# 2. Release Scope

## 2.1 Release-critical scope

The 7 October release is considered successful only when these user journeys work:

### Student journey

```text
Install
  -> Start
  -> Login
  -> Identity resolved
  -> Course visible
  -> Enrollment verified
  -> Open tutor
  -> Ask question
  -> RAG retrieval
  -> AI response
  -> Response validation
  -> Learning evidence recorded
  -> Mastery updated
  -> Next action/adaptation updated
  -> Continue conversation
  -> Restart application
  -> State still correct
```

### Teacher journey

```text
Login
  -> Correct organization
  -> Correct course
  -> Student cohort visible
  -> Learning/mastery state visible
  -> Intervention data visible
  -> Teacher instruction can be applied
  -> Instruction reaches tutor
  -> Student state remains tenant-safe
```

### Admin journey

```text
Login
  -> Correct admin role
  -> Organization administration
  -> Course/curriculum management
  -> Knowledge upload
  -> Ingestion
  -> Validation
  -> Publish
  -> Student access after publish
```

### Security journey

```text
Unauthenticated request -> 401
Wrong role -> 403
Wrong tenant -> 403
Wrong student -> 403
Missing resource -> 404
Expired token -> rejected
Revoked token -> rejected
Mock/demo path in production -> unavailable
```

---

# 3. High-Risk Findings to Resolve

The following items were identified from the current repository audit and must be treated as release blockers until verified fixed.

---

## P0-01 — Production login contains mock/integration fallback

### Observed risk

`central_platform/api/routes/auth.py` contains DB authentication followed by a fallback that can construct identities when a database user is not found.

The production path must never dynamically invent a user.

### Required behavior

```text
unknown user
    -> 401
```

Never:

```text
unknown user
    -> dynamically create identity
    -> issue JWT
```

### Acceptance criteria

- Unknown username returns 401.
- Wrong password returns 401.
- Suspended account returns 403.
- Inactive/deleted user cannot log in.
- Successful DB user receives JWT.
- JWT identity corresponds to authoritative DB identity.
- User organization/role comes from the DB, not request input.
- Production tests prove mock users are unavailable.

### Likely files

```text
central_platform/api/routes/auth.py
central_platform/auth/*
tests/*auth*
```

---

## P0-02 — Model manifest checksum must match the actual model

### Observed risk

`model_manifest.json` contains a checksum that must be verified against the actual GGUF artifact.

### Required behavior

```text
model file
   -> SHA-256
   -> compare with manifest
   -> load only when valid
```

### Acceptance criteria

- Correct checksum stored.
- Missing model produces controlled setup/readiness error.
- Corrupted model is rejected.
- Wrong model file is rejected.
- Release package includes the expected model or clearly documents a separately provisioned model path.
- No checksum is treated as trusted merely because it is present.

### Likely files

```text
model_manifest.json
central_platform/ai/adapters.py
core/*
scripts/*
tests/*
packaging/*
```

---

## P0-03 — Production must never fall back to mock AI

### Observed risk

`central_platform/ai/adapters.py` contains deterministic pedagogical/mock generation logic.

The repository also contains explicit production-mode protections, but the whole runtime call graph must prove that no production path can execute synthetic content.

### Required behavior

```text
real model available
   -> execute real model

real model unavailable
   -> controlled service-unavailable/degraded response

NOT
   -> fabricate educational answer
```

### Acceptance criteria

- `MockAIAdapter` cannot be invoked in production.
- Synthetic pedagogical content generator cannot be reached from production tutor flow.
- Missing local model cannot silently return a fake answer.
- Provider failures are observable.
- User message/state is preserved safely for retry.
- Error response does not mutate mastery as if a real turn completed.

---

## P0-04 — Production model identity is inconsistent

### Observed risk

Different repository components advertise different model identities, while `model_manifest.json` identifies a specific Qwen 0.5B artifact.

### Required behavior

There must be one authoritative production model configuration.

### Acceptance criteria

Every production execution can answer:

```text
model_id
model_name
artifact_path
artifact checksum
context length
quantization
provider
```

and these values are internally consistent.

---

## P0-05 — Production CORS is too permissive

### Observed risk

The API application currently configures:

```text
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

### Required behavior

Production origins must come from explicit configuration.

### Acceptance criteria

- No wildcard origin in production.
- Allowed methods are intentional.
- Allowed headers are intentional.
- Local/test mode may use broader settings if clearly isolated.
- Tests assert production rejects unapproved origins.

---

## P0-06 — Password reset must use verified reset tokens

### Observed risk

The password reset route contains an email-driven reset path that needs production-safe verification semantics.

### Required behavior

```text
forgot password
 -> generic confirmation
 -> short-lived one-time reset token
 -> verified token
 -> password change
 -> invalidate applicable old sessions/refresh tokens
```

### Acceptance criteria

- Reset request does not disclose whether an email exists where inappropriate.
- Reset requires a valid signed/hashed token.
- Token expires.
- Token cannot be reused.
- Successful reset revokes old sessions where intended.
- Direct password reset by email alone is impossible in production.

---

## P0-07 — Packaging references must match repository contents

### Observed risk

`packaging/gayatri_demo.spec` references `training/prompts`, while recent production cleanup removed internal training material from the public repository.

### Acceptance criteria

- Clean clone builds successfully.
- Every packaged source file exists.
- No build depends on developer-only files.
- No private IP or private training artifact is included.
- Prompt contract assets required at runtime are available through the official release path.
- Build fails early if a required asset is missing.

---

## P0-08 — Production runtime validation must be independent of synthetic fixtures

### Observed risk

`validate_production_runtime.py` constructs synthetic organizations, users, course records, RAG records and test content.

This is useful as an automated integration test, but it is not equivalent to validating the actual packaged release.

### Required behavior

Maintain two distinct validation layers:

```text
A. Synthetic automated integration validation
B. Real packaged release acceptance validation
```

Both are mandatory.

---

# 4. Phase Execution Framework

Every phase must use this lifecycle:

```text
PHASE START
   |
   v
Inspect current state
   |
   v
Establish baseline
   |
   v
Identify root cause
   |
   v
Prepare minimal-change plan
   |
   v
Implement
   |
   v
Run targeted tests
   |
   v
Run subsystem regression
   |
   v
Run release smoke suite
   |
   v
Inspect git diff
   |
   v
Check packaging / deployment impact
   |
   v
Record evidence
   |
   v
Commit
   |
   v
Update progress tracker
   |
   v
PHASE GATE
```

A phase may only move from `IN_PROGRESS` to `COMPLETE` when the phase gate is passed.

---

# 5. Test Tiers

Do not run all 1,252 tests after every edit.

Use these tiers.

## Tier 0 — Static sanity

Run after structural edits:

```bash
python -m compileall central_platform app core local_runtime scripts
```

and project-specific syntax/import validation.

---

## Tier 1 — Targeted regression

Run tests directly connected to the changed files.

Examples:

```bash
python -m pytest tests/test_phase01_auth_identity_remediation.py -v
python -m pytest tests/test_phase06_scoped_rag_authorization.py -v
python -m pytest tests/test_phase09_rag.py -v
python -m pytest tests/test_tutor_mode_realtime.py -v
```

Use the actual repository filenames discovered during execution.

---

## Tier 2 — Subsystem regression

Examples:

```text
Auth change
 -> auth tests
 -> RBAC tests
 -> tenant boundary tests

RAG change
 -> RAG tests
 -> course/version scope tests
 -> tutor grounding tests

Tutor change
 -> tutor tests
 -> adaptive learning tests
 -> persistence tests

Packaging change
 -> startup tests
 -> release validation
 -> clean build
```

---

## Tier 3 — Release smoke suite

Mandatory before every release candidate:

```text
1. Startup
2. Health
3. Auth
4. Course
5. Enrollment
6. RAG
7. Tutor
8. Multi-turn
9. Assessment
10. Learning state
11. Adaptive action
12. Teacher dashboard
13. Restart
14. Security negative tests
```

---

## Tier 4 — Full regression

Before final release:

```bash
python -m pytest -q -m "not gui"
```

The exact command should be taken from the repository's current test configuration if it changes.

---

# 6. Phase 0 — Freeze, Baseline & Inventory

## Objective

Create a trustworthy baseline before changing production code.

### Steps

```text
1. git status
2. record branch and commit
3. inspect VERSION
4. inspect pyproject.toml
5. inspect requirements / lock file
6. inspect README
7. inspect environment configuration
8. inspect packaging
9. inspect CI workflow
10. enumerate tests
11. establish current test baseline
```

### Required evidence

Record:

```text
commit SHA
Python version
OS
dependency installation result
Tier 0 result
Tier 4 result
number of tests passed/failed/skipped
```

### Deliverables

Create or update:

```text
docs/release/RELEASE_BASELINE_2026-10-03.md
docs/release/RELEASE_PROGRESS.md
docs/release/OPEN_RELEASE_BLOCKERS.md
```

### Gate

Phase complete only when the baseline is reproducible.

---

# 7. Phase 1 — Production Configuration Hardening

## Objective

Eliminate unsafe development defaults.

### Inspect

```text
core/config.py
central_platform/ai/*
central_platform/auth/*
central_platform/api/app.py
environment loaders
```

### Fix

Ensure:

```text
production
```

requires explicit secure configuration.

At minimum review:

```text
database URL/path
JWT secret
encryption key
allowed origins
AI provider configuration
model path
model checksum
logging level
debug/reload
docs exposure policy
```

### Must test

```text
missing JWT secret
weak JWT secret
missing encryption key
wildcard production CORS
debug mode in production
reload mode in production
missing DB config
missing model
invalid model checksum
```

### Gate

Production startup must fail fast on invalid security-critical configuration.

---

# 8. Phase 2 — Authentication & Identity Remediation

## Objective

Make identity authoritative and production-safe.

### Primary files

```text
central_platform/api/routes/auth.py
central_platform/auth/
central_platform/db.py
tests/*auth*
```

### Fix

Remove production identity fabrication.

Make all production login identity originate from the database.

Verify:

```text
email normalization
account status
credential validation
role
organization
token claims
refresh token
logout/revocation
```

### Add negative tests

```text
unknown user
wrong password
suspended account
deleted account
inactive account
tampered JWT
expired JWT
wrong organization token
```

### Gate

No mock/demo identity can authenticate in production.

---

# 9. Phase 3 — Authorization, RBAC & Tenant Isolation

## Objective

Prove every protected resource respects:

```text
user
role
organization
course
student ownership
```

### Required matrix

| Actor | Resource | Expected |
|---|---|---|
| Anonymous | Protected API | 401 |
| Student | Own data | 200 |
| Student | Other student | 403 |
| Student | Teacher dashboard | 403 |
| Teacher | Assigned course | 200 |
| Teacher | Other tenant course | 403 |
| Org admin | Own org | 200 |
| Org admin | Other org | 403 |
| Super admin | Global admin resources | Based on policy |
| Deleted user | Protected resources | Rejected |

### Inspect

```text
central_platform/auth/dependencies.py
RBAC engine
resource boundary helpers
route dependencies
DB query filters
analytics services
RAG services
sync services
```

### Gate

Tenant isolation must be enforced at both authorization and query/service layers where required by the architecture.

---

# 10. Phase 4 — AI Gateway & Model Routing Hardening

## Objective

Ensure production AI execution is real, deterministic, observable and failure-safe.

### Inspect

```text
central_platform/ai/adapters.py
central_platform/ai/gateway.py
central_platform/ai/model_router.py
central_platform/ai/policy_engine.py
central_platform/ai/context_builder.py
```

### Fix

Establish one authoritative production model route.

Verify:

```text
provider selection
model selection
preferred provider/model handling
fallback behavior
production mock prohibition
timeout handling
network failures
malformed provider responses
empty model responses
telemetry
cost accounting
```

### Important

A model failure must not become a successful tutoring turn.

Required state semantics:

```text
AI failure
 -> turn unsuccessful
 -> no false mastery update
 -> no false learning event
 -> user gets recoverable error
```

### Gate

Run the following scenarios:

```text
model available
model missing
model corrupt
provider timeout
provider 401
provider 429
provider 500
empty response
malformed response
mock adapter forced
```

Every unsafe scenario must fail safely.

---

# 11. Phase 5 — Model Artifact & Manifest Integrity

## Objective

Make the shipped model reproducible.

### Inspect

```text
model_manifest.json
install_llama.py
setup_model.bat
packaging/*
core model loader
```

### Fix

Ensure:

```text
artifact path
model ID
model name
version
checksum
context length
quantization
```

match the actual artifact.

### Build a model integrity utility if needed

Example behavior:

```text
verify_model_manifest()
```

Output:

```text
MODEL_ID:
MODEL_PATH:
EXPECTED_SHA256:
ACTUAL_SHA256:
SIZE:
FORMAT:
VALID:
```

### Gate

Do not load a model with an invalid checksum in production.

---

# 12. Phase 6 — RAG Integrity & Grounding

## Objective

Prove the RAG system actually grounds answers in the correct knowledge.

### Inspect

```text
central_platform/rag/service.py
central_platform/rag/parsers.py
central_platform/rag/cleaner.py
central_platform/rag/security.py
RAG database methods
RAG API routes
```

### Verify ingestion

```text
upload
parse
clean
chunk
metadata
persist
validate
publish
query
```

### Verify scope

Every query must respect:

```text
organization
course
course version
visibility
class
student where applicable
publication status
```

### Test matrix

```text
direct retrieval
paraphrased retrieval
multi-chunk retrieval
out-of-scope question
wrong course
wrong tenant
unpublished material
archived material
document prompt injection
user prompt injection
empty document
corrupt document
duplicate document
large document
```

### Important

Verify whether the current retrieval implementation truly provides the advertised semantics.

Do not claim “vector + BM25” unless the actual execution path does so.

### Gate

For grounded questions:

```text
correct source
correct scope
correct provenance
```

must all be verifiable.

For unsupported questions:

```text
controlled "not found / insufficient context"
```

must be possible.

---

# 13. Phase 7 — Tutor Orchestrator & Multi-Turn Continuity

## Objective

Verify the core product flow.

### Inspect

```text
central_platform/tutor/orchestrator.py
central_platform/api/routes/tutor.py
context builder
query understanding
response planner
response validator
learning state manager
commit pipeline
RAG service
teacher instructions
```

### Required 16-step flow

The implementation must maintain the intended flow:

```text
1. identity
2. enrollment
3. course/version
4. class/cohort
5. learning state
6. instruction cascade
7. policy
8. tool policy
9. RAG
10. context assembly
11. response planning
12. AI execution
13. response validation
14. evidence staging
15. atomic state commit
16. telemetry/audit
```

### Multi-turn test

Use a real conversation:

```text
Turn 1:
student asks concept question

Turn 2:
student says "I still don't understand that"

Turn 3:
student answers tutor question

Turn 4:
student asks for a harder example

Turn 5:
student requests a summary
```

Verify:

```text
context continuity
concept continuity
correct student state
correct teacher instruction
correct RAG scope
correct response planning
```

Then:

```text
restart application
resume session
continue conversation
```

### Gate

No context loss, identity drift, course drift, or fake continuity.

---

# 14. Phase 8 — Adaptive Learning & Mastery Verification

## Objective

Prove adaptation is behavioral.

### Required scenario

```text
Initial state
 -> mastery = baseline

Incorrect response
 -> evaluation evidence
 -> misconception evidence where applicable
 -> mastery changes

Tutor next turn
 -> different intervention/difficulty

Correct response
 -> mastery improves

Spaced review
 -> schedule updates

Restart
 -> state persists
```

### Inspect

```text
central_platform/learning/*
assessment/*
commit_pipeline
misconception engine
spaced review
session state
```

### Required assertions

The agent must assert actual state deltas, not merely that functions executed.

Example:

```text
before mastery:
0.50

after failed attempt:
< baseline or policy-defined change

after successful remediation:
> previous value
```

Use repository-defined formulas rather than inventing new formulas.

### Gate

The same test must pass across process restart.

---

# 15. Phase 9 — Assessment & Anti-Leakage

## Objective

Ensure assessment is reliable and does not falsely award mastery.

### Verify

```text
question loading
answer submission
evaluation
scoring
pass/fail
feedback
attempt persistence
retry handling
anti-answer-leakage behavior
```

### Test

```text
correct answer
wrong answer
partial answer
empty answer
malformed answer
repeated submission
wrong student
wrong assessment
```

### Gate

Assessment outcomes must produce the correct learning evidence.

---

# 16. Phase 10 — Teacher, Admin & Parent Product Surfaces

## Objective

Verify that portal features correspond to real backend capabilities.

### Student

Verify:

```text
dashboard
courses
progress
mastery
tutor
session continuation
settings
```

### Teacher

Verify:

```text
dashboard
students
learning state
alerts
interventions
instructions
copilot
```

### Admin

Verify:

```text
organization
users
roles
courses
curriculum
knowledge upload
publish workflow
```

### Parent

Verify actual implemented scope.

Do not claim a feature is release-ready merely because a route or HTML page exists.

### Silent-failure checks

Every UI action must have:

```text
loading state
success state
empty state
error state
authorization failure state
```

### Gate

No UI action may appear successful while backend operation failed.

---

# 17. Phase 11 — API Contract & Error Semantics

## Objective

Make API behavior consistent and supportable.

### For every production endpoint verify

```text
auth
authorization
input validation
normal success
empty state
not found
conflict
forbidden
unauthorized
server error
```

### Required error properties

Errors must:

```text
have correct HTTP status
have stable machine-readable shape where contract specifies it
not leak stack traces
not expose secrets
include request/correlation ID where architecture supports it
```

### Legacy APIs

Do not remove legacy routes during the final release unless required.

Where possible:

```text
legacy route
   -> canonical service
```

and document deprecation.

---

# 18. Phase 12 — Database, Migration & Restart Safety

## Objective

Prove real state persistence.

### Verify

```text
fresh DB
existing DB
migration sequence
repeat migration
rollback/down behavior where supported
foreign keys
indexes
unique constraints
WAL behavior
transaction boundaries
```

### Restart test

```text
create user
create course
create enrollment
create session
create learning evidence
close process
reopen
verify everything
```

### Failure injection

Test:

```text
exception during transaction
partial operation
duplicate event
duplicate turn
concurrent access where applicable
```

### Gate

No false-success state after transaction failure.

---

# 19. Phase 13 — Packaging & Clean-Machine Release

## Objective

Prove that the distributable artifact works outside the development environment.

### Build

Use the official project packaging workflow.

Verify:

```text
PyInstaller build
dependency collection
Qt WebEngine
llama_cpp binaries
RAG assets
branding
runtime prompts/contracts
model handling
installer
```

### Clean-machine acceptance

On a clean Windows 10/11 machine:

```text
Install
 -> launch
 -> login
 -> load course
 -> tutor
 -> RAG
 -> multi-turn
 -> restart
 -> uninstall
```

The clean machine must not rely on:

```text
repo checkout
Python installation
developer virtual environment
IDE
developer environment variables
local source tree
```

### Gate

The actual installer/executable passes the real user journey.

---

# 20. Phase 14 — Production Observability & Safe Failure

## Objective

Make failures diagnosable without exposing sensitive information.

### Required telemetry

For AI/tutor operations, where appropriate:

```text
request_id
turn_id
user_id
organization_id
course_id
session_id
provider
model
latency
status
error class
```

### Required operational checks

```text
healthz
readyz
livez
database health
model availability
RAG availability
filesystem writeability where needed
```

### Gate

An operator can diagnose:

```text
startup failure
auth failure
AI failure
RAG failure
database failure
packaging issue
```

without reading sensitive payloads.

---

# 21. Phase 15 — Security Release Audit

## Objective

Run the focused security suite before release.

### Required tests

```text
unauthenticated access
expired token
tampered token
revoked token
wrong role
wrong tenant
wrong student
path traversal
unsafe upload
prompt injection
RAG poisoning
malformed input
oversized input
secret leakage
debug mode
wildcard CORS
mock mode in production
demo tokens in production
```

### Gate

Any P0 security failure blocks release.

---

# 22. Phase 16 — Real Product Acceptance Test

This phase is mandatory and independent of the automated synthetic integration suite.

## Test persona set

Create actual acceptance identities:

```text
Organization A
  Admin A
  Teacher A
  Student A1
  Student A2

Organization B
  Admin B
  Teacher B
  Student B1
```

Use real course data and actual packaged runtime.

## Student A1 acceptance journey

```text
login
open course
start session
ask factual question
ask follow-up
answer tutor question incorrectly
request hint
answer correctly
inspect progress
restart
continue
```

## Teacher A acceptance

```text
login
view Student A1
inspect mastery
inspect misconception/intervention
add teacher instruction
verify student tutor behavior changes
```

## Admin A acceptance

```text
upload content
validate
publish
assign/enroll student
verify student can access it
```

## Cross-tenant acceptance

Attempt:

```text
Student A1 -> Student B1 data
Teacher A -> Organization B course
Admin A -> Organization B data
Student A1 -> Organization B RAG source
```

All unauthorized paths must fail safely.

---

# 23. Phase 17 — Release Candidate Freeze

Once all P0/P1 phases are complete:

## Freeze rules

Do not introduce:

```text
new features
new models
large refactors
database redesign
new authentication provider
new frontend framework
```

Only release-blocking fixes are permitted.

## Create

```text
release/<version>
```

or use the repository's existing release workflow.

Record:

```text
commit SHA
build timestamp
model checksum
installer checksum
test summary
known limitations
```

---

# 24. Phase 18 — Final Release Gate

The release gate is binary.

## MUST PASS

### Code

```text
P0 blockers = 0
P1 blockers = 0
```

### Tests

```text
Tier 0 = PASS
Tier 1 = PASS
Tier 2 = PASS
Tier 3 = PASS
Tier 4 = PASS
```

### Product

```text
student flow = PASS
teacher flow = PASS
admin flow = PASS
security flow = PASS
restart persistence = PASS
```

### Packaging

```text
clean install = PASS
clean launch = PASS
actual model = PASS
actual RAG = PASS
actual tutor = PASS
uninstall = PASS
```

### Production mode

```text
mock AI = unavailable
demo tokens = unavailable
dynamic fake users = unavailable
debug defaults = unavailable
wildcard CORS = unavailable
unsafe password reset = unavailable
```

---

# 25. Git Discipline

## Before a phase

```bash
git status
git branch --show-current
git log -1 --oneline
```

## Before commit

```bash
git diff --check
git diff --stat
git diff
```

Review for:

```text
unexpected files
debug prints
temporary code
commented-out code
secrets
test fixtures
generated DBs
model artifacts
private data
```

## Commit convention

Use:

```text
fix(release): <problem>
test(release): <verification>
docs(release): <evidence>
chore(release): <packaging/config>
```

Keep commits phase-scoped.

Avoid mixing:

```text
auth fix + UI redesign + unrelated cleanup
```

in one commit.

---

# 26. Rollback Rule

Every phase must have a rollback point.

Preferred:

```text
phase branch
   -> implementation
   -> verification
   -> commit
   -> merge after gate
```

If a change causes regression:

```text
STOP
IDENTIFY REGRESSION
ROLL BACK OR REVERT
REPRODUCE
FIX ROOT CAUSE
RE-RUN TESTS
```

Do not stack further fixes on top of a known broken state.

---

# 27. Progress Tracking File

Maintain:

```text
docs/release/RELEASE_PROGRESS.md
```

Use exactly this table structure:

| Phase | Status | Owner/Agent | Started | Completed | Commit | Tests | Evidence | Blockers |
|---|---|---|---|---|---|---|---|---|
| 0 Baseline | NOT_STARTED | local-agent | | | | | | |
| 1 Config | NOT_STARTED | local-agent | | | | | | |
| 2 Auth | NOT_STARTED | local-agent | | | | | | |
| 3 RBAC | NOT_STARTED | local-agent | | | | | | |
| 4 AI Gateway | NOT_STARTED | local-agent | | | | | | |
| 5 Model Integrity | NOT_STARTED | local-agent | | | | | | |
| 6 RAG | NOT_STARTED | local-agent | | | | | | |
| 7 Tutor | NOT_STARTED | local-agent | | | | | | |
| 8 Adaptive Learning | NOT_STARTED | local-agent | | | | | | |
| 9 Assessment | NOT_STARTED | local-agent | | | | | | |
| 10 Portals | NOT_STARTED | local-agent | | | | | | |
| 11 API Contracts | NOT_STARTED | local-agent | | | | | | |
| 12 Database | NOT_STARTED | local-agent | | | | | | |
| 13 Packaging | NOT_STARTED | local-agent | | | | | | |
| 14 Observability | NOT_STARTED | local-agent | | | | | | |
| 15 Security | NOT_STARTED | local-agent | | | | | | |
| 16 Product Acceptance | NOT_STARTED | local-agent | | | | | | |
| 17 RC Freeze | NOT_STARTED | local-agent | | | | | | |
| 18 Final Gate | NOT_STARTED | local-agent | | | | | | |

Allowed status values:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
FAILED
READY_FOR_RETEST
COMPLETE
```

---

# 28. Required Per-Phase Evidence

For every completed phase, append:

```markdown
## Phase X — Evidence

### Scope
...

### Root Cause
...

### Files Changed
- ...

### Files Intentionally Not Changed
- ...

### Tests
```text
command
result
```

### Regression Result
...

### Runtime Verification
...

### Security Verification
...

### Packaging Impact
...

### Known Limitations
...

### Commit
`<sha>`

### Status
COMPLETE
```

---

# 29. Change Impact Matrix

Maintain:

```text
docs/release/CHANGE_IMPACT_MATRIX.md
```

Use:

| Change | Module | Caller Impact | DB Impact | API Impact | UI Impact | Security Impact | Packaging Impact | Tests |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Mandatory for any change touching:

```text
auth
AI
RAG
DB
tutor
learning
API routes
packaging
configuration
```

---

# 30. Defect Register

Maintain:

```text
docs/release/RELEASE_DEFECT_REGISTER.md
```

Use:

| ID | Severity | Symptom | Root Cause | Fix | Files | Test | Status |
|---|---|---|---|---|---|---|---|
| P0-01 | P0 | Production login can reach mock/integration identity path | | | | | OPEN |
| P0-02 | P0 | Model checksum must be validated | | | | | OPEN |
| P0-03 | P0 | Production must not use mock AI | | | | | OPEN |
| P0-04 | P0 | Model identity/config mismatch | | | | | OPEN |
| P0-05 | P0 | Wildcard production CORS | | | | | OPEN |
| P0-06 | P0 | Password reset verification | | | | | OPEN |
| P0-07 | P0 | Packaging asset mismatch | | | | | OPEN |
| P0-08 | P0 | Runtime validator relies on synthetic environment | | | | | OPEN |

The agent must add newly discovered defects rather than hiding them in phase notes.

---

# 31. “Looks Working but Is Actually Broken” Checklist

For each feature, ask all of these:

```text
Does the route exist?
Does the frontend call the route?
Does the route call the correct service?
Does the service use authoritative DB state?
Does authorization execute?
Does tenant scoping execute?
Does the result reach the UI?
Does the UI handle errors?
Does persistence occur?
Does restart restore state?
Does production mode behave the same?
Does packaged mode behave the same?
Does the test prove behavior rather than implementation?
```

A feature is not considered working until the whole chain is verified.

---

# 32. Silent-Failure Audit

Search for patterns such as:

```text
except Exception:
    pass

except Exception:
    return ...

logger.error(...)
return success

Response(status_code=200) for failed operations

empty placeholder HTML

fallback values that hide missing data

hard-coded success flags

mock data on empty DB

default IDs

synthetic user IDs

demo tokens

test fixtures imported by production modules
```

Every occurrence must be classified:

```text
safe and intentional
```

or:

```text
release defect
```

---

# 33. Dead-End & Unreachable Code Audit

The agent must look for:

```text
unreferenced modules
unused routes
legacy duplicate services
obsolete providers
dead UI actions
unused feature flags
imports of deleted modules
packaging references to deleted files
environment variables never consumed
functions that are tested but never called in product paths
functions called by tests only
```

Do not delete immediately.

First record:

```text
dead-end candidate
who calls it
whether compatibility requires it
whether packaging requires it
whether tests depend on it
```

Then decide:

```text
KEEP
DEPRECATE
REMOVE
```

---

# 34. Production-vs-Test Call Graph Audit

Explicitly map these components:

```text
Login
Tutor turn
RAG query
Assessment
Learning state update
Teacher dashboard
Admin upload
Model loading
```

For each, document:

```text
Production caller(s)
Test caller(s)
Mock path
Fallback path
Error path
Persistence path
```

The key question is:

> Can the production path reach code that exists only to make tests pass?

If yes, fix it before release.

---

# 35. Packaging Dependency Audit

For every import reachable from:

```text
app/main.py
```

verify:

```text
included in package
dependency installed
hidden import handled if required
runtime asset copied
DLL/shared library copied
configuration available
path resolution correct after packaging
```

Pay special attention to:

```text
PySide6
QtWebEngine
llama_cpp
SQLite
prompt contracts
RAG data
branding
model files
```

---

# 36. Model Runtime Acceptance

The actual model runtime must be verified separately from the adapter code.

Record:

```text
model file
size
SHA-256
loader
context size
threads
generation parameters
first-token latency
generation latency
memory usage
error behavior
```

Use realistic local hardware.

Do not use claimed numbers from configuration as measured performance.

---

# 37. Performance Guardrails

The release is not a performance optimization project, but basic guardrails are required.

Measure:

```text
startup time
time to ready
model load time
RAG query latency
first token latency
full response latency
memory after startup
memory during tutor turn
```

Record actual values in:

```text
docs/release/PERFORMANCE_BASELINE.md
```

Do not change architecture solely to improve a metric unless it is demonstrably a release blocker.

---

# 38. Date-Based Execution Schedule

## 3 October

```text
Phase 0
Phase 1
Phase 2
begin Phase 3
```

Primary focus:

```text
identity
production config
mock elimination
model integrity
```

---

## 4 October

```text
Finish Phase 3
Phase 4
Phase 5
Phase 6
```

Primary focus:

```text
auth/RBAC
AI
model
RAG
```

---

## 5 October

```text
Phase 7
Phase 8
Phase 9
Phase 10
```

Primary focus:

```text
real tutor
multi-turn
adaptive learning
assessment
teacher/admin/student surfaces
```

---

## 6 October

```text
Phase 11
Phase 12
Phase 13
Phase 14
Phase 15
Phase 16
Phase 17
```

Primary focus:

```text
API
database
packaging
security
real product acceptance
release candidate freeze
```

No feature development after RC freeze.

---

## 7 October

```text
Phase 18
release only
```

Allowed work:

```text
release packaging
checksum generation
tagging
release notes
critical hotfixes only
```

---

# 39. Definition of Done

A phase is DONE only when all are true:

```text
[ ] root cause documented
[ ] code changed minimally
[ ] tests added/updated
[ ] targeted tests pass
[ ] subsystem regression passes
[ ] no unexpected API contract changes
[ ] no security regression
[ ] no tenant isolation regression
[ ] no persistence regression
[ ] packaging impact reviewed
[ ] git diff reviewed
[ ] commit created
[ ] evidence recorded
[ ] progress tracker updated
```

A release is DONE only when:

```text
[ ] all P0 blockers closed
[ ] all P1 blockers closed
[ ] full non-GUI regression passes
[ ] real product acceptance passes
[ ] clean-machine installer passes
[ ] packaged model works
[ ] packaged RAG works
[ ] multi-turn works
[ ] adaptive learning works
[ ] restart persistence works
[ ] security negative suite passes
[ ] production configuration audit passes
[ ] release artifacts checksummed
[ ] release notes published
```

---

# 40. Rules for Handling Newly Discovered Bugs

When a new defect is discovered during any phase:

```text
1. Do not silently patch it and continue.
2. Assign ID.
3. Classify severity:
   P0 = blocks safe production release
   P1 = major production failure
   P2 = important but survivable
   P3 = post-release
4. Add to defect register.
5. Determine affected phases.
6. Fix at the earliest safe phase.
7. Re-run all dependent phase gates.
```

If a new P0/P1 issue appears late:

```text
release date takes priority over feature scope.
```

Do not weaken acceptance criteria to preserve the date.

---

# 41. Rules for Local AI Agent Planning

Before each phase, the local agent must produce a machine-readable internal plan containing:

```text
phase_id
objective
repository_state
current_commit
files_to_inspect
root_cause_hypotheses
confirmed_root_cause
planned_changes
dependency_impact
api_contract_impact
db_impact
security_impact
packaging_impact
tests_to_add
tests_to_run
rollback_point
acceptance_criteria
```

After implementation it must produce:

```text
files_changed
tests_added
tests_run
tests_passed
tests_failed
regressions_checked
manual_checks
packaging_checks
security_checks
remaining_risks
commit_sha
phase_status
```

---

# 42. Agent Stop Conditions

The local agent must stop making further code changes and report when:

```text
- root cause is unclear;
- required file/module does not exist;
- multiple architectures conflict;
- a fix requires a broad rewrite;
- a database migration is destructive;
- an API contract would break unexpectedly;
- tenant isolation cannot be proven;
- a production dependency is missing;
- the actual model artifact cannot be verified;
- the packaged build cannot be produced;
- test failures indicate an unrelated pre-existing problem and ownership is unclear.
```

The correct behavior is:

```text
BLOCKED
```

with evidence, not speculative code.

---

# 43. Final Release Evidence Bundle

Before release, generate:

```text
docs/release/
├── RELEASE_BASELINE_2026-10-03.md
├── RELEASE_PROGRESS.md
├── RELEASE_DEFECT_REGISTER.md
├── CHANGE_IMPACT_MATRIX.md
├── PERFORMANCE_BASELINE.md
├── SECURITY_RELEASE_AUDIT.md
├── PRODUCTION_ACCEPTANCE_REPORT.md
├── PACKAGING_ACCEPTANCE_REPORT.md
├── RELEASE_CHECKLIST.md
└── RELEASE_NOTES.md
```

If the repository already contains equivalent documents, update the existing canonical document instead of creating duplicate competing documents.

---

# 44. Recommended Canonical Release Checklist

Create:

```text
docs/release/RELEASE_CHECKLIST.md
```

with:

```markdown
# Gayatri Release Checklist

## Environment
- [ ] Production environment explicitly configured
- [ ] Secrets verified
- [ ] Debug disabled
- [ ] CORS restricted
- [ ] Database configured
- [ ] Model configured
- [ ] Model checksum verified

## Authentication
- [ ] DB-only production identity
- [ ] JWT validation
- [ ] Refresh token validation
- [ ] Revocation
- [ ] Password reset verification
- [ ] Suspended/inactive account behavior

## Security
- [ ] 401 tests
- [ ] 403 role tests
- [ ] 403 tenant tests
- [ ] 403 student-boundary tests
- [ ] 404 resource tests
- [ ] Prompt injection tests
- [ ] Upload traversal tests
- [ ] Secret leakage review
- [ ] Production mock paths blocked

## RAG
- [ ] Ingestion
- [ ] Cleaning
- [ ] Chunking
- [ ] Metadata
- [ ] Validation
- [ ] Publish
- [ ] Correct retrieval
- [ ] Course/version scope
- [ ] Tenant scope
- [ ] Provenance

## Tutor
- [ ] Identity
- [ ] Enrollment
- [ ] Course/version
- [ ] Context
- [ ] RAG
- [ ] Teacher instruction
- [ ] AI execution
- [ ] Response validation
- [ ] Learning evidence
- [ ] Atomic commit
- [ ] Telemetry

## Adaptive learning
- [ ] Incorrect answer changes state correctly
- [ ] Correct answer changes state correctly
- [ ] Difficulty/action adapts
- [ ] Misconception handling
- [ ] Spaced review
- [ ] State survives restart

## Packaging
- [ ] Clean build
- [ ] Clean install
- [ ] Clean launch
- [ ] Model available
- [ ] RAG available
- [ ] Tutor works
- [ ] Restart works
- [ ] Uninstall works

## Release
- [ ] Full regression green
- [ ] Real acceptance green
- [ ] P0 = 0
- [ ] P1 = 0
- [ ] Release tag created
- [ ] SHA-256 artifacts recorded
- [ ] Release notes complete
```

---

# 45. Most Important Instruction to the Local Agent

Do not optimize for:

```text
"make all tests green"
```

Optimize for:

```text
"make the real product path correct, secure, reproducible, observable and regression-safe."
```

The desired final state is:

```text
SOURCE
  ↓
TESTS
  ↓
INTEGRATION
  ↓
PRODUCTION CONFIG
  ↓
PACKAGED APPLICATION
  ↓
REAL USER ACCEPTANCE
  ↓
RELEASE
```

Every layer must agree with the others.

---

# 46. Release Strategy Summary

The agent must work in this order:

```text
Phase 0  Baseline
Phase 1  Production Config
Phase 2  Authentication
Phase 3  RBAC/Tenant Isolation
Phase 4  AI Gateway
Phase 5  Model Integrity
Phase 6  RAG
Phase 7  Tutor/Multi-turn
Phase 8  Adaptive Learning
Phase 9  Assessment
Phase 10 Product Surfaces
Phase 11 API Contracts
Phase 12 Database
Phase 13 Packaging
Phase 14 Observability
Phase 15 Security
Phase 16 Real Product Acceptance
Phase 17 Release Candidate Freeze
Phase 18 Final Release Gate
```

Do not skip a phase merely because a later test passes.

---

# 47. Release Deadline

**Target release: 7 October 2026**

The repository is in an active hardening window. Therefore:

```text
3 Oct -> diagnose and remediate P0
4 Oct -> secure core runtime
5 Oct -> verify product behavior
6 Oct -> package and acceptance-test
7 Oct -> release
```

No unverified feature should be included merely to increase the apparent feature count.

---

# 48. Final Agent Instruction

Start with **Phase 0**.

Do not modify production code until Phase 0 has:

```text
[ ] recorded current commit
[ ] recorded working tree state
[ ] established test baseline
[ ] enumerated architecture
[ ] enumerated release-critical entrypoints
[ ] identified current blockers
[ ] written the initial progress tracker
```

Then proceed phase-by-phase.

After each phase:

```text
STOP
VERIFY
RECORD
COMMIT
THEN CONTINUE
```

Never:

```text
EDIT EVERYTHING
RUN TESTS ONCE
DECLARE PRODUCTION READY
```

The final decision to release must be based on **verified evidence from the actual release artifact**, not only source code inspection, unit tests, or documentation claims.

---
