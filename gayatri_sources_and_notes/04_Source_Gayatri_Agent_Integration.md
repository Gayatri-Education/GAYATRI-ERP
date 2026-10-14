# Source: Gayatri Agent Integration

To integrate an intern AI agent into the core platform repository (`Gayatri-Education/Gayatri`), the platform uses a **partitioned, contract-driven architecture** that keeps proprietary central logic separate from modular agent code.

### 1. Development & Contract Standard (`gayatri-agent-sdk`)
* **Isolated Repositories:** Interns work in domain-specific repositories (`gayatri-agents-educational`, `gayatri-agents-bfsi`, `gayatri-agents-research`, or `gayatri-agents-coding`) rather than directly inside `Gayatri-Education/Gayatri`.
* **Contract Specification:** Every agent extends the `BaseAgent` class provided by `gayatri-agent-sdk` and communicates exclusively using standardized `AgentContext` and `AgentResult` Pydantic models.
* **Local Verification:** Interns validate execution locally using `MockExecutionHarness` and the CLI command (`gayatri-agent run --agent <file.py> --payload <payload.json>`).

### 2. CI/CD Validation Gate
* **Automated Testing:** Pull requests submitted to domain repos trigger `.github/workflows/validate.yml`.
* **Release Tagging:** CI runs automated contract tests (`test_agent_template.py`) to ensure execution assertions pass before a version release is tagged.

### 3. Central Ingestion into `Gayatri-Education/Gayatri`
1. **Submodule / Release Import:** The main core repo ingests tagged domain releases via Git submodules or PR imports.
2. **Registration (`central_platform/ai/agents/registry.py`):** Imported agents are registered alongside core contracts defined in `central_platform/ai/agents/base.py`.
3. **API Exposure (`central_platform/api/routes/agents.py`):** FastAPI endpoints route incoming API requests to the registered intern agent.
4. **SLM-MUX Routing & Governance (`central_platform/ai/slm_mux.py`):** The central platform's routing engine handles model routing, calculates confidence frequency scores ($s_i$), and enforces zero-egress security boundaries.
