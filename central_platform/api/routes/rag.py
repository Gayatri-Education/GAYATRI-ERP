"""Gayatri AI Platform — Plug-and-Play RAG Knowledge API Endpoints (Phase 16).

Provides end-to-end REST endpoints for knowledge source attachment,
multi-format ingestion, validation, publishing, and grounded scoped retrieval.
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.api.schemas import (
    ApiResponse,
    RAGChunkResponse,
    RAGIngestRequest,
    RAGIngestResponse,
    RAGPublishResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGResultItem,
    RAGSourceCreateRequest,
    RAGSourceResponse,
    RAGValidateResponse,
)
from central_platform.auth.dependencies import get_current_user, get_db
from central_platform.models.schema import RAGSource, User, UserRole
from central_platform.rag.service import RAGService
from central_platform.rbac.engine import normalize_role

router = APIRouter(prefix="/rag", tags=["RAG"])

_TEACHER_PLUS = {UserRole.TEACHER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN}
_ADMIN_PLUS = {UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN}


def _get_role(user: User) -> UserRole:
    """Normalize current_user.role to a UserRole enum instance."""
    return normalize_role(user.role)


def _require_teacher_plus(current_user: User) -> UserRole:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    role = _get_role(current_user)
    if role not in _TEACHER_PLUS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers and administrators can perform this action.")
    return role


def _require_admin_plus(current_user: User) -> UserRole:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    role = _get_role(current_user)
    if role not in _ADMIN_PLUS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can perform this action.")
    return role


def get_rag_service() -> RAGService:
    db = get_db()
    return RAGService(db=db)


def _build_source_response(s: RAGSource) -> RAGSourceResponse:
    return RAGSourceResponse(
        id=s.id,
        organization_id=s.organization_id,
        course_id=s.course_id,
        subject=s.subject,
        title=s.title,
        source_type=s.source_type,
        authority=s.authority,
        version=s.version,
        status=s.status,
        checksum=s.checksum,
        chunk_count=s.chunk_count,
        content_type=s.content_type,
        uploaded_by=s.uploaded_by,
        published_by=s.published_by,
        published_at=s.published_at,
        error_message=s.error_message,
        course_version_id=s.course_version_id,
        visibility_scope=s.visibility_scope or "course",
        class_id=s.class_id,
        target_student_ids=s.target_student_ids or [],
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.post("/sources", response_model=ApiResponse[RAGSourceResponse], status_code=status.HTTP_201_CREATED)
async def create_rag_source(
    req: RAGSourceCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """Register a new plug-and-play knowledge source for a course. Requires TEACHER or above."""
    role = _require_teacher_plus(current_user)
    svc = get_rag_service()
    try:
        org_id = current_user.organization_id or "org-default"
        if req.course_id:
            c = svc.db.get_course(req.course_id)
            if not c:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course '{req.course_id}' not found.")
            # Cross-org protection: non-superadmin can only add to their org's courses
            if role != UserRole.SUPER_ADMIN and c.organization_id != org_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot add knowledge sources to a course from another organization.")
            org_id = c.organization_id
        source = svc.register_source(
            organization_id=org_id,
            course_id=req.course_id,
            subject=req.subject,
            title=req.title,
            source_type=req.source_type,
            authority=req.authority,
            version=req.version,
            content_type=req.content_type,
            course_version_id=req.course_version_id,
            visibility_scope=req.visibility_scope,
            class_id=req.class_id,
            target_student_ids=req.target_student_ids,
            metadata=req.metadata,
        )
        return ApiResponse(
            ok=True,
            data=_build_source_response(source),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sources", response_model=ApiResponse[List[RAGSourceResponse]])
async def list_rag_sources(
    course_id: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    authority: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    course_version_id: Optional[str] = Query(None),
    visibility_scope: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """List knowledge sources with optional course, subject, status, or authority filters."""
    svc = get_rag_service()
    role = _get_role(current_user)
    if course_id and role != UserRole.SUPER_ADMIN:
        course = svc.db.get_course(course_id)
        if course:
            c_vis = course.visibility.value if hasattr(course.visibility, "value") else str(course.visibility).upper()
            if c_vis != "PUBLIC" and course.organization_id != current_user.organization_id:
                offering = svc.db.get_course_offering_by_org_and_course(current_user.organization_id, course_id)
                if not offering or (hasattr(offering, "status") and offering.status != "active"):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to course knowledge sources.")

    sources = svc.db.list_rag_sources(
        course_id=course_id,
        subject=subject,
        status=status,
        authority=authority,
        content_type=content_type,
        course_version_id=course_version_id,
        visibility_scope=visibility_scope,
        class_id=class_id,
        limit=limit,
        offset=offset,
    )
    # Filter sources by organization boundary unless SUPER_ADMIN or course is public
    filtered_sources = []
    for s in sources:
        if role == UserRole.SUPER_ADMIN or s.organization_id == current_user.organization_id:
            filtered_sources.append(s)
        elif s.course_id:
            c = svc.db.get_course(s.course_id)
            if c:
                c_vis = c.visibility.value if hasattr(c.visibility, "value") else str(c.visibility).upper()
                if c_vis == "PUBLIC":
                    filtered_sources.append(s)
    return ApiResponse(
        ok=True,
        data=[_build_source_response(s) for s in filtered_sources],
    )


@router.get("/sources/{source_id}", response_model=ApiResponse[RAGSourceResponse])
async def get_rag_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific knowledge source."""
    svc = get_rag_service()
    source = svc.db.get_rag_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Knowledge source '{source_id}' not found.")
    role = _get_role(current_user)
    if role != UserRole.SUPER_ADMIN and source.organization_id != current_user.organization_id:
        if source.course_id:
            c = svc.db.get_course(source.course_id)
            if not c or (c.visibility.value if hasattr(c.visibility, "value") else str(c.visibility).upper()) != "PUBLIC":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to knowledge source.")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to knowledge source.")
    return ApiResponse(
        ok=True,
        data=_build_source_response(source),
    )


@router.post("/sources/{source_id}/ingest", response_model=ApiResponse[RAGIngestResponse])
async def ingest_source_content(
    source_id: str,
    req: RAGIngestRequest,
    current_user: User = Depends(get_current_user),
):
    """Parse, clean, chunk, and index content into the specified knowledge source. Requires TEACHER or above."""
    role = _require_teacher_plus(current_user)
    svc = get_rag_service()
    source = svc.db.get_rag_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Knowledge source '{source_id}' not found.")
    if role != UserRole.SUPER_ADMIN and source.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot ingest into a knowledge source from another organization.")
    try:
        res = svc.ingest_document(
            source_id=source_id,
            content=req.content,
            file_name=req.file_name,
            override_source_type=req.override_source_type,
        )
        return ApiResponse(
            ok=True,
            data=RAGIngestResponse(
                source_id=res["source_id"],
                status=res["status"],
                sections_parsed=res["sections_parsed"],
                chunks_created=res["chunks_created"],
                checksum=res["checksum"],
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@router.post("/sources/{source_id}/validate", response_model=ApiResponse[RAGValidateResponse])
async def validate_rag_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
):
    """Validate ingested chunks, verify lengths, and check prompt injection safety. Requires TEACHER or above."""
    role = _require_teacher_plus(current_user)
    svc = get_rag_service()
    source = svc.db.get_rag_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Knowledge source '{source_id}' not found.")
    if role != UserRole.SUPER_ADMIN and source.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot validate a knowledge source from another organization.")
    try:
        res = svc.validate_source(source_id)
        return ApiResponse(
            ok=True,
            data=RAGValidateResponse(
                valid=res["valid"],
                source_id=res["source_id"],
                status=res["status"],
                chunk_count=res["chunk_count"],
                average_chunk_chars=res["average_chunk_chars"],
                concepts_covered=res["concepts_covered"],
                errors=res["errors"],
                warnings=res["warnings"],
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/sources/{source_id}/publish", response_model=ApiResponse[RAGPublishResponse])
async def publish_rag_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
):
    """Publish a validated knowledge source, making its chunks available for live retrieval. Requires ORG_ADMIN or SUPER_ADMIN."""
    role = _require_admin_plus(current_user)
    svc = get_rag_service()
    source = svc.db.get_rag_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Knowledge source '{source_id}' not found.")
    if role != UserRole.SUPER_ADMIN and source.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot publish a knowledge source from another organization.")
    try:
        source = svc.publish_source(source_id)
        return ApiResponse(
            ok=True,
            data=RAGPublishResponse(
                source_id=source.id,
                status=source.status,
                updated_at=source.updated_at,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sources/{source_id}/chunks", response_model=ApiResponse[List[RAGChunkResponse]])
async def get_source_chunks(
    source_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """List chunks belonging to a knowledge source."""
    svc = get_rag_service()
    source = svc.db.get_rag_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Knowledge source '{source_id}' not found.")
    role = _get_role(current_user)
    if role != UserRole.SUPER_ADMIN and source.organization_id != current_user.organization_id:
        if source.course_id:
            c = svc.db.get_course(source.course_id)
            if not c or (c.visibility.value if hasattr(c.visibility, "value") else str(c.visibility).upper()) != "PUBLIC":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to knowledge source chunks.")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to knowledge source chunks.")

    chunks = svc.db.get_rag_chunks(source_id, limit=limit, offset=offset)
    return ApiResponse(
        ok=True,
        data=[
            RAGChunkResponse(
                id=c.id,
                source_id=c.source_id,
                course_id=c.course_id,
                subject=c.subject,
                chapter=c.chapter,
                topic=c.topic,
                concept=c.concept,
                difficulty=c.difficulty,
                page=c.page,
                section=c.section,
                content_type=c.content_type,
                text=c.text,
                clean_text=c.clean_text,
                provenance_type=c.provenance_type,
                course_version_id=c.course_version_id,
                visibility_scope=c.visibility_scope or "course",
                class_id=c.class_id,
                created_at=c.created_at,
            )
            for c in chunks
        ],
    )


@router.delete("/sources/{source_id}", response_model=ApiResponse[dict])
async def delete_rag_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a knowledge source and all its associated chunks. Requires ORG_ADMIN or SUPER_ADMIN."""
    role = _require_admin_plus(current_user)
    svc = get_rag_service()
    source = svc.db.get_rag_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Knowledge source '{source_id}' not found.")
    if role != UserRole.SUPER_ADMIN and source.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete a knowledge source from another organization.")
    deleted = svc.db.delete_rag_source(source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Knowledge source '{source_id}' not found.")
    return ApiResponse(ok=True, data={"deleted": True, "source_id": source_id})


@router.post("/query", response_model=ApiResponse[RAGQueryResponse])
async def query_rag(
    req: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
):
    """Retrieve grounded knowledge evidence cards scoped to course, subject, and concepts."""
    svc = get_rag_service()
    role = _get_role(current_user)

    # 1. Identity binding & anti-spoofing check
    effective_student_id = req.student_id
    if role == UserRole.STUDENT:
        if req.student_id and req.student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Student cannot query knowledge on behalf of another student.",
            )
        effective_student_id = current_user.id
    elif not effective_student_id:
        effective_student_id = current_user.id

    # 2. Multi-tenant / course enrollment verification
    if req.course_id:
        course = svc.db.get_course(req.course_id)
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course '{req.course_id}' not found.")

        c_vis = course.visibility.value if hasattr(course.visibility, "value") else str(course.visibility).upper()
        if role == UserRole.STUDENT:
            if c_vis != "PUBLIC":
                enrollments = svc.db.get_enrollments_for_student(effective_student_id)
                has_enrollment = any(e.course_id == req.course_id and getattr(e, "is_active", True) for e in enrollments)
                if not has_enrollment:
                    offering = svc.db.get_course_offering_by_org_and_course(current_user.organization_id, req.course_id)
                    has_offering = offering and getattr(offering, "is_active", True)
                    if not has_offering:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied: Student is not enrolled in private course '{req.course_id}'.",
                        )
        elif role != UserRole.SUPER_ADMIN:
            if course.organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot query course knowledge from another organization.",
                )

    try:
        res = svc.query(
            query_text=req.query,
            course_id=req.course_id,
            subject=req.subject,
            concept=req.concept_id,
            course_version_id=req.course_version_id,
            class_id=req.class_id,
            student_id=effective_student_id,
            top_k=req.top_k,
            confidence_threshold=req.confidence_threshold,
        )
        return ApiResponse(
            ok=True,
            data=RAGQueryResponse(
                status=res["status"],
                query=res["query"],
                results=[
                    RAGResultItem(
                        chunk_id=r["chunk_id"],
                        source_id=r.get("source_id"),
                        chapter=r["chapter"],
                        topic=r["topic"],
                        concept=r.get("concept"),
                        page=r["page"],
                        text=r["text"],
                        score=r["score"],
                        citation=r["citation"],
                        course_version_id=r.get("course_version_id"),
                        visibility_scope=r.get("visibility_scope"),
                        class_id=r.get("class_id"),
                        provenance_type=r.get("provenance_type"),
                        content_type=r.get("content_type"),
                    )
                    for r in res["results"]
                ],
                count=res["count"],
                data_context=res.get("data_context"),
                reason=res.get("reason"),
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG query execution failed: {exc}")
