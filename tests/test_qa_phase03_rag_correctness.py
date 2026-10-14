"""Tests for QA Phase 03: RAG Correctness, Grounding & Knowledge Integrity.

Verifies:
- QA-004: RAG health probe requires real retrieval and rejects empty results in production
- QA-006: Hybrid lexical + semantic n-gram + conceptual association retrieval
- QA-007: Fallback error logging and diagnosis rather than silent suppression
- Evidence card integrity, citation formatting, and metadata isolation
"""
import json
from pathlib import Path

import pytest

from central_platform.db import PlatformDatabase
from central_platform.deployment.validator import DeploymentValidator, ValidationStatus
from central_platform.models.schema import (
    Course,
    CourseVisibility,
    Organization,
    RAGChunk,
    RAGSource,
    RAGSourceStatus,
)
from central_platform.rag.service import RAGService


@pytest.fixture
def rag_test_env(tmp_path):
    """Sets up an isolated database with multi-tenant course and RAG data."""
    db_path = str(tmp_path / "rag_test.db")
    db = PlatformDatabase(db_path=db_path)

    # Organizations
    org_a = Organization(id="org_alpha", name="Alpha School", slug="alpha")
    org_b = Organization(id="org_beta", name="Beta School", slug="beta")
    db.create_organization(org_a)
    db.create_organization(org_b)

    # Courses
    crs_a = Course(id="crs_chem_101", title="Chemistry 101", code="CHEM101", organization_id="org_alpha", visibility=CourseVisibility.PUBLIC)
    crs_b = Course(id="crs_bio_201", title="Biology 201", code="BIO201", organization_id="org_beta", visibility=CourseVisibility.PUBLIC)
    db.create_course(crs_a)
    db.create_course(crs_b)

    # Seed RAG source in Course A
    src_a = RAGSource(
        id="src_chem_thermo",
        organization_id="org_alpha",
        course_id="crs_chem_101",
        title="NCERT Thermodynamics",
        subject="Chemistry",
        status=RAGSourceStatus.PUBLISHED.value,
        chunk_count=2,
    )
    db.create_rag_source(src_a)

    # Chunks for Course A
    chunk_1 = RAGChunk(
        id="chk_001",
        source_id="src_chem_thermo",
        course_id="crs_chem_101",
        subject="Chemistry",
        chapter="Thermodynamics",
        topic="First Law",
        concept="enthalpy",
        clean_text="Enthalpy is the heat content of a system at constant pressure. Delta H measures energy changes in exothermic reactions.",
        provenance_type="NCERT",
        page=142,
    )
    chunk_2 = RAGChunk(
        id="chk_002",
        source_id="src_chem_thermo",
        course_id="crs_chem_101",
        subject="Chemistry",
        chapter="Equilibrium",
        topic="Le Chatelier",
        concept="chemical_equilibrium",
        clean_text="Chemical equilibrium occurs when the forward and reverse reaction rates are equal. Le Chatelier's principle dictates state shifts.",
        provenance_type="NCERT",
        page=198,
    )
    db.add_rag_chunks([chunk_1, chunk_2])

    # Seed RAG source in Course B
    src_b = RAGSource(
        id="src_bio_genetics",
        organization_id="org_beta",
        course_id="crs_bio_201",
        title="Genetics Fundamentals",
        subject="Biology",
        status=RAGSourceStatus.PUBLISHED.value,
        chunk_count=1,
    )
    db.create_rag_source(src_b)
    chunk_b = RAGChunk(
        id="chk_b01",
        source_id="src_bio_genetics",
        course_id="crs_bio_201",
        subject="Biology",
        chapter="Genetics",
        topic="DNA",
        clean_text="DNA replication is semiconservative and preserves genetic code.",
        provenance_type="NCERT",
        page=45,
    )
    db.add_rag_chunks([chunk_b])

    service = RAGService(db=db)
    return {
        "db": db,
        "db_path": db_path,
        "service": service,
        "crs_a": crs_a,
        "crs_b": crs_b,
    }


class TestRAGCorrectnessAndIntegrity:
    """Verifies RAG correctness, semantic recall, error reporting, and health checks."""

    def test_semantic_retrieval_and_paraphrase_recall(self, rag_test_env):
        """QA-006: Conceptual associations and morphological variations retrieve relevant chunks."""
        svc: RAGService = rag_test_env["service"]

        # Conceptual association: 'heat energy change' -> matches chunk containing 'enthalpy'
        res = svc.query("heat energy change in reaction", course_id="crs_chem_101")
        assert res["status"] == "RAG_OK"
        assert res["count"] > 0
        top = res["results"][0]
        assert top["chunk_id"] == "chk_001"
        assert top["semantic_score"] > 0
        assert "score" in top
        assert "citation" in top

        # Morphological variation: 'equilibrating dynamic balance' -> matches 'chemical equilibrium'
        res_eq = svc.query("equilibrating dynamic balance", course_id="crs_chem_101")
        assert res_eq["status"] == "RAG_OK"
        assert res_eq["count"] > 0
        assert any(r["chunk_id"] == "chk_002" for r in res_eq["results"])

    def test_course_tenant_isolation(self, rag_test_env):
        """Course A queries never leak chunks from Course B."""
        svc: RAGService = rag_test_env["service"]

        # Query Course A for genetics
        res = svc.query("DNA replication", course_id="crs_chem_101")
        # Genetics is in Course B, so Course A should yield RAG_EMPTY
        assert res["status"] == "RAG_EMPTY"
        assert res["count"] == 0

        # Query Course B for genetics -> retrieved
        res_b = svc.query("DNA replication", course_id="crs_bio_201")
        assert res_b["status"] == "RAG_OK"
        assert res_b["results"][0]["chunk_id"] == "chk_b01"

    def test_legacy_fallback_records_file_errors(self, tmp_path):
        """QA-007: Corrupted fallback JSON files are explicitly recorded in diagnostics, not swallowed."""
        db = PlatformDatabase(":memory:")
        svc = RAGService(db=db)

        # Create temporary directory simulating data/rag
        fake_rag_dir = tmp_path / "data" / "rag"
        fake_rag_dir.mkdir(parents=True, exist_ok=True)

        # Write one corrupt JSON file and one valid file
        corrupt_file = fake_rag_dir / "ncert_corrupt.json"
        corrupt_file.write_text("{malformed: json corrupt", encoding="utf-8")

        valid_file = fake_rag_dir / "ncert_valid.json"
        valid_file.write_text(json.dumps({
            "chapter": "Kinetics",
            "chunks": [{"text": "Reaction rate depends on activation energy.", "page": 88}]
        }), encoding="utf-8")

        res = svc._legacy_fallback_query("activation energy", top_k=5, rag_dir=fake_rag_dir)

        # Verification: result is returned and errors list is populated with filename and error category
        assert res["status"] == "RAG_OK"
        assert res["count"] > 0
        assert "errors" in res
        assert len(res["errors"]) > 0
        err_item = res["errors"][0]
        assert err_item["filename"] == "ncert_corrupt.json"
        assert "JSONDecodeError" in err_item["error_category"]

    def test_deployment_validator_rag_probe_hardening(self, rag_test_env, tmp_path):
        """QA-004: In production, validator fails when 0 RAG sources/evidence exist."""
        # 1. DB with published sources in development mode -> UP, retrieval verified
        v_dev = DeploymentValidator(
            root_dir=Path("."),
            db_path=rag_test_env["db_path"],
            env_vars={"APP_ENV": "development"},
        )
        r_dev = v_dev.validate_health_checks()
        rag_info = r_dev.details["probes"]["rag_service"]
        assert rag_info["status"] == "UP"
        assert rag_info.get("retrieval_verified") is True

        # 2. Empty DB in production mode -> DOWN (empty result is NOT healthy)
        empty_db_path = str(tmp_path / "empty.db")
        PlatformDatabase(db_path=empty_db_path)
        v_prod_empty = DeploymentValidator(
            root_dir=Path("."),
            db_path=empty_db_path,
            env_vars={"APP_ENV": "production"},
        )
        r_prod = v_prod_empty.validate_health_checks()
        rag_info_prod = r_prod.details["probes"]["rag_service"]
        assert rag_info_prod["status"] == "DOWN"
        assert "Zero published RAG sources" in rag_info_prod["error"]
