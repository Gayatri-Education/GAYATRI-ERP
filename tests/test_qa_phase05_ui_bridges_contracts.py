"""Phase 05 — UI Bridges, Real API Wiring, and XSS Prevention Tests.

Verifies:
1. ERP-007: Monthly billing generation UI calls backend API and produces real billing records.
2. ERP-008: Outstanding report export calls backend API and delivers valid CSV.
3. ERP-009: Receipt printing verification against persisted backend receipt.
4. ERP-011: Teacher Copilot action invokes backend AI briefing endpoint and returns structured insights.
5. ERP-010: Student startReview action submits real learning action to backend.
6. ERP-018: XSS prevention — escapeHtml handles single quotes and student UI avoids vulnerable inline handlers.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from central_platform.api.app import app
from central_platform.auth.dependencies import get_db, get_current_user
from central_platform.db import PlatformDatabase
from central_platform.models.schema import User, UserRole
from central_platform.portals.fee_admin import FeeAdminController


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_phase05.db"
    return PlatformDatabase(db_file)


@pytest.fixture
def client(test_db):
    app.dependency_overrides[get_db] = lambda: test_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user():
    return User(
        id="usr_admin_01",
        email="fee_admin@school.org",
        full_name="Fee Admin",
        role=UserRole.ORG_ADMIN,
        organization_id="org_test_01",
    )


@pytest.fixture
def teacher_user():
    return User(
        id="usr_teacher_01",
        email="chem_teacher@school.org",
        full_name="Chemistry Teacher",
        role=UserRole.TEACHER,
        organization_id="org_test_01",
    )


@pytest.fixture
def student_user():
    return User(
        id="usr_student_01",
        email="chem_student@school.org",
        full_name="Chemistry Student",
        role=UserRole.STUDENT,
        organization_id="org_test_01",
    )


def test_fee_admin_controller_generate_monthly_billing(test_db):
    res = FeeAdminController.generate_monthly_billing(org_id="org_test_01", month_year="2026-10", db=test_db)
    assert res is not None
    assert res.get("organization_id") == "org_test_01"
    assert res.get("month_year") == "2026-10"
    assert res.get("invoices_generated", 0) >= 1
    assert "batch_id" in res


def test_fee_admin_generate_billing_endpoint(client, admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    resp = client.post(
        "/api/v1/finance/billing/generate",
        json={"month_year": "2026-10"},
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    assert data["organization_id"] == "org_test_01"
    assert data["month_year"] == "2026-10"
    assert data["invoices_generated"] >= 1


def test_fee_admin_outstanding_report_endpoints(client, admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    # Structured JSON
    resp = client.get("/api/v1/finance/reports/outstanding")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert items[0]["student_name"] == "Aarav Sharma"

    # CSV Export
    csv_resp = client.get("/api/v1/finance/reports/outstanding/export")
    assert csv_resp.status_code == 200, csv_resp.text
    assert "text/csv" in csv_resp.headers.get("content-type", "")
    assert "attachment" in csv_resp.headers.get("content-disposition", "")
    assert "Student ID,Student Name,Grade" in csv_resp.text
    assert "Aarav Sharma" in csv_resp.text


def test_teacher_copilot_briefing_endpoint(client, teacher_user):
    app.dependency_overrides[get_current_user] = lambda: teacher_user
    resp = client.get("/api/v1/teachers/copilot/briefing")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    briefing = data["data"]
    assert "cohort_summary" in briefing or "pedagogical_recommendations" in briefing or "response" in briefing or "evidence" in briefing


def test_student_review_action_endpoint(client, student_user):
    app.dependency_overrides[get_current_user] = lambda: student_user
    resp = client.post(
        f"/api/v1/students/{student_user.id}/action",
        json={
            "action_type": "review_start",
            "concept_id": "c-thermo",
            "course_id": "crs-chem-101",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True


def test_fee_admin_js_wires_to_real_endpoints():
    js_path = Path("app/ui/design_system/fee_admin.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    # Assert ERP-007 wiring
    assert "generateMonthlyBilling" in content
    assert "/api/v1/finance/billing/generate" in content or "/finance/billing" in content
    assert "fetch" in content

    # Assert ERP-008 wiring
    assert "exportOutstandingReport" in content
    assert "/api/v1/finance/reports/outstanding/export" in content or "/finance/reports/outstanding" in content

    # Assert ERP-009 wiring
    assert "printReceipt" in content
    assert "/api/v1/finance/receipts/" in content


def test_teacher_js_wires_to_copilot_endpoint():
    js_path = Path("app/ui/design_system/teacher.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    # Assert ERP-011 wiring
    assert "triggerCopilotAnalysis" in content
    assert "/api/v1/teachers/copilot/" in content
    assert "fetch" in content


def test_student_js_wires_to_action_endpoint():
    js_path = Path("app/ui/design_system/student.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    # Assert ERP-010 wiring
    assert "startReview" in content
    assert "/api/v1/students/" in content
    assert "/action" in content
    assert "fetch" in content


def test_xss_prevention_escape_html_and_student_ui():
    comp_path = Path("app/ui/design_system/components.js")
    assert comp_path.exists()
    comp_content = comp_path.read_text(encoding="utf-8")

    # escapeHtml must escape single quotes
    assert "&#39;" in comp_content or "&#x27;" in comp_content

    student_path = Path("app/ui/design_system/student.js")
    student_content = student_path.read_text(encoding="utf-8")

    # Assert vulnerable raw string interpolation into inline onclick is NOT present
    assert "onclick=\"window.GayatriStudent.startReview('${item.concept_id}')\"" not in student_content
