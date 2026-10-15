# GAYATRI-ERP — Threat Model & Security Risk Analysis

**Document:** `docs/erp_agent/THREAT_MODEL.md`  
**Contract Reference:** [`../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Execution Phase:** Phase 01 — Traceability, Threat Model and Architecture Decisions  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Threat Modeling Methodology

The threat model evaluates the Gayatri-ERP platform against the **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) focusing on the 8 mandatory threat vectors defined in the ERP transformation contract.

---

## 2. Threat Analysis & Mitigation Register

### 2.1 Threat Vector 1: Tenant Breakout & Header Spoofing
- **Description:** An authenticated user of Organization A injects `X-Branch-ID: org-b` or `organization_id=org-b` to read or modify Organization B's students, financial ledgers, or exam results.
- **STRIDE Category:** Elevation of Privilege / Information Disclosure.
- **Vulnerability Surface:** HTTP request headers, query parameters, route path variables.
- **Mitigation Architecture:**
  - Route dependencies (`get_current_user`, `_get_org_id`, `require_permission`) derive the tenant scope strictly from the cryptographically verified JWT payload and internal database user record.
  - Client headers (`X-Branch-ID`) are validated against the user's explicit branch grants list; any unauthorized or mismatching header is rejected with `403 Forbidden`.
  - Database access layer enforces `WHERE organization_id = :org_id` on all CRUD queries.
- **Verification Tests:** `tests/test_qa_phase08_security_adversarial.py:test_cross_tenant_isolation_attack_blocked`.

---

### 2.2 Threat Vector 2: Insecure Direct Object References (IDOR)
- **Description:** A student or parent guesses sequential or UUID identifiers of invoices, marks records, disciplinary notes, or other student profiles (`/api/v1/sis/students/{guessed_id}`).
- **STRIDE Category:** Information Disclosure / Tampering.
- **Vulnerability Surface:** Entity lookup endpoints (`/students/{id}`, `/invoices/{id}`, `/marks/{id}`).
- **Mitigation Architecture:**
  - All lookup queries combine the entity ID with the caller's authorized `organization_id`.
  - Parent endpoints strictly enforce the student-guardian relational table (`student_guardians`) to confirm that the requesting parent is authorized for that specific student ID.
  - Unlinked child access attempts return `403 Forbidden` / `404 Not Found`.
- **Verification Tests:** `tests/test_qa_phase12_security_privacy_xss.py:test_tenant_and_student_idor_boundaries`.

---

### 2.3 Threat Vector 3: Malicious File Uploads, Zip Bombs & Path Traversal
- **Description:** An attacker uploads a student profile image, RAG syllabus document, or certificate containing path traversal payloads (`../../../../etc/passwd` or `..\..\Windows\System32`), executable extensions (`.py`, `.exe`, `.bat`), or zip bombs.
- **STRIDE Category:** Tampering / Elevation of Privilege / Denial of Service.
- **Vulnerability Surface:** `/api/v1/rag/upload`, `/api/v1/sis/students/{id}/photo`, `/api/v1/cms/assets`.
- **Mitigation Architecture:**
  - `SecurityAuditor.audit_upload_filename()` sanitizes all filenames and rejects directory separators and null bytes (`%00`).
  - Target destination directories are validated using `os.path.commonpath([dest, base_dir]) == base_dir` to ensure containment.
  - Archive extraction verifies uncompressed byte size and file count limits before extraction.
  - MIME types are strictly verified against an allowlist (PDF, DOCX, PNG, JPEG, JSON).
- **Verification Tests:** `tests/test_qa_phase12_security_privacy_xss.py:test_file_upload_safety_validation`, `test_archive_safety_zip_bomb_and_path_traversal`.

---

### 2.4 Threat Vector 4: Private Database Theft & Unencrypted State at Rest
- **Description:** Physical theft or unauthorized local access to `gayatri_local.db` or backup files exposing passwords, JWT tokens, student marks, and financial data.
- **STRIDE Category:** Information Disclosure.
- **Vulnerability Surface:** Local filesystem, SQLite WAL files, backup archives.
- **Mitigation Architecture:**
  - Passwords are hashed with bcrypt and unique salts; clear-text passwords are never persisted.
  - Sensitive configurations and tokens are encrypted using AES-256-GCM via `GAYATRI_ENCRYPTION_KEY`.
  - Database backups use isolated, permission-restricted directories. WAL pages are flushed via `PRAGMA wal_checkpoint(TRUNCATE)` prior to copying.
- **Verification Tests:** `tests/test_qa_phase10_packaging_deployment.py:test_backup_restore_and_disaster_recovery`.

---

### 2.5 Threat Vector 5: Replayed Device Punches & Duplicate Payment Webhooks
- **Description:** Network interception or retry storms replay attendance biometric punches or payment gateway webhooks, causing fabricated attendance streaks or duplicate balance credits.
- **STRIDE Category:** Tampering / Repudiation.
- **Vulnerability Surface:** `/api/v1/attendance/records`, `/api/v1/finance/webhooks`.
- **Mitigation Architecture:**
  - Payment webhooks require HMAC-SHA256 signature verification matching provider shared secrets.
  - The deduplication ledger `payment_webhook_events` enforces unique constraints on `(organization_id, provider, event_id)` inside an atomic transaction. Duplicate events return cached results without re-crediting invoices.
  - Attendance punches require unique `(organization_id, class_id, student_id, date, session_type)` idempotency keys.
- **Verification Tests:** `tests/test_qa_phase03_finance_integrity.py:test_webhook_deduplication`, `tests/test_qa_phase13_performance_concurrency_recovery.py:test_payment_webhook_concurrent_race_deduplication`.

---

### 2.6 Threat Vector 6: QR Code Forgery & Certificate Tampering
- **Description:** A student or third party generates a counterfeit student ID, admit card, or transfer certificate (TC) with a fake QR code pointing to a malicious server or forged credentials.
- **STRIDE Category:** Spoofing / Tampering.
- **Vulnerability Surface:** Physical printed ID cards, admit cards, official certificates.
- **Mitigation Architecture:**
  - QR codes never contain clear-text PII.
  - Certificates are issued with a cryptographically generated verification ID (`OfficialCertificate.verification_code`) and signed with HMAC-SHA256.
  - The verification endpoint `/api/v1/campus/certificates/{id}/verify` queries the authoritative database; revoked or altered certificates return `INVALID` or `REVOKED`.
- **Verification Tests:** `tests/test_qa_phase14_e2e_product_acceptance.py` and `central_platform/campus/service.py:verify_certificate`.

---

### 2.7 Threat Vector 7: Offline Sync Replay, Out-of-Order Delivery & Silent Overwrites
- **Description:** A compromised or desynchronized edge node replays old state mutations, overwriting newer marks, attendance, or financial records on the central platform.
- **STRIDE Category:** Tampering / Repudiation.
- **Vulnerability Surface:** `/api/v1/sync/push`, `/api/v1/edge-sync/heartbeat`.
- **Mitigation Architecture:**
  - `sync_operations` tracks client device ID, monotonic sequence numbers, and payload hashes (`payload_hash`).
  - Out-of-order or duplicate operations are detected and rejected.
  - High-consequence conflicts (financial postings, locked exam marks) trigger automatic quarantine instead of silent last-write-wins (LWW) overwriting.
- **Verification Tests:** `tests/test_qa_phase09_workflows_sync_integrity.py` and `central_platform/sync/service.py`.

---

### 2.8 Threat Vector 8: Child Record Exposure & Personal Telemetry Leakage
- **Description:** Sensitive personal data, medical notes, chat dialogues, or prompt interactions are inadvertently exposed to parents, teachers, external logging, or cloud model APIs.
- **STRIDE Category:** Information Disclosure.
- **Vulnerability Surface:** API response serialization, application logs, parent portal feed, cloud AI prompts.
- **Mitigation Architecture:**
  - Parent visibility is filtered through 4 strict policy tiers (`FULL_TRANSPARENCY`, `SUMMARY_ONLY`, `RESTRICTED`, `BLOCKED`).
  - Structured logging automatically scrubs email addresses, phone numbers, auth tokens, and full AI prompts (`SecurityAuditor.sanitize_pii_logs`).
  - Air-gapped / `LOCAL_ONLY` enforcement drops external network transmission of student conversations.
- **Verification Tests:** `tests/test_qa_phase12_security_privacy_xss.py:test_sensitive_field_redaction_in_validation_error`, `tests/test_phase34_parent_privacy.py`.

---

## 3. Threat Mitigation Verification Matrix

| Threat Vector | Mitigation Module | Automated Test File | Result |
|---|---|---|---|
| Tenant Breakout | `central_platform/auth/dependencies.py` | `tests/test_qa_phase08_security_adversarial.py` | PASSED |
| IDOR | `central_platform/sis/`, `central_platform/portals/` | `tests/test_qa_phase12_security_privacy_xss.py` | PASSED |
| Upload Traversal | `central_platform/security/auditor.py` | `tests/test_qa_phase12_security_privacy_xss.py` | PASSED |
| DB Theft | `central_platform/db.py`, `scripts/migrate_db.py` | `tests/test_qa_phase10_packaging_deployment.py` | PASSED |
| Replay Punches/Webhooks | `central_platform/finance/service.py` | `tests/test_qa_phase03_finance_integrity.py` | PASSED |
| QR Forgery | `central_platform/campus/service.py` | `tests/test_qa_phase14_e2e_product_acceptance.py` | PASSED |
| Sync Overwrite | `central_platform/sync/service.py` | `tests/test_qa_phase09_workflows_sync_integrity.py` | PASSED |
| Child Telemetry Leakage | `central_platform/privacy/policies.py` | `tests/test_phase34_parent_privacy.py` | PASSED |
