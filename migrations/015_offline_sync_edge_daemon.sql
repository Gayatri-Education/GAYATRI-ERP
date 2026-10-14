-- 015_offline_sync_edge_daemon.sql: Gayatri School OS — Phase 07 Offline Sync Hardening & Edge Integrations

CREATE TABLE IF NOT EXISTS edge_devices (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    device_code TEXT NOT NULL,
    device_type TEXT NOT NULL,
    device_name TEXT NOT NULL,
    secret_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    last_heartbeat_at TEXT,
    firmware_version TEXT,
    ip_address TEXT,
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, device_code)
);

CREATE INDEX IF NOT EXISTS idx_edge_devices_org_status ON edge_devices(organization_id, status);

CREATE TABLE IF NOT EXISTS edge_punches (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES edge_devices(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    punch_type TEXT NOT NULL,
    punch_time TEXT NOT NULL,
    verification_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    processed_at TEXT,
    UNIQUE(organization_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_edge_punches_org_user_time ON edge_punches(organization_id, user_id, punch_time);
CREATE INDEX IF NOT EXISTS idx_edge_punches_device_status ON edge_punches(device_id, status);

CREATE TABLE IF NOT EXISTS sync_conflict_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    client_payload_json TEXT NOT NULL,
    server_payload_json TEXT NOT NULL,
    resolution_strategy TEXT NOT NULL,
    resolved_by TEXT,
    resolved_at TEXT,
    resolution_notes TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sync_conflicts_org_entity ON sync_conflict_records(organization_id, entity_type, entity_id);

CREATE TABLE IF NOT EXISTS sync_dead_letter_queue (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    error_category TEXT NOT NULL,
    error_message TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sync_dlq_org_device ON sync_dead_letter_queue(organization_id, device_id);
