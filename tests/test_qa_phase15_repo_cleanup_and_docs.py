"""QA Phase 15 Test Suite: Repository Cleanup and Documentation Consolidation.

Verifies:
- README.md accuracy: repo clone URL, directory name, valid CLI commands, absence of stale claims.
- Markdown documentation internal link integrity: files linked in root guides exist on disk.
- File cleanup candidate audit: FILE_CLEANUP_REPORT.md has complete classifications.
- Security sanity: zero production secrets, API keys, or private keys exposed in docs.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_readme_repository_url_and_clone_commands():
    """README.md must reference canonical repo URL and clone folder name."""
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists(), "README.md not found"
    content = readme_path.read_text(encoding="utf-8")

    # Correct clone URL
    assert "https://github.com/Gayatri-Education/GAYATRI-ERP.git" in content
    # Correct directory cd
    assert "cd Gayatri-ERP" in content
    # Correct migration command without duplicate python
    assert "python scripts/migrate_db.py up --db-path gayatri_local.db" in content
    assert "python -m python" not in content


def test_readme_automated_test_count_accuracy():
    """README.md test claims must reflect verified automated regression suites."""
    readme_path = REPO_ROOT / "README.md"
    content = readme_path.read_text(encoding="utf-8")
    # Must claim current verified test count (>1,760 tests)
    assert "1,765+" in content
    # Outdated claim of 1,252 must be gone
    assert "1,252 tests, all must pass" not in content


def test_readme_internal_links_exist_on_disk():
    """Markdown links in README.md must point to actual existing files."""
    readme_path = REPO_ROOT / "README.md"
    content = readme_path.read_text(encoding="utf-8")

    # Extract all markdown links [text](path)
    links = re.findall(r"\[.*?\]\((?!http|mailto|#)(.*?)\)", content)
    for link in links:
        clean_link = link.split("#")[0].strip()
        if not clean_link:
            continue
        target_path = REPO_ROOT / clean_link
        assert target_path.exists(), f"Broken link in README.md: '{link}' -> '{target_path}'"


def test_file_cleanup_report_classifications():
    """FILE_CLEANUP_REPORT.md must contain explicit classifications for candidate modules."""
    report_path = REPO_ROOT / "docs" / "qa" / "FILE_CLEANUP_REPORT.md"
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")

    # Essential modules must be classified
    required_modules = [
        "central_platform/",
        "app/",
        "tests/",
        "migrations/",
        "scripts/",
        "docs/",
    ]
    for mod in required_modules:
        assert mod in content, f"Module '{mod}' missing from cleanup classification log"

    # No unassessed placeholder
    assert "_No candidates assessed yet_" not in content


def test_documentation_secrets_containment():
    """Documentation files must not expose live production API keys or tokens."""
    doc_paths = list((REPO_ROOT / "docs").rglob("*.md")) + [
        REPO_ROOT / "README.md",
        REPO_ROOT / "GAYATRI_ERP_README.md",
    ]

    suspicious_patterns = [
        r"sk-[a-zA-Z0-9]{32,}",
        r"ghp_[a-zA-Z0-9]{36,}",
        r"rzp_live_[a-zA-Z0-9]{14,}",
    ]

    for p in doc_paths:
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in suspicious_patterns:
            matches = re.findall(pat, text)
            assert len(matches) == 0, f"Found credential pattern '{pat}' in '{p}': {matches}"
