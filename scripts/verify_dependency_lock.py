#!/usr/bin/env python3
"""Dependency Lock Integrity and Reconciliation Verifier (Phase 10).

Remediates GQA-014:
- Verifies that requirements.lock exists and contains strictly pinned exact versions (==).
- Reconciles direct dependencies in requirements.txt against requirements.lock to prevent dependency drift.
- Returns exit code 0 on verified compliance, non-zero on violation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def normalize_package_name(name: str) -> str:
    """Normalize Python package name per PEP 503 (lowercase, underscores replaced by hyphens)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements_txt(req_path: Path) -> Dict[str, str]:
    """Parse requirements.txt into a mapping of normalized package name to raw specifier."""
    packages: Dict[str, str] = {}
    if not req_path.is_file():
        return packages

    for line in req_path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        # Split out inline comments
        clean = clean.split("#", 1)[0].strip()
        if not clean:
            continue

        # Match package name and specifier
        match = re.match(r"^([A-Za-z0-9_.\-]+)(.*)$", clean)
        if match:
            pkg_name = normalize_package_name(match.group(1))
            spec = match.group(2).strip()
            packages[pkg_name] = spec

    return packages


def parse_requirements_lock(lock_path: Path) -> Dict[str, str]:
    """Parse requirements.lock into a mapping of normalized package name to exact version."""
    packages: Dict[str, str] = {}
    if not lock_path.is_file():
        return packages

    for line in lock_path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        clean = clean.split("#", 1)[0].strip()
        if not clean:
            continue

        if "==" in clean:
            name, ver = clean.split("==", 1)
            packages[normalize_package_name(name.strip())] = ver.strip()
        else:
            packages[normalize_package_name(clean)] = "UNPINNED"

    return packages


def verify_dependency_lock(
    project_root: Path | None = None,
) -> Tuple[bool, List[str]]:
    """Verify requirements.lock validity and reconcile against requirements.txt."""
    root = project_root or Path(__file__).resolve().parent.parent
    req_file = root / "requirements.txt"
    lock_file = root / "requirements.lock"

    errors: List[str] = []

    # 1. Existence and non-empty check
    if not lock_file.exists():
        errors.append(f"requirements.lock not found at {lock_file}")
        return False, errors

    if lock_file.stat().st_size == 0:
        errors.append("requirements.lock is completely empty")
        return False, errors

    # 2. Strict exact pinning (==) check in lock file
    locked = parse_requirements_lock(lock_file)
    if len(locked) < 20:
        errors.append(f"requirements.lock contains only {len(locked)} packages; expected >= 20")

    unpinned = [pkg for pkg, ver in locked.items() if ver == "UNPINNED"]
    if unpinned:
        errors.append(f"Loose / unpinned packages found in requirements.lock: {unpinned}")

    # 3. Direct dependencies reconciliation check
    if req_file.exists():
        direct = parse_requirements_txt(req_file)
        missing_from_lock = []
        for pkg, spec in direct.items():
            if pkg not in locked:
                missing_from_lock.append(f"{pkg} (spec: {spec})")

        if missing_from_lock:
            errors.append(
                f"Direct dependencies from requirements.txt are missing from requirements.lock: {missing_from_lock}"
            )

    is_valid = len(errors) == 0
    return is_valid, errors


def main() -> int:
    print("=" * 65)
    print("  GAYATRI AI — DEPENDENCY LOCK VERIFIER & RECONCILIATION")
    print("=" * 65)

    is_valid, errors = verify_dependency_lock()
    if is_valid:
        print("[OK] requirements.lock is valid, fully pinned, and reconciled against requirements.txt.")
        return 0
    else:
        print("[FAIL] Dependency lock validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
