# GAYATRI-ERP Blockers Register

No blocker is considered cleared without evidence. Keep credentials/secrets out of this file.

| ID | Date | Phase/domain | Blocker | Impact | Safe work while blocked | Exit condition | Status |
|---|---|---|---|---|---|---|---|
| BLK-001 | 2026-10-15 | Repository integration | GitHub connector write operations returned HTTP 403 Resource not accessible by integration when creating a branch/file. | Roadmap documents could not be committed directly by this session. Product implementation was not attempted. | Add the supplied files locally to a checked-out repository and commit via an authorized developer/local agent; request repository write permission if needed. | A permitted branch/PR or local commit is confirmed by Git status/SHA. | BLOCKED |
| BLK-002 | 2026-10-15 | All implementation | No local checkout/runtime test execution was performed while drafting these planning artifacts. | Initial lack of runtime test proof. | Coding agent ran Phase 00 baseline and recorded actual metrics. | Baseline report records real commands, 1,775 tests passed, and schema verified. | CLOSED |
| BLK-003 | 2026-10-15 | Attendance / Transport | Physical RFID scanners, biometric fingerprint readers, and bus GPS hardware unavailable. | Real hardware live-packet validation cannot be executed in local developer environment. | Software interfaces, packet deduplication, and mock adapters are verified via automated tests. | Connected physical hardware benchmark evidence recorded. | OPEN (DEFER_WITH_REASON) |
