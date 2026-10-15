# Phase 00 Regression Evidence Log

**Document:** `docs/erp_agent/regressions/PHASE_00_REGRESSION.md`  
**Execution Phase:** Phase 00 — Discovery and Independent Baseline  
**Date:** 2026-10-15  
**Baseline Commit:** `8b24bb716bcfce558acd3dd4253c641774905ac6`  

---

## 1. Test Execution Commands & Outputs

### 1.1 Compilation Verification
- **Command:** `python -m compileall -q app core central_platform tests scripts`
- **Exit Code:** `0`
- **Output:** Clean, zero syntax or byte-compilation errors.

### 1.2 Database Migration Ledger Verification
- **Command:** `python scripts/migrate_db.py status --db-path gayatri_local.db`
- **Exit Code:** `0`
- **Output:**
```text
Database Backend: SQLite (Target: gayatri_local.db, Journal: WAL)
Total Applied Migrations: 16
 - Version: 001 | Initial Authoritative Platform Schema | Applied: 2026-10-14T17:42:57.404497+00:00
 - Version: 002 | Curriculum Abstraction | Applied: 2026-10-14T17:42:57.419163+00:00
 - Version: 003 | Fee Management Schema | Applied: 2026-10-14T17:42:57.420880+00:00
 - Version: 004 | Course Domain Model | Applied: 2026-10-14T17:42:57.427715+00:00
 - Version: 005 | Knowledge Assets | Applied: 2026-10-14T17:42:57.437534+00:00
 - Version: 006 | Scoped Rag Authorization | Applied: 2026-10-14T17:42:57.445574+00:00
 - Version: 007 | Teacher Instruction Hierarchy | Applied: 2026-10-14T17:42:57.459319+00:00
 - Version: 008 | Sync Operations | Applied: 2026-10-14T17:42:57.472435+00:00
 - Version: 009 | Shared Identity And Entitlements | Applied: 2026-10-14T17:55:39.218819+00:00
 - Version: 010 | Admissions And Academic Calendar | Applied: 2026-10-14T18:57:31.033938+00:00
 - Version: 011 | Attendance Timetable Communications | Applied: 2026-10-14T18:57:31.043137+00:00
 - Version: 012 | Examinations Grading Report Cards | Applied: 2026-10-14T18:57:31.047355+00:00
 - Version: 013 | Finance Payments Reconciliation | Applied: 2026-10-14T18:57:31.049874+00:00
 - Version: 014 | Full Erp Expansion | Applied: 2026-10-14T18:57:31.049874+00:00
 - Version: 015 | Offline Sync Edge Daemon | Applied: 2026-10-14T19:09:06.790457+00:00
 - Version: 016 | Analytics Exports Diagnostics | Applied: 2026-10-14T19:20:23.785775+00:00
[OK] Migration checksum integrity: VERIFIED
```

### 1.3 Architecture Test Suite
- **Command:** `pytest -v tests/architecture`
- **Exit Code:** `0`
- **Output:**
```text
tests/architecture/test_anti_chemistry_coupling.py::test_courses_domain_zero_chemistry_coupling PASSED [  7%]
tests/architecture/test_anti_chemistry_coupling.py::test_architecture_guard_negative_synthetic_detection PASSED [ 15%]
tests/architecture/test_anti_demo_roster.py::test_courses_and_models_zero_demo_roster PASSED [ 23%]
tests/architecture/test_anti_demo_roster.py::test_demo_roster_guard_negative_synthetic_detection PASSED [ 30%]
tests/architecture/test_anti_legacy_imports.py::test_central_platform_zero_legacy_imports PASSED [ 38%]
tests/architecture/test_anti_legacy_imports.py::test_zero_legacy_imports_in_active_codebase PASSED [ 46%]
tests/architecture/test_anti_legacy_imports.py::test_legacy_guard_negative_synthetic_detection PASSED [ 53%]
tests/architecture/test_anti_legacy_imports.py::test_legacy_directory_eliminated PASSED [ 61%]
tests/architecture/test_migration_integrity.py::test_migrations_have_corresponding_down_scripts PASSED [ 69%]
tests/architecture/test_migration_integrity.py::test_migrations_no_duplicate_create_table_statements PASSED [ 76%]
tests/architecture/test_migration_integrity.py::test_migration_integrity_guard_negative_synthetic_detection PASSED [ 84%]
tests/architecture/test_model_config_registry.py::test_model_manifest_valid_and_complete PASSED [ 92%]
tests/architecture/test_model_config_registry.py::test_core_config_importable PASSED [100%]
============================= 13 passed in 1.08s ==============================
```

### 1.4 Full Headless Regression Suite
- **Command:** `python -m pytest -q -m "not gui"`
- **Exit Code:** `0`
- **Output Summary:**
```text
================ 1775 passed, 2 warnings in 205.11s (0:03:25) =================
```
- **Passed:** 1,775
- **Failed:** 0
- **Errors:** 0
- **Skipped:** 0
- **Warnings:** 2 (Starlette deprecation notices)
- **Duration:** 205.11s
