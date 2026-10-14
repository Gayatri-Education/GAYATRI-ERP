-- ============================================================================
-- Migration 013: Finance, Payments and Reconciliation Subsystem
-- ============================================================================

-- 1. Payment Orders
CREATE TABLE IF NOT EXISTS payment_orders (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    provider TEXT NOT NULL DEFAULT 'razorpay',
    provider_order_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_org ON payment_orders(organization_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_invoice ON payment_orders(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payment_orders_provider_id ON payment_orders(provider_order_id);

-- 2. Payment Webhook Events (Deduplication & Audit)
CREATE TABLE IF NOT EXISTS payment_webhook_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    idempotency_key TEXT,
    payload_json TEXT NOT NULL,
    payload_hash TEXT,
    signature_verified INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'PROCESSED',
    payment_id TEXT,
    processed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(organization_id, provider, event_id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_org ON payment_webhook_events(organization_id);
CREATE INDEX IF NOT EXISTS idx_webhook_events_idemp ON payment_webhook_events(organization_id, idempotency_key);

-- 3. Financial Ledger Entries (Append-only Audit Trail)
CREATE TABLE IF NOT EXISTS financial_ledger_entries (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES fee_accounts(id) ON DELETE CASCADE,
    invoice_id TEXT REFERENCES invoices(id) ON DELETE SET NULL,
    payment_id TEXT REFERENCES payments(id) ON DELETE SET NULL,
    entry_type TEXT NOT NULL,
    amount REAL NOT NULL,
    balance_after REAL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fin_ledger_account ON financial_ledger_entries(account_id);
CREATE INDEX IF NOT EXISTS idx_fin_ledger_org ON financial_ledger_entries(organization_id);

-- 4. Reconciliation Records
CREATE TABLE IF NOT EXISTS reconciliation_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    run_date TEXT NOT NULL,
    provider TEXT NOT NULL,
    total_expected REAL NOT NULL DEFAULT 0.0,
    total_settled REAL NOT NULL DEFAULT 0.0,
    discrepancy_amount REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'RESOLVED',
    notes TEXT,
    reconciled_by TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_org ON reconciliation_records(organization_id);
CREATE INDEX IF NOT EXISTS idx_reconciliation_date ON reconciliation_records(run_date);

-- 5. Fee Concessions
CREATE TABLE IF NOT EXISTS fee_concessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    student_id TEXT NOT NULL,
    fee_structure_id TEXT NOT NULL REFERENCES fee_structures(id) ON DELETE CASCADE,
    concession_type TEXT NOT NULL DEFAULT 'percentage',
    amount_or_percentage REAL NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    requested_by TEXT,
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_concessions_org ON fee_concessions(organization_id);
CREATE INDEX IF NOT EXISTS idx_concessions_student ON fee_concessions(student_id);
