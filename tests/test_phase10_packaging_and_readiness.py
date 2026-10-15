"""Phase 10 — Install, Dependency Lock, Packaging & Model Readiness (QA-010).

Tests:
1. Version Consistency: Verify 3.0.1 across VERSION, pyproject.toml, packaging, and app.main CLI.
2. Dependency Lock Strict Pinning: Verify requirements.lock has == pins and reconciles direct dependencies.
3. Launcher Scripts Parity: Verify setup.bat/sh and launch.bat/sh mode dispatch and fail-closed error contracts.
4. CLI Flag Verification: Verify --help, --version, --check-startup exit 0 headlessly.
5. Post-Install Smoke Test: Verify scripts/smoke_test_install.py succeeds cleanly.
6. Clean Sandbox Database Bootstrap: Verify migration runner bootstraps fresh schema in clean path with integrity OK.
7. Transparent Model Readiness: Verify missing model path produces honest ungrounded/configured state, never false HEALTHY.
8. Release Manifest Integrity: Verify generate_release_manifest.py hashes migrations and records commit SHA.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.verify_dependency_lock import parse_requirements_lock, parse_requirements_txt, verify_dependency_lock


# =====================================================================
# 1. Version Consistency Across All Declared Files
# =====================================================================

def test_version_consistency():
    """Verify that product version 3.0.1 is consistently aligned across all project files."""
    version_file = PROJECT_ROOT / "VERSION"
    assert version_file.exists(), "VERSION file must exist"
    canonical_version = version_file.read_text(encoding="utf-8").strip()
    assert canonical_version == "3.0.1", f"Expected VERSION to be '3.0.1', got '{canonical_version}'"

    # pyproject.toml check
    pyproject_file = PROJECT_ROOT / "pyproject.toml"
    assert pyproject_file.exists(), "pyproject.toml must exist"
    pyproject_text = pyproject_file.read_text(encoding="utf-8")
    assert f'version = "{canonical_version}"' in pyproject_text, f"pyproject.toml version mismatch"

    # Inno Setup script check
    iss_file = PROJECT_ROOT / "packaging" / "installer.iss"
    if iss_file.exists():
        iss_text = iss_file.read_text(encoding="utf-8")
        assert f'#define MyAppVersion "{canonical_version}"' in iss_text

    # app.main --version CLI execution
    res = subprocess.run(
        [sys.executable, "-m", "app.main", "--version"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert canonical_version in res.stdout


# =====================================================================
# 2. Strict Pinning and Dependency Reconciliation
# =====================================================================

def test_dependency_lock_strict_pinning_and_reconciliation():
    """Verify requirements.lock is strictly pinned (==) and covers all direct requirements."""
    is_valid, errors = verify_dependency_lock(PROJECT_ROOT)
    assert is_valid, f"Dependency lock verification failed: {errors}"
    assert len(errors) == 0

    lock_path = PROJECT_ROOT / "requirements.lock"
    locked = parse_requirements_lock(lock_path)
    assert len(locked) >= 30, "Expected at least 30 locked packages"
    for pkg, ver in locked.items():
        assert ver != "UNPINNED", f"Package {pkg} is unpinned in requirements.lock"


def test_dependency_lock_verifier_catches_tampering(tmp_path):
    """Verify that verify_dependency_lock catches unpinned or missing packages."""
    fake_req = tmp_path / "requirements.txt"
    fake_lock = tmp_path / "requirements.lock"

    # Test missing package in lock
    fake_req.write_text("fastapi>=0.100.0\nuvicorn>=0.20.0\n", encoding="utf-8")
    fake_lock.write_text("fastapi==0.110.0\n", encoding="utf-8")
    is_valid, errors = verify_dependency_lock(tmp_path)
    assert not is_valid
    assert any("uvicorn" in err for err in errors)

    # Test unpinned package in lock
    fake_lock.write_text("fastapi>=0.110.0\nuvicorn==0.28.0\n", encoding="utf-8")
    is_valid, errors = verify_dependency_lock(tmp_path)
    assert not is_valid
    assert any("Loose / unpinned" in err for err in errors)


# =====================================================================
# 3. Launcher Scripts Mode Dispatch and Parity
# =====================================================================

def test_launcher_scripts_parity_and_contracts():
    """Verify setup and launch scripts on Windows and POSIX contain required dispatch modes."""
    setup_bat = (PROJECT_ROOT / "setup.bat").read_text(encoding="utf-8")
    setup_sh = (PROJECT_ROOT / "setup.sh").read_text(encoding="utf-8")
    launch_bat = (PROJECT_ROOT / "launch.bat").read_text(encoding="utf-8")
    launch_sh = (PROJECT_ROOT / "launch.sh").read_text(encoding="utf-8")

    # setup scripts must check requirements.lock first
    assert "requirements.lock" in setup_bat
    assert "requirements.lock" in setup_sh
    assert "verify_dependency_lock.py" in setup_bat
    assert "verify_dependency_lock.py" in setup_sh
    assert "compileall" in setup_bat
    assert "compileall" in setup_sh

    # launch scripts must support server and smoke modes
    assert "server" in launch_bat
    assert "smoke" in launch_bat
    assert "server" in launch_sh
    assert "smoke" in launch_sh


# =====================================================================
# 4. CLI Headless Arguments
# =====================================================================

def test_app_main_cli_arguments():
    """Verify that app.main responds to --help, --version, and --check-startup without launching GUI."""
    # Test --help
    help_res = subprocess.run(
        [sys.executable, "-m", "app.main", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert help_res.returncode == 0
    assert "Usage: python -m app.main" in help_res.stdout

    # Test --check-startup
    check_res = subprocess.run(
        [sys.executable, "-m", "app.main", "--check-startup"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert check_res.returncode == 0
    assert "[OK] Startup verification passed" in check_res.stdout


# =====================================================================
# 5. Post-Install Smoke Test
# =====================================================================

def test_post_install_smoke_test():
    """Verify that scripts/smoke_test_install.py executes cleanly and returns 0."""
    smoke_res = subprocess.run(
        [sys.executable, "scripts/smoke_test_install.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert smoke_res.returncode == 0, f"Smoke test failed: {smoke_res.stdout} {smoke_res.stderr}"
    assert "[SUCCESS] All post-installation smoke tests passed cleanly" in smoke_res.stdout


# =====================================================================
# 6. Clean Sandbox Database Bootstrap
# =====================================================================

def test_clean_sandbox_database_bootstrap(tmp_path):
    """Verify that migrations bootstrap a fresh, clean database schema with PRAGMA integrity ok."""
    sandbox_db = tmp_path / "sandbox_bootstrap.db"
    migrate_res = subprocess.run(
        [sys.executable, "scripts/migrate_db.py", "up", "--db-path", str(sandbox_db)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert migrate_res.returncode == 0, f"Migration failed: {migrate_res.stdout} {migrate_res.stderr}"
    assert sandbox_db.exists()

    # Verify PRAGMA integrity
    from central_platform.db import PlatformDatabase
    db = PlatformDatabase(db_path=str(sandbox_db))
    with db._get_connection() as conn:
        row = conn.execute("PRAGMA integrity_check;").fetchone()
        assert row[0] == "ok"
    db.close()


# =====================================================================
# 7. Transparent Model Readiness Probe
# =====================================================================

def test_transparent_model_readiness(tmp_path, monkeypatch):
    """Verify that missing model weights yield explicit ungrounded or non-healthy states, never fake success."""
    nonexistent_model = tmp_path / "nonexistent_model.gguf"
    monkeypatch.setenv("GAYATRI_MODEL_PATH", str(nonexistent_model))
    monkeypatch.setenv("GAYATRI_PRODUCTION_MODE", "true")

    # LocalProvider raises LocalModelError when model file is absent
    from core.providers.local import LocalModelError, LocalProvider
    LocalProvider._model = None  # Reset singleton
    with pytest.raises(LocalModelError) as exc_info:
        LocalProvider._load_model()
    assert "Model not found" in str(exc_info.value) or "does not exist" in str(exc_info.value)

    # DeploymentValidator evaluates provider readiness transparently
    from central_platform.deployment.validator import DeploymentValidator, ModelReadinessState
    deploy_db = tmp_path / "deploy_test.db"
    validator = DeploymentValidator(
        db_path=str(deploy_db),
        env_vars={"APP_ENV": "development", "GAYATRI_JWT_SECRET": "test_secret_32_chars_long_enough_key"},
    )
    report = validator.validate_model_providers()
    readiness = report.details.get("readiness_state")
    assert readiness != ModelReadinessState.HEALTHY.value, "Must not report HEALTHY when model file is missing"


# =====================================================================
# 8. Release Manifest Generation and Integrity
# =====================================================================

def test_release_manifest_generation_and_integrity(tmp_path):
    """Verify release manifest generator parses git state, migration inventory, and computes valid SHA-256."""
    from scripts.generate_release_manifest import build_manifest
    manifest = build_manifest()

    assert manifest["platform"] == "Gayatri School OS"
    assert "git" in manifest
    assert "commit_sha" in manifest["git"]
    assert len(manifest["git"]["commit_sha"]) == 40
    assert "schema" in manifest
    assert manifest["schema"]["total_migration_scripts"] >= 12
    assert "manifest_sha256" in manifest
    assert len(manifest["manifest_sha256"]) == 64
