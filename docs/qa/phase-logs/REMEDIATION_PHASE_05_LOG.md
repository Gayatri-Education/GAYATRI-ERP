# Remediation Phase 05 Execution Log — Edge Devices, Attendance Punches & Invalid Enum Rejection (QA-005)

**Phase ID:** 05  
**Target Vulnerability / Finding:** QA-005 (Edge Device Auth Bypass, Silent Invalid Enum Coercion & Tenant Spoofing)  
**Branch:** `qa/production-readiness-remediation`  
**Execution Timestamp:** 2026-10-15T22:15:20+05:30  
**Status:** PASSED  

---

## 1. Objectives & Inspection Findings
- **Audit Issue QA-005:**
  - `central_platform/api/routes/edge_sync.py:register_device()` caught `ValueError` and silently coerced invalid `device_type` strings to `BIOMETRIC_TERMINAL`.
  - `resolve_conflict()` caught `ValueError` and silently coerced invalid `strategy` strings to `MANUAL_REVIEW`.
  - `heartbeat()` accepted arbitrary `device_id` without caller/device authentication and blindly responded `{"status": "ACK"}` even for non-existent or revoked devices.
  - `ingest_punches()` accepted optional user auth and trusted caller-supplied `X-Organization-ID` without verifying device credentials or tenant ownership.
  - Replays of batches containing unlinked users leaked redundant records into `sync_dead_letter_queue`.
  - Simulated biometric hardware driver lacked truthful property disclosures.

---

## 2. Remediation Details

### A. Strict Enum Validation (HTTP 422 Unprocessable Entity)
- Applied Pydantic field validators on `DeviceRegisterRequest.device_type`, `PunchItemSchema.punch_type`, `PunchItemSchema.verification_type`, and `ConflictResolveRequest.strategy`.
- Replaced silent fallback/coercion with immediate HTTP 422 Unprocessable Entity when unrecognized enum strings are received. Documented defaults remain for omitted fields, but invalid supplied strings are strictly rejected.

### B. Device Authentication & Durable Heartbeats (`routes/edge_sync.py` & `sync/edge_service.py`)
- Added `get_device_unscoped(device_id: str)` to `EdgeSyncService` to support cross-tenant device credential authentication.
- Refactored `heartbeat()`:
  - Requires either authenticated user session or device credentials (`X-Device-Secret` header or body `secret`).
  - Validates device existence (HTTP 404), revocation (HTTP 403), and secret match (HTTP 401).
  - Enforced durable update: `record_heartbeat()` updates `edge_devices` only where `status != 'REVOKED'` and returns `{"status": "ACK"}` after verified DB persistence.

### C. Server-Side Tenant Mapping & Punch Ingestion Hardening
- Refactored `ingest_punches()`:
  - Requires user session or verified device secret (`X-Device-Secret` / body `device_secret`).
  - Derives organization scope strictly from `device.organization_id`.
  - Rejects caller-supplied `X-Organization-ID` if mismatched with `device.organization_id` (HTTP 400 `Organization mismatch for device`).
  - Rejects non-existent devices with HTTP 404, revoked devices with HTTP 403, and invalid secrets with HTTP 401.
- Updated `ingest_punch_batch()` idempotency check:
  - Checks both `edge_punches` and `sync_dead_letter_queue` so that replayed batches containing dead-lettered items return `DUPLICATE` without creating redundant DLQ rows.

### D. Hardware Disclosures
- Added explicit `is_simulated = True` and `driver_name = "SimulatedBiometricDriver"` to `SimulatedBiometricDriver` in accordance with audit guidelines requiring truthful labeling.

---

## 3. Verification & Test Execution
- **Dedicated Test Suite:** Authored `tests/test_phase05_edge_sync_remediation.py` containing 15 comprehensive tests:
  1. `test_invalid_device_type_rejected_with_422`: PASSED
  2. `test_invalid_punch_type_rejected_with_422`: PASSED
  3. `test_invalid_verification_type_rejected_with_422`: PASSED
  4. `test_invalid_conflict_strategy_rejected_with_422`: PASSED
  5. `test_heartbeat_requires_device_credentials_or_user_auth`: PASSED
  6. `test_heartbeat_rejects_invalid_secret_with_401`: PASSED
  7. `test_heartbeat_rejects_unknown_device_with_404`: PASSED
  8. `test_heartbeat_rejects_revoked_device_with_403`: PASSED
  9. `test_heartbeat_durable_ack_with_valid_secret`: PASSED
  10. `test_punch_batch_requires_device_credentials_or_user_auth`: PASSED
  11. `test_punch_batch_derives_tenant_from_device_rejects_mismatch`: PASSED
  12. `test_punch_batch_rejects_revoked_device_with_403`: PASSED
  13. `test_punch_batch_idempotency_and_dead_letter_isolation`: PASSED
  14. `test_durable_read_back_across_db_restart`: PASSED
  15. `test_hardware_driver_disclosures_truthful_simulation`: PASSED
- **Connected Edge Suite:** Executed 25 tests across Phase 05 and Phase 07 Offline Sync Edge Daemon:
  - **Passed:** 25/25 (100%) in 7.59s.
- **Multi-Phase Regression Suite:** Executed 73 tests across Phases 01, 02, 03, 04, 05, and architecture invariants:
  - **Passed:** 73/73 (100%) in 14.91s.

---

## 4. Exit Criteria Verification
- [x] Every edge mutation is authorized using a registered identity/device credential and server-side tenant mapping.
- [x] No invalid enum silently changes the device type, punch type, verification type, or resolution strategy.
- [x] Health, ACK and acceptance counts reflect actual persisted facts.
- [x] Zero test assertions weakened, zero skipped or xfailed tests.
