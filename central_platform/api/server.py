"""Gayatri AI Platform — Canonical Application Server Entrypoint (Phase 10).

Fulfills Section 15 of the Master Remediation Plan:
- Canonical production server runner.
- Zero entrypoint divergence.
- Headless, uvicorn-driven HTTP application runtime.
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("gayatri.api.server")

# Re-export the canonical FastAPI application
from central_platform.api.app import app, create_app  # noqa: F401


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False, log_level: str = "info") -> None:
    """Launch the production ASGI server with uvicorn."""
    import uvicorn
    from central_platform.config import is_production_mode

    if is_production_mode():
        if reload or os.environ.get("RELOAD", "false").lower() in ("true", "1", "yes"):
            raise RuntimeError("Production startup aborted: Reload mode is strictly prohibited in production environment.")
        if os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes"):
            raise RuntimeError("Production startup aborted: Debug mode is strictly prohibited in production environment.")

    logger.info("Starting Gayatri Production Platform API on %s:%s", host, port)
    uvicorn.run("central_platform.api.server:app", host=host, port=port, reload=reload, log_level=log_level)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    run_server(host=host, port=port)
