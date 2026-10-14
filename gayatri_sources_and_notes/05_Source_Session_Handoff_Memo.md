# Source: Session Handoff & System Transition Memo

**Project:** Gayatri AI Platform (`Gayatri-Education/Gayatri`)  
**Focus:** Sovereign AI for BFSI Enterprise Compliance, Educational Tutoring, and Contract-Only SDK Architecture  
**Document Purpose:** Complete state transfer and action plan for the next AI agent or development lead.

## 1. Core System Architecture & Project State
* **Core Mission:** Provide a private, zero-data-egress, sovereign intelligence platform for regulated financial institutions (BFSI) and edge educational deployments.
* **47-Agent Subsystem Architecture:** Divided across 5 operational clusters (Cluster A: Educational, Cluster B: BFSI, Cluster C: Research, Cluster D: Coding, Cluster E: Platform Governance).
* **SLM-MUX Routing Engine:** Orchestrates ensembles of local Small Language Models (Qwen2.5-0.5B via llama-cpp-python) on resource-constrained devices.
  * **Confidence Estimation ($s_i$):** Self-consistency frequency scoring across $k$ candidate samples generated at $T > 0$.
  * **Tie-Breaking Rule:** Settled using historical validation accuracy ($a_i$).
  * **Model Search Objective:** $O(S) = \text{UnionAcc}(S) - \lambda \cdot \text{Contradiction}(S)$, balancing accuracy bounds with penalty thresholds ($\lambda = 1.0$).

## 2. Repository Topology & Important URLs
* **Core Main Repo:** `https://github.com/Gayatri-Education/Gayatri` (Strictly Private In-House Only).
* **Public SDK Repo:** `https://github.com/Gayatri-Education/gayatri-agent-sdk` (Public / Developer SDK).
* **Domain Repo A:** `https://github.com/Gayatri-Education/gayatri-agents-educational` (Educational Tutoring Agents).
* **Domain Repo B:** `https://github.com/Gayatri-Education/gayatri-agents-bfsi` (BFSI Compliance Agents).
* **Domain Repo C:** `https://github.com/Gayatri-Education/gayatri-agents-research` (Research Agents).
* **Domain Repo D:** `https://github.com/Gayatri-Education/gayatri-agents-coding` (Code Automation Agents).

## 3. Completed Technical Deliverables
The `gayatri-agent-sdk` package structure:
* `gayatri_sdk/base.py`: BaseAgent, AgentContext, AgentResult Pydantic models.
* `gayatri_sdk/harness.py`: MockExecutionHarness for local execution.
* `gayatri_sdk/cli.py`: Command-line runner (`gayatri-agent run`).
* `templates/agent_template.py`: Boilerplate implementation.
* `data/synthetic/`: Sample payloads (`mock_docket.json`, `mock_student_profile.json`).
* `tests/test_agent_template.py`: Unit test suite.
* `.github/workflows/validate.yml`: CI workflow for domain repos.
