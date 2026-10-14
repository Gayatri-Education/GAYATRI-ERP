# Gayatri School OS — Incident Response and Disaster Recovery Playbook

**Version:** 1.0.0  
**Phase:** 09 Production Release Gate  
**Governing Standard:** `DEVELOPMENT.md` (§7 Phase 09)

---

## 1. Incident Severity Definitions

| Severity | Definition | Target Response | Target Resolution | Escalation Contact |
|:---:|:---|:---:|:---:|:---|
| **P0 (Critical)** | Core outage: authentication down, payment orders failing, database corrupted, or data leakage detected across tenants. | < 15 mins | < 2 hours | Lead Platform Engineer, Security Officer, Operations Lead |
| **P1 (High)** | Major subsystem impaired: attendance sync stalled, examination marks locked in error, or report card generation failing institution-wide. | < 30 mins | < 4 hours | Platform Domain Owner |
| **P2 (Medium)** | Degraded service with viable workaround: slow exports, individual hardware edge sensor reconnect loop, non-blocking CMS lag. | < 2 hours | < 24 hours | Assigned Maintainer |
| **P3 (Low)** | Minor cosmetic or documentation issues, non-impacting UI alignment defect. | < 8 hours | Next Sprint | Maintenance Backlog |

---

## 2. P0 Emergency Procedures

### 2.1 Multi-Tenant Data Leakage or Unauthorized Access
1. **Immediate Quarantine:** Terminate active ASGI worker processes or invoke firewall rule blocking public traffic.
2. **Token Invalidation:** Increment global token epoch or rotate `GAYATRI_JWT_SECRET` in secret manager to instantly revoke all active bearer sessions.
3. **Audit Log Inspection:** Extract queries matching affected tenant IDs from access logs and `diagnostic_snapshots`.
4. **Tenant Notification:** Prepare factual disclosure stating timeline, affected scope, and remediation actions according to regulatory mandates.

### 2.2 Corrupted Database or Interrupted Migration
1. **Freeze Writes:** Stop API and edge daemon instances immediately.
2. **Execute Diagnostic Check:**
   ```bash
   python scripts/backup_restore_db.py verify --db-path /var/data/gayatri/gayatri_production.db
   ```
3. **Evaluate Migration Failure:**
   - If a migration was interrupted mid-flight, check whether DDL changes rolled back cleanly.
   - If partially applied, execute the corresponding `_down.sql` script for that version:
     ```bash
     python scripts/migrate_db.py down --target-version <previous_version>
     ```
4. **Disaster Recovery Restore:**
   - If integrity cannot be verified, restore the latest verified pre-migration snapshot:
     ```bash
     python scripts/backup_restore_db.py restore \
       --backup-file /var/backups/gayatri/latest_safe_snapshot.db \
       --target-db /var/data/gayatri/gayatri_production.db
     ```

### 2.3 Edge Biometric Daemon Sync Failure or Network Partition
1. The edge daemon is process-isolated and buffers check-ins in its local disk outbox (`local_outbox`).
2. Even during prolonged internet outages, physical gates continue operating.
3. Upon network restoration:
   - Check sync health: `GET /api/v1/edge/health`.
   - Inspect unresolved conflicts: `GET /api/v1/edge/conflicts`.
   - Admin reviews conflict records with clock skew or divergent identities and triggers per-item resolution via `POST /api/v1/edge/conflicts/{id}/resolve`.

---

## 3. Post-Incident Review & Root Cause Analysis (RCA)

Within 24 hours of any P0/P1 incident resolution, the response team must document:
1. Incident Timeline (T0 detection, T1 acknowledgment, T2 mitigation, T3 permanent fix).
2. Root Cause Analysis (5-Whys methodology).
3. Data Impact Statement (reconciled record counts, verified zero lost ledger transactions).
4. Corrective & Preventative Actions (CAPA) with assigned owners and deadline.
