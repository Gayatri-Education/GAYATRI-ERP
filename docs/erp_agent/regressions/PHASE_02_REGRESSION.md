# Phase 02 Regression Evidence Log

**Document:** `docs/erp_agent/regressions/PHASE_02_REGRESSION.md`  
**Execution Phase:** Phase 02 — Shared Identity, Tenancy, Permissions and Audit Foundation  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Test Execution Commands & Outputs

### 1.1 Identity, Tenancy & DB Lifecycle Suite
- **Command:** `python -m pytest tests/test_qa_phase01_auth_remediation.py tests/test_qa_phase02_db_lifecycle_transactions.py tests/test_qa_phase05_auth_revocation_ratelimit.py tests/test_phase07_tenant_isolation.py tests/test_phase3_auth_rbac.py`
- **Exit Code:** `0`
- **Result:** 28 passed, 0 failures, 0 errors, 0 skipped in 6.08s

### 1.2 Isolated Database Restore Drill
- **Command:** `python scripts/migrate_db.py up --db-path temp_drill.db; python scripts/migrate_db.py status --db-path temp_drill.db; Remove-Item -Force temp_drill.db*`
- **Exit Code:** `0`
- **Result:**
```text
[OK] Applied 16 migration(s) on SQLite: 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 012, 013, 014, 015, 016
Database Backend: SQLite (Target: temp_drill.db, Journal: WAL)
Total Applied Migrations: 16
[OK] Migration checksum integrity: VERIFIED
```

---

## 2. Test Verification Matrix

| Area | Assertion Details | Result |
|---|---|---|
| Token Validation | Invalid, expired, or malformed tokens rejected with 401 | PASSED |
| Multi-Worker Revocation | Revoked tokens stored in DB and rejected across workers | PASSED |
| Tenant Isolation | Cross-tenant data requests strictly isolated | PASSED |
| Transaction Rollback | Webhook and finance failures roll back atomically | PASSED |
| RBAC Matrix | Permissions matrix verified across all 6 platform roles | PASSED |
| Migration & Restore | Clean-environment database bootstrap & checksum check | PASSED |
