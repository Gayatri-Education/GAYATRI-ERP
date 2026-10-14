-- ============================================================================
-- Rollback Migration 013: Finance, Payments and Reconciliation Subsystem
-- ============================================================================

DROP TABLE IF EXISTS fee_concessions;
DROP TABLE IF EXISTS reconciliation_records;
DROP TABLE IF EXISTS financial_ledger_entries;
DROP TABLE IF EXISTS payment_webhook_events;
DROP TABLE IF EXISTS payment_orders;
