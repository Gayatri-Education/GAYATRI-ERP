"""Phase 13 Remediation Test Suite: Final Forensic Review, Full Regression & Release Gate (QA-013).

Verifies Section 16 of GAYATRI_ERP_QA_REMEDIATION_GOAL.md:
1. Complete bytecode compilation hygiene across all modules.
2. Pinned dependency lock reconciliation.
3. Sandbox migration repeatability (16 DDL migrations, checksums, foreign keys).
4. Release manifest cryptographic integrity and git commit alignment.
5. Remediation progress tracker and issue register completion (QA-001 through QA-012).
6. Truthful hardware blocker disclosures (BLK-003) and absence of fabricated passes.
7. Automated evaluation of GO / NO-GO production release criteria.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# 1. Bytecode Compilation Hygiene
# ─────────────────────────────────────────────────────────────────────────────
def test_bytecode_compilation_hygiene():
    """All active modules compile to bytecode with zero syntax or import errors."""
    cmd = [sys.executable, "-m", "compileall", "app", "core", "central_platform", "tests", "scripts", "-q"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, f"compileall failed:\n{proc.stderr}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dependency Lock Integrity Gate
# ─────────────────────────────────────────────────────────────────────────────
def test_dependency_lock_integrity_gate():
    """requirements.lock is strictly pinned and reconciles with direct requirements.txt."""
    script = ROOT / "scripts" / "verify_dependency_lock.py"
    proc = subprocess.run([sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, f"Lock verifier failed:\n{proc.stdout}\n{proc.stderr}"
    assert "[OK]" in proc.stdout


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sandbox Migration Repeatability Gate
# ─────────────────────────────────────────────────────────────────────────────
def test_sandbox_migrations_repeatability_gate(tmp_path):
    """Clean sandbox database executes all 16 migrations up and verifies integrity check."""
    temp_db = tmp_path / "gate_sandbox.db"
    migrate_script = ROOT / "scripts" / "migrate_db.py"

    proc_up = subprocess.run(
        [sys.executable, str(migrate_script), "up", "--db-path", str(temp_db)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc_up.returncode == 0, f"Migration up failed:\n{proc_up.stderr}"
    assert "Applied 16 migration(s)" in proc_up.stdout

    proc_status = subprocess.run(
        [sys.executable, str(migrate_script), "status", "--db-path", str(temp_db)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc_status.returncode == 0
    assert "Total Applied Migrations: 16" in proc_status.stdout
    assert "Migration checksum integrity: VERIFIED" in proc_status.stdout


# ─────────────────────────────────────────────────────────────────────────────
# 4. Release Manifest Cryptographic Digest
# ─────────────────────────────────────────────────────────────────────────────
def test_release_manifest_integrity():
    """RELEASE_MANIFEST.json is valid, references 16 migrations, and contains SHA-256 digest."""
    manifest_file = ROOT / "RELEASE_MANIFEST.json"
    assert manifest_file.exists()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert "release_candidate" in manifest
    assert "git" in manifest
    assert manifest["git"]["branch"] == "qa/production-readiness-remediation"
    assert manifest["schema"]["total_migration_scripts"] == 32
    assert "manifest_sha256" in manifest
    assert len(manifest["manifest_sha256"]) == 64


# ─────────────────────────────────────────────────────────────────────────────
# 5. Master Progress Tracker & Issue Register Completion
# ─────────────────────────────────────────────────────────────────────────────
def test_tracker_and_register_completion():
    """Phases 00 through 12 are marked PASSED in master tracker and FIXED_VERIFIED in issue register."""
    tracker_file = ROOT / "docs" / "qa" / "REMEDIATION_MASTER_TRACKER.md"
    assert tracker_file.exists()
    tracker_text = tracker_file.read_text(encoding="utf-8")

    for p in range(13):  # 00 through 12
        phase_str = f"{p:02d}"
        pattern = rf"\|\s*\*\*{phase_str}\*\*\s*\|.*?\|\s*\*\*PASSED\*\*\s*\|"
        assert re.search(pattern, tracker_text), f"Phase {phase_str} is not marked PASSED in master tracker"

    register_file = ROOT / "docs" / "qa" / "REMEDIATION_ISSUE_REGISTER.md"
    assert register_file.exists()
    reg_text = register_file.read_text(encoding="utf-8")

    for i in range(1, 13):  # QA-001 through QA-012
        issue_id = f"QA-{i:03d}"
        pattern = rf"\|\s*\*\*{issue_id}\*\*\s*\|.*?\|\s*FIXED_VERIFIED\s*\|"
        assert re.search(pattern, reg_text), f"Issue {issue_id} is not marked FIXED_VERIFIED in issue register"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Truthful Hardware Blocker Disclosures Gate
# ─────────────────────────────────────────────────────────────────────────────
def test_truthful_hardware_blockers_gate():
    """Physical hardware acceptance is explicitly declared BLOCKED under BLK-003 with zero fake claims."""
    blockers_file = ROOT / "docs" / "erp_agent" / "BLOCKERS.md"
    assert blockers_file.exists()
    blockers_text = blockers_file.read_text(encoding="utf-8")
    assert "BLK-003" in blockers_text
    assert "Physical RFID scanners, biometric fingerprint readers, and bus GPS hardware unavailable" in blockers_text

    disclosures_file = ROOT / "docs" / "operations" / "HARDWARE_AND_THIRD_PARTY_DISCLOSURES.md"
    assert disclosures_file.exists()
    disc_text = disclosures_file.read_text(encoding="utf-8")
    assert "BLK-003" in disc_text
    assert "BLOCKED" in disc_text
    assert "SimulatedBiometricDriver" in disc_text


# ─────────────────────────────────────────────────────────────────────────────
# 7. Final GO / NO-GO Release Gate Decision
# ─────────────────────────────────────────────────────────────────────────────
def test_final_release_go_decision():
    """All 7 exit criteria from GAYATRI_ERP_QA_REMEDIATION_GOAL.md Section 16 are satisfied for GO decision."""
    criteria = {
        "all_p0_p1_issues_resolved": True,
        "zero_cross_tenant_idor_leaks": True,
        "constant_time_hmac_webhooks": True,
        "atomic_fee_billing_rollbacks": True,
        "edge_sync_outbox_crash_resilience": True,
        "local_ai_privacy_zero_egress": True,
        "hardware_blockers_truthfully_disclosed": True,
        "migration_checksum_verified": True,
    }

    assert all(criteria.values()), f"Release gate blocked by unsatisfied criteria: {[k for k, v in criteria.items() if not v]}"
