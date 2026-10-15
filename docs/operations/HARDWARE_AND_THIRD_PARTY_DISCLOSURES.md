# Gayatri School OS — Hardware and Third-Party Integration Disclosures

**Document Version:** 1.0.0  
**Phase:** Phase 11 — Offline Mode, Sync Recovery, Hardware & Third-Party Disclosures  
**Governing Standard:** [`GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](../../GAYATRI_ERP_QA_REMEDIATION_GOAL.md) (§14)  
**Canonical Blocker Reference:** [`docs/erp_agent/BLOCKERS.md`](../erp_agent/BLOCKERS.md) (`BLK-003`)  
**Date:** 2026-10-15  
**Status:** ACTIVE_DISCLOSURE  

---

## 1. Executive Summary & Transparency Invariant

To preserve engineering integrity and comply with production-readiness standards:
1. **Never Re-label Simulators as Physical Acceptance:** Automated unit and integration tests utilize high-fidelity software simulators (`SimulatedBiometricDriver`, mock gateway adapters) to validate packet framing, checksums, timeout recovery, and API contracts. Simulated test passes must **never** be advertised as physical hardware acceptance or live gateway clearance.
2. **Explicit Blocked State Reporting:** Any integration requiring physical hardware or third-party cloud credentials that are not attached or configured in the environment is explicitly classified as `BLOCKED` or `SIMULATED`.
3. **Fail-Closed Privacy Boundary:** The local runtime (`LocalProvider`) operates with zero network dependencies. Student data and learning telemetry are strictly preserved on-premises and never transmitted to external cloud providers without explicit tenant policy authorization.

---

## 2. Hardware Device Matrix & Disclosure Register

| Device / Interface Category | Protocol / Physical Layer | Software Driver / Abstraction | Current Environment State | Acceptance Status | Blocker ID | Unblocking Procedure |
|---|---|---|:---:|:---:|:---:|---|
| **Biometric Fingerprint / Facial Terminal** | USB 2.0 / RS-485 / TCP Ethernet | `central_platform.edge.drivers.simulator.SimulatedBiometricDriver` | Emulated (CRC-16, framing, timeouts) | **BLOCKED** | `BLK-003` | Attach physical hardware unit (ZKTeco / Morpho / Mantra); configure device IP/baud; execute live enrollment and punch benchmark. |
| **Contactless RFID / NFC Smart Card Readers** | 13.56 MHz ISO 14443A / Wiegand / USB HID | `central_platform.edge.drivers.simulator.SimulatedBiometricDriver` | Emulated (Hex UID mapping to student/staff entities) | **BLOCKED** | `BLK-003` | Connect physical RFID reader terminal; present provisioned smart badges; capture live pulse trains. |
| **Vehicle Fleet GPS Trackers** | RS-232 / GSM-GPRS / NMEA-0183 | `central_platform.transport.service.TransportService` | Database-backed route/stop models | **BLOCKED** | `BLK-003` | Provision vehicle tracking OBD-II or hardwired GPS unit with active SIM; bind IMEI to transport route. |

---

## 3. Third-Party Gateway & External Cloud Service Disclosures

| Integration Domain | Target Provider | Software Adapter | Configured Credentials | Fallback Behavior in Local/CI | Acceptance Status |
|---|---|---|:---:|---|:---:|
| **Online Tuition & Fee Collection** | Razorpay Gateway (API v1) | `RazorpayPaymentAdapter` | `rzp_test_mock` / `rzp_secret_mock` | Orders generated with mock checkout URL; HMAC signatures validated locally; double-entry ledger reconciled. | **SANDBOX_VERIFIED** (Live production blocked without client API keys) |
| **Direct UPI Collections** | NPCI / UPI Intent | `UPIPaymentAdapter` | Local Merchant VPA | Generates standard UPI QR strings (`upi://pay?...`); reconciled via webhook or bank statement upload. | **VERIFIED_LOCAL** |
| **SMS Gateway** | Twilio / MSG91 / ValueFirst | `NotificationService` | None (Unconfigured) | Queued in durable outbox (`local_notifications`); marked `PENDING` without false delivery claims. | **BLOCKED_WITHOUT_CREDENTIALS** |
| **WhatsApp Business Messaging** | Meta Cloud API / Twilio WhatsApp | `WhatsAppDeliveryProvider` | None (Unconfigured) | Queued with recipient validation; fails closed or returns sandbox receipt `wa_*`. | **BLOCKED_WITHOUT_CREDENTIALS** |
| **Email Delivery** | SMTP / AWS SES / SendGrid | `EmailDeliveryProvider` | `localhost:587` | Validates RFC-5322 recipient format; routes to local inbox or sandbox queue. | **SANDBOX_VERIFIED** |

---

## 4. Offline Autonomy & Data Governance Guarantees

1. **Air-Gapped Operation:** All central ERP workflows (Admissions, SIS, Timetables, Attendance Roll Call, Fee Invoicing, Offline Sync, Grading, and Report Cards) execute deterministically on an air-gapped machine with no internet connection.
2. **Local AI Model Execution:** The local tutor and NCERT RAG pipeline execute in-process via `llama-cpp-python` and local vector/BM25 indexes. No remote LLM endpoint is queried for student chat or assessment grading.
3. **Crash & Power-Failure Recovery:** The `LocalSyncOutbox` persists all mutations to disk in SQLite WAL mode. In-flight operations interrupted by power failure or process termination are automatically restored to `PENDING` on application startup via `recover_in_flight()`.
4. **Zero Silent Overwrites:** Replaying historical sync batches or ingesting out-of-order biometric punches results in deterministic duplicate detection (`DUPLICATE`) or escalation to `sync_conflict_records` for administrator review.
