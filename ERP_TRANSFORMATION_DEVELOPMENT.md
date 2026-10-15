# GAYATRI-ERP Transformation — Phase-Gated Development Contract

**Target repository:** https://github.com/Gayatri-Education/GAYATRI-ERP  
**Purpose:** Mandatory execution guide for a local AI coding agent.  
**Execution model:** Inspect → plan → implement → test → debug → regress → document evidence → pass gate → next phase.  
**Status:** This is a development contract, not a claim that the target product or any feature is already production-ready.

---

## 1. Mission and product outcome

Implement the requirements in the supplied **GAYATRI-ERP: Technical Architecture & Transformation Roadmap** in the existing repository. The intended product is a privacy-first, offline-capable School Operating System integrating the existing Gayatri learning/tutoring platform with real institutional workflows: identity and governance; admissions and student CRM; attendance and hardware bridges; academics, timetables and substitutions; LMS; examinations and report cards; HR and payroll; fees and double-entry accounting; facilities; document/ID design; communications and helpdesk; public CMS; dynamic administration; local AI assistance; desktop and responsive portals; and install, backup, restore and carefully governed synchronization.

This is not a request to generate mock screens, placeholder APIs, hardcoded sample records, no-op buttons, disconnected modules, or a “complete ERP” label. A feature is complete only when the authorized user can complete the intended workflow, the correct result is persisted, the failure paths are visible and recoverable, access control is enforced on the server, module integration is correct, tests pass, and evidence is recorded.

The target repository already documents a Python/FastAPI, SQLite-WAL, local SLM/RAG platform with existing identity, API, desktop and portal paths and migration history. Treat that as a starting point to verify—not as proof that every documented feature works. Preserve functioning tutoring, scoped RAG, evidence-based mastery, authentication, sync, payment, migration and privacy mechanisms. Extend canonical services; do not create a second source of truth or blindly transplant another ERP's framework.

The agent must proceed autonomously through safe, unblocked phases. Do not ask for confirmation after every phase. Stop only for a genuine need for unavailable credentials or physical devices, an externally visible/destructive action, paid services, or an unresolved material product decision. Record blockers, their impact and a safe next action; continue independent work.

## 2. Mandatory phase workflow — no exceptions

For **every phase**, repeat this loop in order:

1. **Discover:** Read this contract, README, DEVELOPMENT.md, product and QA plans, architecture/data-model/security/privacy/deployment/testing documentation, migration history, source, UI clients, tests, CI and current Git state. Follow actual callers and route registration. Never edit first and inspect later.
2. **Map:** Link each requirement to existing files, symbols, models, services, routes, UI, migration and tests. Label observations as `CODE_OBSERVED`, `TEST_OBSERVED`, `RUNTIME_VERIFIED`, `PROPOSED`, `BLOCKED`, `NOT_RUN` or `NOT_APPLICABLE`.
3. **Plan before coding:** Create `docs/erp_agent/plans/PHASE_NN_PLAN.md` before app-source changes. Specify workflows and states, likely files, existing behavior, design choice, schema impact, permissions, privacy/security risks, failure recovery, tests, rollout/rollback, and binary exit criteria.
4. **Record baseline:** Capture commit SHA, working-tree status, OS/Python/dependency versions, schema/migration version, relevant environment-variable names (never values of secrets), and focused existing test results. Run tests as configured; do not assume README counts or badges are evidence.
5. **Implement one coherent slice:** Reuse existing dependency injection, models, services, routers and events when sound. Make the smallest end-to-end change that produces real behavior. Avoid adding a new service with overlapping responsibility.
6. **Test:** Add a regression test for each defect and appropriate tests for feature behavior: happy path, validation, permissions, tenant/branch boundary, legal state transitions, persistence, idempotency, transaction rollback, retry/recovery, and UI/API integration.
7. **Debug to root cause:** Investigate failing assertions, exceptions, flaky timing, data corruption, concurrency issues, swallowed failures, duplicate events, stale UI, missing API integration and incomplete failure handling. Do not continue while a required check is failing.
8. **Review diff:** Confirm tests were not deleted/loosened, failures not hidden by broad skip/xfail, business logic not replaced with mocks, no unrelated files were changed, no secrets/PII were committed, migrations are safe, and error handling is honest.
9. **Regression:** Run focused module tests, integration tests, all applicable existing tests, compile/lint/type/security checks and startup smoke tests. Hardware/provider/OS checks that cannot actually run are `BLOCKED` or `NOT_RUN`, never `PASSED` by substituting mocks.
10. **Record evidence:** Update `docs/erp_agent/MASTER_PROGRESS.md`, feature traceability, phase plan/report, regression record, decision log and blockers. Record exact commands, versions, result counts, exit codes, sanitized logs, evidence links and unresolved risks.
11. **Gate:** Mark a phase `PASSED` only if every mandatory exit criterion has evidence. P0/P1 issues block dependent work and production release. Never claim tests, integrations, security, performance, backup/restore or real model inference passed if not actually executed.
12. **Commit coherently:** Commit only a focused, tested change. Preserve unrelated user work. Do not force-push, rewrite shared history, delete useful files for repository cleanliness, deploy to production, send real messages, make actual payments or incur paid cloud/GPU costs without explicit authorization.

If GitHub access cannot create branches or write files, do not claim that changes were committed. Use a local branch/worktree or provide a prepared patch and disclose the permission blocker.

## 3. Architecture and correctness guardrails

### 3.1 Tenant, branch and authorization
- Model institution/organization, branch/campus, academic session, identity, role/permission, and resource ownership separately. Document the relationship and lifecycle.
- A client-provided `X-Branch-ID` header is **not authorization**. Resolve the authenticated principal's allowed organizations/branches server-side; reject missing, malformed, inactive or unauthorized scope. A header may select only among scopes already granted.
- Enforce authorization in service/data-access boundaries and in every list, lookup, mutation, export, download, background job, report and sync operation—not merely middleware or the UI.
- Test cross-tenant IDOR, guessed UUIDs, role escalation, unauthorized branch switch, bulk import/export, guardian-to-child relationship, file path guessing, asynchronous task scope and stale session revocation.
- Audit sensitive actions with actor, scope, timestamp, correlation ID, action and safe before/after summary. Do not put secrets, health notes, student message content, tokens or full model prompts in audit logs.

### 3.2 SQLite, migrations and synchronization
- Verify per-connection settings for `foreign_keys`, WAL mode, busy timeout, connection lifecycle, transaction semantics, migration ledger/checksum, indexes and backups.
- SQLite WAL supports concurrent readers with a single-writer model; **WAL + UUIDs do not enable distributed multi-writer operation**. Do not promise peer-to-peer multi-writer safety just because IDs are UUIDs.
- Do not blindly convert the existing schema's integer IDs to UUIDs. First map all foreign keys, serialized IDs, API contracts, fixtures, imports, sync records and migrations. Prefer additive schema evolution. If identity conversion is essential, plan expand/backfill/verify/contract, provide tested backup/rollback, and validate all references before dropping legacy fields.
- Define the sync consistency model before building it: coordinator/authoritative writer or explicitly designed merge strategy; stable event IDs; idempotency; version vectors/revisions as applicable; tombstones; encryption; replay protection; schema negotiation; retry/backoff; quarantine; acknowledgment; reconciliation and operator-visible conflicts. Never silently last-write-wins financial, attendance, exam, identity or payroll records.
- Back up SQLite consistently while handling WAL, verify restore drills, and never commit database files or institutional production data to Git.

### 3.3 Accounting and source-of-truth rules
- Use integer minor currency units (paise) or exact decimal values with documented rounding; do not use binary floating-point `REAL` for authoritative balances.
- Posted journal entries must balance per currency, be immutable, and be corrected through reversal/adjustment entries. Enforce fiscal-period rules and approval permissions. Reconcile invoice totals, allocations, receipts, credits/refunds, outstanding dues, ledgers, trial balance and statements independently.
- Idempotency and transaction boundaries are mandatory for enquiry conversion, admission numbering, payment callbacks, receipts, device punches, imports, payroll runs, document issuance, notification sends and sync events.
- Treat all sample numbers/names/IDs in supplied narrative as illustrative, not production data or known truth. Recalculate sample arithmetic independently. For example, the sample August payroll values in the specification do not exactly reconcile arithmetically; implement assertions and use actual test fixtures, never copy those values into authoritative behavior.

### 3.4 Air-gapped/offline feature truthfulness
- Define separately: fully local/air-gapped, LAN-connected, and WAN-connected/hybrid deployments. A feature may be available only in some modes and must show that honestly.
- WhatsApp, SMS gateways, external email/push providers, online payment providers, public websites, hosted live sessions, remote GPS maps and central cloud sync inherently require external connectivity or service availability. In offline mode queue the work durably, show `PENDING`/`FAILED` accurately, offer a valid local/manual alternative where feasible, and reconcile only after confirmed results. Never state a payment or message was successful merely because it was queued.
- In `LOCAL_ONLY`/air-gapped mode, disable cloud model providers and block unauthorized outbound traffic. Verify with configuration and tests, not only UI labels. Local video/media and LAN local website operation must be separately specified.
- RAM, TTFT, token throughput, sub-10ms retrieval, installer duration and other performance figures in the supplied document are **targets to benchmark**, not acceptance facts. Publish results only with named hardware, data sizes, commands and methodology.

### 3.5 Local AI must remain advisory and validated
- Structured JSON grammar is not a truth guarantee. Validate output through typed schemas **and** business rules, source provenance, valid IDs/enums, authorization and deterministic checks.
- A model must not directly post a journal, finalize marks, approve admission, change payroll, bypass timetable constraints, decide discipline, or automatically deny services based on predicted fee risk.
- Timetable generation needs a deterministic constraint solver and post-solve hard-constraint validation. The SLM can suggest candidate explanations, not override verification.
- Treat exam questions/report remarks as drafts requiring policy-compliant review. Any payment/finance/payroll/exam action needs deterministic service validation and required human approval.
- Missing model, timeout, cancellation, empty retrieval, malformed output, model mismatch or provider failure must be visible and recoverable. Never present mock or canned output as real inference in production. Prompts and retrieved documents are untrusted input; defend against prompt injection and data exfiltration.

### 3.6 Privacy, children, biometrics and uploads
- Minimize student/guardian data. Do not store full Aadhaar/national-ID numbers or sensitive medical notes unless a documented lawful need and appropriate authorization, retention and protection exist; prefer masked/tokenized identifiers where possible.
- Face recognition/biometrics must be feature-gated, institution-approved, legally reviewed, secured at rest/in transit, retention-controlled, and accompanied by a practical manual/non-biometric path. Do not silently enable recognition on arbitrary camera streams.
- Apply strict MIME/content/size limits, safe names, virus/content inspection where feasible, private storage, access checks and deletion policy to profile photos, HR documents, CMS assets, curriculum material and generated documents.
- Redact private data from logs, crash reports, test fixtures, screenshots, CI artifacts and support tickets. Use synthetic data exclusively in automated tests.

### 3.7 No silent failures/dead ends
Every workflow must have valid initial and terminal states; define success, failure, retry, cancellation, timeout, rejection, reconciliation and escalation. No button without behavior, form without persistence, endpoint with fake success, background task stuck indefinitely, upload silently failing, payment without reconciliation, lock bypass, or offline event disappearing without an actionable state.

## 4. Dependency-aware phase plan

The order below is recommended. At Phase 00 the agent must verify current features and may mark already-complete requirements as verified instead of rebuilding them. A phase may be split into smaller checkpoints, but not skipped. Any reordering needs a written dependency rationale in the decision log.

### Phase 00 — Discovery and independent baseline
**Work:** Map entrypoints, package structure, registered routers, identity/auth/RBAC, tenant scoping, migration runner/schema, services, UI/bridge, SLM/RAG invocation, async jobs, sync/outbox, payment workflow, document storage, installer, tests and CI. Reconcile documentation with code. Capture current commit and Git state. Run baseline commands unchanged.

**Artifacts:** `REPOSITORY_MAP.md`, `BASELINE_REPORT.md`, initial `FEATURE_TRACEABILITY.md`, `PHASE_00_PLAN.md`.

**Exit gate:** Existing behavior and schema are mapped; important unknowns and incomplete workflows are listed with source links; baseline tests were run or honestly labelled `BLOCKED`/`NOT_RUN`. No feature implementation starts before this record.

### Phase 01 — Requirements traceability, threat model and architecture decisions
**Work:** Add one row for every requirement in Section 5. Record decisions for tenant/branch hierarchy, authentication, money precision, ledger posting/period close, offline modes, sync consistency, hardware adapters, external integrations, local AI approval gates, backup/restore, module flags and biometrics. Threat-model tenant breakout, IDOR, malicious uploads, private DB theft, replayed device punches/webhooks, QR forgery, sync replay/conflicts and child-record exposure.

**Exit gate:** Every requirement has explicit current status and disposition. No unresolved architecture conflict blocks foundation changes; risky decisions have recorded rationale and test strategy.

### Phase 02 — Shared identity, tenancy, permissions and audit foundation
**Work:** Harden or extend organizations, branches, sessions, identity, branch grants, role/permission assignments, server-derived scope, audit event conventions, common validation and migration safety. Review uniqueness/foreign keys/indexes and seed behavior. Preserve legacy IDs unless safely proven necessary to change.

**Tests:** Missing/invalid tokens; branch header spoofing; inactive branch; cross-tenant list/read/write/export; role escalation; parent-to-unrelated-child access; duplicate codes; concurrent allocation; supported-schema migration and restore.

**Exit gate:** Server denies ungranted scope across all affected routes/services; migration/recovery has isolated evidence; audit records sensitive actions without sensitive payload leakage.

### Phase 03 — Admissions, lead CRM and student lifecycle
**Work:** Enquiry capture sources, dedupe, counselor, follow-up tasks/SLA, status/prioritization, conversion tracking; six-step guided intake; academic session/class/section/category; student legal profile, prior school, photo capture/upload, contacts/address/emergency details; guardians and sibling relationships; only necessary health/identity fields; configurable admission/roll sequence; fee group assignment through canonical finance services; resumable drafts and safe cancellation.

**Tests:** Required fields, duplicate leads, parallel admissions/sequence race, invalid class/section, upload tampering/limits, sibling permissions, interrupted form recovery, conversion retry, invoice failure rollback and scope authorization.

**Exit gate:** Enquiry-to-student conversion is atomic/idempotent, generated numbers obey documented scope/uniqueness rules, and failure cannot leave a false “admitted” result or half-linked finance record.

### Phase 04 — Financial core: billing, double-entry accounting and reconciliation
**Work:** Chart of accounts, account types, fiscal periods, journal headers/lines, posting and approval controls, cash/bank, income/expense/transfer vouchers, fee plans/groups, invoices/line items, discounts/waivers, payments/receipts, split/partial payment allocations, credits/refunds/reversals, day book/general ledger/trial balance/balance sheet/income-expenditure statements, due/overdue/defaulter reports and reconciliation. Build shared charge interfaces for facilities, POS, fines, transport and hostel/mess billing.

**Tests:** Unbalanced journal rejected; balanced post; precision/rounding; partial and overpayments; duplicate callbacks; receipt allocation idempotency; refunds/reversals; period close; concurrent allocations; branch isolation; independently recomputed report totals and transaction rollback.

**Exit gate:** Posted journals always balance, financial correction is append-only/reversible, invoice and ledger reconciliations agree, and status `PAID` requires payment evidence. Financial data is not calculated through floats or sample constants.

### Phase 05 — Attendance engine and hardware adapters
**Work:** Manual register, bulk present/absent with confirmation/undo, QR kiosk, RFID adapter, biometric vendor adapters, device enrollment/authentication, punch normalization, local timestamps/timezones, duplicate filtering, mapping from hardware IDs to entities, shift/late/half-day rules, approved leave reconciliation, correction review/audit, reports and payroll input. Buffering must be bounded, observable and recoverable.

**Tests:** Duplicate/out-of-order punches, reconnect, bad packet, untrusted LAN sender, unknown ID, clock skew, daylight/date boundary, database busy/restart, queue full/backpressure, missing device, corrections and repeat delivery.

**Exit gate:** Punches are durable and idempotent, errors and unknown identities are visible, manual attendance works without devices. Real vendor/hardware tests are `BLOCKED` unless actually performed; no zero-packet-loss claim without a measurement.

### Phase 06 — Academics, timetable solver and substitutions
**Work:** Sessions, classes/sections, subjects, classrooms/labs and capacity, teacher qualification/availability/workload, bell periods/breaks, fixed periods, hard/soft constraints, solver, unsatisfiable input diagnostics, conflict reports, authorized manual override, published schedule versions and rollback. Detect absent faculty from attendance/leave, identify qualified available substitutes, balance load and distribute one canonical schedule to relevant portals.

**Tests:** Teacher/room clashes, capacity, teacher availability, workload ceilings, lab requirement, fixed break, no-solution cases, solver timeouts, deterministic behavior, substitute eligibility and override audit. Always validate hard constraints after solving.

**Exit gate:** Solver returns a hard-constraint-valid schedule or an actionable “no feasible solution” result; no conflicting schedule can be published; updates have version and rollback history.

### Phase 07 — Exams, marks moderation, results and report cards
**Work:** Assessment schemes and weights, grading/co-scholastic rubrics, date sheets, rooms/seats/admit cards, validated marks grid/import, absent/exempt states, teacher submission, HOD/admin review, variance flags, approval/lock/reopen permissions, grade/result calculation, rank/tie policy, statistics, remarks, A4/A3/12x18 print layouts and student 360 reports sourced from canonical attendance/homework/results.

**Tests:** Negative/out-of-range scores; invalid max; missing/duplicate marks; weighted rounding; absent vs zero; exempt; ties; failed import rollback; concurrent edits; lock bypass; audited reopen; report arithmetic; page layout and permission checks.

**Exit gate:** One tested calculation service feeds APIs, reports, rankings and printouts. Locked marks cannot be changed by bypassing the approved correction flow.

### Phase 08 — Staff directory, leave and payroll
**Work:** Staff details and document permissions, departments/designations/qualifications, leave types/quotas/balances/applications/approval, configurable salary components, allowances/deductions, loans/advances and recovery, attendance reconciliation, payroll draft, variance review, approvals/lock, payslip/PDF generation, bank export and payment reconciliation. Legal/statutory rules must be policy-configured and reviewed for the deployment jurisdiction.

**Tests:** Exact gross-to-net arithmetic, rounding, leave quota/overlap, loan caps, leave-attendance interaction, staff eligibility, payroll rerun idempotency, concurrent lock/approval, locked edit prevention, payslip access, masked export, payment reconciliation and correction/reversal.

**Exit gate:** Payroll is deterministic, auditable and locked; “paid” reflects verified evidence, not a UI action; statutory assumptions are documented instead of invented.

### Phase 09 — LMS/course delivery
**Work:** Course catalog, versioned modules/chapters, approved files, offline video/media caching, notes/PDFs, enrollment and entitlement, coupons with eligibility/expiry/limits, lesson progress, live-class schedule metadata, assignments, quizzes, auto-grade rules, submission history and chapter Q&A/teacher responses. Reuse existing course, curriculum, RAG and assessment models where possible.

**Tests:** Enrollment/access rules, expired/reused coupons, file validation, corrupt/missing offline asset, quiz score and resubmission policy, teacher reply authorization, content versioning, approval, revocation and RAG deletion/re-index.

**Exit gate:** Teacher can publish approved course content; an eligible learner completes a lesson/quiz; persisted results appear to the authorized teacher/student. An offline placeholder must not claim that a live hosted class occurred.

### Phase 10 — Campus facilities
**Work:** Transport vehicles/documents/drivers/routes/stops/fuel/maintenance/fees/GPS adapter; hostel buildings/rooms/beds/allocation/mess menus/roll calls/visitors/outpasses and charges; library catalog/copies/barcodes/issue-return/reservations/fines; suppliers, purchase orders, receiving, stock movement, store issue, POS/sales/returns/reorder alerts; visitor/gate-pass issuance/approvals/expiry; alumni directory/events/privacy. All charges post through the canonical finance service.

**Tests:** Vehicle/route conflict, unavailable GPS, protected location data, double bed allocation, stock below zero, purchase idempotency, POS refund, barcode collision, due-fine calculation, gate pass expiry/revocation, visitor visibility, billing rollback and ledger reconciliation.

**Exit gate:** Each enabled workflow has persistent records, RBAC, audit, recovery and finance linkage when chargeable; optional module disablement does not corrupt shared records or bypass APIs.

### Phase 11 — Document/ID card visual designer and QR verification
**Work:** Versioned visual canvas, elements and layout rules, safe dynamic-token allowlist, image/photo/signature assets, QR codes, fonts, borders, page size/orientation/margins, preview and print/PDF renderer. Cover student/staff IDs, admit cards, TC, bonafide, character, merit certificates, invoices and receipts. Verification QR must be signed or resolve an opaque unguessable ID server-side; never embed sensitive student data in clear text.

**Tests:** Dynamic token escaping/injection, missing fields, Unicode/fonts, image bounds, print sizes, template rollback, signature permission, QR tampering, revoked/reissued document, access checks and file path traversal.

**Exit gate:** All claimed document types render authorized real records with tested page dimensions; verification detects tampering/revocation while returning only approved fields.

### Phase 12 — Messaging, notifications, queues and helpdesk
**Work:** Versioned templates; recipient filtering by authorized branch/class/section/route/department; WhatsApp Business, SMS, email and push adapters; absence/fee/birthday/notice events; durable notification outbox, schedule/timezone, retry/backoff/rate-limit/dead-letter, provider callbacks and delivery receipts; consent/suppression rules; parent/staff support tickets, categories, SLA assignment/escalation/resolution history. Provide local in-app notices for air-gapped environments.

**Tests:** Wrong recipient, duplicate send/callback, offline provider, timeout, retry storm, invalid template, rate limit, consent/suppression, timezone boundary, private log redaction, SLA escalation and cross-branch protection.

**Exit gate:** Every message has truthful queued/sent/delivered/failed status with retries and support traces. Live-provider verification is blocked until real configured sandbox/provider tests occur; no false delivery claim.

### Phase 13 — Public institution CMS and protected forms
**Work:** Page/landing builder, banners, vision/mission, news/events/calendar, galleries, downloads, testimonials/FAQs, faculty directory and careers listings; draft/review/preview/scheduled publish/unpublish/version/revert. Public admission/contact/career forms should submit to canonical CRM/HR services with spam protection and privacy notice. Sanitize content and validate media.

**Tests:** XSS/unsafe markup, upload type/content limits, unauthorized draft preview, publish schedule/cache invalidation, abuse/rate limit, duplicate form submission, attachment privacy, and protected admin routes.

**Exit gate:** An authorized editor can preview, publish and revert; public submissions reliably appear in the right CRM/HR queue and do not expose private records.

### Phase 14 — Custom fields, navigation, modules and multi-branch governance
**Work:** Safe no-code form fields and required/optional rules, field types, validation, ordering, version compatibility and migration of old records; menu order/labels; module flags/entitlements; granular read/create/update/approve/post/lock/reopen/export permissions; authorized branch picker; multi-session and group dashboards; searchable audit log. Never execute user-supplied code or interpolate arbitrary SQL for configurable fields.

**Tests:** Existing record compatibility on schema changes, invalid field definitions, malicious field names, hidden-module direct API access, permission inheritance, branch switching, group aggregate isolation, audit changes and rollback.

**Exit gate:** Configuration is versioned, validated, permissioned and reversible. Hiding UI menus is never treated as authorization.

### Phase 15 — Local SLM and RAG operational assistant
**Work:** Use the actual configured local model and existing RAG. Model identity/version/checksum, timeouts/cancellation, local-only provider enforcement, retrieval provenance, schema and business validation, exam-paper drafts, report remarks, timetable suggestions and explainable arrears/workflow signals. Add human approval for sensitive workflows, record model output source and prompt policy, and keep operational systems deterministic.

**Tests:** Model missing/mismatch, invalid grammar/JSON, schema-valid but wrong output, empty/conflicting retrieval, malicious documents/prompt injection, timeouts, cancelled generation, repeated run, unauthorized data in context, outbound-network prohibition and output validation.

**Exit gate:** Real model execution is distinguishable from mocks; AI produces validated, reviewable suggestions and cannot make unapproved financial/academic/payroll decisions. Performance claims are based on benchmarks.

### Phase 16 — Admin, teacher, student, parent portals and desktop UX
**Work:** Connect every portal to canonical authorized APIs; responsive/touch-friendly layout, parent multi-child switcher, session/auth expiry, role-aware nav, dashboard summaries, loading/empty/error/success/retry states, pagination/search, localization and accessibility. Verify PySide6/WebEngine asset caching, IPC bridge, native printing and capability detection.

**Tests:** End-to-end personas, mobile and desktop viewport smoke, keyboard navigation, expired/revoked session, stale API response, missing local asset, API offline, unauthorized child switch, duplicate form submit, file and print failure.

**Exit gate:** No primary UI action is a no-op; every success is based on persisted API result; every unavailable integration is clearly explained with a next step.

### Phase 17 — Offline install, backups, restore, sync and operations
**Work:** Installation preflight/setup, local-only mode, safe secrets/config, startup/liveness/readiness, log rotation, database migration/rollback, backup/restore UI and runbooks, upgrade procedure, asset/model integrity checks, offline dependency packaging, Windows/Linux support matrix and optional sync. Implement approved sync design only, with durable outbox, idempotent receive, reconciliation, quarantines and conflict UI.

**Tests:** Cold start offline, blocked WAN egress in air-gap mode, app/OS crash recovery, WAL backup during use, restore in a clean environment, backup corruption, failed upgrade/rollback, full disk, SQLite busy, schema mismatch, repeated/out-of-order sync, conflicting accounting write and machine/node identity change.

**Exit gate:** Fresh install, upgrade, backup/restore and offline core workflows have reproducible evidence. Conflicts remain visible; sync guarantees and limits are documented. Cloud/provider-only capabilities are not advertised as offline.

### Phase 18 — Full end-to-end acceptance, security, performance and release
**Work:** Cross-module acceptance, data reconciliation, tenant authorization matrix, dependency and secret scanning, accessibility, load/resource benchmarks, packaged install, migration, backup/restore and incident/recovery runbooks. Re-run tests independently instead of trusting prior audit or CI claims.

**Minimum E2E journeys:**
1. Enquiry → intake → parent/sibling → fee group → invoice → receipt → balanced ledger → parent portal.
2. Staff/student roster → attendance → reviewed correction/leave → reports/payroll input → approved payroll → payslip/payment reconciliation.
3. Timetable constraints → valid solver output → publish → teacher absent → substitute → same schedule across portals.
4. Exam setup → marks import/entry → moderation → lock → report PDF → authorized parent view/revocation.
5. Course creation → safe source ingest/approval → learner enrollment → lesson/quiz → grading → progress report.
6. Facility/POS/fine → approved charge → invoice/ledger → refund/correction trail.
7. Template design → actual document → QR verify → revoke/reissue.
8. CMS draft → preview/publish → public application → correct CRM/HR queue.
9. Notification queued offline → provider returns → callback reconciled → truthful delivered/failed state.
10. Local AI/RAG suggestion → validation → human approval → authorized persisted action and audit trail.
11. Restore a backup into a clean environment and verify schema/references/record counts/journal balances.
12. Attempt cross-branch and cross-role access throughout all sensitive domains and verify denial.

**Exit gate:** All applicable tests and evidence complete; no unresolved P0/P1; production release checklist and rollback/recovery verified. Any unavailable hardware, provider, operating system, or full air-gap check remains clearly blocked and limits product claims.

## 5. Complete requirement inventory / traceability

Create `docs/erp_agent/FEATURE_TRACEABILITY.md` with columns: ID, requirement, existing source location, disposition (`VERIFIED_EXISTING`, `IMPLEMENT`, `FIX`, `DEFER_WITH_REASON`, `BLOCKED`), service/API/UI, tests/evidence, status, blocker, release criticality. Every checkbox below must map to implementation and tests; a checkbox alone is not completion.

### A. Admission and CRM
- [ ] Walk-in/phone/website enquiry; source tracking, deduplication, counselor assignment, follow-up SLA, status, priority and conversion history.
- [ ] Six-step intake: admission/class; student details; contact/address; parent/guardian; approved health/identity; fee assignment.
- [ ] Student legal profile, session/class/section/category, previous school, photo capture/upload with size/content validation.
- [ ] Multi-contact guardians, emergency contact, siblings and relationship-safe parent portal access.
- [ ] Data minimization, privacy notice/consent where applicable, access and retention controls.
- [ ] Configurable admission/roll numbering, branch/session rules, concurrent sequence safety and duplicate prevention.
- [ ] Fee group/invoice connection to finance; atomic and idempotent enquiry conversion; save/resume/cancel paths.

### B. Attendance and hardware
- [ ] Manual classroom register, all-present action, review/undo and corrections with audit.
- [ ] QR kiosk and ID-card association.
- [ ] RFID serial/Ethernet interface, authentication and packet deduplication.
- [ ] Biometric SDK/device adapters and a tested compatibility matrix.
- [ ] Shift, late-arrival, half-day, duty-hour, leave and payroll mapping policies.
- [ ] Student/staff attendance summaries and attendance-triggered notification jobs.
- [ ] Optional face recognition, explicit privacy gate, local handling and manual alternative.
- [ ] Durable/bounded event queue, backpressure, device status, replay and no fabricated punches.

### C. Academics and LMS
- [ ] Academic session, class/section, subject, rooms/labs, capacities and teacher qualifications/assignments.
- [ ] Timetable solver with hard/soft constraints and impossible-schedule explanation.
- [ ] Versioned publish/rollback and absent-teacher substitution/workload balancing.
- [ ] Catalog, chapter lessons, media/offline cache, notes, enrollment and progress.
- [ ] Coupon rules, limits, expiry, entitlement and access revocation.
- [ ] Live-class scheduling/integration with honest connectivity/availability status.
- [ ] Assignments, quiz scoring, submissions, Q&A, teacher replies and content version approval.

### D. Exams and reporting
- [ ] Board/school exam schemes, term weightings, grade scales and co-scholastic rubrics.
- [ ] Date sheet, seating/room allocation, admit cards and printable formats.
- [ ] Entry/import validation, absent/exempt states and safe rollback.
- [ ] Teacher submit → department review → admin lock/reopen workflow with audit.
- [ ] Result, weighted marks, ties/ranks, class/subject statistics and independently verified arithmetic.
- [ ] A4/A3/12x18 report output; PDF fonts/layout/access control.
- [ ] 360 student reports aggregating canonical academic, attendance, homework and approved behavior records.

### E. HR and payroll
- [ ] Staff directory, qualifications, role, documents and restricted attachment access.
- [ ] Leave types, annual quotas, overlap, approval, balances and attendance reconciliation.
- [ ] Salary components, allowances/deductions, loans/advances and configurable statutory rules.
- [ ] Draft, variance review, approval/lock, payroll calculation, payslip and payment reconciliation.
- [ ] Immutable payroll history, audited correction/reversal, exact arithmetic and masked exports.

### F. Finance
- [ ] Chart of accounts, accounting periods, journal/voucher posting and approval.
- [ ] Double-entry ledger, day book, general ledger, trial balance and financial statements.
- [ ] Fee structure/groups, invoices, discounts/waivers, partial/multiple payments, allocation, refunds and reversals.
- [ ] Due/overdue/defaulter calculation, reminders and reconciliation.
- [ ] Transport/hostel/mess/library fines/inventory/POS connected to canonical finance service.
- [ ] Idempotency, permissions, closed-period policy, audit and independent arithmetic checks.

### G. Facilities
- [ ] Fleet, vehicle/driver, routes/stops, fuel, maintenance, fee and optional GPS adapter.
- [ ] Hostel/room/bed, allocation, outpass, visitor log, roll call, mess/menu and charge linkage.
- [ ] Library catalog/copies/barcodes, issue/return, reservations and overdue fines.
- [ ] Store, supplier, PO, receiving, inventory movement, internal issue, POS/returns/reorder alert.
- [ ] Visitor check-in/out and time-bound gate-pass approval/revoke/expiry.
- [ ] Alumni directory, registration, events and privacy-controlled communications.

### H. Documents and messaging
- [ ] Canvas designer, versioned templates, safe dynamic tokens, photo/signature assets, QR and print layout.
- [ ] Student/staff ID, admit card, TC, bonafide, character, merit, invoice and receipt outputs.
- [ ] Tamper/revocation verification, no sensitive clear-text QR payload and authorized lookup.
- [ ] WhatsApp/SMS/email/push adapters, template lifecycle, targeting, durable outbox, retry and provider callbacks.
- [ ] Absence, fee, birthday and notices with timezone/consent/suppression controls.
- [ ] Parent/staff support ticketing, categorization, SLA, escalation and resolution.
- [ ] Local notice alternative and truthful offline/provider pending/failed status.

### I. CMS and system governance
- [ ] Pages/landing builder, banners, news/events/calendar, galleries, downloads, testimonials, FAQ, faculty and careers.
- [ ] Draft/preview/review/schedule/publish/unpublish/version/revert and sanitized public assets.
- [ ] Abuse-protected public admissions/contact/job forms connected to canonical CRM/HR services.
- [ ] Custom field builder with safe types, validation, versioning and existing-record compatibility.
- [ ] Menu ordering and module toggles enforced by server permissions, not UI hiding alone.
- [ ] Branch/session/group governance and searchable protected audit trail.

### J. AI, portals and operation
- [ ] Real local model identity/health/checksum, no-cloud enforcement and benchmark evidence.
- [ ] Scoped RAG ingest/retrieve/source provenance/version/delete/re-index and empty-result behavior.
- [ ] Exam/question drafts, remarks, timetable suggestions and explainable follow-up indicators.
- [ ] Structured-output validation, business-rule checks and human approval for sensitive actions.
- [ ] Admin/teacher/student/parent portals and PySide6/WebEngine integration.
- [ ] Local/air-gapped core workflows and durable queued external features.
- [ ] Installer, backup/restore drill, schema migration/rollback, packaging and operations runbooks.
- [ ] Cross-module E2E, tenant boundary security, accessibility, resilience, load and release evidence.

## 6. API, workflow, UI and testing standards

Every workflow must document and test:
- Actor/role and exact permissions for read, create, update, approve, post, lock, reopen, export and delete.
- Initial state, legal transitions and terminal states, including failed, rejected, cancelled, expired, retry and reconciliation.
- Canonical data entities, ownership/tenant keys, constraints, indexes, transaction boundaries, audit and retention.
- Input/output schemas, safe bounds, pagination/ordering allowlists, upload checks and safe error responses.
- Idempotency for operations vulnerable to retry or duplicate events.
- UI-to-API contract and evidence that the client consumes actual persisted results.
- Actionable error/recovery UX for validation, forbidden, stale/conflicting state, network/provider outage and permanent failure.
- Unit, integration, API authorization, migration, UI/end-to-end and failure-injection tests appropriate to risk.
- Logs/metrics with correlation IDs but no secrets, unnecessary personal data or full prompts.

Use existing repository conventions after verifying them. Keep business rules in established service/domain boundaries, not duplicated in routes or UI. Test actual configuration and production-mode defaults. Mocks are permitted for isolated unit/provider tests but must be isolated and impossible to select accidentally in production.

## 7. Progress artifacts, statuses and reporting

Maintain these files without overwriting useful historical QA artifacts:
- `docs/erp_agent/MASTER_PROGRESS.md` — phase/task status and next safe action.
- `docs/erp_agent/REPOSITORY_MAP.md` — actual code/integration map.
- `docs/erp_agent/BASELINE_REPORT.md` — environment, commit and actual validation results.
- `docs/erp_agent/FEATURE_TRACEABILITY.md` — all requirements mapped to source/tests.
- `docs/erp_agent/plans/PHASE_NN_PLAN.md` — written before source changes.
- `docs/erp_agent/reports/PHASE_NN_REPORT.md` — changes, outcomes, risks, evidence.
- `docs/erp_agent/regressions/PHASE_NN_REGRESSION.md` — tests and exact outcomes.
- `docs/erp_agent/evidence/commands/` and `logs/` — sanitized proof artifacts.
- `docs/erp_agent/DECISIONS.md` — dated decisions/rationale.
- `docs/erp_agent/BLOCKERS.md` — dependency, impact, owner/action and exit condition.

Allowed task statuses: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `FAILED`, `PASSED`, `REOPENED`, `NOT_APPLICABLE`. Do not use `PASSED` for commands not executed. Record exact test command, exit code, pass/fail/skip counts, runtime, environment and log path. A phase with missing evidence stays blocked/not run, and the missing proof must be actionable.

## 8. Definition of Done (per phase)

- [ ] Requirements and existing code mapped; sound functionality reused.
- [ ] Written plan and test plan created before implementation.
- [ ] Real workflow completes end to end or capability is explicitly disabled/deferred.
- [ ] Regression tests cover the defect/feature and relevant failure cases.
- [ ] Tenant, branch, role and object-level authorization tests pass.
- [ ] Persistence, rollback, idempotency, audit and external status verified.
- [ ] No silent failure, mock success, hardcoded authoritative sample or dead-end UI.
- [ ] Migration forward and recovery/restore path tested in isolation.
- [ ] Focused, module and full available regression checks recorded.
- [ ] Security, privacy, accessibility and performance impact reviewed.
- [ ] Docs, traceability, progress, runbooks and remaining limitations updated.
- [ ] Diff inspected for weakened tests, secrets, unrelated changes and false-success paths.
- [ ] Phase report links evidence and names residual risks.
- [ ] Coherent commit created; status updated only after the gate.

## 9. Production release blockers

Release is blocked by any confirmed or unresolved P0/P1 issue involving cross-tenant/branch data exposure, authentication/authorization bypass, protected attachment leak, child data privacy, unbalanced/duplicated accounting, fake payment success, corrupted/hidden mark changes, lost authoritative attendance/payroll/sync records, unvalidated AI mutation of sensitive state, production mock activation, silent persistence failure, secret/PII leakage, failed backup/restore, irrecoverable migration or misleading claims about integrations not tested.

## 10. First actions for the coding agent

1. Read this contract alongside the existing README, DEVELOPMENT.md, architecture/security/privacy/data-model/testing/deployment docs, prior QA plans, all migrations, routes/services/UI clients and CI.
2. Create `docs/erp_agent/plans/PHASE_00_PLAN.md` before source edits.
3. Capture commit, Git status, environment and real baseline checks.
4. Build repository map and feature traceability against current source; do not assume the illustrative tables/endpoints/performance claims in the proposal are correct for this codebase.
5. Identify the smallest dependency-safe implementation slice and document it in a phase plan.
6. Implement, test, debug, regress and record proof before marking that phase passed.
7. Continue automatically through the remaining safe phases and update the master tracker on each gate.

**Success means correct, durable, secure and tested institutional workflows—not a long checklist, a large diff, or a green badge.**
