"""Gayatri AI Platform — API Middleware & Global Error Handlers (Phase 02).

Provides:
1. RequestIDMiddleware (propagates or generates X-Request-ID).
2. StructuredLoggingMiddleware (asynchronous request logger with duration).
3. Standard error envelopes for ValidationErrors, HTTPExceptions, and Unhandled Exceptions.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("gayatri.api.middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Ensures every request has a traceable X-Request-ID correlation header."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            req_id = f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming request method, path, response status, and execution latency."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        t0 = time.time()
        req_id = getattr(request.state, "request_id", "req-unknown")
        path = request.url.path
        method = request.method

        response = await call_next(request)

        duration_ms = round((time.time() - t0) * 1000, 2)
        logger.info(
            f"[{req_id}] {method} {path} -> {response.status_code} ({duration_ms}ms)"
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces defense-in-depth HTTP security headers (OWASP best practices)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; frame-ancestors 'none';",
        )
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform structured error handlers on the FastAPI application."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", "req-unknown")
        raw_errors = exc.errors()
        cleaned_errors = []
        for err in raw_errors:
            c = dict(err)
            loc = c.get("loc", ())
            if any(k in str(part).lower() for part in loc for k in ("password", "secret", "token", "key")):
                if "input" in c:
                    c["input"] = "***REDACTED***"
            if "ctx" in c and isinstance(c["ctx"], dict):
                ctx_copy = dict(c["ctx"])
                if "error" in ctx_copy and isinstance(ctx_copy["error"], Exception):
                    ctx_copy["error"] = str(ctx_copy["error"])
                c["ctx"] = ctx_copy
            cleaned_errors.append(c)
        logger.warning(f"[{req_id}] Validation error on {request.url.path}: {cleaned_errors}")
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"validation_errors": cleaned_errors},
                },
                "meta": {
                    "request_id": req_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "api_version": "v1",
                },
            },
            headers={"X-Request-ID": req_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        req_id = getattr(request.state, "request_id", "req-unknown")
        headers = {"X-Request-ID": req_id}
        if getattr(exc, "headers", None):
            headers.update(exc.headers)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "ok": False,
                "detail": str(exc.detail),
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                    "details": None,
                },
                "meta": {
                    "request_id": req_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "api_version": "v1",
                },
            },
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", "req-unknown")
        logger.error(f"[{req_id}] Unhandled error on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "ok": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred while processing the request",
                    "details": {"error_type": exc.__class__.__name__},
                },
                "meta": {
                    "request_id": req_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "api_version": "v1",
                },
            },
            headers={"X-Request-ID": req_id},
        )
