# Source: Gayatri Agent SDK

The **`gayatri-agent-sdk`** provides a standalone local testing and development environment so developers and interns can build and validate modular agents without needing access to the core central platform.

For local testing, the SDK includes:
* **`MockExecutionHarness` (`gayatri_sdk/harness.py`):** A standalone execution harness that loads, validates, and runs agents locally without relying on central platform dependencies.
* **CLI Tooling (`gayatri_sdk/cli.py`):** A command-line runner that allows you to execute agents against payload files using `gayatri-agent run --agent <file.py> --payload <payload.json>`.
* **Synthetic Test Datasets (`data/synthetic/`):** Sample payload files (`mock_docket.json`, `mock_student_profile.json`).
* **Unit Test Suite (`tests/test_agent_template.py`):** Contract and execution assertion checks.
* **Boilerplate Template (`templates/agent_template.py`):** Reference implementation extending `BaseAgent`.
