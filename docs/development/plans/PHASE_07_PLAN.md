# Phase 07 Plan: Offline Sync Hardening and Edge Biometric Integrations

## Status
- [ ] NOT_STARTED
- [ ] IN_PROGRESS
- [x] PASSED
- [ ] FAILED
- [ ] BLOCKED

---

## 1. Objective and Architecture

Deliver comprehensive offline synchronization hardening and hardware edge device integration for Gayatri School OS:
1. **Entity-by-Entity Offline Support Matrix:** Explicit classification (`OFFLINE_SUPPORTED` vs `SERVER_AUTHORITATIVE_ONLY`) preventing undefined offline assumptions.
2. **Edge Biometric Daemon & Driver Sandboxing:** Standalone daemon service running in an isolated execution loop, communicating via an explicit device driver protocol. Hardware disconnects or packet errors never crash or block the UI or AI model inference.
3. **Durable Local Outbox & Central Ledger:** Local SQLite storage persists all punches across crashes and restarts. Central platform records all events in an immutable, idempotent ledger.
4. **Per-Item Batch Semantics:** Ingestion of batches supports partial success; valid items commit, duplicates acknowledge without double-marking, and invalid items route to the dead-letter queue without silent drops.
5. **Deterministic Conflict Handling:** Safe field auto-merge, monotonic sequence check, and escalation of consequential conflicts (e.g. excessive clock skew > 300s or contradictory attendance punches) to `sync_conflict_records`.
6. **Sync Health Observability:** Comprehensive dashboard metrics tracking pending outbox age, retry counts, dead-letter items, unresolved conflicts, and active edge device heartbeats.

---

## 2. Schema Specification (Migration 015)

- `edge_devices`: Registry of biometric terminals and edge appliances with secret hashes, active/revoked states, and heartbeat timestamps.
- `edge_punches`: Authoritative log of device check-in/out punches with verification methods and unique idempotency keys.
- `sync_conflict_records`: Audit journal capturing client vs server conflicting payloads, resolution strategies, and reviewer notes.
- `sync_dead_letter_queue`: Durable quarantine capturing unparseable, malformed, or rejected sync items with retry counters.

---

## 3. Implementation Steps

1. **Migration 015:** Forward (`migrations/015_offline_sync_edge_daemon.sql`) and rollback (`migrations/015_offline_sync_edge_daemon_down.sql`).
2. **Domain Models:** `central_platform/models/sync.py`.
3. **Edge Protocol & Drivers:**
   - `central_platform/edge/protocol.py`: Packet parsing, CRC/checksum verification, punch data structures.
   - `central_platform/edge/drivers/base.py`: Abstract biometric hardware interface.
   - `central_platform/edge/drivers/simulator.py`: High-fidelity simulator driver testing disconnects, corrupted packets, and clock skew.
   - `central_platform/edge/daemon.py`: Standalone `EdgeDaemon` with local disk outbox (`edge_local_outbox.db`), batch sync loop, and retry backoff.
4. **Central Sync & Edge Service:** `central_platform/sync/edge_service.py` (`EdgeSyncService`).
5. **REST API Router:** `central_platform/api/routes/edge_sync.py` mounted under `/api/v1/edge`.
6. **Focused Test Suite:** `tests/test_phase07_offline_sync_edge_daemon.py` (10 tests).
7. **Regression & Certification:** Verify all existing 1,611 tests remain 100% green, document evidence and reports.
