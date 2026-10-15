# GAYATRI-ERP — Authoritative Architecture Decisions Register

**Document:** `docs/erp_agent/DECISIONS.md`  
**Contract Reference:** [`../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Execution Phase:** Phase 01 — Traceability, Threat Model and Architecture Decisions  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## DEC-000 — Existing Repository is Authoritative Implementation Baseline
- **Date:** 2026-10-15
- **Status:** APPROVED & VERIFIED
- **Decision:** Inspect and extend the existing Python/FastAPI/SQLite/PySide6 repository rather than treating it as a greenfield project or transplanting a foreign ERP framework.
- **Rationale:** The repository contains 16 verified migrations, 38+ registered routers, and 1,775 passing tests covering core academic, admission, attendance, finance, HR, LMS, and portal workflows. Rebuilding would introduce regression risks and duplicate sources of truth.
- **Verification:** Phase 00 Baseline Report and Repository Map (`BASELINE_REPORT.md`, `REPOSITORY_MAP.md`).

---

## DEC-001 — Tenant & Branch Scope Must Be Authorized Server-Side
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** Client-provided headers (`X-Branch-ID`, `X-Org-ID`) or query parameters are never accepted as proof of authority. The authenticated principal's granted organizations, branches, and roles are resolved strictly server-side from JWT claims and database grants. A client header may select only among already-granted scopes.
- **Rationale:** Prevents horizontal privilege escalation and cross-tenant IDOR attacks.
- **Verification:** `tests/test_qa_phase08_security_adversarial.py` and `central_platform/auth/dependencies.py`.

---

## DEC-002 — SQLite Concurrency & Synchronization Consistency Model
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** SQLite with WAL mode supports concurrent readers with a single writer; UUID primary keys and WAL do NOT provide distributed multi-master peer-to-peer write safety. For multi-branch or edge synchronization, the central platform acts as the authoritative coordinator. Edge nodes push signed mutation events into an idempotent outbox with sequence numbers and payload hashes. Conflicting concurrent writes are quarantined with operator-visible conflict logs.
- **Rationale:** Avoids silent data corruption or loss in financial, attendance, or exam marks data.
- **Verification:** `central_platform/sync/service.py` and `tests/test_qa_phase09_workflows_sync_integrity.py`.

---

## DEC-003 — Exact Financial Arithmetic, Paise Minor Units & Append-Only Ledgers
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** Authoritative balances, fee payments, concessions, and payroll calculations must use minor currency units (paise as integers) or exact decimal representations with documented banker's/half-even rounding. Binary floating-point `REAL` columns are prohibited for financial balance calculations. Financial entries in `financial_ledger_entries` are immutable and append-only. Corrections require explicit debit/credit reversal vouchers.
- **Rationale:** Eliminates IEEE-754 precision drift, off-by-one errors, and audit trail manipulation.
- **Verification:** `central_platform/finance/service.py` and `tests/test_qa_phase03_finance_integrity.py`.

---

## DEC-004 — Cloud Integrations & Air-Gapped Mode Truthfulness
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** In `LOCAL_ONLY` or air-gapped environments, cloud AI providers, SMS gateways, WhatsApp Business APIs, and remote live streams are disabled. External message dispatches and payment webhooks must be queued in a durable outbox with truthful `PENDING`/`QUEUED`/`OFFLINE` statuses. The UI must never display a fake "Sent" or "Paid" toast without cryptographic/provider delivery receipts.
- **Rationale:** Ensures institutional integrity and complies with strict air-gapped security contracts.
- **Verification:** `central_platform/notifications/queue.py` and `tests/test_qa_phase14_e2e_product_acceptance.py`.

---

## DEC-005 — Local SLM Outputs Remain Strictly Advisory for Consequential Workflows
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** Output from local quantized SLMs or cloud LLMs is treated as untrusted input. Neural output is forbidden from directly posting accounting ledgers, finalizing student marks, approving admissions, modifying payroll, or deciding disciplinary actions. All AI suggestions require deterministic Pydantic schema validation and authorized human review/approval before state mutation.
- **Rationale:** Protects educational and institutional records from hallucinations, jailbreaks, or non-deterministic drift.
- **Verification:** `central_platform/ai/adapters.py` and `tests/test_qa_phase02_ai_execution_integrity.py`.

---

## DEC-006 — Child Data Privacy, Minimization & Biometric Opt-In Consent
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** Full national identity numbers (such as Aadhaar) and sensitive health diagnoses must not be stored in clear text; tokenized or masked representations are stored only when legally mandated. Parent visibility into student telemetry is strictly partitioned into 4 policy levels (`FULL_TRANSPARENCY`, `SUMMARY_ONLY`, `RESTRICTED`, `BLOCKED`). Facial recognition and biometric attendance require written institution consent and must always offer a manual, non-biometric alternative.
- **Rationale:** Compliance with international child online privacy laws (COPPA/GDPR-K) and DPDP Act.
- **Verification:** `central_platform/privacy/policies.py` and `tests/test_phase34_parent_privacy.py`.

---

## DEC-007 — Secure File Uploads, Path Containment & Content Inspection
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** All file uploads (student photos, RAG documents, CMS assets, certificates) must be validated against strict MIME allowlists, maximum byte limits, and sanitized filenames. Relative path traversals (`../`, `..\\`, null bytes) and zip bombs are blocked via `os.path.commonpath` boundary containment checks.
- **Rationale:** Prevents arbitrary file write, remote code execution, and disk exhaustion attacks.
- **Verification:** `central_platform/security/auditor.py` and `tests/test_qa_phase12_security_privacy_xss.py`.

---

## DEC-008 — QR Code Verification & Opaque Identifier Resolution
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** QR codes printed on student ID cards, admit cards, transfer certificates (TC), and receipts must never embed clear-text sensitive personal data. QR codes contain either an HMAC-SHA256 signed payload or an unguessable opaque verification ID that resolves through an authenticated server endpoint (`/api/v1/campus/certificates/{id}/verify`). Revoked documents return explicit `REVOKED` status.
- **Rationale:** Prevents document forgery, credential stuffing, and public data scraping.
- **Verification:** `central_platform/campus/service.py` and `tests/test_qa_phase14_e2e_product_acceptance.py`.

---

## DEC-009 — Webhook Idempotency & Transactional Boundary Protection
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** Ingestion of payment provider webhooks (Razorpay, UPI, Stripe) must occur within an isolated transactional boundary (`with db.transaction():`). An event is verified via HMAC signature, checked against a deduplication ledger (`payment_webhook_events`), and linked to the corresponding payment order before updating invoices and posting ledger entries. Duplicate webhooks return cached results without re-crediting balances.
- **Rationale:** Prevents double-crediting student accounts during network retries or replay attacks.
- **Verification:** `central_platform/finance/service.py:process_payment_webhook` and `tests/test_qa_phase03_finance_integrity.py`.

---

## DEC-010 — Database Backup, WAL Checkpointing & Isolated Restore Drills
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** SQLite backups must execute a WAL checkpoint (`PRAGMA wal_checkpoint(TRUNCATE)`) or use the online backup API before copying database artifacts. Disaster recovery procedures must be verified by restoring backups into clean temporary environments and verifying schema, foreign keys, and ledger checksums.
- **Rationale:** Prevents corrupted backups caused by capturing uncommitted WAL memory pages.
- **Verification:** `scripts/migrate_db.py` and `tests/test_qa_phase10_packaging_deployment.py`.

---

## DEC-011 — Server-Enforced Module Flags & Granular Permissions
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** Dynamic UI navigation hiding does not constitute security. If an institution disables the Hostel, Transport, or Biometrics module, the backend routes must immediately enforce `403 Forbidden` / `404 Not Found` for direct API requests. Granular permissions (`read`, `write`, `approve`, `post`, `lock`, `reopen`, `export`) are verified at the route dependency layer.
- **Rationale:** Eliminates API bypass where disabled features could be manipulated through direct HTTP requests.
- **Verification:** `central_platform/rbac/engine.py` and `tests/test_qa_phase08_security_adversarial.py`.

---

## DEC-012 — Hardware Adapter Abstraction & Simulated Test Boundaries
- **Date:** 2026-10-15
- **Status:** REQUIRED INVARIANT
- **Decision:** Hardware integrations (RFID serial/Ethernet readers, biometric SDKs, bus GPS trackers) must be designed with clean abstraction interfaces (`DeviceAdapterInterface`). In developer and CI environments without physical devices, simulated software drivers are executed. Physical hardware validation is honestly reported as `DEFER_WITH_REASON` / `BLOCKED`.
- **Rationale:** Maintains reproducible automated testing while preventing false claims of physical device verification.
- **Verification:** `central_platform/attendance/service.py` and `docs/erp_agent/BLOCKERS.md`.
