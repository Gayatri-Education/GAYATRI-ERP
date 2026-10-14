# Source: Agent Architecture Matrix

## 47-Agent Subsystem Architecture
The **47-agent subsystem architecture** is divided across five specialized operational clusters, partitioned between **In-House Core IP** and **Intern Domain Work Packages** to preserve security and IP boundaries.

### 1. Agent Cluster Overview & Domain Repositories
* **Cluster A: Educational & Adaptive Tutoring Agents (Agents 1–10)**
  * **Repository:** `gayatri-agents-educational` (Intern Domain Repo A)
  * **Focus:** Adaptive tutoring, Socratic dialogue, and curriculum-driven learning workflows.
* **Cluster B: BFSI Enterprise & Sovereign Compliance Agents (Agents 11–20)**
  * **Repository:** `gayatri-agents-bfsi` (Intern Domain Repo B)
  * **Focus:** KYC/docket parsers, document gap analyzers, and compliance extraction tools.
* **Cluster C: Deep Research & Knowledge Agents (Agents 21–30)**
  * **Repository:** `gayatri-agents-research` (Intern Domain Repo C)
  * **Focus:** Web/local document research, indexing, and synthesis explorers.
* **Cluster D: Software Engineering & Code Automation Agents (Agents 31–39)**
  * **Repository:** `gayatri-agents-coding` (Intern Domain Repo D)
  * **Focus:** Utility code generation, NL2SQL, and NL2Py template tuning.
* **Cluster E: Platform Governance, Orchestration & SLM Engine Agents (Agents 40–47)**
  * **Repository:** `Gayatri-Education/Gayatri` (Core Main Repo — In-House Only)
  * **Focus:** SLM-MUX routing engine, RBAC, zero-egress enforcement, and orchestration.

### 2. Work Package Division Matrix
| Development Tier | Assigned Scope & Responsibilities | Key Components |
|---|---|---|
| **Intern Work Packages** *(Modular Extensions)* | Modular agents built against the `gayatri-agent-sdk` contract in isolated domain repositories. | • Utility Educational Agents<br>• Document Extractors & Parsers<br>• Search & Web Explorers<br>• NL2SQL / NL2Py Template Tuning<br>• UI Adapters & Prompt Files |
| **In-House Scope** *(Core IP & Security)* | Strictly private core codebase containing core routing, security, and database engines. | • SLM-MUX Router & Search Engine<br>• Deterministic Citation & Grounding<br>• RBAC, Zero-Egress & DB Engine<br>• 5-Tier Instruction Cascade<br>• Sandboxed Execution & Rollback |

### 3. Work Package Delivery & Execution Framework
Interns build and test agents locally using the **`gayatri-agent-sdk`** harness:
* **Contract Specification:** All agents extend `BaseAgent` and consume structured `AgentContext` and `AgentResult` Pydantic models.
* **Sample Concrete Work Packages:**
  * **Agent 1:** Socratic Tutor Agent (Educational Cluster)
  * **Agent 12:** Loan Docket Gap Analyzer (BFSI Cluster)
* **Test Datasets & CLI:** Execution is validated locally using synthetic payloads (e.g., `mock_docket.json`, `mock_student_profile.json`) via the CLI command `gayatri-agent run --agent <file.py> --payload <payload.json>`.
