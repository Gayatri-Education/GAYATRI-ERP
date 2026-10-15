"""QA Phase 16 Test Suite: Final Audit, Handover, and Maintenance.

Verifies:
- Complete reconciliation of seed findings ERP-001 through ERP-022 (100% FIXED_VERIFIED).
- Canonical release handover document existence and completeness.
- Phase logs completeness across all 17 phases (PHASE-00 through PHASE-16).
- Progress tracker structure and phase completeness.
- Production release tier verification via DeploymentValidator.
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest

from central_platform.deployment.validator import DeploymentValidator, ReleaseTier

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_seed_findings_complete_reconciliation():
    """All 22 initial seed findings (ERP-001 through ERP-022) must be FIXED_VERIFIED."""
    register_path = REPO_ROOT / "docs" / "qa" / "ISSUE_REGISTER.md"
    assert register_path.exists(), "ISSUE_REGISTER.md missing"
    content = register_path.read_text(encoding="utf-8")

    # Check each finding ERP-001 through ERP-022
    for i in range(1, 23):
        finding_id = f"ERP-{i:03d}"
        assert finding_id in content, f"Finding '{finding_id}' missing from issue register"
        # Must be marked FIXED_VERIFIED
        match = re.search(rf"\|\s*{finding_id}\s*\|.*?\|\s*FIXED_VERIFIED\s*\|", content)
        assert match is not None, f"Finding '{finding_id}' is not marked FIXED_VERIFIED in register"

    # Confirm no unresolved finding statuses remain
    assert "NEEDS_REVALIDATION" not in content
    assert "| OPEN |" not in content
    assert "| BLOCKED |" not in content


def test_root_and_qa_issue_registers_synchronized():
    """Root and docs/qa/ issue registers must agree on all finding statuses."""
    qa_reg = (REPO_ROOT / "docs" / "qa" / "ISSUE_REGISTER.md").read_text(encoding="utf-8")
    root_reg = (REPO_ROOT / "GAYATRI_ERP_ISSUE_REGISTER.md").read_text(encoding="utf-8")

    for i in range(1, 23):
        fid = f"ERP-{i:03d}"
        assert f"| {fid} |" in qa_reg
        assert f"| {fid} |" in root_reg
        assert re.search(rf"\|\s*{fid}\s*\|.*?\|\s*FIXED_VERIFIED\s*\|", root_reg) is not None


def test_release_handover_document_completeness():
    """RELEASE_HANDOVER.md must exist and include all authoritative operational sections."""
    handover_path = REPO_ROOT / "docs" / "qa" / "RELEASE_HANDOVER.md"
    assert handover_path.exists(), "RELEASE_HANDOVER.md missing"
    content = handover_path.read_text(encoding="utf-8")

    required_sections = [
        "Executive Summary",
        "Architectural Blueprint",
        "Configuration & Environment Variables",
        "Deployment, Installation & Startup Guide",
        "Database Migrations & Reversibility",
        "Backup, Restore, and Disaster Recovery Procedures",
        "Monitoring, Health Probes & Incident Response",
        "Resolution Audit of Initial Seed Findings",
        "Phase-by-Phase Execution Summary",
        "Maintenance & Rollback Plan",
    ]
    for sec in required_sections:
        assert sec in content, f"Section '{sec}' missing from RELEASE_HANDOVER.md"

    # Must confirm 100% resolution of findings
    assert "ERP-001 through ERP-022" in content
    assert "PRODUCTION_READY" in content


def test_all_phase_logs_exist_on_disk():
    """All 17 phase logs (PHASE-00 through PHASE-16) must exist in docs/qa/phase-logs/."""
    phase_logs_dir = REPO_ROOT / "docs" / "qa" / "phase-logs"
    assert phase_logs_dir.exists()

    expected_phases = [f"PHASE_{i:02d}_LOG.md" for i in range(17)]
    for phase_log in expected_phases:
        p = phase_logs_dir / phase_log
        assert p.exists(), f"Phase log '{phase_log}' missing from docs/qa/phase-logs/"
        text = p.read_text(encoding="utf-8")
        assert "PASS" in text.upper() or "APPROVED" in text.upper()


def test_production_release_tier_determination():
    """DeploymentValidator must determine PRODUCTION_READY when zero defects and full tests pass."""
    tier = DeploymentValidator.determine_release_tier(
        test_pass_rate=1.0,
        open_p0_count=0,
        open_p1_count=0,
        real_model_verified=True,
        real_rag_verified=True,
        security_audit_passed=True,
    )
    assert tier == ReleaseTier.PRODUCTION_READY
