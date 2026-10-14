# Source: Gayatri Agent Architecture

Intern agents integrate with the core Gayatri platform (`Gayatri-Education/Gayatri`) through a **partitioned, contract-driven architecture** designed to keep central IP secure while allowing modular extensions in isolated environments.

### 1. Isolated Repositories & SDK Contract Standard
* **Domain Isolation:** Interns work in isolated domain repositories (`gayatri-agents-educational`, `gayatri-agents-bfsi`, `gayatri-agents-research`, `gayatri-agents-coding`) rather than writing code directly inside the private core repo.
* **Contract Specification:** All intern agents extend the `BaseAgent` class provided by `gayatri-agent-sdk` and exchange data using standardized `AgentContext` and `AgentResult` Pydantic models.

### 2. Local Testing & Verification
* **Offline Mock Harness:** Interns test their agents on their local machines using `MockExecutionHarness` (`gayatri_sdk/harness.py`), bypassing core central platform dependencies.
* **CLI Runner & Synthetic Data:** Execution is validated locally using synthetic payloads (such as `mock_docket.json` and `mock_student_profile.json`) via the CLI command `gayatri-agent run --agent <file.py> --payload <payload.json>`.
