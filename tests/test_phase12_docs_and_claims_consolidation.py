"""Phase 12 Remediation Test Suite: Consolidate Documentation, Trackers & Release Claims (QA-012).

Verifies Section 15 of GAYATRI_ERP_QA_REMEDIATION_GOAL.md:
1. Root-level pointers cleanly resolve to canonical documents in docs/qa/.
2. Superseded documents have unambiguous deprecation banners pointing to the canonical QA contract.
3. Database migration inventory is synchronized across files (16 DDL migrations).
4. Claims vs Evidence matrix is present in README.md with truthful BLOCKED/SIMULATED hardware disclosures.
5. Cross-links between documentation files resolve to real files on disk.
6. Product version 3.0.1 is consistently declared across canonical documents.
7. Remediation issue register (QA-001 through QA-015) has verified statuses for all completed phases.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# 1. Canonical Pointer Resolution
# ─────────────────────────────────────────────────────────────────────────────
def test_root_document_canonical_pointers():
    """Root-level pointer files redirect to their canonical equivalents."""
    issue_reg = ROOT / "GAYATRI_ERP_ISSUE_REGISTER.md"
    assert issue_reg.exists()
    content_ir = issue_reg.read_text(encoding="utf-8")
    assert "docs/qa/REMEDIATION_ISSUE_REGISTER.md" in content_ir
    assert (ROOT / "docs" / "qa" / "REMEDIATION_ISSUE_REGISTER.md").exists()

    cleanup_rep = ROOT / "GAYATRI_ERP_FILE_CLEANUP_REPORT.md"
    assert cleanup_rep.exists()
    content_cr = cleanup_rep.read_text(encoding="utf-8")
    assert "docs/qa/FILE_CLEANUP_REPORT.md" in content_cr
    assert (ROOT / "docs" / "qa" / "FILE_CLEANUP_REPORT.md").exists()

    dev_guide = ROOT / "GAYATRI_ERP_DEVELOPMENT_GUIDE.md"
    assert dev_guide.exists()
    content_dg = dev_guide.read_text(encoding="utf-8")
    assert "GAYATRI_ERP_QA_REMEDIATION_GOAL.md" in content_dg
    assert "docs/qa/REMEDIATION_MASTER_TRACKER.md" in content_dg


# ─────────────────────────────────────────────────────────────────────────────
# 2. Superseded Plan Deprecation Banners
# ─────────────────────────────────────────────────────────────────────────────
def test_superseded_plan_banners():
    """Historical/preliminary plans clearly identify GAYATRI_ERP_QA_REMEDIATION_GOAL.md as governing."""
    plan1 = ROOT / "GAYATRI_PHASE_BY_PHASE_PRODUCTION_FIX_PLAN.md"
    assert plan1.exists()
    content1 = plan1.read_text(encoding="utf-8")
    assert "Superseded by Canonical QA Remediation Contract" in content1
    assert "GAYATRI_ERP_QA_REMEDIATION_GOAL.md" in content1

    plan2 = ROOT / "Gayatri_QA_Production_Fix_Plan.md"
    assert plan2.exists()
    content2 = plan2.read_text(encoding="utf-8")
    assert "Superseded by Canonical QA Remediation Contract" in content2
    assert "GAYATRI_ERP_QA_REMEDIATION_GOAL.md" in content2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Migration Inventory Parity
# ─────────────────────────────────────────────────────────────────────────────
def test_migration_inventory_parity():
    """All 16 migrations are accounted for across disk, RELEASE_MANIFEST.json, and RELEASE_HANDOVER.md."""
    migrations_dir = ROOT / "migrations"
    up_migrations = sorted([f.name for f in migrations_dir.glob("*_up.sql")] + 
                           [f.name for f in migrations_dir.glob("*.sql") if not f.name.endswith("_down.sql") and not f.name.endswith("_up.sql")])
    assert len(up_migrations) == 16

    manifest_file = ROOT / "RELEASE_MANIFEST.json"
    assert manifest_file.exists()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["schema"]["total_migration_scripts"] == 32
    up_in_manifest = [k for k in manifest["schema"]["migrations"] if not k.endswith("_down.sql")]
    assert len(up_in_manifest) == 16
    assert manifest["schema"]["latest_migration"].startswith("016_")

    handover_file = ROOT / "docs" / "qa" / "RELEASE_HANDOVER.md"
    assert handover_file.exists()
    handover_text = handover_file.read_text(encoding="utf-8")
    assert "16 reversible SQL migrations" in handover_text


# ─────────────────────────────────────────────────────────────────────────────
# 4. Claims vs Evidence Matrix & Truthful Disclosures
# ─────────────────────────────────────────────────────────────────────────────
def test_claims_vs_evidence_matrix():
    """README.md contains the Claims vs Evidence matrix and correctly discloses BLOCKED/SIMULATED hardware."""
    readme_file = ROOT / "README.md"
    assert readme_file.exists()
    readme_text = readme_file.read_text(encoding="utf-8")

    assert "## ⚖️ Claims vs. Evidence Matrix" in readme_text
    assert "BLK-003" in readme_text
    assert "BLOCKED" in readme_text
    assert "SIMULATED / CONTRACT_VERIFIED" in readme_text

    disclosures_file = ROOT / "docs" / "operations" / "HARDWARE_AND_THIRD_PARTY_DISCLOSURES.md"
    assert disclosures_file.exists()
    disc_text = disclosures_file.read_text(encoding="utf-8")
    assert "BLK-003" in disc_text
    assert "SimulatedBiometricDriver" in disc_text
    assert "RazorpayPaymentAdapter" in disc_text


# ─────────────────────────────────────────────────────────────────────────────
# 5. Markdown Cross-Links Validity
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_cross_links_resolve():
    """All relative markdown links inside the README governance section resolve to existing files."""
    readme_file = ROOT / "README.md"
    readme_text = readme_file.read_text(encoding="utf-8")

    # Match markdown links [text](path)
    links = re.findall(r"\[.*?\]\((docs/[^\)]+|GAYATRI_[^\)]+)\)", readme_text)
    assert len(links) > 0

    for link in links:
        target = ROOT / link
        assert target.exists(), f"Broken link in README.md: {link} does not exist at {target}"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Version Consistency (3.0.1)
# ─────────────────────────────────────────────────────────────────────────────
def test_version_consistency_across_canonical_docs():
    """Version 3.0.1 is uniform across VERSION, pyproject.toml, README.md, and RELEASE_HANDOVER.md."""
    version_file = ROOT / "VERSION"
    assert version_file.read_text(encoding="utf-8").strip() == "3.0.1"

    pyproject_file = ROOT / "pyproject.toml"
    assert 'version = "3.0.1"' in pyproject_file.read_text(encoding="utf-8")

    readme_file = ROOT / "README.md"
    assert "version-3.0.1" in readme_file.read_text(encoding="utf-8")

    handover_file = ROOT / "docs" / "qa" / "RELEASE_HANDOVER.md"
    assert "**Version:** 3.0.1" in handover_file.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Remediation Issue Register Status Verification
# ─────────────────────────────────────────────────────────────────────────────
def test_issue_register_verified_statuses():
    """Issues QA-001 through QA-011 in REMEDIATION_ISSUE_REGISTER.md are marked FIXED_VERIFIED."""
    issue_reg = ROOT / "docs" / "qa" / "REMEDIATION_ISSUE_REGISTER.md"
    assert issue_reg.exists()
    content = issue_reg.read_text(encoding="utf-8")

    for i in range(1, 12):
        issue_id = f"QA-{i:03d}"
        pattern = rf"\|\s*\*\*{issue_id}\*\*\s*\|.*?\|\s*FIXED_VERIFIED\s*\|"
        assert re.search(pattern, content), f"Issue {issue_id} is not marked FIXED_VERIFIED in issue register"
