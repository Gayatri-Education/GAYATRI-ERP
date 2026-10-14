# Gayatri School OS — Production Operations Runbook

**Document Version:** 1.0.0  
**Phase:** 09 Production Release Gate  
**Target Platform:** Gayatri School OS (Unified AI Suite & Full ERP)  
**Governing Standard:** `DEVELOPMENT.md` (§7 Phase 09)

---

## 1. System Architecture Overview

Gayatri School OS runs as a resilient, multi-tenant educational enterprise platform:
- **Central API Service:** FastAPI application (`central_platform.api.app:app`) serving REST endpoints for SIS, Admissions, Attendance, Timetable, Exams, Finance, HR/Payroll, Logistics, and Institutional Analytics.
- **Authoritative Database:** Relational database (SQLite local/WAL mode or PostgreSQL production) governed by sequential migrations (`001` through `016`).
- **Edge Biometric Daemon:** Sandboxed edge appliance (`central_platform.edge.daemon:EdgeDaemon`) executing in an isolated process with an append-only disk outbox and binary framing protocol.
- **AI Learning Suite:** Hybrid RAG and local SLM inference engine with deterministic pedagogical guardrails.

---

## 2. Production Startup & Bootstrap Sequence

### 2.1 Environment Configuration
Ensure the following mandatory production environment variables are configured before starting:
```bash
export GAYATRI_ENV=production
export GAYATRI_JWT_SECRET="<minimum-32-char-high-entropy-cryptographic-secret>"
export GAYATRI_ENCRYPTION_KEY="<minimum-16-char-high-entropy-key>"
export GAYATRI_ALLOWED_ORIGINS="https://school.domain.edu,https://portal.domain.edu"
export GAYATRI_DB_PATH="/var/data/gayatri/gayatri_production.db"
export DEBUG=false
export RELOAD=false
export FASTAPI_DEBUG=false
```

### 2.2 Database Initialization & Migration
Execute migrations sequentially prior to launching the application process:
```bash
# Verify schema state and apply forward migrations through version 016
python scripts/migrate_db.py up --db-path /var/data/gayatri/gayatri_production.db

# Verify PRAGMA integrity
python scripts/backup_restore_db.py verify --db-path /var/data/gayatri/gayatri_production.db
```

### 2.3 Starting Central Platform Service
```bash
# Launch production ASGI server via Uvicorn (multi-worker)
uvicorn central_platform.api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --no-access-log \
  --proxy-headers
```

### 2.4 Starting Edge Biometric Daemon (Campus Gateways)
```bash
# Launch isolated edge daemon pointing to local hardware device
python -m central_platform.edge.daemon \
  --device-id "edge-gate-primary" \
  --org-id "org-school-1" \
  --outbox-dir "/var/data/gayatri/edge_outbox" \
  --api-url "https://api.domain.edu"
```

---

## 3. Routine Health Checks & Observability

### 3.1 HTTP Health Endpoints
- **Liveness Probe:** `GET /health` -> HTTP 200 `{"status": "ok"}`
- **System Diagnostics:** `GET /api/v1/analytics/institutional/diagnostics` -> Returns database integrity, table row counts, sync health, and redacted configuration.
- **Sync Metrics:** `GET /api/v1/edge/health` -> Active devices, queue depth, dead-letter count, unresolved conflict metrics.

### 3.2 Scheduled Backup Cadence
- **Hourly Differential Snapshots:** Retained for 48 hours.
- **Daily Full Snapshot:** Retained for 30 days.
- **Weekly Cold Archive:** Encrypted snapshot moved to offsite object storage.

Backup execution command:
```bash
python scripts/backup_restore_db.py backup \
  --db-path /var/data/gayatri/gayatri_production.db \
  --backup-dir /var/backups/gayatri
```

---

## 4. Operational Maintenance Procedures

### 4.1 Schema Migration Upgrades
1. Place application in maintenance mode or route reads to secondary.
2. Create immediate pre-upgrade database backup snapshot.
3. Apply next sequential migration: `python scripts/migrate_db.py up`.
4. Validate table manifest and foreign key integrity.
5. Release maintenance mode.

### 4.2 Restoring from Disaster Recovery Backup
In the event of physical host corruption:
```bash
# Restore cold snapshot into isolated destination
python scripts/backup_restore_db.py restore \
  --backup-file /var/backups/gayatri/backup_20261015_000000.db \
  --target-db /var/data/gayatri/gayatri_production.db

# Audit integrity
python scripts/backup_restore_db.py verify \
  --db-path /var/data/gayatri/gayatri_production.db
```
