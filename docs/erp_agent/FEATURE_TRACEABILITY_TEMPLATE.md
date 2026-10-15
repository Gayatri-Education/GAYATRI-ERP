# Feature Traceability Matrix — Template

Copy the full checklist from `ERP_TRANSFORMATION_DEVELOPMENT.md` into this matrix and add rows for any missing feature discovered in the repository. One requirement per row; do not mark `VERIFIED_EXISTING` from documentation alone.

| ID | Requirement | Current code location (file/symbol) | Disposition | Domain owner | Tests/evidence | Status | Blocker / next action | Release-critical? |
|---|---|---|---|---|---|---|---|---|
| ERP-001 | Example only — replace with an actual requirement | NOT_MAPPED | IMPLEMENT | TBD | NOT_RUN | NOT_STARTED | Inspect source and callers | Yes/No |

## Disposition values

- `VERIFIED_EXISTING`: inspected code and tests prove the requirement works in supported configuration.
- `IMPLEMENT`: required workflow is absent and must be built.
- `FIX`: behavior exists but is defective/incomplete and needs correction.
- `DEFER_WITH_REASON`: scope is deferred with explicit owner/reason and product impact; not counted complete.
- `BLOCKED`: dependency such as hardware, credentials, policy decision or inaccessible environment prevents work.

## Evidence rules

- A README, mock, screenshot, test name, code comment or green CI badge alone is not proof.
- Link tests that exercise actual logic; include runtime evidence for integration claims.
- For hardware/providers, record exact supported model/version and the test environment. Otherwise leave BLOCKED/NOT_RUN.
- Any change to the implementation reopens the affected row until regression evidence is refreshed.
