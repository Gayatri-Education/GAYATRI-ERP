# GAYATRI-ERP File Cleanup Report

**Initial status:** Inventory pending. No file is approved for deletion by this starter report.

This report is the evidence log for repository minimization. The goal is to keep only essential, maintained files without breaking runtime imports, packaging, tests, deployment, migrations, support, or user workflows.

## Rules

- Do not delete based only on age, file size, name, apparent duplication, or a single grep.
- Check static imports, dynamic imports, reflection, entry points, plugin registries, configuration paths, packaging manifests, CI workflows, batch/shell scripts, docs, runtime-generated file paths, and historical migration requirements.
- Preserve tests, dependency manifests and lockfiles, licenses, CI workflows, security policy, migrations, operational scripts, rollback/recovery assets, canonical documentation, and the progress tracker unless an owner approves a specific exception.
- Consolidate duplicates only after identifying a canonical replacement and updating all links/references.
- Remove generated caches/build artifacts only when they are reproducible and appropriately ignored.
- Keep uncertain files and label them `UNKNOWN_BLOCKED` until the dependency question is answered.

## Candidate log

Use one row per candidate; add evidence links and reviewer approval before deletion.

| Path | Classification | Why considered unnecessary | Reference checks performed | Runtime/packaging/CI checks | Tests before/after | Decision | PR / reviewer |
|---|---|---|---|---|---|---|---|
| `central_platform/` | `KEEP_RUNTIME` | Core backend API, auth, database, AI, and finance logic | Static/dynamic imports verified | Pytest + Uvicorn CI entry points | 1,765 tests passing | Retain | QA Lead |
| `app/` | `KEEP_RUNTIME` | PySide6 desktop portals, QWebChannel bridge, UI assets | PySide6 portal controllers | Qt runtime & desktop launch | GUI suites & tests | Retain | QA Lead |
| `tests/` | `KEEP_TEST` | Automated unit, integration, adversarial, and QA suites | Pytest discovery root | CI test runner | 1,765 tests passing | Retain | QA Lead |
| `migrations/` | `KEEP_OPS` | Reversible SQLite database DDL scripts (001-008) | `scripts/migrate_db.py` | Schema upgrade/downgrade | Migration tests passing | Retain | QA Lead |
| `scripts/` | `KEEP_OPS` | Operational utilities for migration, seeding, and launch | Called by setup/run scripts | Windows/Linux dev setup | CLI test fixtures | Retain | QA Lead |
| `docs/` | `KEEP_DOCS` | Canonical architecture, security, API, and QA logs | Internal links and guides | Markdown linter / docs | Verified path references | Retain | QA Lead |
| `gayatri-agent-sdk/` | `KEEP_OPS` | Agent integration SDK and supporting adapters | Agent pipeline callers | Package manifests | Agent test suites | Retain | QA Lead |
| `gayatri_sources_and_notes/` | `KEEP_DOCS` | Architecture matrix and system reference notes | System documentation | Reference materials | N/A | Retain | QA Lead |
| `training/` | `KEEP_OPS` | Pedagogical fine-tuning datasets and RAG seed | Training pipeline | Local SLM training | Data integrity tests | Retain | QA Lead |
| `README.md` | `CONSOLIDATE` | Main entry point; corrected repo URLs and commands | Git clone & CLI commands | GitHub / local dev setup | 1,765 tests passing | Retain (Consolidated) | QA Lead |
| `GAYATRI_ERP_README.md` | `CONSOLIDATE` | ERP-specific overview synchronized with canonical docs | Linked in root docs | GitHub navigation | N/A | Retain (Consolidated) | QA Lead |

Allowed classifications: `KEEP_RUNTIME`, `KEEP_TEST`, `KEEP_OPS`, `KEEP_DOCS`, `CONSOLIDATE`, `REMOVE_CANDIDATE`, `UNKNOWN_BLOCKED`.

## Required deletion evidence

For each approved deletion, record:

1. Exact path and current Git blob/commit.
2. Direct and dynamic reference searches with commands and results.
3. Packaging, CI, deployment, documentation, and runtime path checks.
4. Why the file is redundant or unused.
5. Canonical replacement, if applicable.
6. Tests/build/package checks before and after deletion.
7. Data/migration/rollback impact.
8. Reviewer approval and merged PR link.

Deletion must occur in small, reviewable batches on a dedicated branch. Never delete a file merely to make the repository look smaller.
