# GAYATRI DEMO v4.0.0 — RELEASE CONTRACT & SINGLE SOURCE OF TRUTH

**Contract home / authoritative source-of-truth repository:** `Gayatri-Education/Gayatri`

**Release implementation repository:** `Gayatri-Education/Gayatri-Demo`

**Important repository boundary:** This contract is intentionally stored in the main `Gayatri` repository. The public demo implementation, demo-specific assets, Windows packages, release artifacts, and GitHub release MUST be produced from `Gayatri-Demo`. The agent MUST read and obey this contract from the `Gayatri` repository before and during work on `Gayatri-Demo`.

**Target release:** `v4.0.0` (major demo reset/repositioning from Chemistry-only v3.x)

**Document status:** Authoritative execution contract for the AI development/release agent

**Audience:** Autonomous/local AI software-development agent, QA agent, release agent, engineering maintainers

**Last updated:** 2026-10-08

---

## 0.0 BOOTSTRAP / HOW THE AGENT USES THE TWO REPOSITORIES

Before doing any implementation work, the agent MUST establish both repositories in its workspace:

```text
/reference/Gayatri        ← engineering/source reference + authoritative contract
/workspace/Gayatri-Demo   ← active implementation + packaging + release
```

If the repositories are already present, inspect their actual locations and do not assume these paths literally.

The agent MUST:

1. locate and read `DEMO_RELEASE_CONTRACT.md` from the current `Gayatri-Education/Gayatri` checkout;
2. record the exact `Gayatri` commit SHA and contract file SHA/hash in the Phase 0 baseline;
3. inspect `Gayatri-Demo` independently;
4. perform all demo implementation changes in `Gayatri-Demo`;
5. use `Gayatri` as a read/reference source for platform behaviour and reusable components;
6. build and test the final release exclusively from a clean `Gayatri-Demo` checkout plus explicitly declared vendored/generated dependencies;
7. never depend on an uncommitted local copy of `Gayatri` at runtime.

If the contract cannot be found in the checked-out `Gayatri` repository, the agent MUST STOP before implementation and report the repository/contract mismatch.

## 0. EXECUTIVE DIRECTIVE

This document is the binding product, engineering, QA, packaging, and release contract for the next public Gayatri demonstration release. It is stored in the main `Gayatri` repository so that it remains the authoritative product contract independently of the demo repository's implementation state.

The agent MUST treat this document as higher priority than legacy README files, legacy release notes, stale Chemistry-only demo assumptions, old packaging instructions, or inferred product direction.

### Repository responsibilities

**`Gayatri-Education/Gayatri` is the reference/source repository.**
- It contains the platform engineering that the demo is intended to showcase.
- It is the primary reference for architecture, reusable platform components, APIs, data models, tutor orchestration, RAG, learning, security, and supported capabilities.
- The agent MUST inspect the current implementation in this repository before designing or copying any demo capability.
- This contract MAY reference or depend on capabilities implemented there, but this contract does NOT authorize unrelated production changes to `Gayatri`.

**`Gayatri-Education/Gayatri-Demo` is the release repository.**
- All demo-specific implementation changes belong here unless explicitly instructed otherwise.
- All demo assets, demo data, packaging configuration, installer configuration, release scripts, release documentation, checksums, installers, portable packages, and GitHub Releases for this project belong here.
- The v4 public release MUST be built and tested from a clean checkout of `Gayatri-Demo`.
- The demo MUST be independently reproducible from its own repository state and MUST NOT depend on a developer's untracked local copy of `Gayatri`.

**Operational rule:** Read from `Gayatri` as the engineering reference; build, test, package, and release from `Gayatri-Demo`.

The objective is NOT to make a slightly improved Chemistry tutor.

The objective is to release a polished, stable, institution-facing demonstration of **Gayatri as a complete adaptive learning platform** whose tutoring engine is **course-independent** and can operate on different course-specific knowledge/RAG contexts.

The final release MUST convincingly demonstrate all of the following:

1. Gayatri is an adaptive learning platform, not merely a chatbot.
2. The core tutoring experience is reusable across different courses.
3. Course-specific RAG/knowledge can change the tutor's grounding without changing the tutor application itself.
4. An institution can conceptually bring its own curriculum/material into the platform.
5. The learner experience is adaptive: explain → check → evaluate → remediate/adjust → continue.
6. Teacher/institution views exist as meaningful previews of the wider platform.
7. The demo is interactive and usable as both a guided showcase and an exploratory sandbox.
8. Two high-quality sample courses demonstrate course independence.
9. Chemistry may remain as an optional third sample/legacy showcase, but MUST NOT dominate the product identity.
10. The Windows release is professionally packaged, integrity-verifiable, digitally signed when credentials are available, and engineered to minimize false-positive/security-warning problems.
11. Old Chemistry-only assets, copy, filenames, screenshots, release notes, documentation, and installer branding MUST be removed, rewritten, archived deliberately, or replaced.
12. No release artifact may claim a capability that is not actually implemented and verified.

**Release principle:** Never ship a claim because it sounds good. Ship only what is implemented, tested, observable, and documented.

---

# 1. PRODUCT DECISION RECORD

These decisions are fixed for v4.0.0 unless an authorized maintainer explicitly changes this contract.

| Decision | Locked choice |
|---|---|
| Primary audience | Institutes: management, faculty/HODs, technical/IT leadership |
| Demo mode | Guided showcase + genuinely interactive sandbox |
| Custom knowledge | Basic PDF/DOCX upload + processing/RAG demonstration |
| Sample courses | Exactly 2 primary courses |
| Chemistry | Optional third showcase/legacy course only; never default identity |
| Teacher/Admin | Lightweight interactive/preview experience |
| Runtime | Offline-first with optional API/model configuration where supported |
| Headline | Gayatri as a complete adaptive learning platform |
| Main differentiator | Course-independent adaptive tutoring + institution-owned knowledge |
| Release type | Major demo repositioning/reset |
| Target version | `v4.0.0` |

Recommended primary sample courses:

- **Engineering Mathematics**
- **Digital Electronics**

Alternative engineering pair may be selected only if technical constraints make the above substantially weaker. If changed, the agent MUST document the reason in the progress file before implementation.

Chemistry may be preserved as an optional third dataset only after the two primary engineering-oriented course experiences are complete and stable.

---

# 2. WHAT THE DEMO MUST PROVE

The demo is successful only when an institute can experience the following narrative without requiring an engineer to explain the architecture verbally:

> **Institution curriculum → course knowledge → Gayatri tutor → student interaction → adaptive response → learning state → teacher/institution insight**

The product should communicate these six ideas:

### 2.1 Platform, not subject application

The first screen, application title, documentation, installer name, splash screen, about page, icons, and screenshots MUST NOT position the product as “Gayatri Chemistry Tutor”.

Preferred positioning:

> **Gayatri — AI-Powered Adaptive Learning Platform**

Supporting statement:

> **Course-independent tutoring grounded in institution-defined knowledge.**

### 2.2 Course independence

A user MUST be able to switch from one sample course to another and observe a meaningful change in:

- course context;
- available topics/modules;
- knowledge sources;
- suggested learning actions;
- tutor grounding;
- question style;
- progress/mastery context.

The same application/tutor experience MUST remain intact.

### 2.3 Institution-owned knowledge

The demo MUST communicate that an institution can provide its own PDF/DOCX/structured material and associate it with a course.

The v4 demo must support at minimum a basic happy path:

`Upload document → validate → process/index → associate with course → query from that course context`.

If full production ingestion cannot safely be exposed in the demo, implement a bounded demo-safe ingestion flow with clear status messages and no fake success state.

### 2.4 Adaptive pedagogy

The tutor experience must demonstrate that Gayatri does more than answer a question.

A minimum credible learning interaction is:

`Explain → comprehension check → student response → evaluate → targeted feedback → next question/remediation`.

### 2.5 Learning intelligence

The demo must show at least a lightweight learner state such as:

- mastery percentage;
- topic-level strengths/weaknesses;
- recent learning activity;
- recommended next step;
- one clearly explained reason for adaptation.

### 2.6 Institutional visibility

The teacher/admin preview must demonstrate how student interactions can become actionable educational information without pretending that the demo contains the entire production administration system.

---

# 3. EXPERIENCE CONTRACT

The demo MUST contain the following conceptual journey.

## 3.1 Screen A — Welcome / positioning

Required content:

- Gayatri branding.
- “AI-Powered Adaptive Learning Platform”.
- Course-independent statement.
- Institution-owned knowledge statement.
- Adaptive-learning statement.
- Primary CTA: `Enter Demo`.
- Secondary CTA: `Explore Technology` or equivalent.

Forbidden:

- Chemistry as the primary title.
- NCERT-only positioning.
- “Chemistry Tutor” in the application window title or installer name.
- unsupported benchmark claims.

## 3.2 Screen B — Demo mode selection

Provide two clearly distinguishable entry paths:

### Guided Showcase

A curated path that walks the viewer through the most important capabilities in a controlled order.

### Explore Sandbox

Allows the viewer to select courses, ask questions, inspect progress, and explore the platform without following the guided sequence.

The guided path must never trap the user. A `Skip`, `Exit`, or `Explore` path must exist.

## 3.3 Screen C — Course selector

Show two primary courses:

### Engineering Mathematics

Suggested modules:

- Differential Equations
- Laplace Transform
- Fourier Series
- Complex Variables / Linear Algebra (choose based on available content)

### Digital Electronics

Suggested modules:

- Number Systems
- Boolean Algebra
- Logic Gates
- Combinational Circuits
- Sequential Circuits

The actual modules MUST match the RAG content shipped with the release.

Each course card should communicate:

- course title;
- short description;
- knowledge coverage;
- AI tutor availability;
- course status.

## 3.4 Screen D — Course overview

Display:

- course description;
- module list;
- course knowledge/RAG status;
- learner mastery summary;
- recommended starting point;
- `Start Learning` CTA.

## 3.5 Screen E — Tutor

Chat-style interface, professional enough for a faculty/management demo.

Required visible concepts:

- current course;
- current topic;
- AI tutor identity;
- response state/streaming where supported;
- optional “Knowledge used”/sources panel;
- learner interaction history.

## 3.6 Screen F — RAG/source evidence

When the tutor answers a course-grounded question, provide a user-understandable evidence surface, for example:

- Course knowledge used
- Unit/module
- document/source name
- retrieved section/chunk count
- grounded/not-grounded indicator

Do NOT expose raw database internals or sensitive stack traces.

Never fabricate citations or source references.

If a response is generated without retrieval evidence, the UI MUST distinguish that condition honestly.

## 3.7 Screen G — Adaptive learning demonstration

A guided demo scenario MUST deliberately include:

1. Gayatri explains a concept.
2. Gayatri asks the learner a question.
3. Learner provides an incorrect or partially correct answer.
4. Gayatri identifies the reasoning gap.
5. Gayatri adjusts the next interaction.
6. A new check is presented.
7. Learning state changes or a recommendation is updated.

The sequence must be deterministic enough for a sales/evaluation demonstration while retaining a genuinely interactive path.

## 3.8 Screen H — Switch course demonstration

This is a critical acceptance test.

The user starts with Engineering Mathematics, asks a valid question, then switches to Digital Electronics and asks a valid Digital Electronics question.

The system MUST:

- change active course identity;
- change available curriculum context;
- change retrieval scope;
- prevent stale course context from contaminating the new response;
- retain the learner's overall session appropriately;
- never accidentally answer a Digital Electronics query using Engineering Mathematics evidence.

## 3.9 Screen I — Student progress

Show at least:

- overall mastery;
- topic mastery;
- weak areas;
- recent activity;
- recommended next action;
- one adaptive explanation.

Do not overdesign this as a production analytics dashboard unless the platform already supports it reliably.

## 3.10 Screen J — Teacher preview

Show a class-level view such as:

- student list;
- mastery;
- weak topic;
- recent activity;
- recommended attention area.

The data may be seeded demonstration data, but it MUST be clearly marked as demo data.

## 3.11 Screen K — Institution/Admin preview

Show:

- course catalog;
- knowledge sources;
- users/roles at high level;
- curriculum/RAG management concept;
- model/provider configuration concept where implemented.

No fake controls.

If a control is preview-only, label it `Demo Preview`.

## 3.12 Screen L — Bring Your Curriculum

A basic working path is preferred:

- choose/create demo course;
- upload PDF/DOCX;
- process document;
- show validation status;
- index content;
- make it available to the tutor;
- query against it.

Security and performance limits MUST be enforced.

Document ingestion must not permit arbitrary execution through uploaded files.

---

# 4. ARCHITECTURE PRINCIPLES

The agent MUST use the main `Gayatri` repository as the engineering reference and source of implemented platform capabilities.

The agent MUST first perform a fresh audit of the `Gayatri` repository before deciding which components to implement, port, vendor, wrap, or re-create in `Gayatri-Demo`.

The agent MUST record the exact `Gayatri` commit SHA used as the engineering baseline for the demo release and document that baseline in the progress/evidence files.

Unless an explicit maintainer instruction says otherwise, this contract authorizes **read/reference use of `Gayatri`**, not modification of the production/source repository. Any required demo adaptation MUST be implemented in `Gayatri-Demo`.

The agent MUST NOT blindly duplicate the entire production repository into `Gayatri-Demo`.

The preferred architecture is:

```text
Gayatri-Demo
    │
    ├── Demo UI / presentation shell
    ├── Demo configuration
    ├── Two curated course/RAG datasets
    ├── Demo seed users + progress data
    ├── Safe packaging/build configuration
    └── Selected stable Gayatri platform components
             │
             ├── course layer
             ├── RAG layer
             ├── tutor orchestration
             ├── adaptive learning state
             └── model/provider abstraction
```

The implementation may use one of the following models based on the audit:

### Preferred

A clean demo application built from stable platform components of `Gayatri`, keeping the demo repository independently buildable and releaseable.

### Acceptable

A demo-specific frontend/shell that invokes a stable subset of the main platform through a local packaged runtime/API.

### Prohibited

- A demo that depends on a developer's absolute local path.
- A demo that silently depends on a local Ollama instance without documented/configured handling.
- A demo that requires source-repository state not present in the release package.
- A demo that uses copied code while pretending it automatically tracks the main platform.
- A hard-coded Chemistry-only branch inside generic tutor logic.

---

# 5. COURSE/RAG CONTRACT

## 5.1 Primary dataset 1 — Engineering Mathematics

The agent MUST create a compact, high-quality, internally consistent course knowledge package.

Minimum coverage:

- core definitions;
- formulas;
- worked conceptual examples;
- common misconceptions;
- at least several numerical/problem-solving prompts;
- prerequisite relationships;
- course/module metadata.

Avoid copying copyrighted textbooks wholesale.

The dataset should be original, institution-safe demonstration content or appropriately licensed/public-domain material.

## 5.2 Primary dataset 2 — Digital Electronics

Minimum coverage:

- number systems;
- Boolean algebra;
- logic gates;
- truth tables;
- combinational logic;
- sequential logic;
- conceptual examples;
- common misconceptions;
- prerequisite relationships.

Again, avoid wholesale reproduction of copyrighted textbooks.

## 5.3 Dataset requirements

Each dataset MUST have:

- stable course ID;
- version;
- title;
- subject/domain;
- module/chapter identifiers;
- source identifiers;
- clean chunk IDs;
- prerequisite metadata where supported;
- deterministic seed/sample queries;
- golden expected retrieval cases;
- no cross-course leakage.

Recommended logical structure:

```text
courses/
  engineering_mathematics/
    course.json
    modules.json
    rag/
      *.json
    golden_queries.json
  digital_electronics/
    course.json
    modules.json
    rag/
      *.json
    golden_queries.json
  chemistry_optional/
    ...
```

The exact directory structure may differ if the main Gayatri architecture already provides a stronger course/RAG layout.

## 5.4 Retrieval isolation

The agent MUST create automated tests proving:

- Engineering Mathematics queries retrieve Engineering Mathematics evidence.
- Digital Electronics queries retrieve Digital Electronics evidence.
- Cross-course evidence is excluded unless intentionally configured as shared knowledge.
- Switching courses resets/changes the retrieval scope correctly.
- Empty/noisy retrieval is handled gracefully.

---

# 6. MODEL / AI PROVIDER CONTRACT

The demo is **offline-first**, but may support optional API/model configurations already present in the main platform.

The agent MUST inspect existing model/provider abstractions before introducing a new provider layer.

The demo MUST have:

- a reliable default configuration;
- clear model availability detection;
- graceful failure if an optional model/provider is unavailable;
- timeout handling;
- retry limits;
- user-visible but non-sensitive error states;
- no API keys committed to the repository;
- no silent external network calls.

The UI MUST state the runtime mode honestly, e.g.:

`Local model · Offline mode`

or

`Configured API model · Internet required`

Do not claim “100% offline” if any background network connection occurs.

## 6.1 No hidden cloud behavior

The agent MUST audit all startup, telemetry, update checks, analytics, crash reporters, model downloaders, external URLs, and HTTP calls.

All optional network behaviour must be:

- explicit;
- documented;
- configurable;
- disabled in Local/Offline demo mode.

## 6.2 Failure behavior

If the local model cannot load:

- show a clear status;
- explain how to recover;
- do not crash the application;
- do not leave the UI permanently stuck in “Generating…”.

---

# 7. SECURITY & PRIVACY CONTRACT

The v4 demo MUST be safe to distribute as a public demonstration package.

The agent MUST audit for:

- hard-coded API keys;
- tokens;
- passwords;
- private URLs/credentials;
- developer machine paths;
- private student information;
- debugging endpoints;
- unsafe subprocess invocation;
- arbitrary file execution;
- untrusted upload handling;
- path traversal;
- unsafe extraction of archives;
- insecure temporary files;
- unbounded document ingestion;
- command injection;
- prompt injection paths;
- data leakage across courses;
- accidental telemetry;
- unsafe local server exposure.

## 7.1 Local network binding

If the desktop package runs a local API/service, default to loopback binding (`127.0.0.1`) rather than `0.0.0.0` unless there is a demonstrated and documented reason otherwise.

Do not create Windows Firewall inbound rules unless absolutely required.

The packaged demo MUST NOT expose its local service to the public network by default.

## 7.2 Uploaded documents

PDF/DOCX processing must be constrained by:

- allowed MIME/extension checks;
- file size limits;
- temporary directory isolation;
- safe parser usage;
- filename sanitization;
- path traversal protection;
- timeouts;
- memory controls where practical;
- deletion/cleanup policy.

Uploaded files must never be treated as executable content.

## 7.3 Data persistence

The demo may use local SQLite or the platform's existing local storage layer.

Seed/demo accounts and learner records MUST contain synthetic data only.

---

# 8. WINDOWS EXECUTABLE TRUST / ANTIVIRUS / FIREWALL CONTRACT

This section is mandatory because previous releases reportedly triggered local antivirus or Windows protection warnings.

The agent MUST distinguish at least four separate problems:

1. **SmartScreen reputation warning**: Windows does not recognize a newly downloaded executable.
2. **Microsoft Defender/antivirus malware detection**: a scanner classifies the file or behaviour as malicious/PUA.
3. **Browser download/reputation warning**: the download pipeline blocks or warns on the artifact.
4. **Windows Firewall prompt**: the application requests network access, often because it listens on a non-loopback address/port.

These are different problems and MUST be investigated separately.

## 8.1 Code signing

For production public distribution, all applicable Windows executables and installers MUST be digitally signed using a certificate issued by a trusted authority/service.

Preferred modern path:

- Microsoft Artifact Signing (formerly Trusted Signing/Azure Code Signing) or another reputable trusted code-signing solution.
- Use RSA-based signing for Smart App Control compatibility.
- Apply a trusted timestamp.
- Verify the signature before release.

The agent MUST NOT use a self-signed certificate as the production trust solution.

The agent MUST NOT claim that an EV certificate automatically eliminates SmartScreen warnings. Current Microsoft guidance states that EV no longer provides the old instant SmartScreen bypass; reputation still accumulates.

## 8.2 Signing order

The final release build flow MUST be:

```text
clean checkout
  ↓
clean dependency environment
  ↓
build binaries
  ↓
package installer / portable artifact
  ↓
verify package contents
  ↓
malware/security scans
  ↓
sign final executable artifacts
  ↓
verify signatures
  ↓
calculate SHA-256 hashes
  ↓
final smoke/regression tests on signed artifact
  ↓
publish
```

If signing changes the binary after testing, repeat tests on the signed artifact.

No file may be modified after signing.

## 8.3 Signing scope

The agent MUST determine all executables that need signing, including where applicable:

- installer EXE;
- primary application EXE;
- helper EXEs;
- bundled native binaries/DLLs where signing strategy requires it;
- other user-executed PE files.

The exact signing scope MUST be recorded in the release evidence report.

## 8.4 Signature verification

The release process MUST verify:

- signature exists;
- signature is valid;
- publisher identity is correct;
- certificate chain is trusted;
- timestamp is valid;
- signed content has not changed after signing.

Use Windows `signtool` or equivalent trusted verification tooling.

## 8.5 SmartScreen expectations

The agent MUST NOT promise “no SmartScreen warning” for a brand-new release merely because it is signed.

Microsoft states that SmartScreen uses both publisher reputation and file-hash reputation, and that new files may initially be treated as unrecognized until reputation accumulates.

The release documentation MUST therefore say exactly what is true:

- signed/verified publisher;
- SHA-256 available;
- clean scan evidence available;
- SmartScreen reputation may still be building for a new release.

## 8.6 Antivirus false-positive prevention

Before release, the agent MUST run a clean-room validation of the final artifact.

At minimum:

- Microsoft Defender scan on a clean Windows test environment;
- Windows Security/SmartScreen behaviour check;
- inspect detections and quarantine events;
- repeat after signing;
- verify hashes.

Where practical, test with multiple reputable antivirus engines or an approved malware-scanning service, but never upload private customer/student data.

If an antivirus engine reports a positive, the release is **BLOCKED** until one of the following is true:

- the detection is understood and resolved;
- the offending dependency/packer/loader is removed or replaced;
- the detection is demonstrated to be a false positive and appropriate vendor submission has been made;
- a documented risk acceptance is explicitly approved by the release owner.

Do not simply instruct users to disable antivirus.

Do not package a deliberately obfuscated/packed executable to evade antivirus.

Do not add exclusions to user machines.

## 8.7 Microsoft false-positive submission

If Microsoft Defender incorrectly detects the signed release, the release process SHOULD submit the affected file through Microsoft's software developer malware-analysis/submission workflow and record:

- submission date;
- file name;
- SHA-256;
- detection name;
- submission ID/result;
- remediation/outcome.

The agent MUST NOT fabricate a “Microsoft approved” status.

## 8.8 Firewall issue prevention

The application MUST NOT request external network access unless a real feature requires it.

Audit every socket/listener.

Preferred local architecture:

```text
Desktop UI
   ↕
127.0.0.1 local service
   ↕
local model / SQLite / RAG
```

Avoid:

```text
0.0.0.0:<port>
```

unless explicitly required.

If an optional API provider is configured, network access should occur only when that mode is enabled and must fail gracefully when blocked.

The agent MUST test a no-network environment.

## 8.9 Package size and suspicious behaviour

The previous demo releases contained very large bundled model artifacts. Large executables are not automatically malicious, but oversized self-extracting installers, unusual embedded binaries, runtime unpacking, temporary executable extraction, and native loaders can influence security products.

The agent MUST inspect packaging behaviour and reduce unnecessary complexity.

Where feasible:

- prefer a transparent installer structure;
- avoid unnecessary UPX/packer use;
- avoid runtime downloading of unsigned binaries;
- avoid self-modifying code;
- avoid hidden startup tasks/services;
- avoid unnecessary elevated privileges;
- do not require Administrator rights unless technically unavoidable.

If a native model runtime requires temporary extraction, document and test it carefully.

## 8.10 Windows reputation/distribution strategy

Primary public download SHOULD be from the official GitHub repository/release or official organization-controlled domain.

The release page MUST contain:

- clear publisher/organization identity;
- version;
- architecture;
- system requirements;
- exact artifact names;
- SHA-256 checksums;
- signature information;
- known first-run SmartScreen caveat for a new signed release;
- installation/uninstallation instructions;
- support/reporting instructions.

Do not redistribute the EXE through random mirrors.

---

# 9. BUILD & PACKAGING CONTRACT

The current `Gayatri-Demo` repository contains legacy Chemistry-only release documentation and historical release artifacts, while the current platform implementation lives in `Gayatri`. The agent MUST establish a clean, reproducible v4 build process in `Gayatri-Demo` using the main repository as the engineering reference.

The agent MUST NOT solve this by replacing `Gayatri-Demo` with an uncontrolled mirror of `Gayatri`. The result must be a deliberate, demo-sized release composition with clear provenance and a reproducible dependency strategy.

## 9.1 Build environment

Record:

- Windows version used for packaging;
- Python version;
- architecture (`x64` expected unless explicitly changed);
- compiler/toolchain versions where relevant;
- PyInstaller version if used;
- Inno Setup version if used;
- model runtime version;
- key dependency versions;
- Git commit SHA;
- clean/dirty working tree state.

## 9.2 Clean build requirement

Before final build:

1. clone/checkout exact release commit;
2. verify clean Git state;
3. create isolated environment;
4. install pinned/locked dependencies;
5. remove old build/dist/cache artifacts;
6. build from scratch;
7. run automated validation;
8. package;
9. scan/sign/verify;
10. test final artifacts.

No developer-local DLL or model may accidentally enter the final package.

## 9.3 Installer

Preferred deliverable:

`Gayatri_Adaptive_Learning_Platform_v4.0.0_Setup.exe`

Recommended second deliverable:

`Gayatri_Adaptive_Learning_Platform_v4.0.0_Portable.zip`

Optional:

`Gayatri_v4.0.0_Model_Weights.gguf`

only if redistribution/licensing and user value justify it.

## 9.4 Installation rules

The installer MUST:

- install without unnecessary admin rights where feasible;
- create correct Start Menu/Desktop shortcuts;
- use current Gayatri branding;
- have a clean uninstall path;
- preserve user data only if that behaviour is intentional and documented;
- not install hidden services;
- not create unwanted scheduled tasks;
- not alter browser settings;
- not modify unrelated system files;
- not add unnecessary PATH entries;
- not open firewall ports automatically.

## 9.5 Portable build

The portable package MUST run from an arbitrary user-selected directory and must not depend on absolute paths.

If write access is required, use an appropriate per-user data location or clearly document portable-mode behaviour.

---

# 10. LEGACY CONTENT DISPOSITION

The existing `Gayatri-Demo` repository currently reflects a Chemistry-only v3.x product identity and contains files such as:

- `RELEASE_NOTES_v3.0.0.md`
- `RELEASE_NOTES_v3.0.1.md`
- Chemistry-specific README content
- Chemistry-specific package names/checksums
- Chemistry logo assets where no longer appropriate
- Chemistry-specific Getting Started content
- old v3 EXE/ZIP/model release artifacts on GitHub Releases

The v4 repository MUST be audited and cleaned.

## 10.1 Delete vs archive

Delete from the current live v4 documentation/package surface when irrelevant.

Archive only where historical traceability is useful.

Do not keep stale Chemistry-only files at repository root where a future user/agent may mistake them for current instructions.

Recommended historical archive:

```text
archive/
  v3-chemistry/
    README_v3.0.1.md
    RELEASE_NOTES_v3.0.1.md
    GETTING_STARTED_GUIDE_v3.0.1.md
```

Do not archive giant obsolete binary artifacts into Git history merely for appearance. GitHub Releases can retain old release assets as history if appropriate.

## 10.2 Release assets

The v4 GitHub Release MUST contain only v4 assets and their supporting evidence/documentation.

Do not upload v4 binaries under Chemistry product names.

Do not reuse old checksums.

---

# 11. DOCUMENTATION CONTRACT

The **release repository `Gayatri-Demo`** MUST contain at minimum:

```text
README.md
RELEASE_NOTES_v4.0.0.md
GETTING_STARTED_GUIDE.md
INSTITUTION_DEMO_GUIDE.md
SECURITY_AND_TRUST.md
RELEASE_EVIDENCE_v4.0.0.md
SHA256SUMS.txt
LICENSE.md (if appropriate/current)
DEMO_RELEASE_PROGRESS.md
```

Recommended additional docs:

```text
ARCHITECTURE_DEMO.md
RAG_AND_COURSE_MODEL.md
TROUBLESHOOTING_WINDOWS.md
```

## 11.1 README

The README must lead with the platform proposition, not implementation details.

Recommended structure:

1. What Gayatri is
2. What this demo proves
3. Screenshots / capability overview
4. Courses included
5. Guided walkthrough
6. Custom curriculum/RAG demonstration
7. Teacher/admin preview
8. Offline-first/runtime modes
9. System requirements
10. Download artifacts
11. Verification/signing
12. Security/trust
13. Known limitations
14. Link to main platform repository
15. Release information

## 11.2 Claims audit

Every sentence containing a hard technical claim MUST be traceable to implementation or test evidence.

Avoid unverified claims such as:

- “zero latency”;
- “100% hallucination-free”;
- “perfect accuracy”;
- “enterprise-ready” unless that exact scope has been verified;
- “zero network usage” unless verified;
- “virus-free” as an absolute guarantee.

Prefer evidence-backed wording:

> “The packaged demo operates without external network access in Local mode; this behaviour was verified in the v4 release test environment.”

---

# 12. REQUIRED AUTOMATED TESTING

The agent MUST NOT merely run the existing full main-repository test suite and declare the demo complete.

The agent MUST create demo-specific tests where necessary.

## 12.1 Minimum test layers

### Unit tests

Validate:

- course selection;
- course metadata;
- RAG filtering;
- source association;
- upload validation;
- state transitions;
- mastery updates;
- model configuration handling.

### Integration tests

Validate:

- course → RAG → tutor;
- tutor → evaluation → learning state;
- course switching;
- upload → ingestion → retrieval;
- teacher view reading student state;
- offline mode;
- optional network mode.

### Regression tests

Validate existing stable functionality imported from the main Gayatri platform.

### GUI smoke tests

Validate every primary screen can:

- load;
- navigate;
- perform its main action;
- recover from an error;
- exit cleanly.

### Packaging tests

Validate:

- installer runs;
- application launches from installed location;
- portable version launches;
- uninstall works;
- shortcuts work;
- no dependency is missing;
- model assets resolve correctly;
- local data directory works;
- application works without developer tools installed.

### Security tests

Validate:

- no secrets;
- no public listener by default;
- no unintended outbound calls in offline mode;
- unsafe upload blocked;
- path traversal blocked;
- malicious/invalid document handling is safe;
- no shell injection through user-controlled values;
- no executable extraction from untrusted document input.

### Windows trust tests

Validate:

- signature;
- timestamp;
- certificate chain;
- Defender scan;
- SmartScreen behaviour;
- firewall behaviour;
- hash integrity.

---

# 13. GOLDEN DEMO SCENARIOS

The agent MUST implement deterministic or reproducible golden scenarios for sales/evaluation.

## Scenario 1 — First impression

Expected:

`Launch → Welcome → Enter Demo`

Pass criteria:

- no crash;
- current branding;
- no Chemistry-only identity;
- no stale v3 copy.

## Scenario 2 — Engineering Mathematics

Action:

Select Engineering Mathematics and ask a prepared question.

Expected:

- correct course context;
- relevant RAG evidence;
- useful tutor answer;
- no Digital Electronics content.

## Scenario 3 — Digital Electronics

Action:

Switch to Digital Electronics and ask a prepared question.

Expected:

- correct course context;
- relevant Digital Electronics evidence;
- no Engineering Mathematics evidence.

## Scenario 4 — Adaptive interaction

Action:

Use a prepared wrong/partial answer.

Expected:

- misconception-aware feedback;
- next-step adaptation;
- no premature answer dumping where Socratic behaviour is configured;
- progress state update.

## Scenario 5 — Add curriculum

Action:

Upload a valid demo-safe PDF/DOCX.

Expected:

- validation;
- processing;
- course association;
- searchable knowledge;
- tutor retrieval from uploaded material.

## Scenario 6 — Teacher insight

Action:

Open Teacher Preview.

Expected:

- synthetic/demo class data;
- identifiable weak area;
- actionable student/course insight.

## Scenario 7 — Offline mode

Action:

Disable network on the test machine.

Expected:

- application launches;
- bundled/local functionality works;
- no hidden network dependency;
- clear failure only for explicitly optional online features.

## Scenario 8 — Security failure

Action:

Attempt unsafe file/path payloads.

Expected:

- rejected safely;
- no command execution;
- no crash.

## Scenario 9 — Installer trust

Action:

Download and run the signed installer on a clean Windows machine.

Expected:

- signature verifies;
- publisher identity is visible;
- Defender does not identify the release as malware/PUA;
- any SmartScreen warning is documented as reputation-related and not falsely described as “virus detected”.

## Scenario 10 — Clean uninstall

Action:

Uninstall.

Expected:

- application removed;
- shortcuts removed;
- intentionally retained user data behaves as documented.

---

# 14. AI AGENT OPERATING PROTOCOL

The AI agent MUST work phase-by-phase.

**Never implement the whole project in one uncontrolled pass.**

For each phase, the agent MUST follow:

```text
1. INSPECT
2. UNDERSTAND
3. PLAN
4. RECORD PLAN
5. IMPLEMENT
6. RUN TARGETED TESTS
7. DEBUG
8. RUN REGRESSION CHECKS
9. REVIEW DIFF
10. UPDATE PROGRESS
11. DECLARE PHASE COMPLETE
12. ONLY THEN MOVE TO NEXT PHASE
```

## 14.1 Planning-before-coding rule

Before touching code in a phase, the agent MUST write a short plan containing:

- objective;
- current state;
- assumptions;
- affected files/modules;
- dependencies;
- risks;
- tests to run;
- rollback considerations;
- expected acceptance criteria.

The plan MUST be stored in `DEMO_RELEASE_PROGRESS.md` or a phase-specific engineering note.

## 14.2 No cascading blind edits

An edit in one subsystem MUST trigger a search for dependent callers, routes, schemas, UI contracts, tests, docs, packaging metadata, and release scripts.

## 14.3 Debug before progressing

A phase is NOT complete if:

- tests fail;
- known errors remain unexplained;
- startup warnings indicate likely breakage;
- packaging is broken;
- a changed API has unverified consumers;
- docs contradict behaviour.

## 14.4 Regression discipline

After every meaningful change:

- run targeted tests;
- run relevant integration tests;
- inspect logs;
- check changed files for stale imports/references;
- check UI routes and labels;
- run a minimal regression set.

At phase boundaries, run a broader regression suite.

## 14.5 Never hide failures

The agent MUST NOT:

- disable tests merely to make CI green;
- delete failing tests without evidence;
- comment out code to hide errors;
- swallow exceptions broadly;
- hard-code expected outputs to fake success;
- silently fall back to a different course/model/provider;
- mark a phase complete because “the main flow works”.

All failures MUST be logged with:

- symptom;
- root cause;
- affected component;
- fix;
- regression test;
- status.

---

# 15. PHASE PLAN

The following phases are mandatory.

---

## PHASE 0 — BASELINE / REPOSITORY FORENSICS

### Goal
Understand the current state of both repositories before changing anything.

### Inspect

- current `Gayatri` HEAD and commit history;
- current `Gayatri-Demo` HEAD and commit history;
- current `Gayatri` reference HEAD/commit used for engineering baseline;
- release assets/tags;
- current README/docs;
- packaging scripts/specs;
- model manifest;
- course model;
- RAG service;
- tutor orchestrator;
- student/teacher/admin portals;
- Windows application shell;
- launch scripts;
- test inventory;
- current build outputs.

### Required output

Create:

- `DEMO_BASELINE.md`
- `DEMO_RELEASE_PROGRESS.md`

Record exact commit SHAs.

### Acceptance

No architecture or packaging implementation begins before the baseline is recorded.

---

## PHASE 1 — PRODUCT RESET / DEMO UX SPECIFICATION

### Goal
Replace the Chemistry-only demo identity with the platform showcase identity.

### Tasks

- define information architecture;
- define screen flow;
- define guided path;
- define sandbox path;
- define course switch flow;
- define teacher/admin previews;
- define Bring Your Curriculum path;
- define empty/error/loading states;
- define accessibility expectations;
- define branding/copy inventory.

### Acceptance

A clickable/implementable screen specification exists and maps every user flow to a real capability or explicitly labelled demo preview.

---

## PHASE 2 — ARCHITECTURE SELECTION & DEMO BOUNDARY

### Goal
Choose the smallest reliable subset of `Gayatri` needed to demonstrate the platform.

### Tasks

- map production modules to demo requirements;
- identify reusable components;
- identify legacy/unused components;
- identify platform dependencies;
- define demo-specific adapters where needed;
- prevent unnecessary dependency bloat.

### Acceptance

An architecture document lists every imported component and why it exists.

---

## PHASE 3 — COURSE MODEL & TWO COURSE PACKAGES

### Goal
Build the two primary course datasets.

### Tasks

- Engineering Mathematics dataset;
- Digital Electronics dataset;
- metadata;
- modules;
- prerequisites;
- sample questions;
- misconceptions;
- golden retrieval queries;
- seeded learner progress.

### Acceptance

Both courses are independently loadable and independently queryable.

---

## PHASE 4 — RAG PIPELINE & ISOLATION

### Goal
Make course-specific grounding reliable and demonstrable.

### Tasks

- ingestion/indexing;
- retrieval;
- source metadata;
- course scope;
- query filters;
- source panel;
- upload flow;
- retrieval tests;
- cross-course leakage tests.

### Acceptance

Golden RAG tests pass and course switching changes retrieval scope correctly.

---

## PHASE 5 — GENERIC TUTOR / ADAPTIVE LEARNING INTEGRATION

### Goal
Wire the generic tutor engine to course context and learner state.

### Tasks

- tutor context assembly;
- course selection;
- session state;
- adaptive policy;
- evaluator;
- misconception feedback;
- next-step selection;
- mastery update;
- error handling.

### Acceptance

The same tutor code supports both courses and produces context-appropriate answers.

---

## PHASE 6 — STUDENT EXPERIENCE

### Goal
Build a polished student-facing journey.

### Tasks

- welcome;
- course selection;
- course overview;
- tutor;
- sources;
- adaptive feedback;
- progress dashboard;
- settings/runtime status;
- recovery states.

### Acceptance

Golden student scenarios 1–4 pass.

---

## PHASE 7 — TEACHER / ADMIN PREVIEWS

### Goal
Show institution value without faking unsupported functionality.

### Tasks

- teacher class view;
- student mastery;
- weak area summary;
- institution/course management view;
- knowledge source view;
- clearly mark demo-only sections.

### Acceptance

Teacher/admin flows are usable, consistent, and honest about their demo scope.

---

## PHASE 8 — OFFLINE-FIRST / NETWORK BEHAVIOUR

### Goal
Make runtime behaviour deterministic and trustworthy.

### Tasks

- offline mode audit;
- network call inventory;
- local model handling;
- optional provider handling;
- timeout/retry policy;
- no-network test;
- local host binding.

### Acceptance

The demo behaves correctly with network disabled.

---

## PHASE 9 — WINDOWS PACKAGING HARDENING

### Goal
Produce professional installer and portable package.

### Tasks

- clean build configuration;
- current app branding;
- package paths;
- model packaging;
- dependency verification;
- installer metadata;
- uninstall behaviour;
- shortcuts;
- no unnecessary privilege;
- no hidden service;
- no accidental firewall rule.

### Acceptance

Fresh-machine installation and portable execution succeed.

---

## PHASE 10 — SECURITY / ANTIVIRUS / TRUST HARDENING

### Goal
Address the prior release trust/security warning problem systematically.

### Tasks

- PE inventory;
- executable signature strategy;
- Microsoft Artifact Signing or approved certificate integration;
- trusted timestamp;
- signature verification;
- Defender scan;
- SmartScreen test;
- firewall test;
- outbound network audit;
- suspicious behaviour audit;
- false-positive submission process/documentation;
- hash generation.

### Acceptance

All trust/security gates pass or an explicitly documented exception is approved.

---

## PHASE 11 — FULL DEMO QA / REGRESSION

### Goal
Verify the release as an institute-facing product, not merely as code.

### Tasks

- all golden scenarios;
- GUI smoke tests;
- course isolation tests;
- RAG tests;
- teacher/admin tests;
- offline tests;
- installer tests;
- uninstall tests;
- performance sanity tests;
- error/recovery tests.

### Acceptance

No P0/P1 defect remains.

P2 defects require explicit release decision and documentation.

---

## PHASE 12 — DOCUMENTATION / CLAIMS / RELEASE EVIDENCE

### Goal
Make the public release self-explanatory and technically honest.

### Tasks

- README;
- release notes;
- getting started;
- institution demo guide;
- security/trust doc;
- troubleshooting;
- architecture overview;
- SHA-256 file;
- release evidence;
- known limitations;
- version consistency audit.

### Acceptance

No stale v3 Chemistry-only content remains in the active v4 path.

---

## PHASE 13 — FINAL CLEAN BUILD / SIGN / VERIFY

### Goal
Create the immutable final release candidate.

### Tasks

- clean checkout;
- clean environment;
- rebuild;
- scan;
- sign;
- verify signature;
- retest signed artifacts;
- calculate SHA-256;
- generate evidence.

### Acceptance

Release candidate passes every mandatory release gate.

---

## PHASE 14 — RELEASE PACKAGING / GITHUB RELEASE PREPARATION

### Goal
Prepare public v4.0.0 release assets.

### Required assets

At minimum:

- installer EXE;
- portable ZIP;
- SHA-256 checksums;
- release notes;
- getting started guide;
- security/trust document or link;
- release evidence summary.

Optional:

- standalone model weights;
- source bundle;
- architecture/technical guide.

### Acceptance

Every uploaded asset matches the documented version and checksum.

---

## PHASE 15 — FINAL RELEASE GATE

The agent MUST execute a final independent review pass as if it were a hostile external evaluator.

Questions:

- Does this look like an adaptive learning platform?
- Can I understand the value in 30 seconds?
- Can I demonstrate two genuinely different courses?
- Can I see the RAG difference?
- Can I see adaptive behaviour?
- Can I see institutional value?
- Can I install it on a clean Windows machine?
- Are trust/signature/hash details available?
- Does offline mode actually work?
- Does course switching isolate data?
- Does the app recover from failures?
- Is every claim truthful?
- Are there stale references to v3 Chemistry?

If any answer is “no” for a mandatory area, release is blocked.

---

# 16. PROGRESS TRACKING CONTRACT

The authoritative contract file is stored in `Gayatri-Education/Gayatri`. `DEMO_RELEASE_PROGRESS.md` is the execution ledger stored in `Gayatri-Demo`.

Create and maintain `DEMO_RELEASE_PROGRESS.md` at all times.

The progress ledger MUST record: (a) the path/commit of the authoritative contract read from `Gayatri`, (b) the exact `Gayatri` reference commit used as the platform baseline, and (c) the exact `Gayatri-Demo` commit implementing each completed phase. The agent MUST never silently continue against a different contract revision or source-repository baseline.

Required table:

| Phase | Status | Start | End | Owner/Agent | Tests | Blockers | Evidence | Commit |
|---|---|---|---|---|---|---|---|---|
| 0 | NOT STARTED | | | | | | | |
| 1 | NOT STARTED | | | | | | | |
| 2 | NOT STARTED | | | | | | | |
| 3 | NOT STARTED | | | | | | | |
| 4 | NOT STARTED | | | | | | | |
| 5 | NOT STARTED | | | | | | | |
| 6 | NOT STARTED | | | | | | | |
| 7 | NOT STARTED | | | | | | | |
| 8 | NOT STARTED | | | | | | | |
| 9 | NOT STARTED | | | | | | | |
| 10 | NOT STARTED | | | | | | | |
| 11 | NOT STARTED | | | | | | | |
| 12 | NOT STARTED | | | | | | | |
| 13 | NOT STARTED | | | | | | | |
| 14 | NOT STARTED | | | | | | | |
| 15 | NOT STARTED | | | | | | | |

Allowed status values:

- `NOT STARTED`
- `IN PROGRESS`
- `BLOCKED`
- `READY FOR REVIEW`
- `COMPLETE`
- `REOPENED`

A phase can be `COMPLETE` only when its acceptance criteria are demonstrated.

---

# 17. DEFECT SEVERITY CONTRACT

| Severity | Meaning | Release impact |
|---|---|---|
| P0 | Crash, RCE, malware detection, data leak, catastrophic course contamination, unusable installer | Immediate release block |
| P1 | Core demo journey broken, course switching broken, RAG fundamentally wrong, major install/runtime failure | Release block |
| P2 | Significant but workaround exists | Explicit review required |
| P3 | Cosmetic/minor documentation/UI issue | May ship if documented |

The agent MUST maintain a defect log.

Required fields:

```text
ID
Severity
Area
Reproduction
Expected
Actual
Root Cause
Fix
Regression Test
Status
Commit
```

---

# 18. RELEASE EVIDENCE CONTRACT

Before release, create `RELEASE_EVIDENCE_v4.0.0.md` containing:

## Build evidence

- Git commit SHA
- build environment
- dependency lock/version information
- build commands
- package names
- package sizes
- SHA-256 values

## Test evidence

- unit results
- integration results
- golden demo results
- GUI results
- offline results
- install/uninstall results
- security test results

## Trust evidence

- signature subject/publisher
- certificate issuer
- timestamp
- signature verification result
- Defender scan result
- SmartScreen observation
- firewall observation
- false-positive submissions if any

## Known limitations

Only documented, user-impacting limitations.

---

# 19. VERSION & BRAND CONSISTENCY GATE

The following MUST agree before release:

- application title;
- installer title;
- installer filename;
- portable filename;
- README version;
- release notes;
- package metadata;
- About dialog;
- splash screen;
- executable metadata;
- Git tag;
- GitHub Release title;
- checksums;
- screenshots.

Search the entire repository for stale strings including at minimum:

```text
Gayatri Chemistry Tutor
v3.0.0
v3.0.1
Qwen2.5-0.5B Socratic SLM
NCERT Class 11 & 12
Senior Secondary Chemistry
Chemistry Tutor v3
Gayatri_Chemistry_Tutor
```

Any remaining occurrence MUST be either:

- intentionally historical in `archive/`;
- a technically valid optional Chemistry dataset/feature reference;
- documented as legacy compatibility information.

No stale active-product branding is allowed.

---

# 20. PERFORMANCE CONTRACT

The demo need not optimize for production-scale institutional concurrency.

It MUST optimize for a convincing single-user demonstration on realistic Windows hardware.

The agent MUST measure:

- cold startup;
- warm startup;
- model initialization;
- first response latency;
- response generation throughput where meaningful;
- course switch time;
- RAG retrieval latency;
- document ingestion time for a bounded sample;
- memory usage;
- installer size;
- disk footprint.

Do not invent targets after measurement.

Set reasonable v4 targets during Phase 2 based on actual platform capability and hardware.

---

# 21. USER EXPERIENCE / FAILURE STATE CONTRACT

Every major action needs at least these states where applicable:

- loading;
- success;
- empty;
- validation error;
- runtime error;
- unavailable dependency;
- timeout;
- recovery/retry.

The UI MUST NEVER:

- remain indefinitely on a spinner;
- report success before a backend operation succeeds;
- display raw stack traces to normal users;
- lose course context silently;
- show “online” when offline;
- show “RAG grounded” without evidence.

---

# 22. DEMO DATA CONTRACT

All demo identities must be synthetic.

Recommended sample profile:

`Demo Student`

Do not include real names, phone numbers, email addresses, school IDs, or private student information.

Demo datasets should be reproducible from scripts rather than manually edited database dumps where practical.

---

# 23. RELEASE COMMAND DISCIPLINE

The agent MUST document exact commands used for:

```text
setup
lint
unit tests
integration tests
RAG tests
GUI/smoke tests
build
package
sign
verify signature
scan
hash
release packaging
```

If commands differ between developer and release environments, document both.

No undocumented manual step may be required for the final release unless the step is explicitly listed in the release checklist.

---

# 24. RECOMMENDED REPOSITORY STRUCTURE

The final repository should converge toward something similar to:

```text
Gayatri-Demo/
├── app/                         # demo application / selected platform shell
├── demo_data/
│   ├── courses/
│   │   ├── engineering_mathematics/
│   │   ├── digital_electronics/
│   │   └── chemistry_optional/
│   └── users/
├── packaging/
│   ├── installer.iss
│   ├── *.spec
│   └── signing/
├── scripts/
│   ├── build_demo.py
│   ├── seed_demo.py
│   ├── validate_demo.py
│   ├── verify_release.py
│   └── security_scan.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── rag/
│   ├── gui/
│   ├── security/
│   └── release/
├── docs/
│   ├── ARCHITECTURE_DEMO.md
│   ├── RAG_AND_COURSE_MODEL.md
│   ├── SECURITY_AND_TRUST.md
│   └── TROUBLESHOOTING_WINDOWS.md
├── archive/
│   └── v3-chemistry/
├── README.md
├── GETTING_STARTED_GUIDE.md
├── INSTITUTION_DEMO_GUIDE.md
├── RELEASE_NOTES_v4.0.0.md
├── RELEASE_EVIDENCE_v4.0.0.md
├── DEMO_RELEASE_PROGRESS.md
└── SHA256SUMS.txt
```

The agent may adapt the structure to the real `Gayatri` architecture where a different layout is technically superior.

---

# 25. FINAL RELEASE CHECKLIST

All items below MUST be checked before publishing.

## Product

- [ ] Platform positioning is correct.
- [ ] Two primary courses work.
- [ ] Course switching works.
- [ ] RAG grounding is visible.
- [ ] Adaptive behaviour is visible.
- [ ] Student progress works.
- [ ] Teacher preview works.
- [ ] Admin/institution preview works.
- [ ] Basic curriculum upload path works or is truthfully scoped.
- [ ] Chemistry is optional, not dominant.

## Engineering

- [ ] Clean build.
- [ ] No developer-local paths.
- [ ] No hidden services.
- [ ] No unnecessary firewall changes.
- [ ] No secrets.
- [ ] No cross-course leakage.
- [ ] No known P0/P1 defects.

## Windows distribution

- [ ] Installer works on clean Windows machine.
- [ ] Portable build works.
- [ ] Uninstaller works.
- [ ] All relevant executables signed.
- [ ] RSA-based signing used where Smart App Control compatibility matters.
- [ ] Timestamp valid.
- [ ] Signature verified.
- [ ] Defender scan completed.
- [ ] SmartScreen behaviour documented.
- [ ] Firewall behaviour tested.
- [ ] SHA-256 generated.
- [ ] Artifact names/version consistent.

## Documentation

- [ ] README updated.
- [ ] Getting Started updated.
- [ ] Institution Demo Guide updated.
- [ ] Release Notes updated.
- [ ] Security & Trust updated.
- [ ] Release Evidence updated.
- [ ] Troubleshooting updated.
- [ ] No stale v3 active documentation.

## Release

- [ ] Release candidate built from exact tagged commit.
- [ ] Final signed artifact hashes recorded.
- [ ] GitHub release notes match actual build.
- [ ] Download instructions tested.
- [ ] Public release package contains only intended v4 assets.

---

# 26. NON-NEGOTIABLE AGENT RULES

## 26.0 Repository boundary rules

1. The authoritative contract lives in `Gayatri-Education/Gayatri`; do not create a conflicting second contract in `Gayatri-Demo`.
2. Treat `Gayatri-Education/Gayatri` as the source/engineering reference and `Gayatri-Education/Gayatri-Demo` as the implementation/release repository for this project.
3. Record the exact `Gayatri` commit used by the demo.
4. Do not silently modify `Gayatri` while implementing this demo.
5. Do not rely on uncommitted, ignored, absolute-path, or machine-specific files from the local `Gayatri` checkout.
6. Every production capability claimed by the demo must be traceable to either a verified implementation in `Gayatri` or a verified demo implementation in `Gayatri-Demo`.
7. If the demo needs a capability that exists in `Gayatri` but is not safely reusable, implement a demo-local integration/adaptation rather than creating an undocumented cross-repository runtime dependency.


1. **Never code before inspecting the current state for the phase.**
2. **Never move to the next phase while the current phase has unexplained failures.**
3. **Every material code change must have a validation path.**
4. **Every release claim must have implementation or evidence behind it.**
5. **Never fake a RAG/source result.**
6. **Never silently mix knowledge between courses.**
7. **Never ship secrets or private data.**
8. **Never tell users to disable antivirus/firewall as the normal solution.**
9. **Never rely on unsigned public Windows binaries when signing infrastructure is available and applicable.**
10. **Never assume signing alone guarantees no SmartScreen warning.**
11. **Never use self-signed certificates as the production trust mechanism.**
12. **Never post-build modify signed binaries.**
13. **Never use packers/obfuscation merely to evade antivirus detection.**
14. **Never bind a local service publicly without an explicit requirement.**
15. **Never leave stale Chemistry-only branding in the active v4 product surface.**
16. **Never remove a failing test merely to achieve green CI.**
17. **Never mark a phase complete without evidence.**
18. **When uncertain, inspect the main repository and tests before inventing a new implementation.**
19. **Prefer the simplest architecture that reliably proves the product thesis.**
20. **The final release must be evaluated like an external institute evaluator would evaluate it, not like the developer who built it.**

---

# 27. EXTERNAL SECURITY/TRUST REFERENCES

The following guidance was incorporated into this contract based on current Microsoft documentation reviewed on 2026-10-08:

- Microsoft Learn — SmartScreen reputation for Windows app developers: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- Microsoft Learn — Windows app distribution feature status: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/distribution-feature-status
- Microsoft Learn — Sign your app for Smart App Control compliance: https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control
- Microsoft Learn — Software developer FAQ: https://learn.microsoft.com/en-us/defender-xdr/developer-faq
- Microsoft Security Intelligence — File submission: https://www.microsoft.com/wdsi/filesubmission

Important current guidance reflected here:

- SmartScreen considers publisher and file-hash reputation.
- New signed files may still show recognition/reputation warnings until reputation accumulates.
- EV code signing no longer gives the historical instant SmartScreen bypass.
- Microsoft currently recommends Artifact Signing for non-Store app signing.
- RSA-based trusted signing is required for Smart App Control compatibility; ECC is not currently supported there.
- Developers can submit suspected false positives for Microsoft analysis.

---

# 28. DEFINITION OF DONE — v4.0.0

Gayatri-Demo v4.0.0 is DONE only when an independent reviewer can:

1. Launch the application successfully on a clean supported Windows machine.
2. Immediately understand that Gayatri is an adaptive learning platform.
3. Select Engineering Mathematics.
4. Ask a meaningful question and receive a course-grounded response.
5. Inspect the course/source context.
6. Demonstrate adaptive tutoring through an incorrect/partial answer.
7. Observe a learning/progress change or recommendation.
8. Switch to Digital Electronics.
9. Ask a relevant Digital Electronics question.
10. Verify that the evidence/context belongs to Digital Electronics rather than the previous course.
11. Open Teacher Preview and see actionable learner information.
12. Open Institution/Admin Preview and understand the curriculum/RAG concept.
13. Add a bounded sample knowledge document or otherwise execute the supported Bring Your Curriculum demonstration honestly.
14. Run the demo with network disabled and observe the documented offline behaviour.
15. Verify the Windows executable signature.
16. Verify SHA-256 hashes.
17. Observe no confirmed malware/PUA detection in the final release validation environment.
18. Install/uninstall cleanly.
19. Read the public README and understand the same product story shown in the software.
20. Find no stale active v3 Chemistry-only identity.

Anything less is a candidate build, not the final institutional demo release.

---

# 29. AGENT HANDOFF INSTRUCTION

When this document is supplied to a local AI development agent, the agent's first action is:

> **Read this entire contract. Then inspect both repositories and establish the Phase 0 baseline. Do not begin feature implementation until the baseline, architecture boundary, and release-risk inventory are recorded. Execute phases sequentially. At the end of every phase, run tests, debug failures, update progress, review the diff, and record evidence before continuing. The target is a complete, truthful, institution-facing Gayatri Adaptive Learning Platform demo release v4.0.0 — not a Chemistry Tutor v3 refresh.**

---

# 30. CHANGE CONTROL

This document is the source of truth for the v4 release.

Any change to locked product decisions MUST be recorded in a `Change Control` section of `DEMO_RELEASE_PROGRESS.md` with:

- date;
- old decision;
- new decision;
- reason;
- affected phases;
- risk;
- approval/authority.

Do not silently reinterpret product requirements mid-release.

**END OF CONTRACT**
