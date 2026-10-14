# Gayatri School OS — Entity-by-Entity Offline Support Matrix (Phase 07)

**Document Version:** 1.0.0  
**Phase:** Phase 07 — Offline Sync Hardening & Edge Biometric Integrations  
**Governing Contract:** `DEVELOPMENT.md` (§6.9, §10, §11)  
**Date:** 2026-10-15  

---

## 1. Architectural Principles

1. **Explicit Support Only:** Every entity in the Gayatri School OS is classified as either `OFFLINE_SUPPORTED` or `SERVER_AUTHORITATIVE_ONLY`. No entity has "implied" or untested offline support.
2. **Crash & Power Loss Durability:** All local actions must be persisted in a local, disk-backed SQLite outbox before being acknowledged to the user or device operator. Zero reliance on in-memory buffers for pending syncs.
3. **Idempotent Operations:** Every mutating offline event carries a globally unique `idempotency_key` generated at the origin device. Replaying batches produces zero duplicate consequential business effects.
4. **Per-Item Acknowledgement Semantics:** Batches containing mixed valid and invalid operations return per-item status (`ACKNOWLEDGED`, `DUPLICATE`, `FAILED`, `CONFLICT`). Valid items are committed; failed items are routed to the Dead Letter Queue (`sync_dead_letter_queue`) without aborting valid operations or silently discarding data.
5. **Process Isolation:** The Edge Biometric Daemon and hardware I/O drivers execute in isolated processes/threads separate from desktop GUI and AI model inference. Hardware disconnects, corrupt packets, or network timeouts never crash or block the UI or student tutor.

---

## 2. Entity Offline Support Classification Matrix

| Entity Domain | Canonical Storage | Offline Support Tier | Local Queue Mechanism | Deduplication / Idempotency Key | Conflict Resolution Strategy | Security & Encryption Boundary |
|---|---|---|---|---|---|---|
| **Learning Events** (Tutor sessions, hints, completions) | Central SQLite / Postgres | `OFFLINE_SUPPORTED` | Persistent SQLite Queue (`local_sync_queue`) | `event_id` (UUIDv4) | Last Write Wins (LWW) by monotonically increasing sequence number | Stored in desktop app private directory; synced via TLS with Student JWT |
| **Biometric Attendance** (Student/Staff punches) | Central SQLite / Postgres | `OFFLINE_SUPPORTED` | Edge Daemon Outbox (`edge_local_outbox.db`) | `punch_id` (`{device_id}:{user_id}:{timestamp_epoch}`) | Strict Deduplication; Clock skew > 300s flagged for manual audit | Device Secret / HMAC-SHA256 signature; mutual device auth |
| **Visitor Gate Passes** (Check-in/out badges) | Central SQLite / Postgres | `OFFLINE_SUPPORTED` | Edge Gate Terminal Outbox | `pass_id` (`{org_id}:{visitor_id}:{date_iso}`) | Append-only status transition; duplicate check-in rejected | Gate Guard Token / Device PIN |
| **Fee Invoicing & Payments** | Central SQLite / Postgres | `SERVER_AUTHORITATIVE_ONLY` | Prohibited Offline | Server-generated order ID | N/A (Server-only state machine) | Strictly TLS encrypted; HMAC-SHA256 gateway signatures |
| **Exams, Marks & Grading** | Central SQLite / Postgres | `SERVER_AUTHORITATIVE_ONLY` | Prohibited Offline | Server-generated exam entry ID | N/A (Locked upon finalization) | Role-based RBAC (Teacher/Registrar only) |
| **Payroll Runs & Payslips** | Central SQLite / Postgres | `SERVER_AUTHORITATIVE_ONLY` | Prohibited Offline | Cycle ID (`{org_id}:{year}:{month}`) | N/A (Dual-maker checker approval required) | Highly restricted accountant/admin access |
| **Hostel Bed Allocations** | Central SQLite / Postgres | `SERVER_AUTHORITATIVE_ONLY` | Prohibited Offline | Room-bed composite key | Server-enforced capacity rejection | Warden RBAC |
| **Inventory Stock Movements** | Central SQLite / Postgres | `SERVER_AUTHORITATIVE_ONLY` | Prohibited Offline | Movement Reference (`PO-{id}` or `REQ-{id}`) | Append-only ledger; negative inventory rejected | Storekeeper RBAC |
| **Official Certificates** | Central SQLite / Postgres | `SERVER_AUTHORITATIVE_ONLY` | Prohibited Offline | SHA-256 Document Hash | N/A (Immutable once issued) | Registrar cryptographic key |
| **Public CMS Pages/Posts** | Central SQLite / Postgres | `SERVER_AUTHORITATIVE_ONLY` | Prohibited Offline | Tenant Slug | N/A (Admin publication gate) | Admin RBAC |

---

## 3. Conflict Resolution Taxonomy

When offline events reach the central platform out-of-order or with conflicting state:

1. **Safe Field Auto-Merge:** Non-conflicting attribute updates (e.g. metadata tags, notes) are merged automatically without operator intervention.
2. **Last-Write-Wins (LWW) with Monotonic Check:** For telemetry and learning progression, higher sequence numbers supersede lower sequence numbers provided origin timestamps are within acceptable drift.
3. **Deterministic Rejection:** Out-of-order sequence regressions (e.g. an earlier sequence arriving after a later sequence has been finalized) are rejected with `STALE_WRITE`.
4. **Manual Review Escalation:** Consequential state conflicts (e.g. conflicting attendance status from multiple devices, excessive clock skew > 5 minutes, or punch time collisions) are logged in `sync_conflict_records` and surfaced on the Sync Health Dashboard for administrator decision.

---

## 4. Hardware Failure & Daemon Isolation Contract

1. **Independent Process Lifecycle:** `EdgeDaemon` operates as an independent background service. If the central server is unreachable, the daemon logs an INFO event and continues buffering punches locally.
2. **Driver Sandboxing:** All physical hardware communication (e.g. serial ports, USB biometric sensors, network sockets) is wrapped in resilient timeouts (maximum 2.5s) and catch-all exception boundaries.
3. **No UI Contamination:** No GUI component or AI inference thread directly imports or invokes device drivers. All interaction is mediated via local IPC or standard loopback REST endpoints.
