"""Gayatri AI Platform — Phase 44 Test Suite: 47-Agent Subsystem, SLM-MUX, & API Gateways.

Validates:
1. BaseAgent, AgentContext, and AgentResult contract integrity.
2. 47-Agent Cluster Registry & Cluster E built-in governance agents.
3. In-house Agent 42 (RBAC Enforcement Gate) boundary validation.
4. In-house Agent 43 (Immutable Audit Trail Logger) audit verification.
5. SLMMuxRouter mathematical properties (s_i, tie-breaking, UnionAcc objective).
6. FastAPI endpoints (/api/v1/agents/execute, /api/v1/agents/, etc.).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from central_platform.ai.agents.base import AgentContext, AgentResult, BaseAgent
from central_platform.ai.agents.registry import (
    AgentRegistry,
    AuditTrailAgent,
    RBACEnforcementAgent,
    agent_registry,
    get_governance_agent,
)
from central_platform.ai.slm_mux import SLMMuxRouter, slm_mux
from central_platform.api.app import create_app


# =====================================================================
# Fixtures & Mock Intern Agents
# =====================================================================

class MockSocraticTutorAgent(BaseAgent):
    """Cluster A — Agent 1: Socratic Tutor (Educational)."""
    name = "Socratic Tutor Agent"
    cluster = "A"
    agent_id = 1
    description = "Guides students using Socratic inquiry."
    version = "1.0.0"
    required_role = "student"

    def execute(self, context: AgentContext) -> AgentResult:
        query = context.payload.get("question", "")
        return AgentResult(
            success=True,
            confidence=0.96,
            output={"reply": f"What do you observe about {query}?", "guiding_question": True},
            citations=["NCERT-Class11-Chem-Ch6"],
        )


class MockLoanDocketGapAgent(BaseAgent):
    """Cluster B — Agent 12: Loan Docket Gap Analyzer (BFSI Compliance)."""
    name = "Loan Docket Gap Analyzer"
    cluster = "B"
    agent_id = 12
    description = "Identifies documentation deficiencies in credit dockets."
    version = "1.0.0"
    required_role = "compliance_officer"

    def execute(self, context: AgentContext) -> AgentResult:
        docs = context.payload.get("documents", [])
        missing = []
        if "pan_card" not in docs:
            missing.append("PAN Card")
        if "income_proof" not in docs:
            missing.append("Income Proof (ITR / Form 16)")

        return AgentResult(
            success=True,
            confidence=0.99,
            output={"docket_valid": len(missing) == 0, "missing_documents": missing},
            citations=["RBI-Master-Direction-KYC-2024-Sec4"],
        )


@pytest.fixture(autouse=True)
def setup_test_agents():
    """Register sample domain agents for testing and clean up afterward."""
    agent_registry.register(MockSocraticTutorAgent())
    agent_registry.register(MockLoanDocketGapAgent())
    yield


@pytest.fixture
def api_client():
    app = create_app()
    return TestClient(app)


# =====================================================================
# Test Suite
# =====================================================================

class TestBaseAgentAndContracts:
    def test_agent_context_hashing(self):
        ctx1 = AgentContext(cluster="A", agent_id=1, payload={"question": "What is enthalpy?"})
        ctx2 = AgentContext(cluster="A", agent_id=1, payload={"question": "What is enthalpy?"})
        ctx3 = AgentContext(cluster="A", agent_id=1, payload={"question": "What is entropy?"})

        assert ctx1.get_payload_hash() == ctx2.get_payload_hash()
        assert ctx1.get_payload_hash() != ctx3.get_payload_hash()

    def test_context_agent_id_mismatch_raises(self):
        agent = MockSocraticTutorAgent()
        bad_ctx = AgentContext(cluster="B", agent_id=12, payload={})
        res = agent.run(bad_ctx)
        assert res.success is False
        assert "Context mismatch" in str(res.error)


class TestAgentRegistryAndGovernance:
    def test_governance_agents_pre_registered(self):
        # All 8 Cluster E agents must be active
        for agent_id in [40, 41, 42, 43, 44, 45, 46, 47]:
            agent = get_governance_agent(agent_id)
            assert agent is not None, f"Cluster E Agent {agent_id} must be registered"
            assert agent.cluster == "E"
            assert agent.agent_id == agent_id

    def test_cluster_stats(self):
        stats = agent_registry.get_cluster_stats()
        assert "A" in stats
        assert "B" in stats
        assert "E" in stats
        assert stats["E"]["count"] >= 8
        assert 1 in stats["A"]["agents"]
        assert 12 in stats["B"]["agents"]

    def test_agent_42_rbac_enforcement(self):
        agent12 = agent_registry.get_agent("B", 12)
        assert agent12 is not None

        # Student attempting to run BFSI compliance agent -> PermissionError
        student_ctx = AgentContext(
            cluster="B",
            agent_id=12,
            payload={"documents": ["pan_card"]},
            user_role="student",
        )
        res_student = agent12.run(student_ctx)
        assert res_student.success is False
        assert "RBAC Enforcement Failure" in str(res_student.error)

        # Compliance officer running BFSI agent -> Authorized
        officer_ctx = AgentContext(
            cluster="B",
            agent_id=12,
            payload={"documents": ["pan_card"]},
            user_role="compliance_officer",
        )
        res_officer = agent12.run(officer_ctx)
        assert res_officer.success is True
        assert res_officer.output["missing_documents"] == ["Income Proof (ITR / Form 16)"]

    def test_agent_43_audit_trail_logging(self):
        audit_agent: AuditTrailAgent = get_governance_agent(43)
        initial_count = len(audit_agent._audit_records)

        tutor = agent_registry.get_agent("A", 1)
        ctx = AgentContext(
            cluster="A",
            agent_id=1,
            payload={"question": "Define Hess Law"},
            user_id="std-9921",
            user_role="student",
        )
        result = tutor.run(ctx)
        assert result.success is True
        assert result.audit_trail is not None
        assert result.audit_trail["agent_name"] == "Socratic Tutor Agent"
        assert result.audit_trail["user_id"] == "std-9921"
        assert len(audit_agent._audit_records) == initial_count + 1


class TestSLMMuxRouter:
    def test_self_consistency_confidence_computation(self):
        router = SLMMuxRouter()
        samples = [
            "Hess's law states that enthalpy change is independent of the pathway.",
            "Hess's law states that enthalpy change is independent of the pathway.",
            "Hess's law states that heat capacity changes over time.",
        ]
        majority, confidence = router.compute_self_consistency(samples)
        assert "independent of the pathway" in majority
        assert confidence == pytest.approx(2 / 3, rel=1e-2)

    def test_tie_breaking_via_historical_accuracy(self):
        router = SLMMuxRouter(historical_accuracy={
            "qwen2.5-0.5b-instruct": 0.82,
            "qwen2.5-3b-instruct": 0.91,
        })
        tied = [
            ("Output from small model", "qwen2.5-0.5b-instruct"),
            ("Output from larger model", "qwen2.5-3b-instruct"),
        ]
        selected = router.resolve_tie(tied)
        assert selected == "Output from larger model"

    def test_ensemble_objective_math(self):
        router = SLMMuxRouter(lambda_penalty=1.0)
        # O(S) = UnionAcc(S) - lambda * Contradiction(S)
        score = router.evaluate_ensemble_objective(union_accuracy=0.92, contradiction_rate=0.08)
        assert score == pytest.approx(0.84, rel=1e-3)

    def test_model_selection_by_cluster(self):
        assert slm_mux.select_best_model_for_agent("B", 12) == "qwen2.5-3b-instruct"
        assert slm_mux.select_best_model_for_agent("A", 1) == "qwen2.5-0.5b-instruct"


class TestAgentsApiRoutes:
    def test_list_agents_endpoint(self, api_client: TestClient):
        # Default caller is student: BFSI compliance agent is hidden by RBAC
        resp = api_client.get("/api/v1/agents/")
        assert resp.status_code == 200
        agents = resp.json()
        assert len(agents) >= 9
        names = [a["name"] for a in agents]
        assert "Socratic Tutor Agent" in names
        assert "RBAC Enforcement Gate" in names
        assert "Loan Docket Gap Analyzer" not in names  # Correctly filtered out for students!

    def test_list_agents_cluster_filter(self, api_client: TestClient):
        resp = api_client.get("/api/v1/agents/?cluster=A")
        assert resp.status_code == 200
        agents = resp.json()
        assert all(a["cluster"] == "A" for a in agents)

    def test_get_clusters_endpoint(self, api_client: TestClient):
        resp = api_client.get("/api/v1/agents/clusters")
        assert resp.status_code == 200
        data = resp.json()
        assert "clusters" in data
        assert "A" in data["clusters"]
        assert "B" in data["clusters"]

    def test_execute_agent_educational_success(self, api_client: TestClient):
        payload = {
            "cluster": "A",
            "agent_id": 1,
            "payload": {"question": "What is Gibbs Free Energy?"},
        }
        resp = api_client.post("/api/v1/agents/execute", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["cluster"] == "A"
        assert data["agent_id"] == 1
        assert "Gibbs Free Energy" in str(data["output"])
        assert len(data["citations"]) > 0
        assert data["audit_trail"] is not None

    def test_execute_agent_bfsi_rbac_blocked_for_student(self, api_client: TestClient):
        payload = {
            "cluster": "B",
            "agent_id": 12,
            "payload": {"documents": ["pan_card"]},
        }
        # In unauthenticated/student mode, accessing BFSI compliance returns 403 or failure
        resp = api_client.post("/api/v1/agents/execute", json=payload)
        # Check that it either returns 403 or execution failure due to RBAC
        if resp.status_code == 200:
            assert resp.json()["success"] is False
            assert "RBAC Enforcement Failure" in resp.json()["error"]
        else:
            assert resp.status_code == 403

    def test_execute_unregistered_agent_returns_404(self, api_client: TestClient):
        payload = {
            "cluster": "C",
            "agent_id": 99,
            "payload": {},
        }
        resp = api_client.post("/api/v1/agents/execute", json=payload)
        assert resp.status_code == 404
