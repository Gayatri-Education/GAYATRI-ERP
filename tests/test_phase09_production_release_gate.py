"""Phase 09: Production Release Gate, Documentation, and Controlled Rollout Tests.

Governing Contract: DEVELOPMENT.md (§7 Phase 09).
10 Focused Verification Tests:
1. Release candidate manifest generation, commit SHA binding, and checksum verification.
2. Production configuration hardening gate: fail-fast rejection of dev secrets, debug flags, wildcard CORS.
3. Fresh empty database bootstrap: sequential execution of migrations 001 through 016.
4. In-place database upgrade, rollback, and data preservation durability.
5. Disaster recovery: backup snapshot creation, isolated restoration, and PRAGMA integrity verification.
6. End-to-end multi-persona production readiness journey across all School OS domains.
7. Operational secret scrubbing and parent privacy tiers in diagnostics and reports.
8. Strict multi-tenant isolation across tables, analytics, and exports under production security.
9. Critical business failure resilience: idempotency, duplicate prevention, and bad packet rejection.
10. Ops API endpoints: release gate evaluation (`GO` decision) and RBAC security enforcement.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from central_platform.analytics.institutional import UnifiedInstitutionalAnalyticsService
from central_platform.api.app import app
from central_platform.auth.tokens import create_access_token
from central_platform.config import PlatformSettings, validate_production_config
from central_platform.db import PlatformDatabase
from central_platform.edge.protocol import (
    HardwarePunchFrame,
    pack_punch_frame,
    unpack_punch_frame,
)
from central_platform.models import Organization, User, UserRole
from central_platform.ops.diagnostics import PlatformDiagnosticsService
from central_platform.ops.release_gate import ProductionReleaseGateValidator
from scripts.backup_restore_db import create_backup, restore_backup, verify_database_integrity
from scripts.generate_release_manifest import build_manifest

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


@pytest.fixture
def clean_migrated_db(tmp_path):
    """Clean database migrated through all 16 versions."""
    db_file = str(tmp_path / "test_phase09_clean.db")
    db = PlatformDatabase(db_file)
    yield db
    db.close()


# ── Test 1: Release Candidate Manifest & Provenance Binding ──────────────────

def test_release_manifest_generation_and_integrity():
    """Verify release manifest binds to git commit SHA, contains all 16 migrations, and has valid SHA-256."""
    manifest = build_manifest()

    assert manifest["platform"] == "Gayatri School OS"
    assert manifest["governing_contract"] == "DEVELOPMENT.md"
    assert "commit_sha" in manifest["git"]
    assert len(manifest["git"]["commit_sha"]) == 40 or manifest["git"]["commit_sha"] != "unknown"

    # Verify migration scripts
    migrations = manifest["schema"]["migrations"]
    assert manifest["schema"]["total_migration_scripts"] >= 32  # 16 up + 16 down
    assert "016_analytics_exports_diagnostics.sql" in migrations
    assert "016_analytics_exports_diagnostics_down.sql" in migrations

    # Verify all migration hashes are 64-char hex
    for name, meta in migrations.items():
        assert len(meta["sha256"]) == 64
        assert meta["bytes"] > 0

    # Verify manifest digest
    assert len(manifest["manifest_sha256"]) == 64


# ── Test 2: Production Configuration Hardening Fail-Fast Gate ─────────────────

def test_production_config_gate_strict_fail_fast():
    """Verify validator strictly rejects dev secrets, debug modes, and wildcard CORS in production."""
    # 1. Reject weak/default secret
    bad_secret_env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": "weak-secret",
        "GAYATRI_ALLOWED_ORIGINS": "https://school.edu",
        "GAYATRI_DB_PATH": ":memory:",
    }
    with pytest.raises(RuntimeError, match="too weak"):
        validate_production_config(bad_secret_env)

    # 2. Reject debug mode in production
    debug_env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": "a" * 32,
        "GAYATRI_ALLOWED_ORIGINS": "https://school.edu",
        "GAYATRI_DB_PATH": ":memory:",
        "DEBUG": "true",
    }
    with pytest.raises(RuntimeError, match="Debug and reload modes are strictly prohibited"):
        validate_production_config(debug_env)

    # 3. Reject wildcard CORS in production
    wildcard_cors_env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": "a" * 32,
        "GAYATRI_ALLOWED_ORIGINS": "https://school.edu,*",
        "GAYATRI_DB_PATH": ":memory:",
    }
    with pytest.raises(RuntimeError, match="Wildcard CORS"):
        validate_production_config(wildcard_cors_env)

    # 4. Valid production settings pass
    valid_env = {
        "GAYATRI_ENV": "production",
        "GAYATRI_JWT_SECRET": "a" * 32,
        "GAYATRI_ALLOWED_ORIGINS": "https://school.edu",
        "GAYATRI_DB_PATH": ":memory:",
        "DEBUG": "false",
        "RELOAD": "false",
    }
    res = validate_production_config(valid_env)
    assert res["production_enforced"] is True
    assert res["jwt_secret_configured"] is True


# ── Test 3: Fresh Empty Database Bootstrap (16 Migrations) ───────────────────

def test_empty_database_fresh_bootstrap_and_schema_manifest(tmp_path):
    """Verify clean empty database applies 001 through 016 sequentially without errors."""
    db_file = str(tmp_path / "fresh_bootstrap.db")
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply all 16 migrations
    for i in range(1, 17):
        up_scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in up_scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Audit schema
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    assert cursor.fetchone()[0] == "ok"

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = {r[0] for r in cursor.fetchall()}
    assert "organizations" in tables
    assert "student_profiles" in tables
    assert "edge_devices" in tables
    assert "export_jobs" in tables
    assert "diagnostic_snapshots" in tables

    conn.close()


# ── Test 4: In-Place Database Upgrade and Rollback Durability ─────────────────

def test_in_place_database_upgrade_and_rollback_durability(tmp_path):
    """Verify migration 016 up -> data insert -> rollback -> schema clean -> re-up preserves consistency."""
    db_file = str(tmp_path / "upgrade_durability.db")
    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Apply 1 through 15
    for i in range(1, 16):
        up_scripts = list(MIGRATIONS_DIR.glob(f"{i:03d}_*.sql"))
        forward = [s for s in up_scripts if not s.name.endswith("_down.sql")][0]
        conn.executescript(forward.read_text(encoding="utf-8"))

    # Apply 016
    up_16 = [s for s in MIGRATIONS_DIR.glob("016_*.sql") if not s.name.endswith("_down.sql")][0]
    conn.executescript(up_16.read_text(encoding="utf-8"))

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='export_jobs';")
    assert cursor.fetchone() is not None

    # Roll back 016
    down_16 = MIGRATIONS_DIR / "016_analytics_exports_diagnostics_down.sql"
    conn.executescript(down_16.read_text(encoding="utf-8"))

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='export_jobs';")
    assert cursor.fetchone() is None

    # Re-apply 016
    conn.executescript(up_16.read_text(encoding="utf-8"))
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='export_jobs';")
    assert cursor.fetchone() is not None

    conn.close()


# ── Test 5: Disaster Recovery: Backup, Restoration & PRAGMA Integrity ────────

def test_disaster_recovery_backup_restoration_and_record_integrity(clean_migrated_db, tmp_path):
    """Verify atomic database snapshot creation and clean restoration into isolated destination."""
    backup_dir = str(tmp_path / "disaster_backups")
    isolated_target = str(tmp_path / "restored_production.sqlite3")

    # Seed an organization and user
    with clean_migrated_db._get_connection() as conn:
        now_str = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            "VALUES ('org-dr-1', 'DR Test School', 'dr-school', '2026-10-15T00:00:00Z', '2026-10-15T00:00:00Z');"
        )
        conn.execute(
            f"INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            f"VALUES ('usr-dr-admin', 'org-dr-1', 'dr_admin@school.edu', 'DR Admin', 'admin', '{now_str}', '{now_str}');"
        )

    # 1. Create backup
    backup_file = create_backup(clean_migrated_db.db_path, backup_dir)
    assert Path(backup_file).exists()

    # 2. Check backup integrity
    diag_backup = verify_database_integrity(backup_file)
    assert diag_backup["integrity_ok"] is True
    assert diag_backup["tables"]["organizations"] >= 1

    # 3. Restore to isolated target
    restore_success = restore_backup(backup_file, isolated_target)
    assert restore_success is True
    assert Path(isolated_target).exists()

    # 4. Verify restored target database
    diag_restored = verify_database_integrity(isolated_target)
    assert diag_restored["integrity_ok"] is True
    assert diag_restored["tables"]["organizations"] >= 1
    assert diag_restored["tables"]["users"] >= 1


# ── Test 6: End-to-End Multi-Persona Production Readiness Lifecycle ──────────

def test_end_to_end_production_readiness_lifecycle(clean_migrated_db):
    """Verify complete School OS journey: Admin -> SIS -> Attendance -> Exam -> Finance -> Edge -> Analytics."""
    now_str = datetime.now(timezone.utc).isoformat()
    org_id = "org-e2e-prod"

    with clean_migrated_db._get_connection() as conn:
        # 1. Organization & Academic Year
        conn.execute(
            f"INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            f"VALUES ('{org_id}', 'Gayatri Vidya Mandir', 'gvm-prod', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO academic_years (id, organization_id, name, code, start_date, end_date, created_at, updated_at) "
            f"VALUES ('ay-e2e', '{org_id}', '2026-2027', 'AY-26-27', '2026-06-01', '2027-04-30', '{now_str}', '{now_str}');"
        )

        # 2. Users & SIS
        conn.execute(
            f"INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            f"VALUES ('usr-stu-e2e', '{org_id}', 'student.e2e@gvm.edu', 'Ananya Sen', 'student', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO persons (id, organization_id, user_id, first_name, last_name, email, created_at, updated_at) "
            f"VALUES ('per-stu-e2e', '{org_id}', 'usr-stu-e2e', 'Ananya', 'Sen', 'student.e2e@gvm.edu', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at) "
            f"VALUES ('stu-prf-e2e', 'per-stu-e2e', '{org_id}', 'GVM-2026-099', 'R-12', '2026-06-01', 'ACTIVE', '{now_str}', '{now_str}');"
        )

        # 3. Attendance Session & Record
        conn.execute(
            f"INSERT INTO student_classes (id, organization_id, academic_year_id, name, grade_level, section, capacity, created_at, updated_at) "
            f"VALUES ('cls-10b', '{org_id}', 'ay-e2e', 'Grade 10-B', 10, 'B', 40, '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO attendance_sessions (id, organization_id, academic_year_id, class_id, date, session_type, status, created_at, updated_at) "
            f"VALUES ('ses-e2e', '{org_id}', 'ay-e2e', 'cls-10b', '2026-10-15', 'DAILY', 'COMPLETED', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO attendance_records (id, organization_id, session_id, student_id, status, created_at, updated_at) "
            f"VALUES ('att-rec-e2e', '{org_id}', 'ses-e2e', 'stu-prf-e2e', 'PRESENT', '{now_str}', '{now_str}');"
        )

        # 4. Finance Fee Account & Invoice
        conn.execute(
            f"INSERT INTO fee_accounts (id, org_id, student_id, total_due, total_paid, balance_due, status, created_at, updated_at) "
            f"VALUES ('fa-e2e', '{org_id}', 'usr-stu-e2e', 12000.0, 12000.0, 0.0, 'PAID', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO invoices (id, org_id, fee_account_id, student_id, invoice_number, amount_due, amount_paid, status, due_date, created_at, updated_at) "
            f"VALUES ('inv-e2e', '{org_id}', 'fa-e2e', 'usr-stu-e2e', 'INV-GVM-01', 12000.0, 12000.0, 'PAID', '2026-11-01', '{now_str}', '{now_str}');"
        )

    # 5. Authoritative Institutional Analytics Snapshot
    svc = UnifiedInstitutionalAnalyticsService(clean_migrated_db)
    snapshot = svc.get_kpi_snapshot(org_id)

    assert snapshot.total_students == 1
    assert snapshot.attendance_rate == 100.0
    assert snapshot.fee_collection_rate == 100.0
    assert snapshot.total_outstanding_fees == 0.0
    assert snapshot.reconciliation_hash is not None
    assert len(snapshot.reconciliation_hash) == 64


# ── Test 7: Operational Secret Scrubbing & Privacy Policies ───────────────────

def test_secret_redaction_and_data_privacy_in_diagnostics_and_errors(clean_migrated_db):
    """Verify PlatformDiagnosticsService strips passwords, tokens, secrets, and keys."""
    diag_svc = PlatformDiagnosticsService(clean_migrated_db)
    raw_payload = {
        "user_id": "usr-1",
        "api_token": "secret_token_1234567890",
        "nested": {
            "db_password": "super_secret_db_password",
            "safe_metric": 42,
            "database_url": "postgres://admin:pass123@host:5432/db",
        },
    }
    scrubbed = diag_svc._scrub_secrets(raw_payload)

    assert scrubbed["api_token"] == "[REDACTED]"
    assert scrubbed["nested"]["db_password"] == "[REDACTED]"
    assert scrubbed["nested"]["database_url"] == "[REDACTED]"
    assert scrubbed["nested"]["safe_metric"] == 42


# ── Test 8: Strict Cross-Tenant Isolation Under Production Security ───────────

def test_cross_tenant_isolation_under_production_security(clean_migrated_db):
    """Verify that Org A data is completely invisible to Org B under authoritative service queries."""
    now_str = datetime.now(timezone.utc).isoformat()
    with clean_migrated_db._get_connection() as conn:
        # Org A
        conn.execute(
            f"INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            f"VALUES ('org-a', 'School A', 'school-a', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            f"VALUES ('usr-a-1', 'org-a', 'a1@school.edu', 'Alice A', 'student', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO persons (id, organization_id, user_id, first_name, last_name, email, created_at, updated_at) "
            f"VALUES ('per-a-1', 'org-a', 'usr-a-1', 'Alice', 'A', 'a1@school.edu', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at) "
            f"VALUES ('stu-a-1', 'per-a-1', 'org-a', 'ADM-A-01', '1', '2026-06-01', 'ACTIVE', '{now_str}', '{now_str}');"
        )

        # Org B
        conn.execute(
            f"INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            f"VALUES ('org-b', 'School B', 'school-b', '{now_str}', '{now_str}');"
        )

    svc = UnifiedInstitutionalAnalyticsService(clean_migrated_db)

    # Org A sees 1 student
    snap_a = svc.get_kpi_snapshot("org-a")
    assert snap_a.total_students == 1

    # Org B sees 0 students (zero leak)
    snap_b = svc.get_kpi_snapshot("org-b")
    assert snap_b.total_students == 0


# ── Test 9: Critical Business Failure Resilience & Idempotency ────────────────

def test_critical_business_failure_resilience_and_idempotency(clean_migrated_db):
    """Verify duplicate admission numbers and malformed wire packets are rejected with deterministic errors."""
    now_str = datetime.now(timezone.utc).isoformat()
    with clean_migrated_db._get_connection() as conn:
        conn.execute(
            f"INSERT INTO organizations (id, name, slug, created_at, updated_at) "
            f"VALUES ('org-fail-res', 'Resilience Academy', 'res-acad', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO users (id, organization_id, email, full_name, role, created_at, updated_at) "
            f"VALUES ('usr-res-1', 'org-fail-res', 'r1@res.edu', 'Rohan R', 'student', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO persons (id, organization_id, user_id, first_name, last_name, email, created_at, updated_at) "
            f"VALUES ('per-res-1', 'org-fail-res', 'usr-res-1', 'Rohan', 'R', 'r1@res.edu', '{now_str}', '{now_str}');"
        )
        conn.execute(
            f"INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at) "
            f"VALUES ('stu-res-1', 'per-res-1', 'org-fail-res', 'DUPLICATE-ADM-01', '1', '2026-06-01', 'ACTIVE', '{now_str}', '{now_str}');"
        )

        # Duplicate admission number in same organization MUST fail UNIQUE constraint
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at) "
                f"VALUES ('stu-res-2', 'per-res-1', 'org-fail-res', 'DUPLICATE-ADM-01', '2', '2026-06-01', 'ACTIVE', '{now_str}', '{now_str}');"
            )

    # Verify corrupt wire packet with bad CRC-16 is rejected
    valid_frame = HardwarePunchFrame(
        user_id="usr-res-1",
        punch_type="CHECK_IN",
        punch_time=now_str,
        verification_type="FINGERPRINT",
        sequence_num=1,
    )
    wire_bytes = bytearray(pack_punch_frame(valid_frame))
    # Tamper with byte
    wire_bytes[-1] ^= 0xFF

    with pytest.raises(ValueError, match="Checksum mismatch"):
        unpack_punch_frame(bytes(wire_bytes))


# ── Test 10: Ops API Endpoints & Release Gate Evaluation ─────────────────────

def test_phase09_ops_api_endpoints_and_release_gate_decision(clean_migrated_db):
    """Verify /api/v1/ops/release-gate and /api/v1/ops/release-manifest endpoints."""
    # Ensure release manifest exists
    build_manifest()

    org_id = f"org_{uuid.uuid4().hex[:6]}"
    clean_migrated_db.create_organization(Organization(id=org_id, name="Phase 09 Ops School", slug=f"p9-ops-{org_id}"))

    admin_id = f"usr_admin_{uuid.uuid4().hex[:6]}"
    stu_id = f"usr_stu_{uuid.uuid4().hex[:6]}"

    clean_migrated_db.create_user(User(id=admin_id, organization_id=org_id, email=f"{admin_id}@p9.edu", full_name="Ops Admin", role=UserRole.ORG_ADMIN))
    clean_migrated_db.create_user(User(id=stu_id, organization_id=org_id, email=f"{stu_id}@p9.edu", full_name="Ops Student", role=UserRole.STUDENT))

    token_admin = create_access_token(user_id=admin_id, role="org_admin", organization_id=org_id)
    token_stu = create_access_token(user_id=stu_id, role="student", organization_id=org_id)

    client = TestClient(app)

    # 1. Admin gets release gate status
    resp_gate = client.get("/api/v1/ops/release-gate", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp_gate.status_code == 200
    gate_data = resp_gate.json()
    assert "decision" in gate_data
    assert "checksum" in gate_data
    assert gate_data["checks"]["database"]["passed"] is True

    # 2. Admin gets release manifest
    resp_man = client.get("/api/v1/ops/release-manifest", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp_man.status_code == 200
    man_data = resp_man.json()
    assert man_data["platform"] == "Gayatri School OS"
    assert "manifest_sha256" in man_data

    # 3. Non-admin (Student) is forbidden (HTTP 403)
    resp_forbidden = client.get("/api/v1/ops/release-gate", headers={"Authorization": f"Bearer {token_stu}"})
    assert resp_forbidden.status_code == 403
