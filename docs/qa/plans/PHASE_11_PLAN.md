# Remediation Plan — Phase 11: Offline Mode, Sync Recovery, Hardware & Third-Party Disclosures (QA-011)

**Phase:** Phase 11  
**Issue Identifier:** QA-011  
**Priority:** P2  
**Target Branch:** `qa/production-readiness-remediation`  
**Governing Document:** `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` (Section 14)

---

## 1. Problem Statement & Baseline Findings
Section 14 of `GAYATRI_ERP_QA_REMEDIATION_GOAL.md` sets rigorous invariants for offline operation, sync recovery, hot database backup, and external dependencies:
1. **Sync Lifecycle & Durability:** Events must endure crashes and power loss via a durable disk-backed queue (`LocalSyncOutbox` / `EdgeDaemon`). Batches transitioning through `PENDING` $\rightarrow$ `IN_FLIGHT` $\rightarrow$ `ACKNOWLEDGED` must recover automatically upon ungraceful client shutdown without dropped or duplicate records.
2. **Deduplication & Deterministic Conflict Resolution:** Duplicate event deliveries must return cached receipts without creating duplicated business state (zero double attendance, double billing, or repeated mastery points). Clock skew exceeding acceptable bounds (> 300s) must be routed to conflict journals (`SyncConflictRecord`) rather than corrupting canonical timelines.
3. **Backup & Recovery with Active WAL:** Database backup and restore drills must work seamlessly during active SQLite WAL mode using online backup APIs (`sqlite3.backup`), with verified table counts, integrity checks, and foreign key validity.
4. **Offline AI & Privacy Isolation:** Local AI (`LocalProvider`) must operate without network egress, degraded RAG must return honest ungrounded/empty statuses without remote fallback, and zero student PII may leak to external services.
5. **Hardware & Third-Party Disclosures:** Physical RFID scanners, biometric fingerprint terminals, and vehicle GPS trackers are not connected in local development or CI environments. These must be explicitly declared as `BLOCKED` / `SIMULATED` (referencing `BLK-003`). Similarly, third-party payment gateways (Razorpay/Stripe) and notification providers (WhatsApp/SMS/SMTP) without live production API keys must operate in mock/sandbox/queue mode with transparent status disclosure rather than fabricating external delivery receipts.

---

## 2. Invariants & Guardrails
- **Durable Disk Queuing:** No in-memory-only queues for pending offline events; all mutations must be committed to local SQLite before acknowledgement.
- **Fail-Closed Conflict Detection:** Excessive clock skew (> 300s) or sequence regressions must be quarantined in `sync_conflict_records` for administrator review.
- **ACID Hot Backup:** Database backups during active WAL must preserve transactional integrity without page corruption or foreign-key violations.
- **Zero Student PII Egress:** Local tutor and offline analytics must never transmit student data to unauthorized external endpoints.
- **Truth in Hardware & Integration Claims:** Software simulators (`SimulatedBiometricDriver`, mock payment adapters) must be explicitly marked as `is_simulated = True`. Physical hardware testing must be truthfully recorded as `BLOCKED` (BLK-003) until real hardware benchmarks are executed.

---

## 3. Implementation Steps

### Step 1: Enhance Database Backup Integrity Checks
- In `scripts/backup_restore_db.py`, expand `verify_database_integrity()` to verify `PRAGMA foreign_key_check;` alongside `PRAGMA integrity_check;` and return `foreign_keys_ok: bool`.

### Step 2: Formalize Hardware & Third-Party Disclosure Specification
- Author `docs/operations/HARDWARE_AND_THIRD_PARTY_DISCLOSURES.md` detailing:
  - Component classification (Biometric fingerprint terminals, RFID gate readers, Vehicle GPS units, Razorpay payment gateway, WhatsApp/SMS notification providers).
  - Operating modes (`SIMULATED`, `LOCAL_OUTBOX`, `BLOCKED`).
  - Underlying drivers and interfaces (`SimulatedBiometricDriver`, `RazorpayPaymentAdapter`, `WhatsAppDeliveryProvider`).
  - Unblocking requirements (hardware models, communication protocols, baud rates, API keys, credentials).
  - Explicit cross-references to `BLK-003` in `docs/erp_agent/BLOCKERS.md`.

### Step 3: Author Comprehensive Test Suite (`tests/test_phase11_offline_sync_and_hardware.py`)
- **Test 1:** Outbox lifecycle & crash recovery (enqueue $\rightarrow$ in-flight $\rightarrow$ simulated crash $\rightarrow$ recover_in_flight $\rightarrow$ pending).
- **Test 2:** Outbox acknowledgement & selective deletion (per-item acknowledgement removes only confirmed items).
- **Test 3:** Exponential backoff & retry storm mitigation (failure increments retries, calculates exponential delay $t_{base} \times 2^{\min(r, 6)}$, prevents immediate re-query).
- **Test 4:** Multi-client concurrency & monotonic sequence reconciliation.
- **Test 5:** Edge biometric batch ingestion idempotency (duplicate punch batch produces 0 duplicate records and returns `DUPLICATE` status).
- **Test 6:** Excessive clock skew (> 300s) rejection and conflict journal escalation.
- **Test 7:** Online hot backup & restore drill with active SQLite WAL mode (integrity check + foreign key check + record count parity).
- **Test 8:** Offline AI provider & RAG degraded isolation (local inference requires no internet; empty/degraded RAG returns truthful `RAG_EMPTY` / `RAG_DEGRADED`).
- **Test 9:** Hardware driver simulation & transparent disclosure contract (`is_simulated == True`, simulated timeouts, disconnects, CRC errors, and BLK-003 compliance).
- **Test 10:** Third-party payment & notification provider sandbox isolation (truthful status, signature verification, dead-letter routing, zero fake external delivery).

---

## 4. Verification & Regression Plan
- Run `pytest -v tests/test_phase11_offline_sync_and_hardware.py`.
- Run full regression across Phases 01 through 11 (expecting 118+ passed).
- Verify zero failed, zero skipped, zero fabricated passes.
