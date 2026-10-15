# Gayatri ERP

**Gayatri ERP** is the repository for the Gayatri education platform's ERP and supporting services. It is intended to bring student, teacher, administrator, academic, assessment, AI/tutoring, attendance, finance, and operational workflows into a coherent application.

> **Development status:** Under active QA and remediation. The presence of a route, service, UI control, or test does not by itself prove that a feature works end to end. Critical workflows are being audited for authorization, durable persistence, truthful error reporting, transaction integrity, and UI-to-API wiring.

Repository: [Gayatri-Education/GAYATRI-ERP](https://github.com/Gayatri-Education/GAYATRI-ERP)

## Current priorities

- Verify authentication, role authorization, and tenant/resource isolation.
- Ensure financial webhooks are signature-verified, idempotent, and transactionally safe.
- Ensure API operations persist state and report failures honestly.
- Replace toast-only or placeholder UI actions with tested workflows, or label them as unavailable.
- Verify AI/provider controls, assessment content, tutoring state, and operational health endpoints.
- Maintain a phase-by-phase remediation tracker with test evidence in GitHub.
- Remove unnecessary repository files only after dependency and runtime checks prove they are safe to remove.

Do not interpret this list as proof that every item is currently broken. Use the QA issue register and linked tests for the latest evidence.

## Repository map

The following are likely major areas to inspect; verify paths against the current checkout before relying on this map.

| Path | Purpose |
|---|---|
| `central_platform/` | Central API, services, domain logic, and platform workflows |
| `central_platform/api/` | API application and route handlers |
| `central_platform/auth/` | Authentication and authorization support |
| `central_platform/finance/` | Finance-related service logic |
| `app/` | Application UI and portal assets |
| `tests/` | Automated tests and regression coverage |
| `docs/` | Architecture, development, QA, security, and operations documentation |
| `migrations/` | Database schema evolution, if present in this checkout |
| `scripts/` | Development, migration, validation, and operational utilities, if present |

The checked-out source and its actual imports/configuration are authoritative. Update this map when the repository structure is confirmed.

## Development workflow

All development should follow the canonical [Phase-by-Phase Development Guide](docs/development/DEVELOPMENT_GUIDE.md).

Each phase must use this sequence:

1. Inspect the current branch, commit, tracker, source, tests, and dependencies.
2. Write a plan, acceptance criteria, risk assessment, and test plan.
3. Reproduce the issue before changing code.
4. Implement the smallest safe root-cause fix.
5. Run focused tests and negative/failure-path tests.
6. Debug failures and run risk-based regression tests.
7. Verify the actual end-to-end workflow and inspect the final diff.
8. Update the GitHub progress tracker, issue register, and phase log.
9. Commit to a dedicated branch and open/update a pull request.
10. Move to the next phase only after the current phase gate passes.

### Progress and QA records

- [Development guide](docs/development/DEVELOPMENT_GUIDE.md)
- [Progress tracker](docs/qa/PROGRESS_TRACKER.yaml)
- [Issue register](docs/qa/ISSUE_REGISTER.md)
- [File cleanup report](docs/qa/FILE_CLEANUP_REPORT.md)
- [Phase logs](docs/qa/phase-logs/)

If one of these records already exists at another path, reconcile it with the canonical location instead of creating conflicting duplicates.

## Setup and running

The correct setup commands must be taken from the current dependency manifests, entry points, configuration examples, and CI workflow. Do not copy commands from a different Gayatri repository.

1. Clone this repository.
2. Inspect `pyproject.toml`, `requirements*.txt`, lockfiles, setup scripts, and the current CI workflow to identify the supported Python/runtime version and installation method.
3. Create an isolated virtual environment.
4. Install only the declared project dependencies.
5. Configure local environment variables using a documented example file. Never commit real credentials or production data.
6. Initialize a disposable local/test database using the migration process documented in the repository.
7. Run the focused test suite before starting the application.
8. Start the API or UI using a verified repository entry point.

Example clone command:

```bash
git clone https://github.com/Gayatri-Education/GAYATRI-ERP.git
cd GAYATRI-ERP
```

> Setup commands, required environment variables, migration commands, and run commands must be verified against the current checkout before being advertised as production instructions. If any are missing, document and implement the canonical instructions as part of the relevant development phase.

## Testing

Use the test commands that are actually supported by this checkout. Begin by inspecting the test configuration and CI workflow; do not rely on historical test counts or a green badge as proof.

At minimum, validate:

- Authentication, role authorization, and tenant isolation.
- Payment webhook signature verification, duplicate delivery, and atomicity.
- Database transaction rollback, restart persistence, and migration behavior.
- AI/provider errors and kill-switch behavior.
- Student, teacher, and administrator UI actions end to end.
- Empty-data, invalid-input, permission-denied, timeout, and dependency-failure paths.
- Regression tests for every confirmed defect.

Record each test command, environment, exit code, passed/failed/skipped counts, and evidence in `docs/qa/PROGRESS_TRACKER.yaml` and the relevant phase log. Never hide a failure by deleting or weakening a test.

## Security and data handling

- Do not commit API keys, passwords, signing secrets, JWT secrets, tokens, private student data, production databases, or local environment files.
- Enforce authorization and tenant checks on the server for every protected resource.
- Treat payment provider webhooks as untrusted until cryptographically verified.
- Do not return success when persistence, an external operation, or an audit write has failed.
- Do not treat sample/mock data as production data unless the environment is explicitly configured for demo/test mode.
- Do not delete migrations, tests, deployment/CI configuration, recovery utilities, or other potentially required files without documented dependency checks and review.

Report security issues privately to the repository maintainers rather than publishing exploit details in public issue comments.

## Repository cleanup policy

The repository should contain essential source, tests, dependency manifests/locks, migrations, CI, packaging/deployment files, security and operational documentation, and canonical QA progress records. Remove redundant, generated, obsolete, or unused files only after:

1. checking direct and dynamic imports/references;
2. checking packaging, CI, deployment, scripts, documentation, and runtime path conventions;
3. running relevant tests and packaging checks before and after deletion;
4. documenting the evidence and decision in `docs/qa/FILE_CLEANUP_REPORT.md`;
5. reviewing the cleanup in a dedicated pull request.

When uncertain, retain the file and mark it for investigation rather than deleting it.

## Contributing and pull requests

- Use a dedicated branch for each phase or tightly related set of fixes.
- Keep changes focused and reviewable.
- Include reproduction steps, root cause, acceptance criteria, test commands/results, data/security impact, and rollback notes in the PR.
- Update the progress tracker and issue register in the same PR.
- Do not merge with unresolved P0/P1 defects, failing required checks, or undocumented test exceptions.
- Do not mark a phase complete until the evidence and remote GitHub records are present.

## License

Check the repository's actual `LICENSE` or `LICENSE.md` file before redistributing this project. Do not assume a license based on another Gayatri repository.
