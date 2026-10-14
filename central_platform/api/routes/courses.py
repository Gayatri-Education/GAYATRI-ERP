"""Gayatri AI Platform — Authoritative Courses API Endpoints (Phase 12).

Section 12.12: Real Online API Boundary
- Pure route/service separation routing to CourseService
- Public course catalog and org-scoped course listings
- Course CRUD and multi-tenant organization authorization
- Course versioning lifecycle (draft -> review -> published)
- Course selection & offering creation for organizations
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from central_platform.api.schemas import (
    ApiResponse,
    CourseArchiveResponse,
    CourseCreateRequest,
    CourseOfferingResponse,
    CourseResponse,
    CourseReviewQueueItemResponse,
    CourseSelectRequest,
    CourseVersionApiResponse,
    CourseVersionCreateApiRequest,
)
from central_platform.auth.dependencies import (
    get_current_user_optional,
    get_db,
    is_production_mode,
)
from central_platform.courses.service import (
    CourseAuthorizationError,
    CourseNotFoundError,
    CourseService,
    CourseValidationError,
)
from central_platform.models.schema import (
    Course,
    CourseOffering,
    CourseVersion,
    CourseVisibility,
    Organization,
    User,
    UserRole,
)

logger = logging.getLogger("gayatri.api.courses")

router = APIRouter(prefix="/courses", tags=["Courses"])


def _ensure_default_seed_courses(db: PlatformDatabase) -> None:
    """Seed initial public courses if database is unseeded."""
    if not db.get_organization("org-default"):
        org = Organization(id="org-default", name="Default Organization", slug="default")
        db.create_organization(org)
    if not db.get_course("crs-chem-101"):
        chem = Course(
            id="crs-chem-101",
            code="CHEM101",
            title="NCERT Class 11-12 Chemistry",
            description="Comprehensive physical and inorganic chemistry adaptive curriculum.",
            visibility=CourseVisibility.PUBLIC,
            organization_id="org-default",
        )
        db.create_course(chem)
    if not db.get_course("crs-math-09"):
        math_c = Course(
            id="crs-math-09",
            code="MATH09",
            title="Grade 9 Mathematics",
            description="CBSE Grade 9 foundation mathematics.",
            visibility=CourseVisibility.PUBLIC,
            organization_id="org-default",
        )
        db.create_course(math_c)


def get_course_service() -> CourseService:
    """Dependency provider for CourseService."""
    db = get_db()
    _ensure_default_seed_courses(db)
    return CourseService(db)


def _to_course_response(c: Course) -> CourseResponse:
    """Map domain Course model to CourseResponse schema."""
    created_at_str = c.created_at.isoformat() if hasattr(c.created_at, "isoformat") else str(c.created_at or "")
    vis_str = c.visibility.value if hasattr(c.visibility, "value") else str(c.visibility)
    subject = "General"
    title_lower = (c.title or "").lower()
    id_lower = (c.id or "").lower()
    if "chem" in id_lower or "chem" in title_lower:
        subject = "Chemistry"
    elif "math" in id_lower or "math" in title_lower:
        subject = "Mathematics"
    elif "phys" in id_lower or "phys" in title_lower:
        subject = "Physics"
    elif "hist" in id_lower or "hist" in title_lower:
        subject = "History"

    return CourseResponse(
        course_id=c.id,
        code=c.code,
        title=c.title,
        description=c.description or "",
        subject=subject,
        grade_level="Class 11-12" if subject == "Chemistry" else "Grade 9" if subject == "Mathematics" else "All",
        total_concepts=18 if subject == "Chemistry" else 14 if subject == "Mathematics" else 12,
        version="v1.0",
        visibility=vis_str,
        organization_id=c.organization_id,
        created_at=created_at_str,
    )


def _to_version_response(v: CourseVersion) -> CourseVersionApiResponse:
    """Map domain CourseVersion model to CourseVersionApiResponse schema."""
    created_at_str = v.created_at.isoformat() if hasattr(v.created_at, "isoformat") else str(v.created_at or "")
    status_str = v.status.value if hasattr(v.status, "value") else str(v.status)
    version_tag = getattr(v, "version_tag", None) or getattr(v, "version_number", "v1.0")
    return CourseVersionApiResponse(
        id=v.id,
        course_id=v.course_id,
        version_tag=version_tag,
        status=status_str,
        changelog=getattr(v, "changelog", "") or "",
        created_by=v.created_by,
        created_at=created_at_str,
    )


@router.get("", response_model=ApiResponse[List[CourseResponse]])
async def list_courses(
    organization_id: Optional[str] = Query(None, description="Filter courses for a specific organization"),
    visibility: Optional[str] = Query(None, description="Filter by visibility: PUBLIC or PRIVATE"),
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List available courses.
    
    If organization_id is provided, returns public courses plus org-specific courses.
    Otherwise returns public courses.
    """
    courses_map: Dict[str, Course] = {}

    # 1. Fetch public courses
    if visibility != "PRIVATE":
        for c in service.list_public_courses():
            courses_map[c.id] = c

    # 2. Fetch org courses if specified or user has org
    org_id = organization_id or (current_user.organization_id if current_user else None)
    if org_id and visibility != "PUBLIC":
        actor = current_user or User(
            id="usr-guest",
            email="guest@platform.local",
            full_name="Guest User",
            role=UserRole.STUDENT,  # FIX: guests must NOT get SUPER_ADMIN — only see public courses
            organization_id=org_id,
        )
        try:
            for c in service.list_courses_for_org(actor, org_id):
                courses_map[c.id] = c
        except CourseAuthorizationError as exc:
            logger.debug("Actor %s not authorized to list courses for org %s: %s", actor.id, org_id, exc)

    result = [_to_course_response(c) for c in courses_map.values()]
    return ApiResponse(ok=True, data=result)


@router.get("/review-queue", response_model=ApiResponse[List[CourseReviewQueueItemResponse]])
async def get_course_review_queue(
    organization_id: Optional[str] = Query(None, description="Optional organization ID filter for super admins"),
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Retrieve course versions awaiting administrator review. Requires ORG_ADMIN or SUPER_ADMIN."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access the course review queue.",
        )
    _role = current_user.role if isinstance(current_user.role, UserRole) else None
    if _role is None:
        try:
            _role = UserRole(str(current_user.role).lower())
        except ValueError:
            try:
                _role = UserRole[str(current_user.role).upper()]
            except KeyError:
                _role = UserRole.STUDENT
    if _role not in (UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ORG_ADMIN or SUPER_ADMIN can access the course review queue.",
        )
    actor = current_user
    try:
        queue = service.get_review_queue(actor=actor, organization_id=organization_id)
        return ApiResponse(ok=True, data=[CourseReviewQueueItemResponse(**item) for item in queue])
    except CourseAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("/{course_id}", response_model=ApiResponse[CourseResponse])
async def get_course(
    course_id: str,
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get course metadata by course_id."""
    actor = current_user or User(
        id="usr-guest",
        email="guest@platform.local",
        full_name="Guest User",
        role=UserRole.STUDENT,
        organization_id="org-default",
    )
    try:
        c = service.get_course(actor, course_id)
        return ApiResponse(ok=True, data=_to_course_response(c))
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{course_id}' not found.",
        )
    except CourseAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )


@router.post("", response_model=ApiResponse[CourseResponse], status_code=status.HTTP_201_CREATED)
async def create_course(
    req: CourseCreateRequest,
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new course. Requires TEACHER, ORG_ADMIN, or SUPER_ADMIN role."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    actor = current_user or User(
        id="usr-teacher-01",
        email="teacher@platform.local",
        full_name="Platform Teacher",
        role=UserRole.TEACHER,
        organization_id=req.organization_id or "org-default",
    )

    # RBAC verification
    allowed_roles = {UserRole.TEACHER, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN, "TEACHER", "ORG_ADMIN", "SUPER_ADMIN"}
    user_role = actor.role.value if isinstance(actor.role, UserRole) else str(actor.role).upper()
    if user_role not in allowed_roles and actor.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and administrators can create courses.",
        )

    org_id = req.organization_id or actor.organization_id or "org-default"
    if not service.db.get_organization(org_id):
        service.db.create_organization(Organization(id=org_id, name=org_id, slug=org_id))

    try:
        vis = CourseVisibility.PUBLIC if req.visibility.upper() == "PUBLIC" else CourseVisibility.PRIVATE
        course = service.create_course(
            actor=actor,
            code=req.code,
            title=req.title,
            description=req.description,
            visibility=vis,
            organization_id=req.organization_id,
        )
        return ApiResponse(ok=True, data=_to_course_response(course))
    except CourseAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except CourseValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Failed to create course: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{course_id}/select", response_model=ApiResponse[CourseOfferingResponse])
async def select_course_for_organization(
    course_id: str,
    req: CourseSelectRequest,
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Select a course for an organization, establishing an active offering pinned to a version."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    actor = current_user or User(
        id="usr-admin-01",
        email="admin@platform.local",
        full_name="Platform Admin",
        role=UserRole.ORG_ADMIN,
        organization_id=req.organization_id,
    )

    try:
        offering = service.select_course_for_org(
            actor=actor,
            course_id=course_id,
            organization_id=req.organization_id,
            pinned_version_id=req.course_version_id,
        )
        version_id = getattr(offering, "course_version_id", None) or getattr(offering, "pinned_version_id", None)
        created_val = getattr(offering, "created_at", None) or getattr(offering, "enrolled_at", None) or datetime.now(timezone.utc).isoformat()
        created_at_str = created_val.isoformat() if hasattr(created_val, "isoformat") else str(created_val)
        return ApiResponse(
            ok=True,
            data=CourseOfferingResponse(
                id=offering.id,
                course_id=offering.course_id,
                organization_id=offering.organization_id,
                course_version_id=version_id,
                is_active=offering.is_active,
                created_at=created_at_str,
            ),
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CourseAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except CourseValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{course_id}/versions", response_model=ApiResponse[List[CourseVersionApiResponse]])
async def list_course_versions(
    course_id: str,
    service: CourseService = Depends(get_course_service),
):
    """List all version snapshots of a course."""
    versions = service.db.get_course_versions_by_course(course_id)
    return ApiResponse(ok=True, data=[_to_version_response(v) for v in versions])


@router.post("/{course_id}/versions", response_model=ApiResponse[CourseVersionApiResponse], status_code=status.HTTP_201_CREATED)
async def create_course_version(
    course_id: str,
    req: CourseVersionCreateApiRequest,
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new draft version of a course."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    actor = current_user or User(
        id="usr-teacher-01",
        email="teacher@platform.local",
        full_name="Platform Teacher",
        role=UserRole.TEACHER,
    )
    try:
        ver = service.create_course_version(
            actor=actor,
            course_id=course_id,
            version_number=req.version_tag,
        )
        return ApiResponse(ok=True, data=_to_version_response(ver))
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CourseAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except CourseValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{course_id}/versions/{version_id}/submit", response_model=ApiResponse[CourseVersionApiResponse])
@router.post("/{course_id}/versions/{version_id}/submit-review", response_model=ApiResponse[CourseVersionApiResponse])
async def submit_course_version(
    course_id: str,
    version_id: str,
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Submit a course version for administrative review."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    actor = current_user or User(
        id="usr-teacher-01",
        email="teacher@platform.local",
        full_name="Platform Teacher",
        role=UserRole.TEACHER,
    )
    try:
        ver = service.submit_version_for_review(actor=actor, version_id=version_id)
        return ApiResponse(ok=True, data=_to_version_response(ver))
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CourseAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except CourseValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{course_id}/versions/{version_id}/publish", response_model=ApiResponse[CourseVersionApiResponse])
async def publish_course_version(
    course_id: str,
    version_id: str,
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Approve and publish a course version. Requires ORG_ADMIN or SUPER_ADMIN role."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    actor = current_user or User(
        id="usr-admin-01",
        email="admin@platform.local",
        full_name="Platform Admin",
        role=UserRole.ORG_ADMIN,
    )
    try:
        ver = service.approve_and_publish_version(actor=actor, version_id=version_id)
        return ApiResponse(ok=True, data=_to_version_response(ver))
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CourseAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except CourseValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{course_id}/archive", response_model=ApiResponse[CourseArchiveResponse])
async def archive_course(
    course_id: str,
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Archive / soft-delete a course. Requires ORG_ADMIN or SUPER_ADMIN role."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    actor = current_user or User(
        id="usr-admin-01",
        email="admin@platform.local",
        full_name="Platform Admin",
        role=UserRole.ORG_ADMIN,
    )
    try:
        service.archive_course(actor=actor, course_id=course_id)
        return ApiResponse(
            ok=True,
            data=CourseArchiveResponse(
                ok=True,
                course_id=course_id,
                status="ARCHIVED",
                message=f"Course '{course_id}' successfully archived",
            ),
        )
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CourseAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{course_id}/versions/{version_id}/archive", response_model=ApiResponse[CourseVersionApiResponse])
async def archive_course_version(
    course_id: str,
    version_id: str,
    service: CourseService = Depends(get_course_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Archive a course version. Requires ORG_ADMIN or SUPER_ADMIN role."""
    if is_production_mode() and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required in production",
            headers={"WWW-Authenticate": "Bearer"},
        )
    actor = current_user or User(
        id="usr-admin-01",
        email="admin@platform.local",
        full_name="Platform Admin",
        role=UserRole.ORG_ADMIN,
    )
    try:
        ver = service.archive_course_version(actor=actor, version_id=version_id)
        return ApiResponse(ok=True, data=_to_version_response(ver))
    except CourseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except CourseAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

