-- 015_offline_sync_edge_daemon_down.sql: Rollback Migration 015

DROP TABLE IF EXISTS sync_dead_letter_queue;
DROP TABLE IF EXISTS sync_conflict_records;
DROP TABLE IF EXISTS edge_punches;
DROP TABLE IF EXISTS edge_devices;
