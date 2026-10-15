"""Gayatri School OS — Transport API Router (Phase 06)."""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from central_platform.auth.dependencies import get_current_user, get_db
from central_platform.db import PlatformDatabase
from central_platform.transport.service import TransportService
from central_platform.api.routes.identity import _get_org_id

logger = logging.getLogger("gayatri.api.routes.transport")

router = APIRouter(prefix="/transport", tags=["Transport & Fleet"])


def get_transport_service(db: PlatformDatabase = Depends(get_db)) -> TransportService:
    return TransportService(db)


class RouteCreateRequest(BaseModel):
    name: str
    code: str
    start_point: str
    end_point: str


@router.post("/routes", status_code=status.HTTP_201_CREATED)
def create_route(
    req: RouteCreateRequest,
    current_user: Any = Depends(get_current_user),
    service: TransportService = Depends(get_transport_service),
):
    org_id = _get_org_id(current_user)
    route = service.create_route(
        organization_id=org_id,
        name=req.name,
        code=req.code,
        start_point=req.start_point,
        end_point=req.end_point,
    )
    return route.__dict__
