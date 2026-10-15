# Phase 17 Regression Evidence Log

**Document:** `docs/erp_agent/regressions/PHASE_17_REGRESSION.md`  
**Execution Phase:** Phase 17 — Offline Install, Sync, Backup/Restore and Operations  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Test Execution Commands & Outputs

- **Command:** `pytest tests/test_qa_phase09_workflows_sync_integrity.py tests/test_qa_phase10_packaging_deployment.py tests/test_qa_phase11_packaging_operations.py tests/test_phase07_offline_sync_edge_daemon.py`
- **Exit Code:** `0`
- **Result:** 33 passed, 0 failures, 0 errors, 0 skipped in 14.76s

---

## 2. Test Verification Matrix

| Area | Assertion Details | Result |
|---|---|---|
| Clean Machine Bootstrap | Database initializes from scratch with 16 migrations and 0 developer cache | PASSED |
| Backup & Disaster Rollback | Automated snapshot, file destruction, and clean rollback restore | PASSED |
| Cross-Platform Scripts | Windows (.bat) and Linux (.sh) scripts verified with headless offscreen handling | PASSED |
| Edge Daemon Outbox | Local disk outbox survives daemon crash, restart, and power interruption | PASSED |
| Batch Sync & Partial Success | Mixed valid/duplicate/invalid punches commit valid records & route failures to DLQ | PASSED |
| Replay Idempotency | Replayed batches produce zero duplicate punches or side effects | PASSED |
| Clock Skew Detection | Forward clock skew (>300s) quarantined to conflict journal | PASSED |
| Binary Frame Protocol | Binary frame packing, CRC-16 checksum, and bit corruption rejection | PASSED |
| Hardware Fault Isolation | Hardware disconnects or timeouts sandbox cleanly without process termination | PASSED |
| Operational Smoke Tests | scripts/smoke_test_install.py executes cleanly with exit code 0 | PASSED |
