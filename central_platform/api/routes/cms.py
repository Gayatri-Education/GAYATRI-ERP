"""Gayatri School OS — Public CMS API Router (Phase 06)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user
from central_platform.db import PlatformDatabase
from central_platform.campus.service import CampusService
from central_platform.api.routes.identity import _get_org_id

logger = logging.getLogger("gayatri.api.routes.cms")

router = APIRouter(prefix="/cms", tags=["Public CMS"])


def get_db() -> PlatformDatabase:
    return PlatformDatabase()


def get_campus_service(db: PlatformDatabase = Depends(get_db)) -> CampusService:
    return CampusService(db)


class PageCreateRequest(BaseModel):
    title: str
    slug: str
    content_html: str


@router.post("/pages", status_code=status.HTTP_201_CREATED)
def create_page(
    req: PageCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: CampusService = Depends(get_campus_service),
):
    org_id = _get_org_id(current_user)
    try:
        page = service.create_page(
            organization_id=org_id,
            title=req.title,
            slug=req.slug,
            content_html=req.content_html,
        )
        return page.__dict__
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/public/pages")
def list_public_pages(
    organization_id: str = Query(...),
    service: CampusService = Depends(get_campus_service),
):
    # Unauthenticated public endpoint
    return [p.__dict__ for p in service.list_published_pages(organization_id)]
