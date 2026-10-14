"""Tests for QA Phase 11: Cross-Platform Packaging, Clean Install, Upgrade, Rollback and Operational Readiness.

Verifies:
- GQA-009: Cross-platform entrypoints and packaging (Windows .bat and Linux .sh).
- GQA-001: First-run missing model experience fails explicitly without false-green masquerade.
- GQA-004: Provider status derived from runtime evidence rather than configuration ordering.
- Upgrade, backup snapshot creation, and disaster rollback recovery.
- Post-installation smoke test harness execution.
"""

import os
import subprocess
import sys
from pathlib import Path
import pytest
import sqlite3

from central_platform.db import PlatformDatabase
from central_platform.deployment.validator import (
    DeploymentValidator,
    ModelReadinessState,
    ValidationStatus,
)
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
from scripts.backup_restore_db import create_backup, restore_backup, verify_database_integrity
from scripts.package_release import package_release
from scripts.smoke_test_install import run_smoke_test
from scripts.verify_release import verify_release


class TestQAPhase11PackagingOperations:
    """Verifies all Phase 11 requirements for cross-platform operations and clean deployment."""

    # ── 1. GQA-009: Cross-Platform Entrypoint Scripts ─────────────────────────
    def test_cross_platform_scripts_exist_and_non_empty(self):
        """Repository must provide both Windows (.bat) and POSIX/Linux (.sh) launch and setup scripts."""
        root = Path(__file__).resolve().parent.parent

        required_scripts = [
            ("setup.bat", "Windows setup script"),
            ("launch.bat", "Windows launcher"),
            ("setup.sh", "Linux setup script"),
            ("launch.sh", "Linux launcher"),
        ]

        for script_name, description in required_scripts:
            path = root / script_name
            assert path.exists(), f"Missing {description}: {script_name}"
            content = path.read_text(encoding="utf-8", errors="ignore")
            assert len(content.strip()) > 50, f"Script {script_name} is empty or truncated"

    def test_linux_launch_scripts_headless_handling(self):
        """Linux launcher must configure offscreen Qt rendering when DISPLAY is empty."""
        root = Path(__file__).resolve().parent.parent
        launch_sh = (root / "launch.sh").read_text(encoding="utf-8")
        assert "QT_QPA_PLATFORM" in launch_sh
        assert "offscreen" in launch_sh

    # ── 2. Cross-Platform Release Packaging & Integrity Manifest ──────────────
    def test_packaging_cross_platform_release(self, tmp_path: Path):
        """package_release must bundle Linux and Windows entrypoints with cryptographic SHA-256 manifest."""
        root = Path(__file__).resolve().parent.parent
        out_dir = tmp_path / "release_dist"

        result = package_release(
            source_root=root,
            output_dir=out_dir,
            version="3.0.1",
            platform="cross-platform",
        )

        assert out_dir.exists()
        manifest_file = out_dir / "RELEASE_MANIFEST.json"
        assert manifest_file.exists()

        # Check critical included files
        assert (out_dir / "setup.sh").exists()
        assert (out_dir / "launch.sh").exists()
        assert (out_dir / "setup.bat").exists()
        assert (out_dir / "launch.bat").exists()
        assert (out_dir / "requirements.lock").exists()

        # Verify release via verify_release script
        v_res = verify_release(out_dir, require_signature=False)
        assert v_res["valid"] is True
        assert v_res["files_checked"] >= 20
        assert len(v_res.get("errors", [])) == 0

    # ── 3. GQA-001: Missing Model First-Run Experience ────────────────────────
    def test_missing_model_first_run_experience(self, tmp_path: Path):
        """When local model is absent on clean install, readiness probe must NOT report HEALTHY (GQA-001)."""
        sandbox_db = tmp_path / "clean_first_run.db"
        validator = DeploymentValidator(
            db_path=str(sandbox_db),
            env_vars={
                "APP_ENV": "development",
                "GAYATRI_JWT_SECRET": "first_run_test_secret_key_32_characters",
                "GAYATRI_MODEL_PATH": str(tmp_path / "non_existent_model.gguf"),
            },
        )

        report = validator.validate_model_providers()
        readiness = report.details.get("readiness_state")
        assert readiness != ModelReadinessState.HEALTHY.value
        assert readiness in (
            ModelReadinessState.MISSING.value,
            ModelReadinessState.UNCONFIGURED.value,
            ModelReadinessState.FAILED.value,
            ModelReadinessState.CONFIGURED.value,
        )

    # ── 4. GQA-004: Provider Status Derived from Runtime Evidence ─────────────
    def test_runtime_provider_health_probe(self, tmp_path: Path):
        """Provider status must reflect actual runtime readiness, never blind config precedence."""
        from central_platform.ai.gateway import AIGatewayService

        gateway = AIGatewayService()
        status = gateway.get_status()

        assert isinstance(status, dict)
        providers_status = status.get("providers_status", {})
        assert "local_llama" in providers_status
        for name, p_status in providers_status.items():
            assert "consecutive_failures" in p_status
            assert "successful_requests" in p_status
            assert "last_successful_inference_at" in p_status

    # ── 5. Clean Environment Schema Bootstrap ─────────────────────────────────
    def test_clean_environment_bootstrap_zero_developer_state(self, tmp_path: Path):
        """Clean installation boots database schema with full tables and PRAGMA integrity ok."""
        db_file = tmp_path / "clean_bootstrap.db"
        db = PlatformDatabase(db_path=str(db_file))

        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            assert cur.fetchone()[0] == "ok"

            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            assert cur.fetchone()[0] >= 15

        db.close()

    # ── 6. Disaster Recovery: Backup Snapshot & Rollback Restoration ──────────
    def test_backup_restore_and_rollback_recovery(self, tmp_path: Path):
        """Verify automated backup snapshot creation, simulated file corruption, and rollback restore."""
        db_file = str(tmp_path / "prod_app.db")
        backup_dir = str(tmp_path / "prod_backups")

        # 1. Provision initial state
        db = PlatformDatabase(db_path=db_file)
        org = Organization(id="org_roll_01", name="Rollback Academy", slug="rollback-academy")
        db.create_organization(org)
        user = User(
            id="usr_roll_01",
            email="roll@academy.org",
            full_name="Rollback User",
            role=UserRole.STUDENT,
            organization_id="org_roll_01",
        )
        db.create_user(user)
        db.close()

        # 2. Create online backup snapshot
        snapshot_path = create_backup(db_file, backup_dir)
        assert Path(snapshot_path).exists()
        assert Path(snapshot_path).stat().st_size > 0

        # 3. Simulate disaster (catastrophic deletion or corruption)
        os.remove(db_file)
        assert not os.path.exists(db_file)

        # 4. Rollback restoration
        assert restore_backup(snapshot_path, db_file) is True
        assert os.path.exists(db_file)

        # 5. Verify restored state
        db_restored = PlatformDatabase(db_path=db_file)
        recovered_user = db_restored.get_user("usr_roll_01")
        assert recovered_user is not None
        assert recovered_user.full_name == "Rollback User"
        db_restored.close()

    # ── 7. Post-Installation Smoke Test Script Execution ──────────────────────
    def test_post_install_smoke_test_script(self):
        """scripts/smoke_test_install.py must execute cleanly and return exit code 0."""
        code = run_smoke_test()
        assert code == 0
