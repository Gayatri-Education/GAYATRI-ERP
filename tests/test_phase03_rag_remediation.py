"""Phase 03 Remediation Adversarial & Contract Test Suite.

Governing Plan: GAYATRI_AI_AGENT_FORENSIC_REMEDIATION_PLAN.md (Section 8)
Defects Addressed:
- F-005 (P0): Removal of hardcoded Chemistry fallback chunk ('chunk-thermo-01' / 'Delta U = q + w')
- F-006 (P0): Removal of retrieve-anyway unfiltered fallback in core retriever
- F-007 (P0): Strict JWT authentication on RAG API endpoints (no anonymous access)
- F-008 (P0): Anti-spoofing student identity checks & multi-tenant course enrollment scoping
- F-009 (P1): Exact grounding attribution and fail-closed RAG_EMPTY semantics
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db
from central_platform.auth.tokens import create_access_token
from central_platform.db import PlatformDatabase
from central_platform.models.schema import (
    Course,
    CourseVersion,
    CourseVisibility,
    CourseStatus,
    Enrollment,
    KnowledgeContentType,
    Organization,
    RAGChunk,
    RAGSource,
    RAGSourceStatus,
    User,
    UserRole,
)
from central_platform.rag.service import RAGService
from core.rag.schema import DocumentChunk, RAGStatus
from core.rag.retriever import NCERTRetriever
from core.rag.store import RAGStore


@pytest.fixture
def rag_test_env(tmp_path):
    """Sets up an isolated platform database and test client for Phase 3 testing."""
    db_path = str(tmp_path / "rag_remediation_test.db")
    db = PlatformDatabase(db_path=db_path)

    # 1. Organizations
    org_alpha = Organization(id="org-alpha-rag", name="Alpha University", slug="alpha-rag")
    org_beta = Organization(id="org-beta-rag", name="Beta College", slug="beta-rag")
    db.create_organization(org_alpha)
    db.create_organization(org_beta)

    # 2. Users
    student_alpha = User(
        id="std-alpha-1",
        email="student.alpha@alpha.edu",
        full_name="Alpha Student One",
        role=UserRole.STUDENT,
        organization_id="org-alpha-rag",
    )
    student_beta = User(
        id="std-beta-1",
        email="student.beta@beta.edu",
        full_name="Beta Student One",
        role=UserRole.STUDENT,
        organization_id="org-beta-rag",
    )
    teacher_alpha = User(
        id="tch-alpha-1",
        email="teacher.alpha@alpha.edu",
        full_name="Alpha Teacher One",
        role=UserRole.TEACHER,
        organization_id="org-alpha-rag",
    )
    admin_alpha = User(
        id="adm-alpha-1",
        email="admin.alpha@alpha.edu",
        full_name="Alpha Admin",
        role=UserRole.ORG_ADMIN,
        organization_id="org-alpha-rag",
    )
    db.create_user(student_alpha)
    db.create_user(student_beta)
    db.create_user(teacher_alpha)
    db.create_user(admin_alpha)

    # 3. Courses
    course_public = Course(
        id="crs-pub-physics",
        organization_id="org-alpha-rag",
        code="PHY-101",
        title="Public General Physics",
        visibility=CourseVisibility.PUBLIC,
    )
    course_private = Course(
        id="crs-priv-defense",
        organization_id="org-alpha-rag",
        code="DEF-501",
        title="Classified Defense Materials",
        visibility=CourseVisibility.PRIVATE,
    )
    course_beta = Course(
        id="crs-priv-beta",
        organization_id="org-beta-rag",
        code="BIO-201",
        title="Beta Private Biology",
        visibility=CourseVisibility.PRIVATE,
    )
    db.create_course(course_public)
    db.create_course(course_private)
    db.create_course(course_beta)

    # Versions
    db.create_course_version(CourseVersion(id="ver-pub-1", course_id="crs-pub-physics", version_number="1.0.0", status=CourseStatus.PUBLISHED, created_by="adm-alpha-1"))
    db.create_course_version(CourseVersion(id="ver-priv-1", course_id="crs-priv-defense", version_number="1.0.0", status=CourseStatus.PUBLISHED, created_by="adm-alpha-1"))

    # Enrollments: student_alpha enrolled in course_private; student_beta NOT enrolled
    db.create_enrollment(Enrollment(id="enr-std-a-priv", student_id="std-alpha-1", course_id="crs-priv-defense"))

    # 4. Seed published knowledge in course_private
    src_defense = RAGSource(
        id="src-def-01",
        organization_id="org-alpha-rag",
        course_id="crs-priv-defense",
        course_version_id="ver-priv-1",
        subject="Defense",
        title="Radar Systems Principles",
        source_type="textbook",
        authority="Institutional",
        version="1.0",
        status=RAGSourceStatus.PUBLISHED.value,
        content_type=KnowledgeContentType.TEXTBOOK.value,
        visibility_scope="course",
    )
    db.create_rag_source(src_defense)
    db.add_rag_chunks([
        RAGChunk(
            id="chk-radar-01",
            source_id="src-def-01",
            course_id="crs-priv-defense",
            course_version_id="ver-priv-1",
            subject="Defense",
            chapter="Chapter 4: Pulse Radar",
            topic="Doppler Effect",
            concept="DOPPLER_RADAR",
            difficulty="intermediate",
            page=45,
            section="4.2",
            content_type="textbook",
            text="Pulse Doppler radar uses the Doppler shift in echoes to differentiate moving targets from stationary clutter.",
            clean_text="Pulse Doppler radar uses the Doppler shift in echoes to differentiate moving targets from stationary clutter.",
            provenance_type="institutional",
            visibility_scope="course",
        )
    ])

    tokens = {
        "student_alpha": create_access_token(user_id="std-alpha-1", role="student", organization_id="org-alpha-rag"),
        "student_beta": create_access_token(user_id="std-beta-1", role="student", organization_id="org-beta-rag"),
        "teacher_alpha": create_access_token(user_id="tch-alpha-1", role="teacher", organization_id="org-alpha-rag"),
        "admin_alpha": create_access_token(user_id="adm-alpha-1", role="org_admin", organization_id="org-alpha-rag"),
    }

    import central_platform.auth.dependencies as auth_deps
    old_db = auth_deps._DB_INSTANCE
    old_env_path = os.environ.get("GAYATRI_DB_PATH")
    os.environ["GAYATRI_DB_PATH"] = db_path
    auth_deps._DB_INSTANCE = db
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    try:
        yield {
            "db": db,
            "tokens": tokens,
            "client": client,
            "course_public": course_public,
            "course_private": course_private,
            "course_beta": course_beta,
        }
    finally:
        auth_deps._DB_INSTANCE = old_db
        if old_env_path is not None:
            os.environ["GAYATRI_DB_PATH"] = old_env_path
        else:
            os.environ.pop("GAYATRI_DB_PATH", None)
        app.dependency_overrides.pop(get_db, None)


# ── F-005: Removal of Hardcoded Chemistry Fallback ──────────────────────────

def test_F005_empty_query_never_returns_chemistry_chunk_thermo_01(rag_test_env):
    """Verify that a query matching no knowledge records returns RAG_EMPTY, never chunk-thermo-01."""
    svc = RAGService(db=rag_test_env["db"])

    # Query for something completely absent from both DB and legacy files
    res = svc.query(query_text="NonExistentAlienLanguageQuery_XYZ987654321")

    assert res["status"] in ("RAG_EMPTY", "RAG_UNAVAILABLE")
    assert res["count"] == 0
    assert len(res["results"]) == 0
    assert res["data_context"] == ""

    # Adversarial invariant: chunk-thermo-01 and Delta U must NEVER be returned
    for r in res["results"]:
        assert r.get("chunk_id") != "chunk-thermo-01"
        assert "Delta U" not in r.get("text", "")
        assert "ncert_chem_11_ch6" not in r.get("source_id", "")


def test_F005_legacy_fallback_never_fabricates_chunk_on_miss(rag_test_env):
    """Directly test _legacy_fallback_query to ensure it returns RAG_EMPTY on total miss."""
    svc = RAGService(db=rag_test_env["db"])
    res = svc._legacy_fallback_query("ZyzzyvaQuarkPlasmaUnobtainium_9999", top_k=3)

    assert res["status"] == "RAG_EMPTY"
    assert res["count"] == 0
    assert len(res["results"]) == 0
    assert res["data_context"] == ""


# ── F-006: Removal of Retrieve-Anyway Unfiltered Fallback ────────────────────

def test_F006_metadata_filtering_mismatch_returns_empty_never_leaks_unfiltered(tmp_path):
    """Verify that when metadata filters match 0 candidates, retriever returns RAG_EMPTY without leaking."""
    db_path = tmp_path / "test_retriever_f006.db"
    store = RAGStore(db_path=db_path)

    # Add chunk belonging strictly to Unit 6
    chunk_thermo = DocumentChunk(
        chunk_id="chk_thermo_only",
        source_id="NCERT 11",
        chapter="Unit 6",
        topic="Thermodynamics",
        subtopic="Internal Energy",
        concept="THERMO_U",
        page=160,
        text="Internal energy U is state function.",
    )
    store.add_chunk(chunk_thermo)

    retriever = NCERTRetriever(store=store)

    # Query with a non-matching chapter filter
    ctx = retriever.retrieve_hybrid("What is energy?", chapter="Unit 14 Biomolecules")

    # Before F-006 fix, this would fall back to vector_candidates and return Unit 6!
    # With F-006 fix, fail-closed semantics return empty RAGContext
    assert ctx.status == RAGStatus.RAG_EMPTY
    assert len(ctx.results) == 0
    assert ctx.evidence_card is None


# ── F-007: Strict Authentication on RAG Endpoints ────────────────────────────

def test_F007_rag_routes_unauthenticated_rejected_401(rag_test_env):
    """Verify that unauthenticated calls to all RAG endpoints are rejected with HTTP 401."""
    client = rag_test_env["client"]

    # 1. POST /api/v1/rag/query
    r_query = client.post("/api/v1/rag/query", json={"query": "Doppler radar echo"})
    assert r_query.status_code == 401, f"Expected 401 for unauthenticated query, got {r_query.status_code}"

    # 2. GET /api/v1/rag/sources
    r_sources = client.get("/api/v1/rag/sources")
    assert r_sources.status_code == 401, f"Expected 401 for unauthenticated sources list, got {r_sources.status_code}"

    # 3. GET /api/v1/rag/sources/{source_id}
    r_source = client.get("/api/v1/rag/sources/src-def-01")
    assert r_source.status_code == 401, f"Expected 401 for unauthenticated source get, got {r_source.status_code}"

    # 4. GET /api/v1/rag/sources/{source_id}/chunks
    r_chunks = client.get("/api/v1/rag/sources/src-def-01/chunks")
    assert r_chunks.status_code == 401, f"Expected 401 for unauthenticated chunks list, got {r_chunks.status_code}"

    # 5. POST /api/v1/rag/sources
    r_create = client.post("/api/v1/rag/sources", json={"title": "Test", "subject": "Test"})
    assert r_create.status_code == 401, f"Expected 401 for unauthenticated source create, got {r_create.status_code}"

    # 6. POST /api/v1/rag/sources/{source_id}/ingest
    r_ingest = client.post("/api/v1/rag/sources/src-def-01/ingest", json={"content": "Sample content"})
    assert r_ingest.status_code == 401, f"Expected 401 for unauthenticated ingest, got {r_ingest.status_code}"

    # 7. POST /api/v1/rag/sources/{source_id}/validate
    r_val = client.post("/api/v1/rag/sources/src-def-01/validate")
    assert r_val.status_code == 401, f"Expected 401 for unauthenticated validate, got {r_val.status_code}"

    # 8. POST /api/v1/rag/sources/{source_id}/publish
    r_pub = client.post("/api/v1/rag/sources/src-def-01/publish")
    assert r_pub.status_code == 401, f"Expected 401 for unauthenticated publish, got {r_pub.status_code}"

    # 9. DELETE /api/v1/rag/sources/{source_id}
    r_del = client.delete("/api/v1/rag/sources/src-def-01")
    assert r_del.status_code == 401, f"Expected 401 for unauthenticated delete, got {r_del.status_code}"


# ── F-008: Student Identity Anti-Spoofing & Multi-Tenant Scoping ─────────────

def test_F008_student_cannot_spoof_another_student_id_in_query(rag_test_env):
    """Verify that a student cannot execute RAG queries on behalf of a different student ID."""
    client = rag_test_env["client"]
    token_alpha = rag_test_env["tokens"]["student_alpha"]

    # Student Alpha attempts to query passing student_id="std-beta-1"
    resp = client.post(
        "/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token_alpha}"},
        json={
            "query": "Doppler radar echo",
            "course_id": "crs-priv-defense",
            "student_id": "std-beta-1",
        },
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


def test_F008_student_cannot_query_private_course_without_enrollment(rag_test_env):
    """Verify that a student cannot query a private course they are not enrolled in."""
    client = rag_test_env["client"]
    token_beta = rag_test_env["tokens"]["student_beta"]

    # Student Beta (org-beta-rag) queries private course in org-alpha-rag without enrollment
    resp = client.post(
        "/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token_beta}"},
        json={
            "query": "Doppler radar echo",
            "course_id": "crs-priv-defense",
        },
    )
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]


def test_F008_teacher_cannot_create_source_for_another_organization(rag_test_env):
    """Verify that a teacher cannot register a knowledge source for a course in another org."""
    client = rag_test_env["client"]
    token_teacher = rag_test_env["tokens"]["teacher_alpha"]

    # Teacher Alpha (org-alpha-rag) attempts to attach source to course_beta (org-beta-rag)
    resp = client.post(
        "/api/v1/rag/sources",
        headers={"Authorization": f"Bearer {token_teacher}"},
        json={
            "course_id": "crs-priv-beta",
            "subject": "Biology",
            "title": "Malicious Cross-Tenant Textbook",
        },
    )
    assert resp.status_code == 403
    assert "Cannot add knowledge sources to a course from another organization" in resp.json()["detail"]


# ── F-009: Grounding Attribution and Legitimate Retrieval ─────────────────────

def test_F009_enrolled_student_retrieves_exact_grounded_chunks(rag_test_env):
    """Verify that an enrolled student querying their course retrieves strictly grounded chunks."""
    client = rag_test_env["client"]
    token_alpha = rag_test_env["tokens"]["student_alpha"]

    resp = client.post(
        "/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token_alpha}"},
        json={
            "query": "Doppler shift in echoes moving targets",
            "course_id": "crs-priv-defense",
            "top_k": 2,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["status"] == "RAG_OK"
    assert data["count"] >= 1
    assert any("Pulse Doppler radar" in r["text"] for r in data["results"])
    assert data["results"][0]["chunk_id"] == "chk-radar-01"


def test_F009_enrolled_student_querying_missing_concept_returns_rag_empty(rag_test_env):
    """Verify that querying a missing concept returns clean RAG_EMPTY without fallback leaks."""
    client = rag_test_env["client"]
    token_alpha = rag_test_env["tokens"]["student_alpha"]

    resp = client.post(
        "/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token_alpha}"},
        json={
            "query": "photosynthesis chloroplast thylakoid light reactions",
            "course_id": "crs-priv-defense",
            "top_k": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "RAG_EMPTY"
    assert data["count"] == 0
    assert len(data["results"]) == 0
    assert data["data_context"] == ""
