"""Gayatri AI Platform — FastAPI Application Factory & Central Engine (Phase 02).

Implements Section 11 of the Master Plan:
1. Asynchronous FastAPI production platform layer.
2. 16 versioned route groups under /api/v1/*.
3. Request ID and Structured Logging middleware.
4. Healthz, Readyz, Livez probes.
5. Strict backwards compatibility with existing /api/* endpoints and HTML Teacher Command Center at /.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from typing import Any, Dict, Optional

# Auto-detect local database when running the standalone platform server (outside pytest)
if "pytest" not in sys.modules and "PYTEST_CURRENT_TEST" not in os.environ and not os.environ.get("GAYATRI_DB_PATH"):
    for candidate in ["gayatri_local.db", os.path.join(os.path.dirname(__file__), "..", "..", "gayatri_local.db")]:
        if os.path.exists(candidate):
            os.environ["GAYATRI_DB_PATH"] = os.path.abspath(candidate)
            break

logger = logging.getLogger("gayatri.api.app")

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from central_platform.api.middleware import (
    RequestIDMiddleware,
    StructuredLoggingMiddleware,
    register_exception_handlers,
)
from central_platform.api.schemas import (
    HealthStatusResponse,
    StudentSnapshotRequest,
    TeacherInstructionCreateRequest,
)

from central_platform.api.routes.academic import router as academic_router
from central_platform.api.routes.admin import router as admin_router
from central_platform.api.routes.admissions import router as admissions_router
from central_platform.api.routes.agents import router as agents_router
from central_platform.api.routes.ai import router as ai_router
from central_platform.api.routes.analytics import router as analytics_router
from central_platform.api.routes.assessments import router as assessments_router
from central_platform.api.routes.attendance import router as attendance_router
from central_platform.api.routes.auth import router as auth_router
from central_platform.api.routes.classes import router as classes_router
from central_platform.api.routes.courses import router as courses_router
from central_platform.api.routes.curricula import router as curricula_router
from central_platform.api.routes.communications import router as communications_router
from central_platform.api.routes.enrollments import router as enrollments_router
from central_platform.api.routes.examinations import router as examinations_router
from central_platform.api.routes.finance import router as finance_router
from central_platform.api.routes.grading import router as grading_router
from central_platform.api.routes.identity import router as identity_router
from central_platform.api.routes.instructions import router as instructions_router
from central_platform.api.routes.learning import router as learning_router
from central_platform.api.routes.notifications import router as notifications_router
from central_platform.api.routes.organizations import router as organizations_router
from central_platform.api.routes.rag import router as rag_router
from central_platform.api.routes.reports import router as reports_router
from central_platform.api.routes.sessions import router as sessions_router
from central_platform.api.routes.sis import router as sis_router
from central_platform.api.routes.students import router as students_router
from central_platform.api.routes.sync import router as sync_router
from central_platform.api.routes.teachers import router as teachers_router
from central_platform.api.routes.timetable import router as timetable_router
from central_platform.api.routes.tools import router as tools_router
from central_platform.api.routes.transport import router as transport_router
from central_platform.api.routes.cms import router as cms_router
from central_platform.api.routes.edge_sync import router as edge_sync_router
from central_platform.api.routes.institutional_analytics import router as institutional_analytics_router
from central_platform.api.routes.ops_gate import router as ops_gate_router
from central_platform.api.routes.tutor import router as tutor_router
from central_platform.api.routes.users import router as users_router
from central_platform.health.service import PlatformHealthService
from central_platform.api.schemas import PlatformHealthResponse

# Central Platform Domain Services
from central_platform.sync.manager import SyncEvent, SyncManager
from central_platform.teacher.copilot import TeacherCopilot
from central_platform.teacher.instruction import (
    TeacherInstruction,
    TeacherInstructionEngine,
)
from central_platform.teacher.intervention import (
    TeacherAlert,
    TeacherInterventionEngine,
)
from central_platform.teacher.portal import TeacherPortalService, get_shared_portal_service

# Central Platform Domain Service Instances (Phase 10: decoupled from root server.py)
_portal_service = get_shared_portal_service()
_instruction_engine = TeacherInstructionEngine()
_intervention_engine = TeacherInterventionEngine()
_copilot = TeacherCopilot()
_sync_manager = SyncManager()


def create_app() -> FastAPI:
    """Create and configure the production FastAPI application."""
    from central_platform.config import is_production_mode, validate_production_config

    is_prod = is_production_mode()
    if is_prod:
        validate_production_config()

    # Docs exposure policy: in production, Swagger/OpenAPI docs are disabled unless explicitly enabled
    enable_docs = not is_prod or os.environ.get("GAYATRI_ENABLE_DOCS", "false").lower() in ("true", "1", "yes")

    app = FastAPI(
        title="Gayatri AI — Production Platform API",
        version="2.0.0",
        description="Authoritative, three-sided adaptive learning platform API (Student, Teacher, Admin).",
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
    )

    # 1. Register CORS Middleware
    from central_platform.config import get_authoritative_settings
    settings = get_authoritative_settings()
    allowed_origins = settings.allowed_origins

    if is_prod:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept", "Origin"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins if allowed_origins else ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 2. Register Custom Tracing & Logging Middleware
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # 3. Register Structured Exception Handlers
    register_exception_handlers(app)

    # 4. Mount Versioned Route Groups under /api/v1
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(identity_router, prefix="/api/v1")
    app.include_router(academic_router, prefix="/api/v1")
    app.include_router(admissions_router, prefix="/api/v1")
    app.include_router(sis_router, prefix="/api/v1")
    app.include_router(attendance_router, prefix="/api/v1")
    app.include_router(timetable_router, prefix="/api/v1")
    app.include_router(communications_router, prefix="/api/v1")
    app.include_router(examinations_router, prefix="/api/v1")
    app.include_router(grading_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(finance_router, prefix="/api/v1")
    app.include_router(students_router, prefix="/api/v1")
    app.include_router(teachers_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(courses_router, prefix="/api/v1")
    app.include_router(curricula_router, prefix="/api/v1")
    app.include_router(enrollments_router, prefix="/api/v1")
    app.include_router(classes_router, prefix="/api/v1")
    app.include_router(organizations_router, prefix="/api/v1")
    app.include_router(instructions_router, prefix="/api/v1")
    app.include_router(sessions_router, prefix="/api/v1")
    app.include_router(learning_router, prefix="/api/v1")
    app.include_router(assessments_router, prefix="/api/v1")
    app.include_router(rag_router, prefix="/api/v1")
    app.include_router(ai_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(sync_router, prefix="/api/v1")
    app.include_router(tools_router, prefix="/api/v1")
    app.include_router(tutor_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(transport_router, prefix="/api/v1")
    app.include_router(cms_router, prefix="/api/v1")
    app.include_router(edge_sync_router, prefix="/api/v1")
    app.include_router(institutional_analytics_router, prefix="/api/v1")
    app.include_router(ops_gate_router, prefix="/api/v1")

    # 5. Live Operational Probes & Health Subsystem
    health_svc = PlatformHealthService()
    app.state.health_service = health_svc

    @app.get("/healthz", tags=["Probes"])
    async def healthz():
        data = health_svc.check_health()
        status_code = 200 if data["status"] != "UNHEALTHY" else 503
        return JSONResponse(status_code=status_code, content=data)

    @app.get("/readyz", tags=["Probes"])
    async def readyz():
        is_ready, data = health_svc.check_ready()
        status_code = 200 if is_ready else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "ready": is_ready,
                "status": data["status"],
                "subsystems": data["subsystems"],
            },
        )

    @app.get("/livez", tags=["Probes"])
    async def livez():
        return health_svc.check_live()

    @app.get("/api/v1/health", response_model=PlatformHealthResponse, tags=["Probes"])
    async def api_v1_health():
        data = health_svc.check_health()
        status_code = 200 if data["status"] != "UNHEALTHY" else 503
        return JSONResponse(status_code=status_code, content=data)

    # 6. Backwards-Compatibility Endpoints (Preserving 100% contracts for existing tests & client apps)
    @app.get("/api/health", tags=["Legacy Compatibility"])
    async def legacy_api_health():
        h = health_svc.check_health()
        students_count = 5
        try:
            students_count = _portal_service.get_dashboard_overview("crs-chem-101").total_students
        except Exception as exc:
            logger.debug("Failed resolving total_students for legacy health overview: %s", exc)
        return {
            "status": "HEALTHY" if h["status"] != "UNHEALTHY" else "UNHEALTHY",
            "service": "TeacherPortalServer",
            "students_monitored": students_count,
        }

    @app.get("/api/teacher/dashboard", tags=["Legacy Compatibility"])
    async def legacy_teacher_dashboard(course_id: str = "crs-chem-101"):
        overview = _portal_service.get_dashboard_overview(course_id)
        students = _portal_service.get_all_students(course_id)
        alerts = _intervention_engine.get_all_alerts(course_id=course_id)
        briefing = _copilot.query("Summarize overall cohort progress and critical misconceptions.")
        return {
            "ok": True,
            "course_id": course_id,
            "overview": overview.to_dict(),
            "students": students,
            "alerts": [a.to_dict() for a in alerts],
            "copilot_briefing": briefing.to_dict(),
        }

    @app.get("/api/teacher/instructions", tags=["Legacy Compatibility"])
    async def legacy_teacher_instructions(
        student_id: Optional[str] = Query(default=None),
        course_id: Optional[str] = Query(default="crs-chem-101"),
    ):
        if student_id:
            insts = _instruction_engine.get_instructions_for_student(student_id, course_id or "")
        else:
            insts = [
                i for i in _instruction_engine._instructions.values()
                if not course_id or i.course_id == course_id or i.course_id in ("all", "*")
            ]
        return {
            "ok": True,
            "instructions": [i.to_dict() for i in insts],
        }

    @app.post("/api/teacher/instruction", tags=["Legacy Compatibility"])
    @app.post("/instruction", tags=["Legacy Compatibility"])
    async def legacy_add_instruction(payload: Dict[str, Any] = Body(...)):
        instruction_text = payload.get("instruction", "").strip()
        if not instruction_text:
            raise HTTPException(status_code=400, detail="Missing instruction text")
        inst_id = f"inst-{uuid.uuid4().hex[:6]}"
        inst = TeacherInstruction(
            instruction_id=inst_id,
            teacher_id="tchr-101",
            student_id=payload.get("student_id", "all"),
            course_id=payload.get("course_id", "crs-chem-101"),
            instruction_text=instruction_text,
            priority=payload.get("priority", 2),
            concept_scope=payload.get("concept_scope", "ALL"),
            is_active=True,
        )
        _instruction_engine.add_instruction(inst)
        return {"ok": True, "instruction_id": inst_id, "instruction": inst.to_dict()}

    @app.post("/instruction/toggle", tags=["Legacy Compatibility"])
    async def legacy_toggle_instruction(payload: Dict[str, Any] = Body(...)):
        inst_id = payload.get("instruction_id")
        active = payload.get("active", True)
        success = _instruction_engine.toggle_instruction(inst_id, active)
        return {"ok": success, "instruction_id": inst_id, "active": active}

    @app.post("/alert/resolve", tags=["Legacy Compatibility"])
    @app.post("/api/teacher/alert/resolve", tags=["Legacy Compatibility"])
    async def legacy_resolve_alert(payload: Dict[str, Any] = Body(...)):
        alert_id = payload.get("alert_id")
        note = payload.get("resolution_note", "Resolved by teacher directive")
        success = _intervention_engine.resolve_alert(alert_id, note)
        return {"ok": success, "alert_id": alert_id}

    @app.post("/api/student/snapshot", tags=["Legacy Compatibility"])
    async def legacy_student_snapshot(payload: Dict[str, Any] = Body(...)):
        sid = payload.get("student_id", "student_001")
        name = payload.get("student_name", f"Student {sid}")
        mastery = float(payload.get("mastery", 0.5))
        needs_attn = bool(payload.get("needs_attention", False))
        misc = payload.get("misconceptions", [])
        hints = int(payload.get("hint_count", 0))
        retention = float(payload.get("retention_rate", 0.85))

        _portal_service.update_student_snapshot(
            student_id=sid,
            student_name=name,
            course_id="crs-chem-101",
            mastery=mastery,
            needs_attention=needs_attn,
            misconceptions=misc,
            hint_count=hints,
            retention_rate=retention,
        )
        return {"ok": True, "student_id": sid, "mastery": mastery}

    @app.post("/api/sync/events", tags=["Legacy Compatibility"])
    async def legacy_sync_events(payload: Dict[str, Any] = Body(...)):
        events = payload.get("events", [])
        student_id = payload.get("student_id", "student_001")
        for ev in events:
            sync_ev = SyncEvent(
                event_id=ev.get("event_id", f"sync-{uuid.uuid4().hex[:6]}"),
                student_id=student_id,
                device_id=ev.get("device_id", f"dev-{student_id}"),
                event_type=ev.get("event_type", "turn_completed"),
                payload=ev,
                timestamp=ev.get("timestamp", ""),
            )
            _sync_manager.record_event(sync_ev)
        return {"ok": True, "synced_count": len(events), "student_id": student_id}

    # 7. Web Dashboard at GET /
    @app.get("/", response_class=HTMLResponse, tags=["Dashboard UI"])
    async def get_dashboard_html():
        """Serve the interactive Teacher Command Center HTML."""
        try:
            from central_platform.teacher.views import render_teacher_dashboard_html
            html = render_teacher_dashboard_html("crs-chem-101")
            return HTMLResponse(content=html, status_code=200)
        except Exception as exc:
            logger.error(f"Error rendering dashboard HTML: {exc}", exc_info=True)
            return HTMLResponse(
                content=f"<h1>Teacher Command Center</h1><p>Error rendering UI: {exc}</p>",
                status_code=500,
            )

    @app.get("/teacher", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/portal", response_class=HTMLResponse, tags=["Dashboard UI"])
    async def get_teacher_portal_html():
        """Serve the Teacher Web Portal browser SPA."""
        import os
        portal_path = os.path.join(os.path.dirname(__file__), "..", "..", "app", "ui", "teacher_portal.html")
        if os.path.exists(portal_path):
            with open(portal_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        return HTMLResponse(content="<h1>Teacher Web Portal</h1>", status_code=200)

    @app.get("/admin", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/admin/portal", response_class=HTMLResponse, tags=["Dashboard UI"])
    async def get_admin_portal_html():
        """Serve the Admin Multi-Tiered Web Portal browser SPA."""
        import os
        admin_path = os.path.join(os.path.dirname(__file__), "..", "..", "app", "ui", "admin_portal.html")
        if os.path.exists(admin_path):
            with open(admin_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        return HTMLResponse(content="<h1>Admin Web Portal</h1>", status_code=200)

    @app.get("/student", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/student/dashboard", response_class=HTMLResponse, tags=["Dashboard UI"])
    async def get_student_dashboard_html():
        """Serve the Student Progress & Mastery Web Portal SPA."""
        import os
        student_path = os.path.join(os.path.dirname(__file__), "..", "..", "app", "ui", "student_dashboard.html")
        if os.path.exists(student_path):
            with open(student_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        return HTMLResponse(content="<h1>Student Dashboard</h1>", status_code=200)

    @app.get("/tutor", response_class=HTMLResponse, tags=["Dashboard UI"])
    @app.get("/interactive", response_class=HTMLResponse, tags=["Dashboard UI"])
    async def get_interactive_tutor_html():
        """Serve the Interactive Web Tutor Client."""
        import os
        tutor_path = os.path.join(os.path.dirname(__file__), "..", "..", "app", "ui", "index.html")
        if os.path.exists(tutor_path):
            with open(tutor_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        return HTMLResponse(content="<h1>Interactive Tutor</h1>", status_code=200)

    # Static Assets & Web Icons (Fixing 404s for favicon.ico, gai3.png, gai3.ico, marked.min.js)
    from fastapi.responses import FileResponse

    ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "app", "ui"))

    @app.get("/favicon.ico", include_in_schema=False)
    @app.get("/gai3.ico", include_in_schema=False)
    async def get_favicon():
        for candidate in [
            os.path.join(ui_dir, "gai3.ico"),
            os.path.join(os.path.dirname(__file__), "..", "..", "gai3.ico"),
        ]:
            if os.path.exists(candidate):
                return FileResponse(candidate, media_type="image/x-icon")
        return Response(status_code=204)

    @app.get("/gai3.png", include_in_schema=False)
    async def get_gai3_png():
        for candidate in [
            os.path.join(ui_dir, "gai3.png"),
            os.path.join(os.path.dirname(__file__), "..", "..", "gai3.png"),
        ]:
            if os.path.exists(candidate):
                return FileResponse(candidate, media_type="image/png")
        return Response(status_code=204)

    @app.get("/marked.min.js", include_in_schema=False)
    async def get_marked_js():
        js_path = os.path.join(ui_dir, "marked.min.js")
        if os.path.exists(js_path):
            return FileResponse(js_path, media_type="application/javascript")
        return Response(content="", media_type="application/javascript")

    return app


app = create_app()


