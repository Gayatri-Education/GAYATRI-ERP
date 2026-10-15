"""
tests/test_smoke.py
Canonical Smoke & Evaluation Test Suite for Gayatri School OS.

Verifies end-to-end platform readiness:
1. User portal UI templates and assets
2. Central Platform API application and route registration
3. Health probe and subsystem diagnostics
4. Platform database connection and core schema
5. Prompt contract loading and system policies
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_portal_ui_templates_exist():
    """Verify that all stakeholder web portal templates exist and have valid structure."""
    ui_dir = PROJECT_ROOT / "app" / "ui"
    portals = [
        "admin_portal.html",
        "student_dashboard.html",
        "teacher_portal.html",
        "parent_portal.html",
    ]
    for portal in portals:
        portal_path = ui_dir / portal
        assert portal_path.exists(), f"Portal UI missing: {portal}"
        content = portal_path.read_text(encoding="utf-8")
        assert len(content) > 500, f"Portal template unexpectedly empty: {portal}"
        assert "<!DOCTYPE html>" in content or "<html" in content

def test_platform_api_health_probe():
    """Verify that the FastAPI platform application boots and passes /healthz."""
    from central_platform.api.app import app
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in ("ok", "healthy", "ONLINE")
    assert data.get("database") == "CONNECTED"

def test_platform_database_connection():
    """Verify that SQLite platform database initializes cleanly."""
    from central_platform.db import PlatformDatabase
    db = PlatformDatabase()
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert len(tables) > 0, "Database initialized with zero tables"

def test_prompt_contracts():
    """Verify that system prompt contracts load cleanly."""
    from core.prompts.loader import get_prompt_loader
    loader = get_prompt_loader()
    assert loader is not None
    # Loading fallback should be graceful even if specific contract is empty
    prompt = loader.load_prompt("general_assistant_system_v1.txt")
    assert isinstance(prompt, str)

def test_static_and_demo_assets():
    """Verify branding and demo video assets exist in docs/assets/demos/."""
    demo_dir = PROJECT_ROOT / "docs" / "assets" / "demos"
    assert demo_dir.exists(), "docs/assets/demos directory missing"
    assert (PROJECT_ROOT / "gai3.png").exists(), "Branding gai3.png missing"
    assert (PROJECT_ROOT / "gai3.ico").exists(), "Branding gai3.ico missing"
    
    # Check that video walkthroughs are present
    videos = list(demo_dir.glob("*.webm"))
    assert len(videos) >= 4, f"Expected at least 4 demo videos, found {len(videos)}"
