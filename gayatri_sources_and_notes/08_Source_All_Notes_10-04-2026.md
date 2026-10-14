# Source: All Notes 10/4/2026 Summary

The Gayatri platform utilizes a **partitioned, contract-driven architecture** that neatly separates sensitive central intellectual property from modular, intern-built extensions.

* **Repository Partitioning:** Development is split across four isolated domain repositories (`gayatri-agents-educational`, `gayatri-agents-bfsi`, `gayatri-agents-research`, and `gayatri-agents-coding`) while core governance remains in `Gayatri-Education/Gayatri`.
* **Standardization via SDK:** The `gayatri-agent-sdk` mandates that every agent inherit `BaseAgent` and exchange data using `AgentContext` and `AgentResult` Pydantic models.
* **Offline Verification:** Developers run tests locally using `MockExecutionHarness` and CLI against synthetic payloads (`mock_docket.json`, `mock_student_profile.json`).
* **Central System:** Central platform orchestrates up to 47 agents across 5 clusters using `slm_mux.py` and zero-egress sandboxing.
