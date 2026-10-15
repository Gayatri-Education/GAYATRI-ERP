# Phase 05 Plan — Edge Devices, Attendance Punches & Invalid Enum Rejection (QA-005)

## 1. Context & Objectives
In Phase 04, we remediated payment webhook verification, tenant binding, and accounting invariants (QA-004).
In Phase 05, we remediate QA-005: enforcing explicit edge device authentication, binding attendance punches to authenticated devices and server-side tenant mappings, eliminating caller-controlled `X-Organization-ID` overrides, rejecting invalid enums with HTTP 422 instead of silent coercion, and making heartbeat ACKs reflect durable persisted state.

### Target Locations
- `central_platform/api/routes/edge_sync.py`: Device registration, heartbeat, punch batch ingestion, and conflict resolution routes.
- `central_platform/sync/edge_service.py`: Device lookup, authentication, durable heartbeat recording, and atomic punch batch ingestion.
- `central_platform/models/sync.py`: Enums and schemas for `DeviceType`, `PunchType`, `VerificationType`, and `ConflictResolutionStrategy`.

---

## 2. Gap Analysis & Root Causes
1. **Silent Enum Coercion:**
   - In `register_device()`, invalid `device_type` strings caught `ValueError` and coerced to `DeviceType.BIOMETRIC_TERMINAL`.
   - In `resolve_conflict()`, invalid `strategy` strings caught `ValueError` and coerced to `ConflictResolutionStrategy.MANUAL_REVIEW`.
   - In `PunchItemSchema`, unrecognized `punch_type` or `verification_type` values were not validated prior to processing.
2. **Unauthenticated Heartbeat Endpoint:**
   - `POST /api/v1/edge/devices/heartbeat` accepted any arbitrary `device_id` without checking device credentials, user auth, registration, or revocation, and responded `{"status": "ACK"}` even for non-existent or revoked devices.
3. **Tenant Spoofing in Punch Ingestion:**
   - `POST /api/v1/edge/punches/batch` allowed unauthenticated callers to specify `X-Organization-ID` without verifying that the device actually belonged to that organization or that the caller possessed device credentials.
4. **Hardware Reality Disclosure:**
   - Physical RFID/biometric hardware drivers without real connected hardware must be marked truthfully as `SIMULATED` or `BLOCKED`.

---

## 3. Remediation Architecture

### A. Strict Enum Validation (HTTP 422 Unprocessable Entity)
- Use Pydantic field validators on `DeviceRegisterRequest.device_type`, `PunchItemSchema.punch_type`, `PunchItemSchema.verification_type`, and `ConflictResolveRequest.strategy`.
- An invalid string must raise `ValueError` during schema parsing, resulting in an immediate HTTP 422 Unprocessable Entity response with descriptive error details.
- Legitimate omissions will receive documented defaults (`BIOMETRIC_TERMINAL`, `CHECK_IN`, `FINGERPRINT`, `AUTO_MERGED`), but supplied invalid values must never be coerced into valid ones.

### B. Device Authentication & Tenant Binding
- Add `get_device_unscoped(device_id: str) -> Optional[EdgeDevice]` to `EdgeSyncService`.
- **Heartbeat Authentication:**
  - Route requires either:
    1. Authenticated user belonging to the device's organization; or
    2. Registered device secret passed via `X-Device-Secret` header or body `secret`.
  - Validate device existence (404 if missing), revocation (403 if revoked), and secret matching (401 if invalid).
  - Durable update: `record_heartbeat()` updates database row and returns `ACK` only when durable update succeeds.
- **Punch Batch Ingestion Authentication:**
  - Require user authentication or valid device credentials (`X-Device-Secret` / `device_secret`).
  - Derive organization scope `org_id` strictly from `device.organization_id`.
  - If caller provides `X-Organization-ID`, verify `x_org_id == device.organization_id`; reject mismatch with HTTP 400.
  - Reject non-existent devices with HTTP 404, revoked devices with HTTP 403, and bad credentials with HTTP 401.

### C. Ingestion Invariants & Conflict Sandboxing
- Maintain atomic batch guarantees and per-item status reporting (`ACKNOWLEDGED`, `DUPLICATE`, `FAILED`, `CONFLICT`).
- Excessive clock skew (> 300s into future) continues to be routed safely to `sync_conflict_records`.
- Unmatched student IDs continue to be quarantined in dead letter queue (`sync_dead_letter_queue`).

---

## 4. Verification & Testing Strategy
Author `tests/test_phase05_edge_sync_remediation.py` covering:
1. Rejection of invalid `device_type` with HTTP 422 (no silent coercion).
2. Rejection of invalid `punch_type` with HTTP 422.
3. Rejection of invalid `verification_type` with HTTP 422.
4. Rejection of invalid conflict resolution `strategy` with HTTP 422.
5. Heartbeat requires device credentials or user auth (401 on missing credentials).
6. Heartbeat rejects invalid device secret with HTTP 401.
7. Heartbeat rejects revoked device with HTTP 403.
8. Heartbeat rejects unknown device with HTTP 404.
9. Heartbeat updates database timestamp and returns ACK upon verified credentials.
10. Punch batch requires device credentials or user auth (401 on missing credentials).
11. Punch batch derives tenant strictly from authenticated device (rejects spoofed `X-Organization-ID` mismatch with 400).
12. Punch batch rejects revoked device with HTTP 403.
13. Punch batch rejects unknown device with HTTP 404.
14. Batch idempotency: duplicate punch keys return `DUPLICATE` without creating double records.
15. Dead-letter queue isolation for unknown users.
16. Clock-skew conflict sandboxing.
17. Durable read-back of punches and heartbeat across database restart.

Regression Verification:
- `pytest tests/test_phase07_offline_sync_edge_daemon.py tests/test_phase08_sync_remediation.py -v`
- Full headless regression and architecture invariants.

---

## 5. Exit Criteria
- [ ] Every edge mutation is authorized using a registered identity/device credential and server-side tenant mapping.
- [ ] No invalid enum silently changes the device type, punch type, verification type, or resolution strategy.
- [ ] Health, ACK and acceptance counts reflect actual persisted facts.
- [ ] Zero test assertions weakened, zero skipped or xfailed tests.
