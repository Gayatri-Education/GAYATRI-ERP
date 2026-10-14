"""Gayatri School OS — Production Release Gate & Rollout Auditor (Phase 09).

Evaluates whether a target environment meets all criteria to issue an evidence-linked
GO / NO-GO release decision under DEVELOPMENT.md (§7 Phase 09).
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from central_platform.config import (
    DEFAULT_INSECURE_SECRET,
    MIN_SECRET_LENGTH,
    WEAK_SECRETS,
    get_environment,
    is_production_mode,
)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = ROOT_DIR / "migrations"

REQUIRED_TABLES_PHASE_09 = [
    "organizations",
    "users",
    "persons",
    "student_profiles",
    "academic_years",
    "student_classes",
    "attendance_sessions",
    "attendance_records",
    "exam_schedules",
    "exam_student_marks",
    "fee_accounts",
    "invoices",
    "staff_leave_requests",
    "transport_vehicles",
    "hostel_rooms",
    "edge_devices",
    "edge_punches",
    "export_jobs",
    "diagnostic_snapshots",
]


@dataclass
class ReleaseGateResult:
    decision: str  # "GO", "NO-GO", "GO_WITH_APPROVED_P2_EXCEPTIONS"
    passed: bool
    summary: str
    reasons: List[str] = field(default_factory=list)
    checks: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""


class ProductionReleaseGateValidator:
    """Verifies production release invariants before deployment or rollout."""

    def __init__(self, db_path: Optional[str] = None, env_vars: Optional[Dict[str, str]] = None):
        self.envs = env_vars if env_vars is not None else dict(os.environ)
        self.db_path = db_path or self.envs.get("GAYATRI_DB_PATH", "gayatri_local.db")

    def audit_environment_configuration(self) -> Dict[str, Any]:
        """Audit environment variables for production security readiness."""
        issues = []
        is_prod = is_production_mode(self.envs)

        # 1. JWT Secret Entropy
        jwt_secret = (
            self.envs.get("GAYATRI_JWT_SECRET")
            or self.envs.get("JWT_SECRET")
            or self.envs.get("SECRET_KEY")
            or ""
        )
        if is_prod:
            if not jwt_secret or jwt_secret == DEFAULT_INSECURE_SECRET:
                issues.append("Production requires explicit GAYATRI_JWT_SECRET.")
            elif jwt_secret.lower() in WEAK_SECRETS:
                issues.append("Configured JWT secret is in weak secrets blacklist.")
            elif len(jwt_secret) < MIN_SECRET_LENGTH:
                issues.append(f"Configured JWT secret is shorter than {MIN_SECRET_LENGTH} characters.")

        # 2. Debug & Reload flags
        debug = self.envs.get("DEBUG", "false").lower() in ("true", "1", "yes")
        reload_mode = self.envs.get("RELOAD", "false").lower() in ("true", "1", "yes")
        fastapi_debug = self.envs.get("FASTAPI_DEBUG", "false").lower() in ("true", "1", "yes")
        if is_prod and (debug or reload_mode or fastapi_debug):
            issues.append("Debug or reload flags are enabled in production mode.")

        # 3. CORS Origins
        allowed_origins = self.envs.get("GAYATRI_ALLOWED_ORIGINS") or self.envs.get("ALLOWED_ORIGINS")
        if is_prod:
            if not allowed_origins:
                issues.append("GAYATRI_ALLOWED_ORIGINS must be explicitly configured in production mode.")
            elif "*" in [o.strip() for o in allowed_origins.split(",")]:
                issues.append("Wildcard CORS ('*') is strictly prohibited in production mode.")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "environment": get_environment(self.envs),
            "is_production": is_prod,
            "debug": debug,
            "reload": reload_mode,
        }

    def audit_database_schema(self, connection: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
        """Audit database tables ensuring all 16 migrations are applied."""
        conn = connection
        close_needed = False
        if conn is None:
            if not Path(self.db_path).exists():
                return {
                    "passed": False,
                    "issues": [f"Database file does not exist: {self.db_path}"],
                    "tables_found": [],
                    "missing_tables": REQUIRED_TABLES_PHASE_09,
                }
            conn = sqlite3.connect(self.db_path)
            close_needed = True

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = {r[0] for r in cursor.fetchall()}

            missing = [t for t in REQUIRED_TABLES_PHASE_09 if t not in tables]

            # Integrity check
            cursor.execute("PRAGMA integrity_check;")
            integrity_row = cursor.fetchone()
            integrity_ok = integrity_row is not None and integrity_row[0] == "ok"

            issues = []
            if missing:
                issues.append(f"Missing required tables for Phase 09: {missing}")
            if not integrity_ok:
                issues.append("Database PRAGMA integrity_check failed.")

            return {
                "passed": len(issues) == 0,
                "issues": issues,
                "integrity_ok": integrity_ok,
                "total_tables": len(tables),
                "missing_tables": missing,
            }
        finally:
            if close_needed:
                conn.close()

    def audit_critical_path_safety(self) -> Dict[str, Any]:
        """Verify that zero mock adapters or dangerous demo bypasses are active."""
        issues = []
        is_prod = is_production_mode(self.envs)

        mock_payments = self.envs.get("GAYATRI_ENABLE_MOCK_PAYMENTS", "false").lower() in ("true", "1", "yes")
        if is_prod and mock_payments:
            issues.append("Mock payment adapter is enabled in production mode.")

        demo_roster = self.envs.get("GAYATRI_ENABLE_DEMO_ROSTER", "false").lower() in ("true", "1", "yes")
        if is_prod and demo_roster:
            issues.append("Demo roster bypass is enabled in production mode.")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "mock_payments_active": mock_payments,
            "demo_roster_active": demo_roster,
        }

    def evaluate_release_gate(self, connection: Optional[sqlite3.Connection] = None) -> ReleaseGateResult:
        """Run all audits and evaluate final GO / NO-GO release gate status."""
        env_audit = self.audit_environment_configuration()
        db_audit = self.audit_database_schema(connection)
        safety_audit = self.audit_critical_path_safety()

        all_issues = env_audit["issues"] + db_audit["issues"] + safety_audit["issues"]
        passed = len(all_issues) == 0

        decision = "GO" if passed else "NO-GO"
        summary = (
            f"Release Gate {decision}: All {len(REQUIRED_TABLES_PHASE_09)} tables present, "
            f"PRAGMA check verified, zero mock adapters in critical paths."
            if passed
            else f"Release Gate {decision}: {len(all_issues)} blocking issue(s) detected."
        )

        # Compute deterministic checksum of release state
        hasher = hashlib.sha256()
        hasher.update(decision.encode("utf-8"))
        hasher.update(str(sorted(all_issues)).encode("utf-8"))
        hasher.update(str(db_audit.get("total_tables", 0)).encode("utf-8"))
        checksum = hasher.hexdigest()

        return ReleaseGateResult(
            decision=decision,
            passed=passed,
            summary=summary,
            reasons=all_issues,
            checks={
                "environment": env_audit,
                "database": db_audit,
                "critical_safety": safety_audit,
            },
            checksum=checksum,
        )
