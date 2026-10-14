-- 016_analytics_exports_diagnostics.sql: Gayatri School OS — Phase 08 Unified Analytics, Exports & Diagnostics

CREATE TABLE IF NOT EXISTS export_jobs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    export_type TEXT NOT NULL,
    format TEXT NOT NULL DEFAULT 'CSV',
    status TEXT NOT NULL DEFAULT 'PENDING',
    row_count INTEGER DEFAULT 0,
    file_path TEXT,
    requested_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filters_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_export_jobs_org_status ON export_jobs(organization_id, status);

CREATE TABLE IF NOT EXISTS diagnostic_snapshots (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    snapshot_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_diag_snapshots_org_type ON diagnostic_snapshots(organization_id, snapshot_type);
