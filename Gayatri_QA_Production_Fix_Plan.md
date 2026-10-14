# Gayatri Repository — QA, Bug-Fix, Hardening & Production Readiness Execution Plan

**Repository:** `https://github.com/Gayatri-Education/Gayatri`  
**Branch:** `main`  
**Document purpose:** This file is the master execution specification for a local AI coding agent responsible for auditing, fixing, validating, and hardening the Gayatri repository.

---

## 0. Mission

The local coding agent must take the current Gayatri repository from a broad pre-production engineering build to a defensible production-ready release.

The agent must prioritize **correctness over cosmetic completion**.

The agent must assume:

- A feature that merely returns a response is not necessarily working.
- A passing unit test is not proof of end-to-end correctness.
- A mock response is not proof that a real model executed.
- A manifest existing is not proof that a model is loadable.
- A RAG dictionary response is not proof that retrieval was successful.
- A health check that verifies only files/classes is not proof of service health.
- A “production ready” label in documentation is not evidence of actual readiness.
- A fallback must never be indistinguishable from successful primary execution.
- Fixing one subsystem must not silently break another subsystem.

The final release gate must be based on **real behavior**, not on test-count alone.

---

# 1. Non-Negotiable Agent Rules

These rules apply to every phase.

## 1.1 Plan before changing code

Before modifying any source file, the agent MUST:

1. Read this document.
2. Read the current repository state relevant to the phase.
3. Inspect dependencies between affected modules.
4. Identify all files likely to be affected.
5. Identify existing tests covering the behavior.
6. Identify likely regression risks.
7. Produce a phase-specific implementation plan.
8. Wait for no human approval unless the environment explicitly requires it; the plan is mandatory as an internal execution artifact, not a request for permission.
9. Save the plan to:

```text
docs/qa_agent/plans/PHASE_<NN>_PLAN.md
```

The plan must be written **before** source modifications begin.

---

## 1.2 Do not patch blindly

The agent MUST NOT:

- rewrite large portions of the repository merely to “clean things up”
- remove tests just because they fail
- weaken assertions to make tests pass
- convert real behavior into mocks
- disable security controls to bypass test failures
- change production logic solely to satisfy a shallow test
- delete compatibility code without tracing all callers
- introduce a new framework without a concrete need
- change public API contracts without documenting the change
- alter database schema without migration handling
- silently change learning logic because a test is inconvenient
- mark an item fixed without reproducing or validating the defect

---

## 1.3 Preserve working behavior

Before modifying a subsystem, determine:

```text
Current behavior
↓
Expected behavior
↓
Failure/defect
↓
Minimal safe fix
↓
Regression risk
```

Prefer the smallest correct change that restores the intended invariant.

Refactoring is allowed only when needed to remove a real defect, architectural hazard, duplicated authority, or testability blocker.

---

## 1.4 Run tests after every logical change group

After each meaningful change:

1. Run the smallest relevant test set.
2. Debug failures.
3. Re-run the relevant test set.
4. Only then proceed to the next change within the same phase.

At the end of every phase, the agent MUST run a **repository-wide regression cycle**.

The agent must not advance to the next phase until the phase exit gate passes.

---

# 2. Mandatory Development Loop

Every phase MUST use this exact loop.

```text
PHASE START
   ↓
Read phase requirements
   ↓
Inspect repository and dependencies
   ↓
Write phase plan
   ↓
Capture baseline tests/results
   ↓
Implement one logical change group
   ↓
Run focused tests
   ↓
Debug until focused tests pass
   ↓
Repeat for next change group
   ↓
Run entire repository regression suite
   ↓
Run static checks / compile checks
   ↓
Review changed files and diffs
   ↓
Verify no unrelated behavior regressed
   ↓
Update phase progress tracker
   ↓
Write phase completion report
   ↓
PHASE EXIT GATE
   ↓
NEXT PHASE
```

---

# 3. Required Agent Artifacts

The agent must maintain these files throughout the project.

```text
docs/qa_agent/
├── MASTER_PROGRESS.md
├── BASELINE_REPORT.md
├── plans/
│   ├── PHASE_01_PLAN.md
│   ├── PHASE_02_PLAN.md
│   └── ...
├── reports/
│   ├── PHASE_01_REPORT.md
│   ├── PHASE_02_REPORT.md
│   └── ...
├── regressions/
│   ├── PHASE_01_REGRESSION.md
│   ├── PHASE_02_REGRESSION.md
│   └── ...
├── evidence/
│   ├── commands/
│   ├── logs/
│   └── screenshots/
└── decisions/
    └── DECISION_LOG.md
```

If these directories do not exist, create them in Phase 1.

---

# 4. Master Progress Tracker

The agent must keep this table updated after every task.

| Phase | Status | Planned | Implemented | Focused Tests | Full Regression | Exit Gate | Last Updated |
|---|---|---:|---:|---:|---:|---|---|
| 01 Baseline & Instrumentation | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 02 AI Execution Integrity | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 03 RAG Correctness & Grounding | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 04 Session & Persistence Integrity | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 05 Security Hardening | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 06 Adaptive Learning & Pedagogy | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 07 Portals & Cross-Component Contracts | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 08 Reliability, Recovery & Observability | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 09 Training & Model Build Pipeline | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 10 Packaging, Deployment & Upgrade Safety | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 11 End-to-End QA & Adversarial Validation | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |
| 12 Final Release Gate & Evidence Pack | NOT_STARTED | 0 | 0 | 0 | 0 | PENDING | |

Status values:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
FAILED
PASSED
REOPENED
```

---

# 5. Severity Definitions

## P0 — Release blocker

A defect that can:

- cause incorrect educational behavior
- make real functionality appear to work when it does not
- expose student/teacher/admin data
- permit privilege escalation
- break core startup or inference
- corrupt/loss learner state
- invalidate production readiness claims
- make recovery impossible
- allow major tenant isolation failure

P0 items must be fixed before release.

---

## P1 — High priority

A defect that can:

- materially degrade correctness
- cause repeated failures under realistic conditions
- break important workflows
- cause significant retrieval quality loss
- compromise observability
- make scaling unsafe
- make training/release non-reproducible

P1 items must normally be fixed before production.

---

## P2 — Medium priority

A defect that:

- creates maintainability risk
- causes edge-case failures
- weakens test confidence
- produces avoidable UX/API inconsistencies
- creates technical debt with realistic future impact

---

## P3 — Low priority

Cosmetic issues, documentation polish, or non-blocking improvements.

P3 work must not be allowed to delay P0/P1 remediation.

---

# 6. Baseline Findings To Preserve

The initial audit identified the following high-priority concerns. The agent must verify every item against the current repository before changing it.

## QA-001 — Deterministic AI fallback can masquerade as successful real inference

**Severity:** P0  
**Primary file:** `central_platform/ai/adapters.py`

The AI layer contains `generate_dynamic_pedagogical_content()` with hard-coded/deterministic pedagogical responses for many topics.

`LocalGGUFAdapter.execute()` can fall back to deterministic generated content when the real model is unavailable outside production mode.

### Required outcome

The execution path must explicitly expose:

```text
REAL_MODEL
MOCK
DEGRADED_FALLBACK
FAILED
```

No successful response may be indistinguishable from genuine model execution.

### Acceptance criteria

- Real model execution is explicitly marked.
- Mock execution is explicitly marked.
- Fallback execution is explicitly marked.
- Production mode cannot use mock/deterministic educational content as a success path.
- Tests prove model-unavailable conditions are observable.
- UI/telemetry can determine which execution path produced an answer.

---

## QA-002 — Master AI audit validates response existence, not real inference

**Severity:** P0  
**Primary file:** `tests/test_phase29_final_platform_audit_master.py`

Current logic permits a mock/fallback path to satisfy an “AI gateway works” test.

### Required outcome

Add tests that distinguish:

```text
gateway accepted request
```

from:

```text
real model successfully generated response
```

### Acceptance criteria

At minimum test:

1. model discovery
2. model file validation
3. model load
4. actual inference
5. streaming
6. cancellation
7. malformed response
8. timeout
9. provider failure
10. fallback provenance

---

## QA-003 — Production validator can report readiness without true model health

**Severity:** P0  
**Primary file:** `central_platform/deployment/validator.py`

Model health is currently influenced by local manifest/configuration state.

### Required outcome

Production readiness must distinguish:

```text
CONFIGURED
LOADABLE
EXECUTABLE
HEALTHY
```

### Acceptance criteria

The production gate must fail when:

- manifest exists but model file is missing
- model file exists but checksum is wrong
- model cannot load
- inference fails
- model is configured but provider credentials are invalid
- only mock mode is available

---

## QA-004 — RAG health probe can pass with a structurally valid but empty response

**Severity:** P0  
**Primary file:** `central_platform/deployment/validator.py`

The RAG probe currently treats a dictionary response as sufficient.

### Required outcome

A RAG health check must validate actual retrieval capability.

### Acceptance criteria

The health check must verify:

- retriever initialized
- knowledge asset available
- query succeeds
- at least one expected evidence item can be retrieved
- result provenance exists
- retrieval is marked healthy
- an empty result is not considered healthy

---

## QA-005 — Production/certification terminology is stronger than current evidence

**Severity:** P0  
**Area:** release documentation/tests

The repository has historically used production/certification language while important runtime paths remain insufficiently validated.

### Required outcome

Release status terminology must reflect evidence.

Use:

```text
PRE_PRODUCTION
RELEASE_CANDIDATE
PRODUCTION_READY
RELEASED
```

only when the matching gate has actually passed.

---

## QA-006 — RAG retrieval is primarily lexical

**Severity:** P1  
**Primary file:** `central_platform/rag/service.py`

Current scoring uses lexical overlap, phrase bonuses, metadata matches, and authority weighting.

### Risk

Reduced semantic recall for:

- paraphrases
- conceptually equivalent questions
- mixed-language queries
- spelling variations
- indirect conceptual questions
- prerequisite questions

### Required outcome

Implement a retrieval architecture that can support:

```text
lexical retrieval
+
semantic retrieval
+
metadata filtering
+
reranking
```

without breaking the current approved-source and tenant-isolation rules.

---

## QA-007 — Legacy RAG fallback suppresses file errors

**Severity:** P1  
**Primary file:** `central_platform/rag/service.py`

A broad `except Exception` in the legacy fallback can silently skip malformed files.

### Required outcome

Failures must be:

- logged
- classified
- associated with source filename
- exposed to diagnostics
- excluded from fabricated success status

---

## QA-008 — Path traversal validation uses unsafe string-prefix containment

**Severity:** P1  
**Primary file:** `central_platform/security/auditor.py`

Current `sanitize_path()` uses string-prefix logic.

### Required outcome

Use canonical path comparison based on resolved paths.

### Regression cases

Test:

```text
/data/uploads/file.pdf
/data/uploads/sub/file.pdf
/data/uploads/../secret.txt
/data/uploads_evil/file.pdf
/data/uploads2/file.pdf
C:\uploads_evil\file.txt
symlink escape where supported
```

---

## QA-009 — Rate limiter is process-local

**Severity:** P1  
**Primary file:** `central_platform/security/auditor.py`

The in-memory timestamp dictionary does not provide global limits across multiple workers.

### Required outcome

Design the limiter so the architecture can support:

```text
single-process local mode
multi-worker production mode
shared/distributed rate limiting
```

At minimum document the guarantee of the implementation currently used.

---

## QA-010 — Async session writes can lose recent learner state

**Severity:** P1  
**Primary file:** `core/session.py`

The session writer uses a background queue.

### Required outcome

Determine and guarantee durability semantics for:

- chat messages
- tutor context
- mastery-related state
- application shutdown
- abnormal process termination

Add explicit tests for:

```text
save
→ shutdown
→ reopen
→ data exists
```

and for queued write failure.

---

## QA-011 — Hard-coded `local_user_1` identity

**Severity:** P1  
**Primary files:**

- `app/bridge/facade.py`
- `core/session.py`

### Required outcome

Introduce an identity/context abstraction.

Desktop single-user mode may use a local identity, but it must not be confused with authenticated multi-user identity.

---

## QA-012 — Training pipeline ignores shell command exit codes

**Severity:** P1  
**Primary file:** `training/train_slm.py`

The script uses `os.system()` for build/install/conversion steps.

### Required outcome

Replace critical shell operations with checked subprocess execution.

The pipeline must fail fast when:

- clone fails
- dependency install fails
- CMake configuration fails
- compilation fails
- conversion fails
- quantization fails

---

## QA-013 — Training environment reproducibility is insufficient

**Severity:** P1  
**Areas:**

- training scripts
- notebooks
- dependencies
- model references
- quantization tooling

### Required outcome

Record and/or pin:

- Python
- PyTorch
- Transformers
- PEFT
- TRL
- datasets
- tokenizer revision
- base model revision
- CUDA/toolchain assumptions
- llama.cpp revision
- dataset checksums
- training hyperparameters
- quantization parameters

---

## QA-014 — Pedagogical model validation is too shallow

**Severity:** P1  
**Primary file:** `training/train_slm.py`

Current behavioral verification covers only a very small sample of tutoring invariants.

### Required outcome

Build a real evaluation suite covering:

- factual correctness
- chemistry correctness
- mathematical correctness
- Socratic behavior
- answer leakage
- hints
- misconception handling
- difficulty adjustment
- RAG grounding
- citation behavior
- multilingual behavior
- refusal/safety behavior
- hallucination rate
- consistency

---

## QA-015 — Domain-specific teaching heuristics are mixed into provider abstraction

**Severity:** P2  
**Primary file:** `central_platform/ai/adapters.py`

Provider adapters should primarily execute model requests, not act as a domain-specific chemistry knowledge engine.

### Required outcome

Move domain/pedagogical policy toward:

```text
Tutor policy
Curriculum
Retrieval
Evaluation
Orchestration
```

while leaving provider adapters responsible for model execution.

---

## QA-016 — Broad exception handling can hide defects

**Severity:** P2  
**Area:** repository-wide

Search for:

```python
except Exception:
```

and similar broad handlers.

### Required outcome

Each broad handler must be categorized:

```text
EXPECTED_RECOVERY
TRANSIENT_PROVIDER_FAILURE
CORRUPT_INPUT
USER_INPUT
PROGRAMMER_ERROR
UNEXPECTED_FATAL
```

Unexpected exceptions must remain observable.

---

## QA-017 — CI lacks complete real-model end-to-end verification

**Severity:** P2  
**Primary file:** `.github/workflows/ci.yml`

Current CI is strong for compile/test hygiene, but it does not by itself prove the full real user workflow.

### Required outcome

Design practical CI tiers:

```text
Tier 1: static / compilation
Tier 2: unit
Tier 3: integration
Tier 4: deterministic model smoke
Tier 5: RAG integration
Tier 6: packaging smoke
Tier 7: optional real-model/manual release gate
```

Do not make expensive model tests mandatory on every commit if that makes CI impractical. Use separate release workflows where appropriate.

---

## QA-018 — Packaging and clean-install validation need stronger automation

**Severity:** P2

Validate a clean environment rather than only the development checkout.

### Required outcome

Test:

```text
clean machine
→ install
→ configure
→ launch
→ model discovery
→ chat
→ streaming
→ save session
→ restart
→ reload session
```

---

# 7. Phase Plan

---

# PHASE 01 — Baseline, Inventory, Instrumentation & Safety Rails

**Status:** NOT_STARTED

## Objective

Create a trustworthy baseline before modifying behavior.

## Files/areas to inspect

- repository root
- `pyproject.toml`
- `requirements.txt`
- `requirements.lock`
- `.github/workflows/ci.yml`
- `app/`
- `core/`
- `central_platform/`
- `scripts/`
- `training/`
- `tests/`
- `model_manifest.json`
- packaging scripts

## Tasks

### 01.1 Create QA tracking structure

Create:

```text
docs/qa_agent/
docs/qa_agent/plans/
docs/qa_agent/reports/
docs/qa_agent/regressions/
docs/qa_agent/evidence/
docs/qa_agent/evidence/commands/
docs/qa_agent/evidence/logs/
docs/qa_agent/evidence/screenshots/
docs/qa_agent/decisions/
```

### 01.2 Record repository baseline

Capture:

- commit SHA
- Python version
- OS
- package installation state
- model availability
- model checksum
- database state
- test count
- test result
- compile result
- lint result
- packaging result if available

### 01.3 Run baseline checks

At minimum:

```bash
python --version
python -m compileall app core central_platform tests scripts
pytest -q
ruff check .
```

Do not assume every command exists. If unavailable, record the reason.

### 01.4 Establish test count

Record exact number of tests discovered:

```bash
pytest --collect-only -q
```

Do not use a historical test-count claim as the current truth.

### 01.5 Search for high-risk patterns

Search repository-wide for:

```text
except Exception
pass
TODO
FIXME
os.system(
subprocess.run(
eval(
exec(
pickle
yaml.load
shell=True
startswith(
local_user_1
mock
fallback
legacy
```

Classify findings rather than indiscriminately fixing them.

## Exit gate

Phase 1 passes only when:

- baseline environment documented
- test suite collected
- baseline test result recorded
- lint/compile result recorded
- working tree state documented
- all high-risk patterns have been inventoried
- no source code was modified without a written plan

---

# PHASE 02 — AI Execution Integrity & Provider Routing

**Severity focus:** P0

## Objective

Guarantee that Gayatri never confuses a mock/degraded response with genuine model inference.

## Primary files

- `central_platform/ai/adapters.py`
- `central_platform/ai/gateway.py`
- `central_platform/ai/schema.py`
- `model_manifest.json`
- local provider files
- provider registry/router files
- relevant tests

## Tasks

### 02.1 Map the complete AI execution path

Document:

```text
UI
→ bridge
→ orchestrator
→ agent/runtime
→ AI gateway
→ provider router
→ provider adapter
→ model
→ response normalization
→ UI
```

### 02.2 Define execution provenance

Create a formal enum/model such as:

```text
REAL_MODEL
MOCK
DEGRADED_FALLBACK
FAILED
```

or an equivalent stronger design.

### 02.3 Fix local-model fallback semantics

Ensure model failure cannot become an unexplained success.

### 02.4 Validate model manifest

Validate:

- model ID
- path
- existence
- file size
- checksum
- format
- architecture
- context window
- compatibility
- loadability

### 02.5 Validate provider error handling

Test:

- API key missing
- 401
- 403
- 429
- 500
- timeout
- connection failure
- malformed JSON
- missing choices
- empty content
- unexpected schema

### 02.6 Validate streaming

Test:

```text
first token
multiple chunks
final chunk
done event
error during stream
cancel during stream
session switch during stream
```

### 02.7 Validate cancellation

Ensure cancellation:

- actually stops generation
- releases resources
- clears active state
- cannot leave the UI permanently “busy”

### 02.8 Remove or isolate misleading canned educational content

Deterministic pedagogical responses may remain only where justified as explicit mock/test adapters.

They must not be part of a real production provider success path.

## Required tests

Add/update tests for all above cases.

## Phase exit gate

Must prove:

```text
real model = real inference
mock = mock
fallback = fallback
failure = failure
```

and all existing repository tests pass.

---

# PHASE 03 — RAG Correctness, Grounding & Knowledge Integrity

**Severity focus:** P0/P1

## Objective

Make RAG trustworthy, observable, source-grounded, tenant-safe, and semantically useful.

## Primary files

- `central_platform/rag/service.py`
- RAG parsers/chunkers
- RAG security utilities
- database RAG methods
- retrieval-related tests
- curriculum/knowledge data

## Tasks

### 03.1 Trace ingestion pipeline

Document:

```text
source
→ upload
→ validation
→ parser
→ sections
→ chunks
→ metadata
→ persistence
→ approval
→ publish
→ retrieval
→ evidence
```

### 03.2 Test ingestion failures

Include:

- empty document
- corrupt PDF
- malformed JSON
- invalid encoding
- oversized file
- missing metadata
- duplicate source
- unchanged source
- changed source
- parser returns zero sections

### 03.3 Fix silent fallback errors

Do not silently swallow malformed source failures.

### 03.4 Validate metadata filters

Test:

- organization
- course
- course version
- class
- student
- visibility
- publication state
- authority
- teacher content

### 03.5 Strengthen semantic retrieval

Implement the least disruptive semantic-retrieval architecture compatible with current dependencies and deployment constraints.

Potential architecture:

```text
BM25
+
dense embeddings
+
metadata constraints
+
reranking
```

Do not add a vector database only for the sake of saying one exists.

### 03.6 Validate evidence integrity

Every retrieved result should have:

- source ID
- chunk ID
- provenance
- chapter/topic
- page where applicable
- retrieval score
- visibility scope

### 03.7 Validate grounding

Create adversarial tests:

```text
question answerable from RAG
question absent from RAG
question conflicting with RAG
prompt injection inside RAG
irrelevant retrieved context
multiple conflicting sources
private source from another organization
```

## Phase exit gate

Must prove:

- correct sources retrieved
- unauthorized sources never retrieved
- empty retrieval is not reported as healthy retrieval
- source failures are observable
- grounded answers contain valid evidence references where expected

---

# PHASE 04 — Session, Database & Persistence Integrity

**Severity focus:** P1

## Objective

Guarantee learner history, tutor state, and session data are durable and isolated.

## Primary files

- `core/session.py`
- database utilities
- migration scripts
- session schema
- platform DB
- controllers
- relevant tests

## Tasks

### 04.1 Map persistence ownership

Clearly identify the authoritative source for:

- sessions
- messages
- tutor context
- learning events
- mastery
- student profile
- organization relationship

### 04.2 Validate async writer lifecycle

Test:

```text
queue write
flush
shutdown
reopen
```

and:

```text
queue write
kill process
reopen
```

Document expected durability.

### 04.3 Fix identity model

Remove hidden dependence on `local_user_1`.

Use explicit local vs authenticated identity.

### 04.4 Validate session isolation

Test two users and two sessions concurrently.

### 04.5 Validate migrations

Test:

```text
old database versions
→ current migrations
→ existing data intact
```

### 04.6 Validate deletion semantics

Test:

- clear session
- delete session
- delete student where allowed
- cascade behavior
- backup restore

## Phase exit gate

No critical learner state loss or cross-user session leakage under tested scenarios.

---

# PHASE 05 — Security Hardening

**Severity focus:** P0/P1

## Objective

Turn security controls from “detection helpers” into reliable enforcement.

## Primary files

- `central_platform/security/auditor.py`
- auth/token modules
- API dependencies
- upload handling
- RAG security
- CORS/CSRF logic
- database access code

## Tasks

### 05.1 Path traversal

Replace unsafe prefix validation with canonical path containment.

### 05.2 IDOR

Test every endpoint that accepts:

```text
student_id
organization_id
course_id
session_id
source_id
payment/fee record ID
teacher/admin identifiers
```

against unauthorized users.

### 05.3 Tenant isolation

Test:

```text
Org A user → Org B data
Org A teacher → Org B student
Org A admin → Org B course
```

### 05.4 JWT/authentication

Test:

- invalid signature
- expired token
- malformed token
- revoked token
- wrong role
- missing organization
- replay
- algorithm confusion where relevant
- token substitution

### 05.5 Prompt injection

Test:

- system prompt extraction
- role injection
- multi-turn injection
- indirect RAG injection
- instruction injection from uploaded files

### 05.6 Upload security

Validate:

- extension
- MIME
- content signature
- size
- filename
- null bytes
- path traversal
- archive bomb risks where supported
- executable content

### 05.7 SQL injection

Review every dynamically assembled query.

Prefer parameterized database access.

### 05.8 XSS

Audit:

- markdown rendering
- teacher notes
- student answers
- document metadata
- portal templates
- error messages

### 05.9 Rate limiting

Document and test current guarantee.

If distributed deployment is supported, design a shared limiter.

### 05.10 Secrets

Ensure:

- no hard-coded production secret
- environment references only
- secret values never enter logs
- exception messages do not expose keys

## Phase exit gate

All critical security regression tests pass, including adversarial access attempts.

---

# PHASE 06 — Adaptive Learning & Pedagogical Correctness

**Severity focus:** P0/P1 for core tutor behavior

## Objective

Validate that Gayatri actually adapts to learner behavior.

## Areas

- tutor engine
- evaluator
- mastery engine
- misconception engine
- adaptive engine
- spaced review
- concept resolution
- prompt system
- learning events
- recommendation engine

## Required behavior chain

The canonical test must prove:

```text
student receives concept
↓
student answers incorrectly
↓
answer is evaluated correctly
↓
misconception is detected
↓
mastery changes
↓
difficulty changes appropriately
↓
tutor response changes
↓
student retries
↓
correct response updates mastery
↓
next recommendation reflects new state
```

## Test categories

### 06.1 Numerical correctness

Chemistry/math numerical answers.

### 06.2 Concept correctness

Examples:

- thermodynamics
- equilibrium
- acids/bases
- inorganic chemistry
- prerequisites

### 06.3 Misconception detection

Use known misconception fixtures.

### 06.4 Difficulty adaptation

Test:

```text
weak learner
average learner
strong learner
```

and ensure recommendations differ.

### 06.5 Socratic policy

Verify:

- does not always reveal answer
- asks appropriate guiding questions
- increases/decreases hints appropriately
- does not get stuck repeating one response

### 06.6 Conversation state

Ensure adaptive state survives:

```text
message
restart
reload session
continue
```

### 06.7 Prevent hard-coded adaptation

Detect logic that produces the same response/state regardless of learner evidence.

## Phase exit gate

At least one complete multi-turn adaptive scenario must pass end-to-end using actual application components.

---

# PHASE 07 — Portals & Cross-Component Contracts

**Severity:** P1/P2

## Objective

Validate student, teacher, parent, admin, fee/payment and shared UI contracts.

## Areas

- student portal
- teacher portal
- parent portal
- admin portal
- fee admin
- payment abstraction
- i18n
- explainability
- analytics

## Required test flows

### Student

```text
login
→ course
→ tutor
→ answer
→ progress
→ session history
```

### Teacher

```text
login
→ cohort
→ student
→ learning state
→ intervention/instruction
→ save instruction
→ student receives instruction
```

### Parent

Verify strict privacy boundaries.

### Admin

Verify:

- RBAC
- organizations
- users
- courses
- knowledge assets
- health
- kill switch

### Fees/payments

Use mock gateway for unit tests, but verify provider abstraction and failure rollback.

## Phase exit gate

Cross-portal data contracts remain consistent and no role can access unauthorized information.

---

# PHASE 08 — Reliability, Recovery & Observability

**Severity:** P1

## Objective

Ensure system failures are detectable, recoverable and diagnosable.

## Areas

- `central_platform/recovery/manager.py`
- provider failures
- RAG failures
- DB failures
- malformed model output
- logging
- metrics
- health endpoints
- kill switch

## Tasks

### 08.1 Failure taxonomy

All recovery paths should classify failures consistently.

### 08.2 Provider timeout

Verify:

```text
primary provider fails
→ fallback selected
→ fallback provenance recorded
→ user sees usable state
```

### 08.3 RAG outage

Verify:

```text
RAG unavailable
→ correct degraded behavior
→ no fabricated citation
→ no silent false-grounding
```

### 08.4 Database outage

Verify whether:

- read cache
- snapshot
- offline mode

is safe and clearly marked.

### 08.5 Malformed model output

Test:

- JSON fence
- trailing text
- missing fields
- wrong types
- empty output
- invalid Unicode

### 08.6 Logging

Every important error should provide:

- category
- severity
- timestamp
- correlation/request ID where appropriate
- sanitized context

Never log secrets.

### 08.7 Health endpoints

Distinguish:

```text
liveness
readiness
dependency health
deep health
```

Do not let deep health return green merely because an object can be instantiated.

## Phase exit gate

Inject representative failures and verify both recovery and observability.

---

# PHASE 09 — Training & Model Build Pipeline

**Severity:** P1

## Objective

Create a deterministic, reproducible model-training and quantization pipeline.

## Primary areas

- `training/train_slm.py`
- `training/train_colab.py`
- training notebooks
- datasets
- prompts
- model manifest
- quantization tooling

## Tasks

### 09.1 Replace unchecked shell commands

Use checked subprocess execution.

### 09.2 Validate dataset

Check:

- JSONL validity
- required fields
- empty records
- duplicate examples
- train/validation contamination
- unsafe data
- source provenance
- checksum

### 09.3 Training determinism

Record:

- random seed
- base model revision
- tokenizer revision
- hyperparameters
- LoRA config
- sequence length
- precision
- hardware

### 09.4 Validation set integrity

Ensure validation examples are not copied from training.

### 09.5 Model output evaluation

Create evaluation categories:

```text
factual correctness
pedagogical alignment
grounding
safety
answer leakage
math
chemistry
Socratic style
```

### 09.6 Quantization validation

Verify the final GGUF:

- exists
- valid header
- expected architecture
- expected tensor metadata
- loadable
- performs inference
- quality does not collapse beyond defined tolerance

### 09.7 Manifest correctness

Update the manifest only after successful artifact verification.

### Phase exit gate

A clean environment can reproduce a valid model artifact or produce a clearly documented, deterministic failure.

---

# PHASE 10 — Packaging, Deployment & Upgrade Safety

**Severity:** P1/P2

## Objective

Prove that the product works outside the developer machine.

## Areas

- `setup.bat`
- `run.bat`
- `run_gayatri.bat`
- `launch.bat`
- packaging/
- Windows desktop application
- server entry points
- model setup
- database migration

## Tasks

### 10.1 Clean-install test

No:

- pre-existing database
- developer cache
- local model cache
- hidden environment variables

unless explicitly documented prerequisites.

### 10.2 Launch test

Verify:

- startup
- dependency error
- model error
- window startup
- single-instance behavior
- shutdown

### 10.3 User workflow

Verify:

```text
new chat
→ ask question
→ streaming
→ cancel
→ save
→ close
→ reopen
→ continue
```

### 10.4 Upgrade migration

Test at least one previous schema.

### 10.5 Deployment configuration

Verify:

- production environment
- secrets
- HTTPS
- database
- model
- logging
- health
- backup

## Phase exit gate

A clean installation can perform the critical workflow without developer-only assumptions.

---

# PHASE 11 — Full End-to-End QA & Adversarial Validation

**Severity:** P0

## Objective

Perform black-box and white-box validation of the complete product.

## Required scenarios

### 11.1 Normal learner journey

```text
start
→ select course
→ ask concept question
→ RAG retrieval
→ model answer
→ student responds
→ evaluation
→ adaptation
→ session persistence
→ analytics
```

### 11.2 Model failure

```text
model unavailable
→ system detects failure
→ correct degraded path
→ no false “real model” status
```

### 11.3 RAG failure

```text
retriever unavailable
→ no fabricated citation
→ correct fallback
```

### 11.4 Security attack

Test:

- prompt injection
- IDOR
- tenant breakout
- path traversal
- malicious file
- JWT abuse
- XSS
- SQL injection
- rate limit bypass

### 11.5 Data corruption

Simulate malformed:

- session
- learning event
- model response
- RAG source
- database record

### 11.6 Concurrency

Run multiple students/sessions concurrently and check:

- session isolation
- model state isolation
- DB correctness
- rate limits
- latency
- memory
- thread safety

### 11.7 Long session

Verify behavior across a long conversation:

- context growth
- truncation
- persistence
- summarization if present
- latency growth
- memory growth

### Phase exit gate

All release-blocking scenarios pass with evidence.

---

# PHASE 12 — Final Release Gate & Evidence Pack

**Severity:** P0

## Objective

Produce a final evidence-backed release decision.

## Required final checks

```text
compileall
ruff
pytest
architecture tests
security tests
integration tests
real-model smoke
RAG smoke
adaptive-learning smoke
packaging smoke
migration test
backup/restore test
health checks
failure-injection tests
```

## Final production gate criteria

### REQUIRED

- 0 P0 open defects
- 0 known security-critical failures
- 0 known learner-data integrity failures
- 0 cross-tenant access failures
- real model execution verified
- real RAG retrieval verified
- adaptive learning verified end-to-end
- production health checks verified
- clean-install path verified
- upgrade/migration verified
- backup/restore verified
- release artifact verified

### ACCEPTABLE

- documented P2/P3 defects with no release impact
- known performance limitations with measured thresholds
- optional provider-specific issues when provider is not part of release scope

## Final report

Create:

```text
docs/qa_agent/reports/FINAL_RELEASE_READINESS_REPORT.md
```

Include:

1. repository commit SHA
2. test count
3. passed/failed/skipped
4. known defects
5. fixed defects
6. security results
7. AI execution results
8. RAG results
9. adaptive-learning results
10. performance results
11. packaging results
12. deployment results
13. residual risk
14. explicit release decision

Release decision must be one of:

```text
BLOCKED
RELEASE CANDIDATE
PRODUCTION READY
```

---

# 8. Full-Repository Regression Policy

After every phase, the agent must run the repository-wide test suite.

## Minimum

```bash
pytest -q
```

plus:

```bash
python -m compileall app core central_platform tests scripts
ruff check .
```

where supported.

## If full tests cannot run

The agent must:

1. explain exactly why
2. run the largest possible substitute
3. mark the phase `BLOCKED` unless the missing test layer is proven irrelevant
4. never claim full regression passed

---

# 9. Regression Debugging Procedure

When any test fails:

```text
1. Reproduce
2. Identify exact failure
3. Determine whether failure is:
   - pre-existing
   - caused by current change
   - flaky
   - environmental
   - genuinely missing functionality
4. Trace dependency chain
5. Fix root cause
6. Add/adjust regression test
7. Run focused test
8. Run affected subsystem suite
9. Run full repository suite
10. Update report
```

Do not suppress the failure merely to continue.

---

# 10. Anti-False-Green Rules

The agent must treat the following as **insufficient proof**:

## Not sufficient

```text
class imports successfully
```

## Not sufficient

```text
object can be instantiated
```

## Not sufficient

```text
manifest exists
```

## Not sufficient

```text
method returns dict
```

## Not sufficient

```text
response.content is non-empty
```

## Not sufficient

```text
mock test passes
```

## Not sufficient

```text
health endpoint returns HTTP 200
```

## Not sufficient

```text
pytest count is high
```

## Strong evidence

```text
real workflow
+
real dependency
+
real failure injection
+
expected observable behavior
+
regression test
```

---

# 11. AI-Specific QA Matrix

| Test | Mock | Local Real Model | API Provider | Required |
|---|---:|---:|---:|---|
| basic response | ✅ | ✅ | ✅ | YES |
| provenance | ✅ | ✅ | ✅ | YES |
| streaming | ✅ | ✅ | ✅ | YES |
| cancellation | ✅ | ✅ | ✅ | YES |
| timeout | ✅ | ✅ | ✅ | YES |
| malformed response | ✅ | ✅ | ✅ | YES |
| model missing | ✅ | ✅ | ✅ | YES |
| retry/fallback | ✅ | ✅ | ✅ | YES |
| RAG grounding | ✅ | ✅ | ✅ | YES |
| adaptive behavior | ❌ | ✅ | ✅ | YES |
| pedagogical evaluation | ❌ | ✅ | ✅ | YES |
| hallucination evaluation | ❌ | ✅ | ✅ | YES |

The mock adapter is for deterministic contract testing only. It must never be used as evidence that the real model is production-ready.

---

# 12. RAG-Specific QA Matrix

| Scenario | Expected |
|---|---|
| published correct source | retrieved |
| unpublished source | not retrieved |
| wrong organization | denied |
| wrong class | denied |
| wrong student scope | denied |
| empty course | explicit empty result |
| malformed source | explicit failure |
| injection in source | sanitized/rejected |
| exact question | retrieved |
| paraphrased question | semantically retrieved |
| irrelevant question | low/empty confidence |
| citation missing | test failure where citation required |

---

# 13. Adaptive Learning QA Matrix

| Scenario | Expected |
|---|---|
| first correct answer | mastery increases |
| first incorrect answer | mastery does not falsely increase |
| repeated misconception | misconception persists/strengthens |
| misconception resolved | confidence improves |
| weak mastery | easier intervention |
| high mastery | increased challenge |
| hint requested | hint, not uncontrolled final answer |
| session restart | state preserved |
| new session | old state not leaked |
| teacher intervention | appropriate student-visible update |
| RAG evidence changes | tutor response reflects evidence |

---

# 14. Security Regression Matrix

The agent must maintain a permanent security regression suite.

```text
AUTH-001 invalid token
AUTH-002 expired token
AUTH-003 revoked token
AUTH-004 wrong role
AUTH-005 missing org
IDOR-001 student A reads student B
IDOR-002 teacher A reads org B
TENANT-001 org A accesses org B course
TENANT-002 org A accesses org B RAG
RAGSEC-001 injection in retrieved content
RAGSEC-002 system prompt extraction
UPLOAD-001 path traversal
UPLOAD-002 dangerous extension
UPLOAD-003 oversized file
UPLOAD-004 MIME mismatch
XSS-001 script payload
SQLI-001 union/select injection
RATE-001 burst traffic
RATE-002 multi-worker bypass test
SECRET-001 API key log leak
SECRET-002 JWT/token log leak
```

---

# 15. Performance QA

Do not optimize without measuring.

Collect:

- model load time
- first token latency
- total response latency
- RAG retrieval latency
- DB query latency
- session save latency
- memory usage
- CPU usage
- concurrent user behavior

Test:

```text
1 user
5 concurrent
10 concurrent
25 concurrent
50 concurrent
```

only where the environment can support meaningful results.

Record:

```text
p50
p95
p99
error rate
timeout rate
memory growth
```

---

# 16. Database QA

For every schema change:

1. write migration
2. test forward migration
3. test data preservation
4. test foreign keys
5. test rollback strategy where supported
6. test backup
7. test restore
8. run regression

Never modify production schema directly from application startup without understanding migration ownership.

---

# 17. API Contract QA

Every externally used API should have tests covering:

```text
valid request
invalid request
unauthenticated request
unauthorized request
missing resource
invalid state
dependency failure
internal failure
```

Responses should have stable machine-readable structure.

Avoid leaking raw exception strings to clients.

---

# 18. UI / Desktop QA

At minimum test:

## Startup

- first launch
- missing dependency
- missing model
- invalid config
- second-instance startup
- clean shutdown

## Tutor

- send message
- streaming
- stop
- new chat
- history
- mode switch
- long message
- empty message
- malformed server/model output

## Session

- save
- restart
- reload
- clear
- multiple sessions

## Portal

- login
- role routing
- permissions
- dashboard loading
- empty data states
- error states

---

# 19. Definition of Done for Any Bug

A defect is **DONE** only when all are true:

- root cause identified
- fix implemented
- focused regression test exists
- test passes
- affected tests pass
- full repository regression passes
- static checks pass
- diff reviewed
- no unintended API/schema change
- relevant documentation updated
- progress tracker updated
- phase report updated

A code change without a regression test is not automatically accepted for P0/P1 defects.

---

# 20. Definition of Done for Any Phase

A phase is **PASSED** only when:

```text
Phase plan exists
AND
all planned implementation tasks completed
AND
focused tests pass
AND
full repository regression passes
AND
compile checks pass
AND
lint/static checks pass
AND
no P0/P1 defect introduced
AND
phase report exists
AND
progress tracker updated
AND
exit gate satisfied
```

---

# 21. Rollback Policy

Before each phase:

- record current commit SHA
- record changed files
- ensure git diff is reviewable

If a phase introduces an unresolvable regression:

1. stop
2. document the failure
3. revert only the unsafe change group where possible
4. restore passing baseline
5. update the phase report
6. re-plan the phase

Never continue layering changes on top of a broken baseline.

---

# 22. Decision Log

Every significant architectural choice must be recorded in:

```text
docs/qa_agent/decisions/DECISION_LOG.md
```

Format:

```markdown
## DEC-<ID> — <Title>

### Date

YYYY-MM-DD

### Context

What problem was being solved?

### Decision

What was selected?

### Alternatives

What else was considered?

### Consequences

What becomes easier/harder?

### Tests

Which tests prove the decision?
```

---

# 23. Phase Report Template

Every phase completion report must contain:

```markdown
# Phase <NN> Report

## Status

PASSED / FAILED / BLOCKED / REOPENED

## Commit

<sha>

## Scope

<what was changed>

## Findings

<defects discovered>

## Fixes

<what was fixed>

## Files Changed

- ...

## Focused Tests

- ...

## Full Regression

- pytest:
- compileall:
- ruff:

## Security Impact

<none / details>

## Data Migration Impact

<none / details>

## Remaining Defects

- ...

## Exit Gate

PASS / FAIL

## Evidence

<paths to logs/results>
```

---

# 24. Mandatory Final Evidence

The agent must finish with evidence for:

### Code quality

```text
compileall
ruff
test suite
```

### AI

```text
real model load
real inference
streaming
cancellation
failure/fallback
```

### RAG

```text
ingestion
retrieval
grounding
citation
tenant isolation
failure handling
```

### Learning

```text
evaluation
misconception
mastery update
difficulty adaptation
state persistence
```

### Security

```text
auth
RBAC
IDOR
tenant isolation
uploads
prompt injection
RAG injection
XSS
SQL injection
rate limiting
secrets
```

### Operations

```text
health
readiness
recovery
logging
backup/restore
```

### Release

```text
clean installation
startup
upgrade
database migration
model setup
student workflow
```

---

# 25. Recommended Execution Order

The agent must not skip the sequence.

```text
PHASE 01
Baseline
   ↓
PHASE 02
AI execution truth
   ↓
PHASE 03
RAG truth
   ↓
PHASE 04
Persistence truth
   ↓
PHASE 05
Security hardening
   ↓
PHASE 06
Adaptive learning correctness
   ↓
PHASE 07
Portals/contracts
   ↓
PHASE 08
Reliability/observability
   ↓
PHASE 09
Training pipeline
   ↓
PHASE 10
Packaging/deployment
   ↓
PHASE 11
End-to-end/adversarial QA
   ↓
PHASE 12
Final release gate
```

The sequence may only be changed when a dependency makes the original order impossible. Any such change must be documented in the decision log.

---

# 26. Agent Startup Instruction

Before doing any work, the local agent must execute this conceptual procedure:

```text
READ MASTER PLAN
↓
INSPECT CURRENT REPOSITORY
↓
CHECK CURRENT GIT STATUS
↓
CHECK CURRENT COMMIT
↓
READ PHASE REQUIREMENTS
↓
WRITE PHASE PLAN
↓
RUN BASELINE TESTS FOR THAT PHASE
↓
ONLY THEN MODIFY CODE
```

---

# 27. Important Engineering Principle

The primary objective is **not** to make the repository report “1252/1252 tests passing.”

The objective is to make the following statement defensible:

> “A real student can use Gayatri, with a real model and approved knowledge, and receive correct, grounded, adaptive, secure and persistent learning behavior; when dependencies fail, the system fails safely and observably rather than pretending success.”

All phase decisions must support this outcome.

---

# 28. Initial Phase Checklist

Immediately after opening this document, the agent should create `docs/qa_agent/plans/PHASE_01_PLAN.md` and then complete:

- [ ] Inspect git status
- [ ] Record commit SHA
- [ ] Record Python version
- [ ] Record OS/runtime
- [ ] Inspect dependency installation
- [ ] Collect complete test suite
- [ ] Run baseline pytest
- [ ] Run compileall
- [ ] Run ruff
- [ ] Verify model manifest
- [ ] Verify model file availability
- [ ] Verify database setup
- [ ] Inventory broad exception handlers
- [ ] Inventory mock/fallback logic
- [ ] Inventory unsafe path checks
- [ ] Inventory hard-coded identities
- [ ] Inventory shell command execution
- [ ] Inventory existing production/readiness claims
- [ ] Write baseline report
- [ ] Update `MASTER_PROGRESS.md`
- [ ] Complete Phase 01 report
- [ ] Pass Phase 01 exit gate
- [ ] Only then begin Phase 02

---

# 29. Final Rule

**Never advance because a phase “looks finished.”**

Advance only when:

```text
PLAN → DEVELOP → FOCUSED DEBUG → FULL REPO DEBUG → VERIFY → DOCUMENT → EXIT GATE → NEXT PHASE
```

That sequence is mandatory for every phase.
