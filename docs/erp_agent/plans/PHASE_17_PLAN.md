# Phase 17 Plan — Offline Install, Sync, Backup/Restore and Operations

**Document:** `docs/erp_agent/plans/PHASE_17_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 17 — Offline Install, Sync, Backup/Restore and Operations  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 17 verifies offline installations, backup/restore durability, migration rollback, edge daemon synchronization, and operational health:
1. **Air-Gapped & Clean-Machine Bootstrap:** Database schema initialization in clean environments with zero pre-existing developer state (`test_clean_environment_bootstrap_zero_developer_state`).
2. **Online Backup & Disaster Recovery Rollback:** Automated snapshot backup creation, simulated data corruption/destruction, and restoration matching database integrity (`test_backup_restore_and_rollback_recovery`).
3. **Cross-Platform Packaging & Entrypoints:** Windows (`.bat`) and Linux/POSIX (`.sh`) launchers with headless Qt handling (`DISPLAY=""`) and SHA-256 release packaging manifests.
4. **Edge Daemon & Local Outbox Persistence:** Biometric/attendance punch persistence in local disk outbox surviving system crashes, reboots, and power loss (`test_edge_daemon_local_outbox_persistence_and_restart`).
5. **Sync Idempotency & Conflict Resolution:** Batch replay idempotency (zero double marking or duplicate consequential records), partial success with per-item acknowledgements, and forward clock skew (>300s) quarantined to conflict journals.
6. **Binary Framing & CRC-16 Checksumming:** Hardware adapter frame packing, CRC-16 verification, and bit-rot corruption rejection.
7. **Production Deployment Validation:** Missing secret detection, runtime provider health checks, and truthful first-run model status.

---

## 2. Likely Files & Scope Boundary

- `central_platform/sync/` (`EdgeSyncDaemon`, `SyncBatchProcessor`, `ConflictJournal`)
- `central_platform/backup/` (`BackupManager`, `DisasterRecoveryDrill`)
- `scripts/` (`setup.bat`, `run.bat`, `run.sh`, `package_release.py`, `smoke_test_install.py`)
- `central_platform/deployment/` (`DeploymentValidator`)
- `tests/test_qa_phase09_workflows_sync_integrity.py`
- `tests/test_qa_phase10_packaging_deployment.py`
- `tests/test_qa_phase11_packaging_operations.py`
- `tests/test_phase07_offline_sync_edge_daemon.py`

---

## 3. Targeted Test Scenarios

1. Clean install bootstrap with zero developer state (`test_clean_environment_bootstrap_zero_developer_state`).
2. Backup snapshot creation, file destruction, and clean rollback (`test_backup_restore_and_rollback_recovery`).
3. Cross-platform scripts and headless Linux offscreen support (`test_linux_launch_scripts_headless_handling`).
4. Migration 015 up and down rollback (`test_migration_015_up_and_down`).
5. Edge outbox punch persistence across crash/restart (`test_edge_daemon_local_outbox_persistence_and_restart`).
6. Batch partial success and per-item acknowledgement (`test_batch_partial_success_and_per_item_acknowledgement`).
7. Clock skew detection and quarantine (`test_clock_skew_detection_and_conflict_routing`).
8. Binary packet protocol CRC-16 checksumming (`test_binary_packet_protocol_framing_and_checksum`).
9. Post-install smoke test script execution (`test_post_install_smoke_test_script`).

---

## 4. Exit Criteria (Binary Gate)

- [ ] Clean machine bootstrap and schema initialization verified.
- [ ] Database backup, destruction, and rollback restore drill verified.
- [ ] Edge sync outbox persistence and idempotency verified.
- [ ] Clock skew quarantine and binary frame CRC-16 checks verified.
- [ ] Cross-platform launch scripts (.bat / .sh) verified.
- [ ] `docs/erp_agent/reports/PHASE_17_REPORT.md` and `docs/erp_agent/regressions/PHASE_17_REGRESSION.md` generated with passing evidence.
