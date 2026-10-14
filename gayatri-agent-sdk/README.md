# Gayatri Agent SDK (`gayatri-agent-sdk`)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

The **Gayatri Agent SDK** provides the universal contract, local execution harness, CLI runner, and synthetic test datasets for building modular AI agents across the 47-agent platform.

---

## 🚀 Quick Start (Local Setup)

Install in editable mode:
```bash
git clone https://github.com/Gayatri-Education/gayatri-agent-sdk.git
cd gayatri-agent-sdk
pip install -e .
```

Verify installation:
```bash
gayatri-agent --help
```

---

## 🛠️ The 3 Contract Rules for Interns

Every agent built for Gayatri AI must satisfy 3 rules:

1. **Extend `BaseAgent`** (from `gayatri_sdk.base`)
2. **Accept `AgentContext`** as the input parameter to `execute()`
3. **Return `AgentResult`** as the output from `execute()`

### Minimal Agent Example:

```python
from gayatri_sdk.base import BaseAgent, AgentContext, AgentResult

class SimpleAgent(BaseAgent):
    name = "Sample Calculator Agent"
    cluster = "D"
    agent_id = 31
    version = "1.0.0"

    def execute(self, context: AgentContext) -> AgentResult:
        a = context.payload.get("a", 0)
        b = context.payload.get("b", 0)
        return AgentResult(
            success=True,
            confidence=1.0,
            output={"sum": a + b},
            citations=["Math-Core-v1"]
        )
```

---

## 🧪 Testing Locally (Offline Simulation)

Run your agent locally with synthetic test payloads using the CLI:

```bash
gayatri-agent run --agent templates/agent_template.py --payload data/synthetic/mock_student_profile.json
```

Run automated contract validation:
```bash
pytest tests/
```

---

## 📁 Repository Structure

```
gayatri-agent-sdk/
├── gayatri_sdk/
│   ├── base.py       # BaseAgent, AgentContext, AgentResult Pydantic models
│   ├── harness.py    # MockExecutionHarness (standalone offline simulator)
│   └── cli.py        # CLI command: 'gayatri-agent run'
├── templates/
│   └── agent_template.py  # Boilerplate for interns
├── examples/
│   ├── agent_01_socratic_tutor.py    # Cluster A (Educational) reference
│   └── agent_12_loan_docket_gap.py   # Cluster B (BFSI Compliance) reference
├── data/synthetic/
│   ├── mock_student_profile.json     # Fake student profile
│   ├── mock_docket.json              # Fake loan docket
│   └── mock_resume.json              # Fake HR applicant CV
└── .github/workflows/
    └── validate.yml  # Automated CI gate for domain repo pull requests
```
