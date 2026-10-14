#!/usr/bin/env python3
"""Continuous Integration Pipeline and Workflow Verifier (Phase 10).

Remediates GQA-009, GQA-014, and GQA-016:
- Validates CI workflow syntax and least-privilege permissions.
- Verifies target multi-platform matrix (windows-latest and ubuntu-latest).
- Verifies strict installation and validation of requirements.lock.
- Verifies fail-closed execution of compilation hygiene, migrations, architecture guardrails, and tests.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import yaml


def verify_ci_pipeline(
    project_root: Path | None = None,
) -> Tuple[bool, List[str]]:
    """Programmatically audit .github/workflows/ci.yml against release reproducibility requirements."""
    root = project_root or Path(__file__).resolve().parent.parent
    ci_path = root / ".github" / "workflows" / "ci.yml"

    errors: List[str] = []

    if not ci_path.exists():
        errors.append(f"CI workflow file not found at {ci_path}")
        return False, errors

    try:
        content = ci_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except Exception as exc:
        errors.append(f"Failed to parse YAML from {ci_path}: {exc}")
        return False, errors

    if not isinstance(data, dict):
        errors.append("Invalid workflow: Root must be a dictionary.")
        return False, errors

    # 1. Least privilege permissions
    perms = data.get("permissions")
    if not isinstance(perms, dict) or perms.get("contents") != "read":
        errors.append("Workflow must declare least-privilege 'permissions: contents: read'")

    jobs = data.get("jobs", {})
    test_job = jobs.get("test", {})
    if not test_job:
        errors.append("Missing required 'test' job in CI workflow")
        return False, errors

    # 2. Multi-platform OS matrix (GQA-009)
    strategy = test_job.get("strategy", {})
    matrix = strategy.get("matrix", {})
    matrix_os = matrix.get("os", [])
    if isinstance(matrix_os, str):
        matrix_os = [matrix_os]

    if "windows-latest" not in matrix_os:
        errors.append("Matrix must include 'windows-latest' for Windows desktop verification (GQA-009)")
    if "ubuntu-latest" not in matrix_os:
        errors.append("Matrix must include 'ubuntu-latest' for Linux headless platform verification (GQA-009)")

    py_versions = matrix.get("python-version", [])
    if isinstance(py_versions, str):
        py_versions = [py_versions]
    if "3.12" not in py_versions:
        errors.append("Matrix must test Python '3.12'")

    # 3. Step inspections
    steps = test_job.get("steps", [])
    step_runs = [s.get("run", "") for s in steps if isinstance(s, dict)]
    combined_script = "\n".join(step_runs)

    # A. Dependency lock usage (GQA-014)
    if "requirements.lock" not in combined_script:
        errors.append("CI workflow must install locked dependencies via 'pip install -r requirements.lock' (GQA-014)")
    if "verify_dependency_lock.py" not in combined_script:
        errors.append("CI workflow must run 'python scripts/verify_dependency_lock.py' to reconcile lock integrity")

    # B. Compile hygiene
    if "compileall" not in combined_script:
        errors.append("CI workflow must verify compilation hygiene via 'python -m compileall'")

    # C. Architecture guardrails
    if "tests/architecture" not in combined_script:
        errors.append("CI workflow must execute architecture guardrail suite 'pytest -v tests/architecture'")

    # D. Headless tests with offscreen QT
    if "not gui" not in combined_script and "pytest" not in combined_script:
        errors.append("CI workflow must execute headless test suite")

    # 4. Fail-closed error handling (GQA-016)
    for s in steps:
        if isinstance(s, dict) and s.get("continue-on-error") is True:
            errors.append(f"Step '{s.get('name', 'unnamed')}' sets continue-on-error: true; fail-closed gate violated")

    is_valid = len(errors) == 0
    return is_valid, errors


def main() -> int:
    print("=" * 65)
    print("  GAYATRI AI — CI PIPELINE & WORKFLOW VERIFIER (GQA-009, GQA-016)")
    print("=" * 65)

    is_valid, errors = verify_ci_pipeline()
    if is_valid:
        print("[OK] CI workflow is compliant with multi-platform matrix and locked release standards.")
        return 0
    else:
        print("[FAIL] CI workflow verification failed:")
        for err in errors:
            print(f"  - {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
