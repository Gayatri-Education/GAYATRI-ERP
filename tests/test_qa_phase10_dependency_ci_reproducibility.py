"""Tests for QA Phase 10: Dependency Locking, CI Design and Release Reproducibility.

Verifies:
- GQA-009: Target matrix includes both windows-latest and ubuntu-latest.
- GQA-014: Pinned requirements.lock installed in CI and reconciled with requirements.txt.
- GQA-016: CI pipeline declared with least privilege, fail-closed error handling,
  compilation hygiene, architecture guardrails, and isolated database migrations.
"""

from pathlib import Path
import pytest
import yaml

from scripts.verify_ci_pipeline import verify_ci_pipeline
from scripts.verify_dependency_lock import (
    normalize_package_name,
    parse_requirements_lock,
    parse_requirements_txt,
    verify_dependency_lock,
)


class TestQAPhase10DependencyCIReproducibility:
    """Verifies all Phase 10 invariants for GQA-009, GQA-014, and GQA-016."""

    # ── 1. GQA-009: Multi-Platform CI Matrix ──────────────────────────────────
    def test_ci_workflow_multi_platform_matrix(self):
        """CI workflow must define a multi-platform matrix covering Windows and Ubuntu Linux."""
        ci_path = Path(".github/workflows/ci.yml")
        assert ci_path.exists()

        data = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
        test_job = data["jobs"]["test"]
        matrix = test_job["strategy"]["matrix"]

        os_list = matrix["os"]
        if isinstance(os_list, str):
            os_list = [os_list]

        assert "windows-latest" in os_list, "Missing Windows runner in CI matrix"
        assert "ubuntu-latest" in os_list, "Missing Ubuntu Linux runner in CI matrix"
        assert "3.12" in matrix["python-version"]

    # ── 2. GQA-014: Pinned Lock File & Dependency Reconciliation ──────────────
    def test_ci_workflow_installs_exact_lock_file(self):
        """CI workflow must install locked dependencies via requirements.lock, not loose requirements.txt."""
        ci_path = Path(".github/workflows/ci.yml")
        data = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
        steps = data["jobs"]["test"]["steps"]

        step_commands = [s.get("run", "") for s in steps if isinstance(s, dict)]
        combined = "\n".join(step_commands)

        assert "pip install -r requirements.lock" in combined
        assert "requirements.txt" not in combined.split("pip install -r")[1].splitlines()[0]

    def test_dependency_lock_exact_pinning_and_completeness(self):
        """requirements.lock must exist, have substantial dependencies, and strictly use exact '==' pinning."""
        lock_file = Path("requirements.lock")
        assert lock_file.exists()
        assert lock_file.stat().st_size > 500

        locked = parse_requirements_lock(lock_file)
        assert len(locked) >= 50

        # Every locked package must be strictly pinned with an exact version
        for pkg, ver in locked.items():
            assert ver != "UNPINNED", f"Package '{pkg}' in requirements.lock is loose or unpinned!"
            assert len(ver) > 0

    def test_dependency_lock_reconciliation_against_requirements_txt(self):
        """Every direct runtime requirement in requirements.txt must be pinned in requirements.lock."""
        is_valid, errors = verify_dependency_lock()
        assert is_valid is True, f"Dependency lock reconciliation failed: {errors}"
        assert len(errors) == 0

    def test_dependency_lock_verifier_detects_missing_packages(self, tmp_path: Path):
        """verify_dependency_lock catches unpinned or missing dependencies when tested on sandbox files."""
        fake_req = tmp_path / "requirements.txt"
        fake_lock = tmp_path / "requirements.lock"

        # Declare a package in requirements.txt that is absent from requirements.lock
        fake_req.write_text("fastapi>=0.110.0\nunlisted-mystery-package>=1.0.0\n", encoding="utf-8")
        fake_lock.write_text("fastapi==0.141.1\n", encoding="utf-8")

        is_valid, errors = verify_dependency_lock(project_root=tmp_path)
        assert is_valid is False
        assert any("unlisted-mystery-package" in e for e in errors)

    def test_package_normalization_pep503(self):
        """Package name normalization follows PEP 503 rules."""
        assert normalize_package_name("PySide6") == "pyside6"
        assert normalize_package_name("llama_cpp_python") == "llama-cpp-python"
        assert normalize_package_name("psycopg2-binary") == "psycopg2-binary"
        assert normalize_package_name("Jaraco.Classes") == "jaraco-classes"

    # ── 3. GQA-016: Pipeline Verification & Fail-Closed Release Invariants ─────
    def test_ci_workflow_least_privilege_permissions(self):
        """Workflow must declare read-only contents permission."""
        ci_path = Path(".github/workflows/ci.yml")
        data = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
        assert data.get("permissions") == {"contents": "read"}

    def test_ci_workflow_fail_closed_error_handling(self):
        """Zero steps may ignore errors with continue-on-error: true."""
        ci_path = Path(".github/workflows/ci.yml")
        data = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
        steps = data["jobs"]["test"]["steps"]

        for step in steps:
            if isinstance(step, dict):
                assert step.get("continue-on-error") is not True, (
                    f"Step '{step.get('name')}' violates fail-closed release posture"
                )

    def test_ci_pipeline_verifier_script_passes(self):
        """Standalone verify_ci_pipeline script passes with zero errors."""
        is_valid, errors = verify_ci_pipeline()
        assert is_valid is True, f"CI pipeline verification errors: {errors}"
        assert len(errors) == 0

    def test_ci_database_migration_target_is_temporary(self):
        """CI workflow must not mutate local developer gayatri_local.db during setup."""
        ci_path = Path(".github/workflows/ci.yml")
        content = ci_path.read_text(encoding="utf-8")
        assert "gayatri_local.db" not in content
        assert "test_ci.db" in content
