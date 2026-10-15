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
| _No candidates assessed yet_ | `UNKNOWN_BLOCKED` | Inventory not complete | N/A | N/A | N/A | Retain | N/A |

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
