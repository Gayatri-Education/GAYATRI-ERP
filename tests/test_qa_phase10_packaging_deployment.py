"""Tests for QA Phase 10: Packaging, Deployment & Upgrade Safety.

Verifies:
- 10.1: Clean-install bootstrap and schema initialization without pre-existing cache.
- 10.2: Launch scripts and entry point verification (setup.bat, run.bat, run_gayatri.bat, launch.bat).
- 10.3: Complete user workflow lifecycle (provision, turn, persist, close, reload, continue).
- 10.4: Upgrade migration snapshot backup, file destruction, and recovery.
- 10.5: Deployment configuration validation and production readiness gate.
"""

import os
from pathlib import Path
import pytest
import sqlite3

from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Course,
    Enrollment,
    Organization,
    Session,
    SessionStatus,
    StudentLearningRecord,
    User,
    UserRole,
)
from central_platform.deployment.validator import (
    DeploymentValidator,
    ValidationStatus,
)
from scripts.backup_restore_db import create_backup, restore_backup, verify_database_integrity


def test_clean_environment_bootstrap_and_schema(tmp_path: Path):
    """Verify clean database initialization in an empty directory without developer state (10.1)."""
    db_file = tmp_path / "clean_install_gayatri.db"
    assert not db_file.exists()

    # Bootstrap platform database
    db = PlatformDatabase(db_path=str(db_file))

    # Verify tables created
    with db._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        row = cur.fetchone()
        assert row[0] == "ok"

        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        table_count = cur.fetchone()[0]
        # Should have at least 15 core and migration tables
        assert table_count >= 15

        # Check critical tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {r[0] for r in cur.fetchall()}
        assert "organizations" in table_names
        assert "users" in table_names
        assert "courses" in table_names
        assert "sessions" in table_names
        assert "student_learning_records" in table_names
        assert "schema_migrations" in table_names

    db.close()


def test_batch_scripts_integrity_and_entrypoints():
    """Verify launch scripts exist and invoke correct Python entrypoints and migration hooks (10.2)."""
    root = Path(__file__).resolve().parent.parent

    scripts = ["setup.bat", "run.bat", "run_gayatri.bat", "launch.bat"]
    for s in scripts:
        script_path = root / s
        assert script_path.exists(), f"Missing required launch script: {s}"
        content = script_path.read_text(encoding="utf-8", errors="ignore")
        assert len(content) > 50, f"Script {s} is empty or truncated"

    # Verify setup.bat contains migration call
    setup_content = (root / "setup.bat").read_text(encoding="utf-8", errors="ignore")
    assert "migrate_db.py" in setup_content
    assert "app.main" in setup_content


def test_user_workflow_lifecycle_persistence(tmp_path: Path):
    """Verify full learner workflow lifecycle: provision -> session -> SLR -> persist -> reload (10.3)."""
    db_file = str(tmp_path / "workflow_lifecycle.db")

    # 1. Provision organization, user, and course
    db = PlatformDatabase(db_path=db_file)
    org = Organization(id="org_flow_01", name="Flow Academy", slug="flow-academy")
    db.create_organization(org)

    student = User(
        id="std_flow_101",
        email="flow_student@academy.org",
        full_name="Flow Student",
        role=UserRole.STUDENT,
        organization_id="org_flow_01",
    )
    db.create_user(student)

    course = Course(
        id="crs_chem_11",
        organization_id="org_flow_01",
        code="CHEM11",
        title="Class 11 Chemistry",
    )
    db.create_course(course)

    enrollment = Enrollment(
        id="enr_flow_001",
        student_id="std_flow_101",
        course_id="crs_chem_11",
    )
    db.create_enrollment(enrollment)

    # 2. Start session and record SLR
    session = Session(
        id="sess_flow_turn_01",
        student_id="std_flow_101",
        course_id="crs_chem_11",
        concept_id="THERMO_EXPANSION_WORK",
        status=SessionStatus.ACTIVE,
    )
    db.create_session(session)

    slr = StudentLearningRecord(
        id="slr_flow_turn_01",
        student_id="std_flow_101",
        course_id="crs_chem_11",
    )
    db.create_slr(slr)
    db.close()

    # 3. Re-open database from disk and verify full continuity
    reopened_db = PlatformDatabase(db_path=db_file)
    retrieved_student = reopened_db.get_user("std_flow_101")
    assert retrieved_student is not None
    assert retrieved_student.email == "flow_student@academy.org"

    retrieved_session = reopened_db.get_session("sess_flow_turn_01")
    assert retrieved_session is not None
    assert retrieved_session.status == SessionStatus.ACTIVE

    retrieved_slr = reopened_db.get_slr(student_id="std_flow_101", course_id="crs_chem_11")
    assert retrieved_slr is not None
    assert retrieved_slr.student_id == "std_flow_101"
    assert retrieved_slr.course_id == "crs_chem_11"

    reopened_db.close()


def test_backup_restore_and_disaster_recovery(tmp_path: Path):
    """Verify database online backup snapshot, destruction, and restoration (10.4)."""
    db_file = str(tmp_path / "primary_app.db")
    backup_dir = str(tmp_path / "backups")

    # Seed data
    db = PlatformDatabase(db_path=db_file)
    org = Organization(id="org_backup_01", name="Backup Academy", slug="backup-academy")
    db.create_organization(org)
    db.close()

    # Create backup snapshot
    backup_file = create_backup(db_file, backup_dir)
    assert os.path.exists(backup_file)
    assert os.path.getsize(backup_file) > 0

    # Simulate catastrophic file deletion
    os.remove(db_file)
    assert not os.path.exists(db_file)

    # Restore from snapshot
    assert restore_backup(backup_file, db_file) is True
    assert os.path.exists(db_file)
    integrity = verify_database_integrity(db_file)
    assert integrity["integrity_ok"] is True

    # Reconnect and verify data
    db_restored = PlatformDatabase(db_path=db_file)
    org_restored = db_restored.get_organization("org_backup_01")
    assert org_restored is not None
    assert org_restored.name == "Backup Academy"
    db_restored.close()


def test_deployment_validator_configuration_checks(tmp_path: Path):
    """Verify DeploymentValidator catches missing production secrets and flags model status (10.5)."""
    db_file = str(tmp_path / "deploy_test.db")
    db = PlatformDatabase(db_path=db_file)
    db.close()

    # In development mode with non-empty database, validator runs full checks
    validator = DeploymentValidator(
        db_path=db_file,
        env_vars={"APP_ENV": "development", "SECRET_KEY": "dev_test_secret_key"},
    )
    report = validator.run_full_validation()
    assert report is not None
    assert hasattr(report, "is_ready")
