"""Gayatri AI Platform — Plug-and-Play Curricula API Endpoints (Phase 15 / Section 24).

Master Plan Section 24:
- Dynamic course/curriculum hierarchy retrieval:
  Course -> Curriculum Version -> Subject -> Module -> Topic -> Concept -> Prerequisites.
- Full versioning & lifecycle: draft -> validated -> published -> archived.
- Immutable after publication: published versions cannot be modified.
- Structural DAG validation: detects cycles and orphan prerequisites.
- Universal declarative package import / export with round-trip fidelity.
- Multi-tenant RBAC gatekeeping (Students blocked with 403 Forbidden).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

logger = logging.getLogger("gayatri.central_platform.api.routes.curricula")

from central_platform.api.schemas import (
    ApiResponse,
    CurriculumExportResponse,
    CurriculumHierarchyResponse,
    CurriculumImportRequest,
    CurriculumImportResponse,
    CurriculumResponse,
    CurriculumValidationResponse,
    CurriculumVersionCreateRequest,
    CurriculumVersionPublishResponse,
)
from central_platform.auth.dependencies import (
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.curriculum.service import (
    CurriculumService,
    CurriculumStatus,
)
from central_platform.models.schema import User, UserRole
from central_platform.rbac.engine import normalize_role

router = APIRouter(prefix="/curricula", tags=["Curricula"])
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

def get_curriculum_service() -> CurriculumService:
    db = get_db()
    return CurriculumService(db)


def _enforce_authoring_auth(current_user: Optional[User]) -> User:
    """Ensure user is authorized to create, import, or publish curricula."""
    if not current_user:
        if is_production_mode():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required in production",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return User(
            id="admin-default",
            email="admin@gayatri.edu",
            full_name="System Administrator",
            role=UserRole.SUPER_ADMIN,
        )
    user_role = normalize_role(current_user.role)
    if user_role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.COURSE_ADMIN, UserRole.TEACHER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Students and parents cannot author, import, or publish curricula",
        )
    return current_user


# ── 1. Dynamic Curriculum Retrieval (Phase 02 & Phase 15 compatible) ───────

@router.get("/{course_id}", response_model=ApiResponse[CurriculumResponse])
async def get_curriculum(course_id: str):
    """Retrieve full curriculum hierarchy, concepts, and DAG prerequisites for a course."""
    service = get_curriculum_service()

    # Try resolving dynamically from authoritative database
    try:
        hierarchy = service.get_curriculum_hierarchy(course_id)
        modules = hierarchy.get("modules", [])

        # Build chapters from modules
        chapters = []
        for m in modules:
            mod_concepts = []
            for t in m.get("topics", []):
                for c in t.get("concepts", []):
                    mod_concepts.append(c)
            chapters.append({
                "chapter_name": m.get("title", "Core Module"),
                "concepts": mod_concepts,
                "concept_count": len(mod_concepts),
            })

        total_concepts = hierarchy.get("total_concepts", sum(len(c["concepts"]) for c in chapters))
        total_topics = hierarchy.get("total_topics", len(chapters))

        if total_concepts > 0 and len(chapters) > 0:
            res = CurriculumResponse(
                course_id=course_id,
                chapters=chapters,
                total_topics=total_topics,
                total_concepts=total_concepts,
            )
            return ApiResponse(ok=True, data=res)
    except Exception as exc:
        logger.debug("Database curriculum lookup for %s failed, falling back to local files: %s", course_id, exc)

    # Fallback to local curriculum files in data/curriculum
    candidates = [
        PROJECT_ROOT / "data" / "curriculum" / "chemistry" / "ncert_class11_12.json",
        PROJECT_ROOT / "data" / "curriculum" / "math" / "grade9_cbse.json",
        PROJECT_ROOT / "data" / "curriculum" / "python" / "beginner.json",
        PROJECT_ROOT / "data" / "curriculum" / "science" / "grade9_ncert.json",
    ]

    selected_file = None
    for cand in candidates:
        if cand.exists():
            if course_id.lower() in cand.name.lower() or (cand.parent.name.lower() in course_id.lower()):
                selected_file = cand
                break
    if not selected_file and candidates[0].exists():
        selected_file = candidates[0]

    if not selected_file or not selected_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Curriculum not found for course '{course_id}'")

    try:
        with open(selected_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        concepts = data.get("concepts", [])

        chapters_map = {
            "Thermodynamics": [c for c in concepts if "thermo" in c.get("id", "")],
            "Chemical Bonding": [c for c in concepts if "bond" in c.get("id", "")],
            "Coordination Chemistry": [c for c in concepts if "coord" in c.get("id", "")],
            "Periodic Trends & Inorganic": [c for c in concepts if "inorg" in c.get("id", "") or "periodic" in c.get("id", "")],
        }
        # If none matched the 4 chemistry categories, group generically
        if not any(chapters_map.values()) and concepts:
            chunk_size = max(1, len(concepts) // 4)
            chapters = [
                {"chapter_name": f"Module {i+1}", "concepts": concepts[i * chunk_size : (i + 1) * chunk_size], "concept_count": len(concepts[i * chunk_size : (i + 1) * chunk_size])}
                for i in range(4)
            ]
        else:
            chapters = [
                {"chapter_name": k, "concepts": v, "concept_count": len(v)}
                for k, v in chapters_map.items()
            ]

        res = CurriculumResponse(
            course_id=course_id,
            chapters=chapters,
            total_topics=len(chapters),
            total_concepts=len(concepts),
        )
        return ApiResponse(ok=True, data=res)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ── 2. Full Hierarchy Query ───────────────────────────────────────────────

@router.get("/versions/{version_id}/hierarchy", response_model=ApiResponse[CurriculumHierarchyResponse])
async def get_version_hierarchy(version_id: str):
    """Retrieve complete Course -> Subject -> Module -> Topic -> Concept tree."""
    service = get_curriculum_service()
    ver = service.db.get_curriculum_version(version_id)
    if not ver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version '{version_id}' not found")

    hierarchy = service.get_curriculum_hierarchy(ver.curriculum_id)
    return ApiResponse(
        ok=True,
        data=CurriculumHierarchyResponse(
            curriculum_id=hierarchy.get("curriculum_id", ver.curriculum_id),
            version_id=ver.id,
            course_id=hierarchy.get("course_id", ""),
            course_title=hierarchy.get("course_title", ""),
            title=hierarchy.get("title", ""),
            version=ver.version_num,
            status=ver.status,
            subjects=hierarchy.get("subjects", []),
            modules=hierarchy.get("modules", []),
            total_modules=hierarchy.get("total_modules", len(hierarchy.get("modules", []))),
            total_topics=hierarchy.get("total_topics", 0),
            total_concepts=hierarchy.get("total_concepts", 0),
        ),
    )


# ── 3. Versioning & Draft Creation ────────────────────────────────────────

@router.get("/{curriculum_id}/versions", response_model=ApiResponse[List[Dict[str, Any]]])
async def list_curriculum_versions(curriculum_id: str):
    """List all versions and their lifecycle statuses for a curriculum."""
    service = get_curriculum_service()
    versions = service.db.get_curriculum_versions(curriculum_id)
    return ApiResponse(
        ok=True,
        data=[
            {
                "id": v.id,
                "curriculum_id": v.curriculum_id,
                "version_num": v.version_num,
                "change_log": v.change_log,
                "status": v.status,
                "published_at": v.published_at,
                "created_at": v.created_at,
            }
            for v in versions
        ],
    )


@router.post("/{curriculum_id}/versions", response_model=ApiResponse[Dict[str, Any]], status_code=201)
async def create_curriculum_version(
    curriculum_id: str,
    req: CurriculumVersionCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new version draft, optionally cloned from a base version."""
    admin = _enforce_authoring_auth(current_user)
    service = get_curriculum_service()
    try:
        new_ver = service.create_version_draft(
            admin=admin,
            curriculum_id=curriculum_id,
            new_version_num=req.version_num,
            change_log=req.change_log,
            base_version_id=req.base_version_id,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ApiResponse(
        ok=True,
        data={
            "id": new_ver.id,
            "curriculum_id": new_ver.curriculum_id,
            "version_num": new_ver.version_num,
            "status": new_ver.status,
            "change_log": new_ver.change_log,
            "created_at": new_ver.created_at,
        },
    )


# ── 4. DAG & Structural Validation ────────────────────────────────────────

@router.post("/versions/{version_id}/validate", response_model=ApiResponse[CurriculumValidationResponse])
async def validate_curriculum_version(version_id: str):
    """Run structural DAG validation (cycle detection, orphan prerequisites) on a version."""
    service = get_curriculum_service()
    report = service.validate_curriculum(version_id)
    return ApiResponse(
        ok=True,
        data=CurriculumValidationResponse(
            is_valid=report.is_valid,
            errors=report.errors,
            warnings=report.warnings,
            concept_count=report.concept_count,
            cycle_nodes=report.cycle_nodes,
            orphan_prerequisites=report.orphan_prerequisites,
            dag_depth=report.dag_depth,
        ),
    )


# ── 5. Publishing & Immutability ──────────────────────────────────────────

@router.post("/versions/{version_id}/publish", response_model=ApiResponse[CurriculumVersionPublishResponse])
async def publish_curriculum_version(
    version_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Validate and publish a curriculum version, making it active and strictly immutable."""
    admin = _enforce_authoring_auth(current_user)
    service = get_curriculum_service()
    try:
        ver = service.publish_curriculum_version(admin, version_id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ApiResponse(
        ok=True,
        data=CurriculumVersionPublishResponse(
            version_id=ver.id,
            version_num=ver.version_num,
            status=ver.status,
            published_at=ver.published_at or "",
        ),
    )


# ── 6. Declarative Package Import & Export ────────────────────────────────

@router.post("/import", response_model=ApiResponse[CurriculumImportResponse], status_code=201)
async def import_curriculum(
    req: CurriculumImportRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Import a declarative curriculum JSON package with validation and relational persistence."""
    admin = _enforce_authoring_auth(current_user)
    service = get_curriculum_service()
    try:
        result = service.import_curriculum_package(
            admin=admin,
            course_id=req.course_id,
            package=req.package,
            publish=req.publish,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ApiResponse(
        ok=True,
        data=CurriculumImportResponse(
            curriculum_id=result["curriculum_id"],
            version_id=result["version_id"],
            version=result["version"],
            title=result["title"],
            status=result["status"],
            concept_count=result["concept_count"],
        ),
    )


@router.get("/versions/{version_id}/export", response_model=ApiResponse[Dict[str, Any]])
async def export_curriculum(version_id: str):
    """Export a curriculum version as a declarative canonical package with round-trip fidelity."""
    service = get_curriculum_service()
    try:
        pkg = service.export_curriculum_package(version_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return ApiResponse(ok=True, data=pkg)
