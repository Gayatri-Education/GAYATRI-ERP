#!/usr/bin/env python3
"""Generate authoritative RELEASE_MANIFEST.json for Gayatri School OS Phase 09 release candidate."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT_DIR / "migrations"


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_git_info() -> dict:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT_DIR, text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT_DIR, text=True).strip()
        return {
            "commit_sha": commit,
            "branch": branch,
            "clean_working_tree": len(status) == 0,
        }
    except Exception as exc:
        return {
            "commit_sha": "unknown",
            "branch": "unknown",
            "clean_working_tree": False,
            "error": str(exc),
        }


def build_manifest() -> dict:
    git_info = get_git_info()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Collect migration checksums
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    migrations_meta = {}
    for mf in migration_files:
        migrations_meta[mf.name] = {
            "bytes": mf.stat().st_size,
            "sha256": sha256_file(mf),
        }

    # Core source hashes
    core_files = [
        "central_platform/db.py",
        "central_platform/config.py",
        "central_platform/api/app.py",
        "central_platform/ops/release_gate.py",
        "central_platform/ops/diagnostics.py",
        "central_platform/analytics/institutional.py",
        "central_platform/analytics/exports.py",
    ]
    core_hashes = {}
    for rel in core_files:
        p = ROOT_DIR / rel
        if p.exists():
            core_hashes[rel] = {
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }

    manifest = {
        "release_candidate": "1.0.0-rc1",
        "generated_at": now_iso,
        "platform": "Gayatri School OS",
        "governing_contract": "DEVELOPMENT.md",
        "git": git_info,
        "schema": {
            "latest_migration": "016_analytics_exports_diagnostics.sql",
            "total_migration_scripts": len(migration_files),
            "migrations": migrations_meta,
        },
        "core_artifacts": core_hashes,
    }

    # Calculate overall manifest digest
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()

    return manifest


def main():
    manifest = build_manifest()
    formatted = json.dumps(manifest, indent=2)

    root_target = ROOT_DIR / "RELEASE_MANIFEST.json"
    root_target.write_text(formatted, encoding="utf-8")
    print(f"Wrote release manifest to: {root_target}")

    evidence_dir = ROOT_DIR / "docs" / "development" / "evidence" / "phase09"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_target = evidence_dir / "RELEASE_MANIFEST.json"
    evidence_target.write_text(formatted, encoding="utf-8")
    print(f"Wrote copy to: {evidence_target}")
    print(f"Commit SHA: {manifest['git']['commit_sha']}")
    print(f"Manifest Digest: {manifest['manifest_sha256']}")


if __name__ == "__main__":
    main()
