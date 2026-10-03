"""Platform central database storage layer and tenant isolation manager (Phase 03).

Provides authoritative data access across all 29 Section 12 entities, supporting:
- Relational foreign key integrity & cascades
- Multi-tenant organization scoping
- Soft deletion & audit logging
- Automated schema migrations via scripts/migrate_db.py
- Dual-engine execution (PostgreSQL in production, SQLite in local/CI)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("gayatri.central_platform.db")

from central_platform.rbac.engine import hash_password, verify_password
from central_platform.models.fees import (
    Discount,
    DiscountType,
    FeeAccount,
    FeeFrequency,
    FeePlan,
    FeeStructure,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Receipt,
    Refund,
    RefundStatus,
)

from central_platform.models.schema import (
    AIExecutionLog,
    AIModel,
    AIProvider,
    AlertSeverity,
    AlertStatus,
    Assessment,
    AssessmentAttempt,
    AssessmentItem,
    AssessmentType,
    Assignment,
    AuditLog,
    ClassGroup,
    Cohort,
    Concept,
    Course,
    CourseOffering,
    CoursePolicy,
    CourseStatus,
    CourseToolPolicy,
    CourseVersion,
    CourseVisibility,
    Curriculum,
    CurriculumBoard,
    CurriculumVersion,
    Enrollment,
    InterventionRecord,
    LearningEvent,
    MasteryState,
    Misconception,
    Module,
    Notification,
    Organization,
    Permission,
    Prerequisite,
    QuestionBankItem,
    RAGChunk,
    RAGSource,
    RAGSourceStatus,
    Reassessment,
    Role,
    Session,
    SessionStatus,
    StudentLearningRecord,
    StudentMisconceptionRecord,
    Subject,
    TeacherInstructionRecord,
    Topic,
    User,
    UserRole,
    SyncOperationRecord,
    DeviceBinding,
)
from scripts.migrate_db import run_all_migrations


class _ConnectionContextWrapper:
    """Connection wrapper that suppresses per-operation auto-commit when inside an outer transaction."""

    def __init__(self, raw_conn: sqlite3.Connection, db: PlatformDatabase):
        self._raw_conn = raw_conn
        self._db = db

    def __enter__(self):
        if not self._db.in_transaction:
            return self._raw_conn.__enter__()
        return self._raw_conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._db.in_transaction:
            return self._raw_conn.__exit__(exc_type, exc_val, exc_tb)
        return False

    def __getattr__(self, name):
        return getattr(self._raw_conn, name)


class PlatformDatabase:
    """Central data layer manager supporting multi-tenant isolation and 29 domain entities."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or os.environ.get("GAYATRI_DB_PATH", ":memory:"))
        self._conn: Optional[sqlite3.Connection] = sqlite3.connect(
            self.db_path, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            try:
                self._conn.execute("PRAGMA journal_mode = WAL;")
                self._conn.execute("PRAGMA synchronous = NORMAL;")
            except Exception:
                pass
        self._tx_depth: int = 0
        self._conn_wrapper: Optional[_ConnectionContextWrapper] = _ConnectionContextWrapper(self._conn, self)
        self._init_db()

    @property
    def in_transaction(self) -> bool:
        """True if an explicit transaction is active on this database connection."""
        return self._tx_depth > 0

    @contextmanager
    def transaction(self):
        """Context manager providing an atomic database transaction.

        Supports nested transactions using SQLite SAVEPOINTs.
        Guarantees all DML operations within the block are committed together,
        or completely rolled back on error with zero partial writes.
        """
        self._tx_depth += 1
        depth = self._tx_depth
        sp_name = f"tx_sp_{depth}"
        raw_conn = self._get_raw_connection()
        if depth > 1:
            raw_conn.execute(f"SAVEPOINT {sp_name};")
        try:
            yield raw_conn
            if depth > 1:
                raw_conn.execute(f"RELEASE SAVEPOINT {sp_name};")
            else:
                raw_conn.commit()
        except Exception:
            if depth > 1:
                raw_conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name};")
                raw_conn.execute(f"RELEASE SAVEPOINT {sp_name};")
            else:
                raw_conn.rollback()
            raise
        finally:
            self._tx_depth -= 1

    def _get_raw_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON;")
            if self.db_path != ":memory:":
                try:
                    self._conn.execute("PRAGMA journal_mode = WAL;")
                    self._conn.execute("PRAGMA synchronous = NORMAL;")
                except Exception:
                    pass
            self._conn_wrapper = _ConnectionContextWrapper(self._conn, self)
        return self._conn

    def _get_connection(self) -> _ConnectionContextWrapper:
        if self._conn is None or self._conn_wrapper is None:
            self._get_raw_connection()
        return self._conn_wrapper

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._conn_wrapper = None

    def checkpoint(self, mode: str = "TRUNCATE") -> None:
        """Checkpoint SQLite WAL entries into the database file."""
        if self.db_path != ":memory:":
            try:
                conn = self._get_connection()
                conn.execute(f"PRAGMA wal_checkpoint({mode});")
            except Exception:
                pass

    def _init_db(self) -> None:
        """Run initial DDL and migrations automatically."""
        conn = self._get_connection()
        run_all_migrations(conn)
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS device_bindings (
                    device_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    organization_id TEXT,
                    device_name TEXT,
                    device_type TEXT DEFAULT 'desktop',
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    bound_at TEXT NOT NULL,
                    last_synced_at TEXT,
                    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_device_bindings_student
                ON device_bindings (student_id);
                """
            )
        self.checkpoint("TRUNCATE")


    # ── 1. Organizations & Identity ──────────────────────────────────────────

    def create_organization(self, org: Organization) -> Organization:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO organizations (id, name, slug, created_at, updated_at, is_deleted, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    org.id,
                    org.name,
                    org.slug,
                    org.created_at,
                    org.updated_at,
                    1 if org.is_deleted else 0,
                    org.deleted_at,
                ),
            )
        return org

    def get_organization(self, org_id: str, include_deleted: bool = False) -> Optional[Organization]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM organizations WHERE id = ?"
            if not include_deleted:
                sql += " AND is_deleted = 0"
            r = conn.execute(sql, (org_id,)).fetchone()
            if r:
                return Organization(
                    id=r["id"],
                    name=r["name"],
                    slug=r["slug"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]),
                    deleted_at=r["deleted_at"],
                )
            return None

    def list_organizations(self, include_deleted: bool = False) -> List[Organization]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM organizations"
            if not include_deleted:
                sql += " WHERE is_deleted = 0"
            sql += " ORDER BY name ASC;"
            rows = conn.execute(sql).fetchall()
            return [
                Organization(
                    id=r["id"],
                    name=r["name"],
                    slug=r["slug"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]),
                    deleted_at=r["deleted_at"],
                )
                for r in rows
            ]

    def soft_delete_organization(self, org_id: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE organizations SET is_deleted = 1, deleted_at = ? WHERE id = ? AND is_deleted = 0;",
                (now_iso, org_id),
            )
            return cursor.rowcount > 0

    def create_user(self, user: User) -> User:
        with self._get_connection() as conn:
            role_val = user.role.value if isinstance(user.role, UserRole) else str(user.role)
            conn.execute(
                """
                INSERT OR REPLACE INTO users (id, email, full_name, role, organization_id, is_active, created_at, updated_at, is_deleted, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    user.id,
                    user.email,
                    user.full_name,
                    role_val,
                    user.organization_id,
                    1 if user.is_active else 0,
                    user.created_at,
                    user.updated_at,
                    1 if user.is_deleted else 0,
                    user.deleted_at,
                ),
            )
        return user

    def get_user(self, user_id: str, include_deleted: bool = False) -> Optional[User]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM users WHERE id = ?"
            if not include_deleted:
                sql += " AND is_deleted = 0"
            r = conn.execute(sql, (user_id,)).fetchone()
            if r:
                return User(
                    id=r["id"],
                    email=r["email"],
                    full_name=r["full_name"],
                    role=UserRole(r["role"]),
                    organization_id=r["organization_id"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]),
                    deleted_at=r["deleted_at"],
                )
            return None

    def get_users_by_organization(self, organization_id: str, include_deleted: bool = False) -> List[User]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM users WHERE organization_id = ?"
            if not include_deleted:
                sql += " AND is_deleted = 0"
            sql += " ORDER BY full_name ASC;"
            rows = conn.execute(sql, (organization_id,)).fetchall()
            return [
                User(
                    id=r["id"],
                    email=r["email"],
                    full_name=r["full_name"],
                    role=UserRole(r["role"]),
                    organization_id=r["organization_id"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]),
                    deleted_at=r["deleted_at"],
                )
                for r in rows
            ]

    def get_users_by_role(
        self,
        role: UserRole | str,
        organization_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[User]:
        role_val = role.value if hasattr(role, "value") else str(role)
        with self._get_connection() as conn:
            sql = "SELECT * FROM users WHERE (role = ? OR LOWER(role) = LOWER(?))"
            params: list[Any] = [role_val, role_val]
            if organization_id:
                sql += " AND organization_id = ?"
                params.append(organization_id)
            if not include_deleted:
                sql += " AND is_deleted = 0"
            sql += " ORDER BY full_name ASC;"
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [
                User(
                    id=r["id"],
                    email=r["email"],
                    full_name=r["full_name"],
                    role=UserRole(r["role"]),
                    organization_id=r["organization_id"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]),
                    deleted_at=r["deleted_at"],
                )
                for r in rows
            ]

    def soft_delete_user(self, user_id: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE users SET is_deleted = 1, deleted_at = ? WHERE id = ? AND is_deleted = 0;",
                (now_iso, user_id),
            )
            return cursor.rowcount > 0

    def get_user_by_email(self, email: str, include_deleted: bool = False) -> Optional[User]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM users WHERE email = ?"
            if not include_deleted:
                sql += " AND is_deleted = 0"
            r = conn.execute(sql, (email.strip().lower(),)).fetchone()
            if not r:
                r = conn.execute(sql.replace("email = ?", "LOWER(email) = LOWER(?)"), (email.strip(),)).fetchone()
            if r:
                return User(
                    id=r["id"],
                    email=r["email"],
                    full_name=r["full_name"],
                    role=UserRole(r["role"]),
                    organization_id=r["organization_id"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]),
                    deleted_at=r["deleted_at"],
                )
            return None

    def set_user_password(self, user_id: str, password: str) -> None:
        """Hash and persist password with salt in user_credentials."""
        password_hash, salt_hex = hash_password(password)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_credentials 
                (user_id, password_hash, salt_hex, is_suspended, failed_login_attempts, password_reset_token, updated_at)
                VALUES (?, ?, ?, 0, 0, NULL, ?);
                """,
                (user_id, password_hash, salt_hex, now_iso),
            )

    def get_user_credentials(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            r = conn.execute(
                "SELECT * FROM user_credentials WHERE user_id = ?;",
                (user_id,),
            ).fetchone()
            if r:
                return dict(r)
            return None

    def suspend_user(self, user_id: str, reason: Optional[str] = None) -> bool:
        """Suspend user account to prevent login."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            c = conn.execute(
                "UPDATE user_credentials SET is_suspended = 1, updated_at = ? WHERE user_id = ?;",
                (now_iso, user_id),
            )
            return c.rowcount > 0

    def unsuspend_user(self, user_id: str) -> bool:
        """Unsuspend user account and clear failed login attempts."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            c = conn.execute(
                "UPDATE user_credentials SET is_suspended = 0, failed_login_attempts = 0, updated_at = ? WHERE user_id = ?;",
                (now_iso, user_id),
            )
            return c.rowcount > 0

    def set_password_reset_token(self, email: str, token: str) -> bool:
        """Set a one-time password reset token for the given email."""
        user = self.get_user_by_email(email)
        if not user:
            return False
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            c = conn.execute(
                "UPDATE user_credentials SET password_reset_token = ?, updated_at = ? WHERE user_id = ?;",
                (token, now_iso, user.id),
            )
            return c.rowcount > 0

    def reset_password_with_token(self, token: str, new_password: str) -> bool:
        """Reset password using a valid one-time reset token."""
        with self._get_connection() as conn:
            r = conn.execute(
                "SELECT user_id FROM user_credentials WHERE password_reset_token = ?;",
                (token,),
            ).fetchone()
            if not r:
                return False
            user_id = r["user_id"]
        self.set_user_password(user_id, new_password)
        return True

    def authenticate_user(self, email_or_identifier: str, password: str) -> Optional[User]:
        """Authenticate user by email or user_id, checking password hash and account status."""
        user = self.get_user_by_email(email_or_identifier)
        if not user:
            user = self.get_user(email_or_identifier)
        if not user or not user.is_active or user.is_deleted:
            return None

        creds = self.get_user_credentials(user.id)
        if not creds:
            return None

        if creds["is_suspended"]:
            return None

        if verify_password(password, creds["password_hash"], creds["salt_hex"]):
            now_iso = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE user_credentials SET failed_login_attempts = 0, updated_at = ? WHERE user_id = ?;",
                    (now_iso, user.id),
                )
            return user
        else:
            now_iso = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE user_credentials SET failed_login_attempts = failed_login_attempts + 1, updated_at = ? WHERE user_id = ?;",
                    (now_iso, user.id),
                )
            return None

    def get_assigned_student_ids_for_teacher(self, teacher_id: str) -> Set[str]:
        """Resolve all student IDs assigned to courses or class groups taught by the teacher's organization."""
        with self._get_connection() as conn:
            teacher_row = conn.execute("SELECT organization_id FROM users WHERE id = ?;", (teacher_id,)).fetchone()
            org_id = teacher_row["organization_id"] if teacher_row else None

            if org_id:
                rows = conn.execute(
                    """
                    SELECT DISTINCT e.student_id 
                    FROM enrollments e
                    JOIN class_groups cg ON e.course_id = cg.course_id
                    JOIN users u ON e.student_id = u.id
                    WHERE e.is_active = 1 AND (cg.organization_id = ? OR u.organization_id = ?);
                    """,
                    (org_id, org_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT e.student_id 
                    FROM enrollments e
                    JOIN class_groups cg ON e.course_id = cg.course_id
                    WHERE e.is_active = 1;
                    """
                ).fetchall()
            student_ids = {r["student_id"] for r in rows}
            t_rows = conn.execute(
                "SELECT DISTINCT student_id FROM teacher_instructions WHERE teacher_id = ?;",
                (teacher_id,),
            ).fetchall()
            for tr in t_rows:
                if tr["student_id"] and tr["student_id"] != "all":
                    student_ids.add(tr["student_id"])
            return student_ids

    def create_role(self, role: Role) -> Role:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO roles (id, name, description, created_at) VALUES (?, ?, ?, ?);",
                (role.id, role.name, role.description, role.created_at),
            )
        return role

    def create_permission(self, perm: Permission) -> Permission:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO permissions (id, code, description, created_at) VALUES (?, ?, ?, ?);",
                (perm.id, perm.code, perm.description, perm.created_at),
            )
        return perm

    def assign_role_permission(self, role_id: str, permission_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?);",
                (role_id, permission_id),
            )

    # ── 2. Academic Curriculum Hierarchy ────────────────────────────────────

    def _row_to_course(self, r: sqlite3.Row) -> Course:
        keys = r.keys()
        vis_val = r["visibility"] if "visibility" in keys and r["visibility"] else "PRIVATE"
        try:
            vis = CourseVisibility(vis_val)
        except Exception:
            vis = CourseVisibility.PRIVATE
        return Course(
            id=r["id"],
            organization_id=r["organization_id"],
            code=r["code"],
            title=r["title"],
            description=r["description"] if "description" in keys and r["description"] else "",
            visibility=vis,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            is_deleted=bool(r["is_deleted"]),
            deleted_at=r["deleted_at"] if "deleted_at" in keys else None,
        )

    def create_course(self, course: Course) -> Course:
        vis_val = course.visibility.value if isinstance(course.visibility, CourseVisibility) else str(course.visibility)
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO courses (id, organization_id, code, title, description, visibility, created_at, updated_at, is_deleted, deleted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        course.id,
                        course.organization_id,
                        course.code,
                        course.title,
                        course.description,
                        vis_val,
                        course.created_at,
                        course.updated_at,
                        1 if course.is_deleted else 0,
                        course.deleted_at,
                    ),
                )
            except sqlite3.OperationalError:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO courses (id, organization_id, code, title, description, created_at, updated_at, is_deleted, deleted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        course.id,
                        course.organization_id,
                        course.code,
                        course.title,
                        course.description,
                        course.created_at,
                        course.updated_at,
                        1 if course.is_deleted else 0,
                        course.deleted_at,
                    ),
                )
        return course

    def get_course(self, course_id: str, include_deleted: bool = False) -> Optional[Course]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM courses WHERE id = ?"
            if not include_deleted:
                sql += " AND is_deleted = 0"
            r = conn.execute(sql, (course_id,)).fetchone()
            if r:
                return self._row_to_course(r)
            return None

    def get_courses_by_organization(self, organization_id: str, include_deleted: bool = False) -> List[Course]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM courses WHERE organization_id = ?"
            if not include_deleted:
                sql += " AND is_deleted = 0"
            sql += " ORDER BY code ASC;"
            rows = conn.execute(sql, (organization_id,)).fetchall()
            return [self._row_to_course(r) for r in rows]

    def list_courses(self, organization_id: Optional[str] = None, include_deleted: bool = False) -> List[Course]:
        """List all courses with optional organization filter and soft-delete filtering."""
        with self._get_connection() as conn:
            sql = "SELECT * FROM courses"
            conditions = []
            params: list[Any] = []
            if organization_id:
                conditions.append("organization_id = ?")
                params.append(organization_id)
            if not include_deleted:
                conditions.append("is_deleted = 0")
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY code ASC;"
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [self._row_to_course(r) for r in rows]

    def get_public_courses(self, include_deleted: bool = False) -> List[Course]:
        with self._get_connection() as conn:
            try:
                sql = "SELECT * FROM courses WHERE visibility = 'PUBLIC'"
                if not include_deleted:
                    sql += " AND is_deleted = 0"
                sql += " ORDER BY code ASC;"
                rows = conn.execute(sql).fetchall()
                return [self._row_to_course(r) for r in rows]
            except sqlite3.OperationalError:
                return []

    def create_course_version(self, version: CourseVersion) -> CourseVersion:
        status_val = version.status.value if isinstance(version.status, CourseStatus) else str(version.status)
        tool_policy_json = json.dumps(version.tool_policy.to_dict() if hasattr(version.tool_policy, "to_dict") else version.tool_policy)
        tutor_policy_json = json.dumps(version.tutor_policy.to_dict() if hasattr(version.tutor_policy, "to_dict") else version.tutor_policy)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO course_versions (id, course_id, version_number, status, tool_policy, tutor_policy, checksum, created_by, published_by, created_at, published_at, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    version.id,
                    version.course_id,
                    version.version_number,
                    status_val,
                    tool_policy_json,
                    tutor_policy_json,
                    version.checksum,
                    version.created_by,
                    version.published_by,
                    version.created_at,
                    version.published_at,
                    1 if version.is_deleted else 0,
                ),
            )
        return version

    def get_course_version(self, version_id: str, include_deleted: bool = False) -> Optional[CourseVersion]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM course_versions WHERE id = ?"
            if not include_deleted:
                sql += " AND is_deleted = 0"
            r = conn.execute(sql, (version_id,)).fetchone()
            if r:
                return self._row_to_course_version(r)
            return None

    def get_course_versions_by_course(self, course_id: str, include_deleted: bool = False) -> List[CourseVersion]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM course_versions WHERE course_id = ?"
            if not include_deleted:
                sql += " AND is_deleted = 0"
            sql += " ORDER BY version_number ASC;"
            rows = conn.execute(sql, (course_id,)).fetchall()
            return [self._row_to_course_version(r) for r in rows]

    def list_course_versions(self, course_id: str, include_deleted: bool = False) -> List[CourseVersion]:
        """List all versions for a course (alias for get_course_versions_by_course)."""
        return self.get_course_versions_by_course(course_id, include_deleted=include_deleted)

    def get_latest_published_course_version(self, course_id: str) -> Optional[CourseVersion]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM course_versions WHERE course_id = ? AND status = 'PUBLISHED' AND is_deleted = 0 ORDER BY version_number DESC LIMIT 1;"
            r = conn.execute(sql, (course_id,)).fetchone()
            if r:
                return self._row_to_course_version(r)
            return None

    def publish_course_version(self, version_id: str, published_by: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE course_versions
                SET status = 'PUBLISHED', published_by = ?, published_at = ?
                WHERE id = ? AND is_deleted = 0;
                """,
                (published_by, now_iso, version_id),
            )
            return cursor.rowcount > 0

    def archive_course(self, course_id: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE courses
                SET is_deleted = 1, deleted_at = ?, updated_at = ?
                WHERE id = ? AND is_deleted = 0;
                """,
                (now_iso, now_iso, course_id),
            )
            return cursor.rowcount > 0

    def archive_course_version(self, version_id: str, archived_by: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE course_versions
                SET status = 'ARCHIVED'
                WHERE id = ? AND is_deleted = 0;
                """,
                (version_id,),
            )
            return cursor.rowcount > 0

    def get_course_versions_by_status(
        self,
        status: CourseStatus,
        organization_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[CourseVersion]:
        status_val = status.value if isinstance(status, CourseStatus) else str(status)
        with self._get_connection() as conn:
            if organization_id:
                sql = """
                SELECT cv.* FROM course_versions cv
                JOIN courses c ON cv.course_id = c.id
                WHERE cv.status = ? AND c.organization_id = ?
                """
                if not include_deleted:
                    sql += " AND cv.is_deleted = 0 AND c.is_deleted = 0"
                sql += " ORDER BY cv.created_at DESC;"
                rows = conn.execute(sql, (status_val, organization_id)).fetchall()
            else:
                sql = "SELECT * FROM course_versions WHERE status = ?"
                if not include_deleted:
                    sql += " AND is_deleted = 0"
                sql += " ORDER BY created_at DESC;"
                rows = conn.execute(sql, (status_val,)).fetchall()
            return [self._row_to_course_version(r) for r in rows]

    def _row_to_course_version(self, r: sqlite3.Row) -> CourseVersion:
        try:
            status = CourseStatus(r["status"])
        except Exception:
            status = CourseStatus.DRAFT
        try:
            tool_dict = json.loads(r["tool_policy"]) if r["tool_policy"] else {}
        except Exception:
            tool_dict = {}
        try:
            tutor_dict = json.loads(r["tutor_policy"]) if r["tutor_policy"] else {}
        except Exception:
            tutor_dict = {}
        return CourseVersion(
            id=r["id"],
            course_id=r["course_id"],
            version_number=r["version_number"],
            status=status,
            tool_policy=CourseToolPolicy.from_dict(tool_dict),
            tutor_policy=CoursePolicy.from_dict(tutor_dict),
            checksum=r["checksum"] or "",
            created_by=r["created_by"] or "",
            published_by=r["published_by"],
            created_at=r["created_at"],
            published_at=r["published_at"],
            is_deleted=bool(r["is_deleted"]),
        )

    def create_course_offering(self, offering: CourseOffering) -> CourseOffering:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO organization_course_offerings (id, org_id, course_id, pinned_version_id, is_active, enrolled_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    offering.id,
                    offering.organization_id,
                    offering.course_id,
                    offering.pinned_version_id,
                    1 if offering.is_active else 0,
                    offering.enrolled_at,
                ),
            )
        return offering

    def get_course_offering(self, offering_id: str) -> Optional[CourseOffering]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM organization_course_offerings WHERE id = ?"
            r = conn.execute(sql, (offering_id,)).fetchone()
            if r:
                return CourseOffering(
                    id=r["id"],
                    organization_id=r["org_id"],
                    course_id=r["course_id"],
                    pinned_version_id=r["pinned_version_id"],
                    is_active=bool(r["is_active"]),
                    enrolled_at=r["enrolled_at"],
                )
            return None

    def get_course_offerings_by_org(self, organization_id: str) -> List[CourseOffering]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM organization_course_offerings WHERE org_id = ? AND is_active = 1;"
            rows = conn.execute(sql, (organization_id,)).fetchall()
            return [
                CourseOffering(
                    id=r["id"],
                    organization_id=r["org_id"],
                    course_id=r["course_id"],
                    pinned_version_id=r["pinned_version_id"],
                    is_active=bool(r["is_active"]),
                    enrolled_at=r["enrolled_at"],
                )
                for r in rows
            ]

    def get_course_offering_by_org_and_course(self, organization_id: str, course_id: str) -> Optional[CourseOffering]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM organization_course_offerings WHERE org_id = ? AND course_id = ? AND is_active = 1 LIMIT 1;"
            r = conn.execute(sql, (organization_id, course_id)).fetchone()
            if r:
                return CourseOffering(
                    id=r["id"],
                    organization_id=r["org_id"],
                    course_id=r["course_id"],
                    pinned_version_id=r["pinned_version_id"],
                    is_active=bool(r["is_active"]),
                    enrolled_at=r["enrolled_at"],
                )
            return None

    def get_offerings_by_course(self, course_id: str) -> List[CourseOffering]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM organization_course_offerings WHERE course_id = ? AND is_active = 1;"
            rows = conn.execute(sql, (course_id,)).fetchall()
            return [
                CourseOffering(
                    id=r["id"],
                    organization_id=r["org_id"],
                    course_id=r["course_id"],
                    pinned_version_id=r["pinned_version_id"],
                    is_active=bool(r["is_active"]),
                    enrolled_at=r["enrolled_at"],
                )
                for r in rows
            ]


    def create_subject(self, subject: Subject) -> Subject:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO subjects (id, course_id, name, code, created_at) VALUES (?, ?, ?, ?, ?);",
                (subject.id, subject.course_id, subject.name, subject.code, subject.created_at),
            )
        return subject

    def create_curriculum(self, curriculum: Curriculum) -> Curriculum:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO curricula (id, course_id, title, board, metadata, version, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    course_id=excluded.course_id,
                    title=excluded.title,
                    board=excluded.board,
                    metadata=excluded.metadata,
                    version=excluded.version,
                    is_active=excluded.is_active,
                    created_at=excluded.created_at;
                """,
                (
                    curriculum.id, 
                    curriculum.course_id, 
                    curriculum.title, 
                    curriculum.board.value,
                    json.dumps(curriculum.metadata),
                    curriculum.version, 
                    1 if curriculum.is_active else 0, 
                    curriculum.created_at
                ),
            )
        return curriculum

    def get_curriculum(self, curriculum_id: str) -> Optional[Curriculum]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM curricula WHERE id = ?;", (curriculum_id,)).fetchone()
            if r:
                # Handle migrations gracefully where board/metadata might not be fetched 
                # if sqlite PRAGMA table_info is out of sync in tests
                board_val = r["board"] if "board" in r.keys() else "custom"
                metadata_val = r["metadata"] if "metadata" in r.keys() else "{}"
                return Curriculum(
                    id=r["id"],
                    course_id=r["course_id"],
                    title=r["title"],
                    board=CurriculumBoard(board_val),
                    metadata=json.loads(metadata_val) if metadata_val else {},
                    version=r["version"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                )
            return None

    def get_curriculum_for_course(self, course_id: str) -> Optional[Curriculum]:
        with self._get_connection() as conn:
            r = conn.execute(
                "SELECT * FROM curricula WHERE course_id = ? AND is_active = 1 ORDER BY created_at DESC;",
                (course_id,),
            ).fetchone()
            if r:
                board_val = r["board"] if "board" in r.keys() else "custom"
                metadata_val = r["metadata"] if "metadata" in r.keys() else "{}"
                return Curriculum(
                    id=r["id"],
                    course_id=r["course_id"],
                    title=r["title"],
                    board=CurriculumBoard(board_val),
                    metadata=json.loads(metadata_val) if metadata_val else {},
                    version=r["version"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                )
            return None

    def create_curriculum_version(self, cv: CurriculumVersion) -> CurriculumVersion:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO curriculum_versions 
                (id, curriculum_id, version_num, change_log, status, published_at, schema_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    curriculum_id=excluded.curriculum_id,
                    version_num=excluded.version_num,
                    change_log=excluded.change_log,
                    status=excluded.status,
                    published_at=excluded.published_at,
                    schema_data=excluded.schema_data,
                    created_at=excluded.created_at;
                """,
                (cv.id, cv.curriculum_id, cv.version_num, cv.change_log, cv.status, cv.published_at, cv.schema_data, cv.created_at),
            )
        return cv

    def get_curriculum_version(self, version_id: str) -> Optional[CurriculumVersion]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM curriculum_versions WHERE id = ?;", (version_id,)).fetchone()
            if r:
                return CurriculumVersion(
                    id=r["id"],
                    curriculum_id=r["curriculum_id"],
                    version_num=r["version_num"],
                    change_log=r["change_log"] or "",
                    status=r["status"] if "status" in r.keys() else "draft",
                    published_at=r["published_at"] if "published_at" in r.keys() else None,
                    schema_data=r["schema_data"] if "schema_data" in r.keys() else "{}",
                    created_at=r["created_at"],
                )
            return None

    def get_curriculum_versions(self, curriculum_id: str) -> List[CurriculumVersion]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM curriculum_versions WHERE curriculum_id = ? ORDER BY created_at DESC;",
                (curriculum_id,),
            ).fetchall()
            return [
                CurriculumVersion(
                    id=r["id"],
                    curriculum_id=r["curriculum_id"],
                    version_num=r["version_num"],
                    change_log=r["change_log"] or "",
                    status=r["status"] if "status" in r.keys() else "draft",
                    published_at=r["published_at"] if "published_at" in r.keys() else None,
                    schema_data=r["schema_data"] if "schema_data" in r.keys() else "{}",
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def update_curriculum_version_status(self, version_id: str, status: str, published_at: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            if published_at:
                c = conn.execute(
                    "UPDATE curriculum_versions SET status = ?, published_at = ? WHERE id = ?;",
                    (status, published_at, version_id),
                )
            else:
                c = conn.execute(
                    "UPDATE curriculum_versions SET status = ? WHERE id = ?;",
                    (status, version_id),
                )
            return c.rowcount > 0

    def update_curriculum_version_schema(self, version_id: str, schema_data: str) -> bool:
        with self._get_connection() as conn:
            c = conn.execute(
                "UPDATE curriculum_versions SET schema_data = ? WHERE id = ?;",
                (schema_data, version_id),
            )
            return c.rowcount > 0

    def get_subjects_by_course(self, course_id: str) -> List[Subject]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM subjects WHERE course_id = ? ORDER BY name ASC;", (course_id,)).fetchall()
            return [
                Subject(
                    id=r["id"],
                    course_id=r["course_id"],
                    name=r["name"],
                    code=r["code"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def get_modules_by_curriculum(self, curriculum_id: str) -> List[Module]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM modules WHERE curriculum_id = ? ORDER BY sequence_order ASC;",
                (curriculum_id,),
            ).fetchall()
            return [
                Module(
                    id=r["id"],
                    curriculum_id=r["curriculum_id"],
                    title=r["title"],
                    sequence_order=int(r["sequence_order"]),
                    subject_id=r["subject_id"] if "subject_id" in r.keys() else None,
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def get_topics_by_module(self, module_id: str) -> List[Topic]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM topics WHERE module_id = ? ORDER BY sequence_order ASC;",
                (module_id,),
            ).fetchall()
            return [
                Topic(
                    id=r["id"],
                    module_id=r["module_id"],
                    title=r["title"],
                    sequence_order=int(r["sequence_order"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def get_concepts_by_topic(self, topic_id: str) -> List[Concept]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM concepts WHERE topic_id = ? ORDER BY difficulty ASC;",
                (topic_id,),
            ).fetchall()
            return [
                Concept(
                    id=r["id"],
                    topic_id=r["topic_id"],
                    name=r["name"],
                    description=r["description"],
                    difficulty=float(r["difficulty"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def create_module(self, mod: Module) -> Module:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO modules (id, curriculum_id, title, sequence_order, subject_id, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                (mod.id, mod.curriculum_id, mod.title, mod.sequence_order, mod.subject_id, mod.created_at),
            )
        return mod

    def create_topic(self, topic: Topic) -> Topic:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO topics (id, module_id, title, sequence_order, created_at) VALUES (?, ?, ?, ?, ?);",
                (topic.id, topic.module_id, topic.title, topic.sequence_order, topic.created_at),
            )
        return topic

    def create_concept(self, concept: Concept) -> Concept:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO concepts (id, topic_id, name, description, difficulty, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                (concept.id, concept.topic_id, concept.name, concept.description, concept.difficulty, concept.created_at),
            )
        return concept

    def get_concept(self, concept_id: str) -> Optional[Concept]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM concepts WHERE id = ?;", (concept_id,)).fetchone()
            if r:
                return Concept(
                    id=r["id"],
                    topic_id=r["topic_id"],
                    name=r["name"],
                    description=r["description"],
                    difficulty=float(r["difficulty"]),
                    created_at=r["created_at"],
                )
            return None

    def add_prerequisite(self, prereq: Prerequisite) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO prerequisites (prerequisite_concept_id, dependent_concept_id) VALUES (?, ?);",
                (prereq.prerequisite_concept_id, prereq.dependent_concept_id),
            )

    def get_prerequisites_for_concept(self, concept_id: str) -> List[str]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT prerequisite_concept_id FROM prerequisites WHERE dependent_concept_id = ?;",
                (concept_id,),
            ).fetchall()
            return [r[0] for r in rows]

    # ── 3. Class Groups & Enrollments ────────────────────────────────────────

    def create_class_group(self, class_group: ClassGroup) -> ClassGroup:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO class_groups (id, organization_id, course_id, name, section, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                (class_group.id, class_group.organization_id, class_group.course_id, class_group.name, class_group.section, class_group.created_at),
            )
        return class_group

    def get_class_group(self, class_id: str) -> Optional[ClassGroup]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM class_groups WHERE id = ?;", (class_id,)).fetchone()
            if r:
                return ClassGroup(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    course_id=r["course_id"],
                    name=r["name"],
                    section=r["section"] if "section" in r.keys() else "A",
                    created_at=r["created_at"],
                )
            return None

    def list_class_groups_by_organization(self, organization_id: str) -> List[ClassGroup]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM class_groups WHERE organization_id = ? ORDER BY name ASC;",
                (organization_id,),
            ).fetchall()
            return [
                ClassGroup(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    course_id=r["course_id"],
                    name=r["name"],
                    section=r["section"] if "section" in r.keys() else "A",
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def list_class_groups_by_course(self, course_id: str, organization_id: Optional[str] = None) -> List[ClassGroup]:
        with self._get_connection() as conn:
            if organization_id:
                rows = conn.execute(
                    "SELECT * FROM class_groups WHERE course_id = ? AND organization_id = ? ORDER BY name ASC;",
                    (course_id, organization_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM class_groups WHERE course_id = ? ORDER BY name ASC;",
                    (course_id,),
                ).fetchall()
            return [
                ClassGroup(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    course_id=r["course_id"],
                    name=r["name"],
                    section=r["section"] if "section" in r.keys() else "A",
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def get_students_for_class_group(self, class_id: str) -> List[User]:
        """Resolve all enrolled students belonging to this class group."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT u.* FROM users u
                JOIN enrollments e ON u.id = e.student_id
                JOIN cohorts c ON e.cohort_id = c.id
                WHERE c.class_group_id = ? AND e.is_active = 1
                ORDER BY u.full_name ASC;
                """,
                (class_id,),
            ).fetchall()
            if not rows:
                cg = conn.execute("SELECT course_id, organization_id FROM class_groups WHERE id = ?;", (class_id,)).fetchone()
                if cg:
                    rows = conn.execute(
                        """
                        SELECT DISTINCT u.* FROM users u
                        JOIN enrollments e ON u.id = e.student_id
                        WHERE e.course_id = ? AND u.organization_id = ? AND e.is_active = 1
                        ORDER BY u.full_name ASC;
                        """,
                        (cg["course_id"], cg["organization_id"]),
                    ).fetchall()

            return [
                User(
                    id=r["id"],
                    email=r["email"],
                    full_name=r["full_name"],
                    role=UserRole(r["role"]),
                    organization_id=r["organization_id"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]),
                    deleted_at=r["deleted_at"],
                )
                for r in rows
            ]

    def create_cohort(self, cohort: Cohort) -> Cohort:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cohorts (id, class_group_id, name, academic_year, created_at) VALUES (?, ?, ?, ?, ?);",
                (cohort.id, cohort.class_group_id, cohort.name, cohort.academic_year, cohort.created_at),
            )
        return cohort

    def get_cohort(self, cohort_id: str) -> Optional[Cohort]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM cohorts WHERE id = ?;", (cohort_id,)).fetchone()
            if r:
                return Cohort(
                    id=r["id"],
                    class_group_id=r["class_group_id"],
                    name=r["name"],
                    academic_year=r["academic_year"],
                    created_at=r["created_at"],
                )
            return None

    def get_cohorts_for_class_group(self, class_group_id: str) -> List[Cohort]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM cohorts WHERE class_group_id = ? ORDER BY created_at ASC;",
                (class_group_id,),
            ).fetchall()
            return [
                Cohort(
                    id=r["id"],
                    class_group_id=r["class_group_id"],
                    name=r["name"],
                    academic_year=r["academic_year"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def create_enrollment(self, enrollment: Enrollment) -> Enrollment:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO enrollments (id, student_id, course_id, cohort_id, enrolled_at, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                (enrollment.id, enrollment.student_id, enrollment.course_id, enrollment.cohort_id, enrollment.enrolled_at, 1 if enrollment.is_active else 0),
            )
        return enrollment

    def get_enrollments_for_student(self, student_id: str) -> List[Enrollment]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM enrollments WHERE student_id = ? AND is_active = 1;",
                (student_id,),
            ).fetchall()
            return [
                Enrollment(
                    id=r["id"],
                    student_id=r["student_id"],
                    course_id=r["course_id"],
                    cohort_id=r["cohort_id"],
                    enrolled_at=r["enrolled_at"],
                    is_active=bool(r["is_active"]),
                )
                for r in rows
            ]

    # ── 4. Sessions & Granular Telemetry ─────────────────────────────────────

    def create_session(self, session: Session) -> Session:
        with self._get_connection() as conn:
            status_val = session.status.value if isinstance(session.status, SessionStatus) else str(session.status)
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions 
                (id, student_id, course_id, concept_id, status, started_at, ended_at, course_version_id, class_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    session.id,
                    session.student_id,
                    session.course_id,
                    session.concept_id,
                    status_val,
                    session.started_at,
                    session.ended_at,
                    session.course_version_id,
                    session.class_id,
                ),
            )
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM sessions WHERE id = ?;", (session_id,)).fetchone()
            if r:
                keys = r.keys()
                return Session(
                    id=r["id"],
                    student_id=r["student_id"],
                    course_id=r["course_id"],
                    concept_id=r["concept_id"],
                    status=SessionStatus(r["status"]),
                    started_at=r["started_at"],
                    ended_at=r["ended_at"],
                    course_version_id=r["course_version_id"] if "course_version_id" in keys else None,
                    class_id=r["class_id"] if "class_id" in keys else None,
                )
            return None

    def end_session(self, session_id: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET status = 'completed', ended_at = ? WHERE id = ? AND status = 'active';",
                (now_iso, session_id),
            )
            return cursor.rowcount > 0

    def update_session_status(self, session_id: str, status: SessionStatus | str) -> bool:
        status_val = status.value if hasattr(status, "value") else str(status)
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET status = ?, ended_at = CASE WHEN ? = 'completed' THEN ? ELSE ended_at END WHERE id = ?;",
                (status_val, status_val, now_iso, session_id),
            )
            return cursor.rowcount > 0

    def get_sessions_for_student(self, student_id: str, course_id: Optional[str] = None, limit: int = 20) -> List[Session]:
        with self._get_connection() as conn:
            if course_id:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE student_id = ? AND course_id = ? ORDER BY started_at DESC LIMIT ?;",
                    (student_id, course_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE student_id = ? ORDER BY started_at DESC LIMIT ?;",
                    (student_id, limit),
                ).fetchall()
            result = []
            for r in rows:
                keys = r.keys()
                result.append(
                    Session(
                        id=r["id"],
                        student_id=r["student_id"],
                        course_id=r["course_id"],
                        concept_id=r["concept_id"],
                        status=SessionStatus(r["status"]),
                        started_at=r["started_at"],
                        ended_at=r["ended_at"],
                        course_version_id=r["course_version_id"] if "course_version_id" in keys else None,
                        class_id=r["class_id"] if "class_id" in keys else None,
                    )
                )
            return result


    def record_learning_event(self, event: LearningEvent) -> LearningEvent:
        with self._get_connection() as conn:
            payload_str = json.dumps(event.payload) if isinstance(event.payload, dict) else str(event.payload)
            conn.execute(
                """
                INSERT OR IGNORE INTO learning_events 
                (id, session_id, student_id, organization_id, course_id, concept_id, event_type, source, payload, score, schema_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.id,
                    event.session_id,
                    event.student_id,
                    event.organization_id,
                    event.course_id,
                    event.concept_id or "",
                    event.event_type,
                    event.source or "student_desktop",
                    payload_str,
                    event.score,
                    event.schema_version or "1.0.0",
                    event.created_at,
                ),
            )
        return event

    def record_learning_events_batch(self, events: List[LearningEvent]) -> List[LearningEvent]:
        if not events:
            return []
        rows = [
            (
                e.id,
                e.session_id,
                e.student_id,
                e.organization_id,
                e.course_id,
                e.concept_id or "",
                e.event_type,
                e.source or "student_desktop",
                json.dumps(e.payload) if isinstance(e.payload, dict) else str(e.payload),
                e.score,
                e.schema_version or "1.0.0",
                e.created_at,
            )
            for e in events
        ]
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO learning_events 
                (id, session_id, student_id, organization_id, course_id, concept_id, event_type, source, payload, score, schema_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows,
            )
        return events

    def get_existing_learning_event_ids(self, event_ids: List[str]) -> Set[str]:
        if not event_ids:
            return set()
        existing: Set[str] = set()
        chunk_size = 500
        with self._get_connection() as conn:
            for i in range(0, len(event_ids), chunk_size):
                chunk = event_ids[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(f"SELECT id FROM learning_events WHERE id IN ({placeholders});", chunk).fetchall()
                for r in rows:
                    existing.add(r[0])
        return existing

    def get_learning_event(self, event_id: str) -> Optional[LearningEvent]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM learning_events WHERE id = ?;", (event_id,)).fetchone()
            if r:
                return self._row_to_learning_event(r)
            return None

    def get_learning_events_for_session(self, session_id: str) -> List[LearningEvent]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM learning_events WHERE session_id = ? ORDER BY created_at ASC, id ASC;",
                (session_id,),
            ).fetchall()
            return [self._row_to_learning_event(r) for r in rows]

    def query_learning_events(
        self,
        student_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        course_id: Optional[str] = None,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
    ) -> List[LearningEvent]:
        query = "SELECT * FROM learning_events WHERE 1=1"
        params: List[Any] = []
        if student_id:
            query += " AND student_id = ?"
            params.append(student_id)
        if organization_id:
            query += " AND organization_id = ?"
            params.append(organization_id)
        if course_id:
            query += " AND course_id = ?"
            params.append(course_id)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if since:
            query += " AND created_at >= ?"
            params.append(since)
        if until:
            query += " AND created_at <= ?"
            params.append(until)
        query += " ORDER BY created_at ASC, id ASC LIMIT ?;"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._row_to_learning_event(r) for r in rows]

    def _row_to_learning_event(self, r: sqlite3.Row) -> LearningEvent:
        keys = r.keys()
        payload_data = {}
        raw_payload = r["payload"]
        if raw_payload and raw_payload.startswith("{"):
            try:
                payload_data = json.loads(raw_payload)
            except Exception:
                payload_data = {}
        return LearningEvent(
            id=r["id"],
            session_id=r["session_id"],
            student_id=r["student_id"],
            concept_id=r["concept_id"] if "concept_id" in keys else "",
            event_type=r["event_type"],
            organization_id=r["organization_id"] if "organization_id" in keys else None,
            course_id=r["course_id"] if "course_id" in keys else None,
            course_version_id=r["course_version_id"] if "course_version_id" in keys else None,
            source=r["source"] if "source" in keys and r["source"] else "student_desktop",
            payload=payload_data,
            score=float(r["score"]) if r["score"] is not None else None,
            schema_version=r["schema_version"] if "schema_version" in keys and r["schema_version"] else "1.0.0",
            created_at=r["created_at"],
        )


    # ── 5. Student Learning Records & Mastery ────────────────────────────────

    def create_slr(self, slr: StudentLearningRecord) -> StudentLearningRecord:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO student_learning_records (id, student_id, course_id, authoritative, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?);",
                (slr.id, slr.student_id, slr.course_id, 1 if slr.authoritative else 0, slr.created_at, slr.updated_at),
            )
        return slr

    def get_slr(self, student_id: str, course_id: Optional[str] = None) -> Optional[StudentLearningRecord]:
        with self._get_connection() as conn:
            if course_id:
                r = conn.execute(
                    "SELECT * FROM student_learning_records WHERE student_id = ? AND course_id = ?;",
                    (student_id, course_id),
                ).fetchone()
            else:
                r = conn.execute(
                    "SELECT * FROM student_learning_records WHERE student_id = ? ORDER BY updated_at DESC LIMIT 1;",
                    (student_id,),
                ).fetchone()
            if r:
                return StudentLearningRecord(
                    id=r["id"],
                    student_id=r["student_id"],
                    course_id=r["course_id"],
                    authoritative=bool(r["authoritative"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
            return None

    def get_student_learning_record(self, student_id: str, course_id: Optional[str] = None) -> Optional[StudentLearningRecord]:
        return self.get_slr(student_id, course_id)

    def upsert_mastery_state(self, state: MasteryState) -> MasteryState:
        # Clamp score/confidence to [0.0, 1.0] as a hard DB-level safety net
        state.score = max(0.0, min(1.0, round(state.score, 4)))
        state.confidence = max(0.0, min(1.0, round(state.confidence, 4)))
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO mastery_states (id, slr_id, concept_id, score, confidence, updated_at) VALUES (?, ?, ?, ?, ?, ?);",
                (state.id, state.slr_id, state.concept_id, state.score, state.confidence, state.updated_at),
            )
        return state

    def get_mastery_states_for_slr(self, slr_id: str) -> List[MasteryState]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM mastery_states WHERE slr_id = ?;", (slr_id,)).fetchall()
            return [
                MasteryState(
                    id=r["id"],
                    slr_id=r["slr_id"],
                    concept_id=r["concept_id"],
                    score=float(r["score"]),
                    confidence=float(r["confidence"]),
                    updated_at=r["updated_at"],
                )
                for r in rows
            ]

    def get_mastery_states(self, student_id: str, course_id: Optional[str] = None) -> List[MasteryState]:
        slr = self.get_slr(student_id, course_id=course_id)
        if not slr:
            return []
        return self.get_mastery_states_for_slr(slr.id)


    def create_misconception(self, misc: Misconception) -> Misconception:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO misconceptions (id, code, category, name, description, remediation) VALUES (?, ?, ?, ?, ?, ?);",
                (misc.id, misc.code, misc.category, misc.name, misc.description, misc.remediation),
            )
        return misc

    def record_student_misconception(self, record: StudentMisconceptionRecord) -> StudentMisconceptionRecord:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO student_misconceptions (id, student_id, misconception_code, frequency, last_observed) VALUES (?, ?, ?, ?, ?);",
                (record.id, record.student_id, record.misconception_code, record.frequency, record.last_observed),
            )
        return record

    def get_student_misconceptions(self, student_id: str) -> List[StudentMisconceptionRecord]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM student_misconceptions WHERE student_id = ? ORDER BY frequency DESC;",
                (student_id,),
            ).fetchall()
            return [
                StudentMisconceptionRecord(
                    id=r["id"],
                    student_id=r["student_id"],
                    misconception_code=r["misconception_code"],
                    frequency=int(r["frequency"]),
                    last_observed=r["last_observed"],
                )
                for r in rows
            ]

    def get_misconception_by_code(self, code: str) -> Optional[Misconception]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM misconceptions WHERE code = ?;", (code,)).fetchone()
            if r:
                return Misconception(
                    id=r["id"],
                    code=r["code"],
                    category=r["category"],
                    name=r["name"],
                    description=r["description"] or "",
                    remediation=r["remediation"] or "",
                )
            return None

    # ── 6. Assessments & Question Bank ───────────────────────────────────────

    def create_question_bank_item(self, item: QuestionBankItem) -> QuestionBankItem:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO question_bank_items (
                    id, course_id, organization_id, subject_id, concept_id, topic_id,
                    question_text, item_type, options, correct_answer, rubric,
                    difficulty, bloom_level, hints, explanation, tags, is_active,
                    created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item.id,
                    item.course_id,
                    item.organization_id,
                    item.subject_id,
                    item.concept_id,
                    item.topic_id,
                    item.question_text,
                    item.item_type,
                    json.dumps(item.options),
                    item.correct_answer,
                    json.dumps(item.rubric),
                    item.difficulty,
                    item.bloom_level,
                    json.dumps(item.hints),
                    item.explanation,
                    json.dumps(item.tags),
                    1 if item.is_active else 0,
                    item.created_by,
                    item.created_at,
                ),
            )
        return item

    def get_question_bank_item(self, item_id: str) -> Optional[QuestionBankItem]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM question_bank_items WHERE id = ?;", (item_id,)).fetchone()
            if r:
                return QuestionBankItem(
                    id=r["id"],
                    course_id=r["course_id"],
                    organization_id=r["organization_id"] if "organization_id" in r.keys() else None,
                    subject_id=r["subject_id"] if "subject_id" in r.keys() else None,
                    concept_id=r["concept_id"] if "concept_id" in r.keys() else "",
                    topic_id=r["topic_id"] if "topic_id" in r.keys() else "",
                    question_text=r["question_text"],
                    item_type=r["item_type"],
                    options=json.loads(r["options"]) if "options" in r.keys() and r["options"] else [],
                    correct_answer=r["correct_answer"] if "correct_answer" in r.keys() else "",
                    rubric=json.loads(r["rubric"]) if "rubric" in r.keys() and r["rubric"] else {},
                    difficulty=int(r["difficulty"]) if "difficulty" in r.keys() else 1,
                    bloom_level=r["bloom_level"] if "bloom_level" in r.keys() else "recall",
                    hints=json.loads(r["hints"]) if "hints" in r.keys() and r["hints"] else [],
                    explanation=r["explanation"] if "explanation" in r.keys() else "",
                    tags=json.loads(r["tags"]) if "tags" in r.keys() and r["tags"] else [],
                    is_active=bool(r["is_active"]) if "is_active" in r.keys() else True,
                    created_by=r["created_by"] if "created_by" in r.keys() else None,
                    created_at=r["created_at"],
                )
            return None

    def list_question_bank_items(
        self,
        course_id: Optional[str] = None,
        concept_id: Optional[str] = None,
        difficulty: Optional[int] = None,
        item_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[QuestionBankItem]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM question_bank_items WHERE is_active = 1"
            params: list = []
            if course_id:
                sql += " AND course_id = ?"
                params.append(course_id)
            if concept_id:
                sql += " AND concept_id = ?"
                params.append(concept_id)
            if difficulty is not None:
                sql += " AND difficulty = ?"
                params.append(difficulty)
            if item_type:
                sql += " AND item_type = ?"
                params.append(item_type)
            sql += " ORDER BY created_at DESC LIMIT ?;"
            params.append(limit)

            rows = conn.execute(sql, tuple(params)).fetchall()
            return [
                QuestionBankItem(
                    id=r["id"],
                    course_id=r["course_id"],
                    organization_id=r["organization_id"] if "organization_id" in r.keys() else None,
                    subject_id=r["subject_id"] if "subject_id" in r.keys() else None,
                    concept_id=r["concept_id"] if "concept_id" in r.keys() else "",
                    topic_id=r["topic_id"] if "topic_id" in r.keys() else "",
                    question_text=r["question_text"],
                    item_type=r["item_type"],
                    options=json.loads(r["options"]) if "options" in r.keys() and r["options"] else [],
                    correct_answer=r["correct_answer"] if "correct_answer" in r.keys() else "",
                    rubric=json.loads(r["rubric"]) if "rubric" in r.keys() and r["rubric"] else {},
                    difficulty=int(r["difficulty"]) if "difficulty" in r.keys() else 1,
                    bloom_level=r["bloom_level"] if "bloom_level" in r.keys() else "recall",
                    hints=json.loads(r["hints"]) if "hints" in r.keys() and r["hints"] else [],
                    explanation=r["explanation"] if "explanation" in r.keys() else "",
                    tags=json.loads(r["tags"]) if "tags" in r.keys() and r["tags"] else [],
                    is_active=bool(r["is_active"]) if "is_active" in r.keys() else True,
                    created_by=r["created_by"] if "created_by" in r.keys() else None,
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def create_assessment(self, asmt: Assessment) -> Assessment:
        with self._get_connection() as conn:
            type_val = asmt.assessment_type.value if isinstance(asmt.assessment_type, AssessmentType) else str(asmt.assessment_type)
            conn.execute(
                """
                INSERT OR REPLACE INTO assessments (
                    id, course_id, title, assessment_type, total_marks,
                    organization_id, description, duration_minutes, passing_score,
                    item_ids, config, rubric, status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    asmt.id,
                    asmt.course_id,
                    asmt.title,
                    type_val,
                    asmt.total_marks,
                    asmt.organization_id,
                    asmt.description,
                    asmt.duration_minutes,
                    asmt.passing_score,
                    json.dumps(asmt.item_ids),
                    json.dumps(asmt.config),
                    json.dumps(asmt.rubric),
                    asmt.status,
                    asmt.created_by,
                    asmt.created_at,
                    asmt.updated_at or asmt.created_at,
                ),
            )
        return asmt

    def get_assessment(self, assessment_id: str) -> Optional[Assessment]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM assessments WHERE id = ?;", (assessment_id,)).fetchone()
            if r:
                return Assessment(
                    id=r["id"],
                    course_id=r["course_id"],
                    title=r["title"],
                    assessment_type=AssessmentType(r["assessment_type"]),
                    total_marks=float(r["total_marks"]),
                    organization_id=r["organization_id"] if "organization_id" in r.keys() else None,
                    description=r["description"] if "description" in r.keys() else "",
                    duration_minutes=int(r["duration_minutes"]) if "duration_minutes" in r.keys() else 0,
                    passing_score=float(r["passing_score"]) if "passing_score" in r.keys() else 70.0,
                    item_ids=json.loads(r["item_ids"]) if "item_ids" in r.keys() and r["item_ids"] else [],
                    config=json.loads(r["config"]) if "config" in r.keys() and r["config"] else {},
                    rubric=json.loads(r["rubric"]) if "rubric" in r.keys() and r["rubric"] else {},
                    status=r["status"] if "status" in r.keys() else "published",
                    created_by=r["created_by"] if "created_by" in r.keys() else None,
                    created_at=r["created_at"],
                    updated_at=r["updated_at"] if "updated_at" in r.keys() and r["updated_at"] else r["created_at"],
                )
            return None

    def list_assessments(
        self,
        course_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        assessment_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Assessment]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM assessments WHERE 1=1"
            params: list = []
            if course_id:
                sql += " AND course_id = ?"
                params.append(course_id)
            if organization_id:
                sql += " AND organization_id = ?"
                params.append(organization_id)
            if assessment_type:
                sql += " AND assessment_type = ?"
                params.append(assessment_type)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC LIMIT ?;"
            params.append(limit)

            rows = conn.execute(sql, tuple(params)).fetchall()
            return [
                Assessment(
                    id=r["id"],
                    course_id=r["course_id"],
                    title=r["title"],
                    assessment_type=AssessmentType(r["assessment_type"]),
                    total_marks=float(r["total_marks"]),
                    organization_id=r["organization_id"] if "organization_id" in r.keys() else None,
                    description=r["description"] if "description" in r.keys() else "",
                    duration_minutes=int(r["duration_minutes"]) if "duration_minutes" in r.keys() else 0,
                    passing_score=float(r["passing_score"]) if "passing_score" in r.keys() else 70.0,
                    item_ids=json.loads(r["item_ids"]) if "item_ids" in r.keys() and r["item_ids"] else [],
                    config=json.loads(r["config"]) if "config" in r.keys() and r["config"] else {},
                    rubric=json.loads(r["rubric"]) if "rubric" in r.keys() and r["rubric"] else {},
                    status=r["status"] if "status" in r.keys() else "published",
                    created_by=r["created_by"] if "created_by" in r.keys() else None,
                    created_at=r["created_at"],
                    updated_at=r["updated_at"] if "updated_at" in r.keys() and r["updated_at"] else r["created_at"],
                )
                for r in rows
            ]

    def create_assessment_item(self, item: AssessmentItem) -> AssessmentItem:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO assessment_items (
                    id, assessment_id, question_text, item_type, correct_answer, max_marks,
                    concept_id, options, rubric, difficulty, hints, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    item.id,
                    item.assessment_id,
                    item.question_text,
                    item.item_type,
                    item.correct_answer,
                    item.max_marks,
                    item.concept_id,
                    json.dumps(item.options),
                    json.dumps(item.rubric),
                    item.difficulty,
                    json.dumps(item.hints),
                    item.explanation,
                ),
            )
        return item

    def get_assessment_items(self, assessment_id: str) -> List[AssessmentItem]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM assessment_items WHERE assessment_id = ?;", (assessment_id,)).fetchall()
            return [
                AssessmentItem(
                    id=r["id"],
                    assessment_id=r["assessment_id"],
                    question_text=r["question_text"],
                    item_type=r["item_type"],
                    correct_answer=r["correct_answer"],
                    max_marks=float(r["max_marks"]),
                    concept_id=r["concept_id"] if "concept_id" in r.keys() else "",
                    options=json.loads(r["options"]) if "options" in r.keys() and r["options"] else [],
                    rubric=json.loads(r["rubric"]) if "rubric" in r.keys() and r["rubric"] else {},
                    difficulty=int(r["difficulty"]) if "difficulty" in r.keys() else 1,
                    hints=json.loads(r["hints"]) if "hints" in r.keys() and r["hints"] else [],
                    explanation=r["explanation"] if "explanation" in r.keys() else "",
                )
                for r in rows
            ]

    def create_assignment(self, assignment: Assignment) -> Assignment:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO assignments (
                    id, course_id, assessment_id, title, organization_id,
                    cohort_id, class_group_id, assigned_by, teacher_id, instructions, due_at, due_date, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    assignment.id,
                    assignment.course_id,
                    assignment.assessment_id or "",
                    assignment.title,
                    assignment.organization_id,
                    assignment.cohort_id,
                    assignment.class_group_id,
                    assignment.assigned_by or assignment.teacher_id,
                    assignment.teacher_id or assignment.assigned_by,
                    assignment.instructions,
                    assignment.due_at or assignment.due_date,
                    assignment.due_date or assignment.due_at,
                    1 if assignment.is_active else 0,
                    assignment.created_at,
                ),
            )
        return assignment

    def get_assignment(self, assignment_id: str) -> Optional[Assignment]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM assignments WHERE id = ?;", (assignment_id,)).fetchone()
            if r:
                return Assignment(
                    id=r["id"],
                    course_id=r["course_id"],
                    assessment_id=r["assessment_id"],
                    title=r["title"],
                    organization_id=r["organization_id"] if "organization_id" in r.keys() else None,
                    cohort_id=r["cohort_id"] if "cohort_id" in r.keys() else None,
                    class_group_id=r["class_group_id"] if "class_group_id" in r.keys() else None,
                    assigned_by=r["assigned_by"] if "assigned_by" in r.keys() else None,
                    instructions=r["instructions"] if "instructions" in r.keys() else "",
                    due_at=r["due_at"] if "due_at" in r.keys() else None,
                    is_active=bool(r["is_active"]) if "is_active" in r.keys() else True,
                    created_at=r["created_at"],
                )
            return None

    def list_assignments(
        self,
        course_id: Optional[str] = None,
        cohort_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        class_group_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Assignment]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM assignments WHERE is_active = 1"
            params: list = []
            if course_id:
                sql += " AND course_id = ?"
                params.append(course_id)
            if cohort_id:
                sql += " AND cohort_id = ?"
                params.append(cohort_id)
            if class_group_id:
                sql += " AND class_group_id = ?"
                params.append(class_group_id)
            if organization_id:
                sql += " AND organization_id = ?"
                params.append(organization_id)
            sql += " ORDER BY created_at DESC LIMIT ?;"
            params.append(limit)

            rows = conn.execute(sql, tuple(params)).fetchall()
            return [
                Assignment(
                    id=r["id"],
                    course_id=r["course_id"],
                    assessment_id=r["assessment_id"],
                    title=r["title"],
                    organization_id=r["organization_id"] if "organization_id" in r.keys() else None,
                    cohort_id=r["cohort_id"] if "cohort_id" in r.keys() else None,
                    class_group_id=r["class_group_id"] if "class_group_id" in r.keys() else None,
                    assigned_by=r["assigned_by"] if "assigned_by" in r.keys() else None,
                    instructions=r["instructions"] if "instructions" in r.keys() else "",
                    due_at=r["due_at"] if "due_at" in r.keys() else None,
                    is_active=bool(r["is_active"]) if "is_active" in r.keys() else True,
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def get_assignments_for_student(self, student_id: str, course_id: str) -> List[Assignment]:
        """Retrieve assignments accessible to the student for a given course."""
        enrollments = self.get_enrollments_for_student(student_id)
        enr = next((e for e in enrollments if e.course_id == course_id), None)
        if not enr:
            return []

        class_id = None
        if enr.cohort_id:
            cohort = self.get_cohort(enr.cohort_id)
            if cohort and cohort.class_group_id:
                class_id = cohort.class_group_id

        with self._get_connection() as conn:
            params: list = [course_id]
            if class_id:
                sql = """
                    SELECT * FROM assignments
                    WHERE course_id = ? AND is_active = 1
                      AND (class_group_id IS NULL OR class_group_id = '' OR class_group_id = ?)
                    ORDER BY created_at DESC;
                """
                params.append(class_id)
            else:
                sql = """
                    SELECT * FROM assignments
                    WHERE course_id = ? AND is_active = 1
                      AND (class_group_id IS NULL OR class_group_id = '')
                    ORDER BY created_at DESC;
                """
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [
                Assignment(
                    id=r["id"],
                    course_id=r["course_id"],
                    assessment_id=r["assessment_id"],
                    title=r["title"],
                    organization_id=r["organization_id"] if "organization_id" in r.keys() else None,
                    cohort_id=r["cohort_id"] if "cohort_id" in r.keys() else None,
                    class_group_id=r["class_group_id"] if "class_group_id" in r.keys() else None,
                    assigned_by=r["assigned_by"] if "assigned_by" in r.keys() else None,
                    instructions=r["instructions"] if "instructions" in r.keys() else "",
                    due_at=r["due_at"] if "due_at" in r.keys() else None,
                    is_active=bool(r["is_active"]) if "is_active" in r.keys() else True,
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def get_knowledge_sources_for_student(self, student_id: str, course_id: str) -> List[RAGSource]:
        """Retrieve published knowledge sources authorized for this student in this course."""
        enrollments = self.get_enrollments_for_student(student_id)
        enr = next((e for e in enrollments if e.course_id == course_id), None)
        if not enr:
            return []

        class_id = None
        if enr.cohort_id:
            cohort = self.get_cohort(enr.cohort_id)
            if cohort and cohort.class_group_id:
                class_id = cohort.class_group_id

        sources = self.list_rag_sources(course_id=course_id, status="published")
        authorized = []
        for s in sources:
            scope = (s.visibility_scope or "course").lower()
            if scope in ("course", "public"):
                authorized.append(s)
            elif scope == "class":
                if class_id and s.class_id == class_id:
                    authorized.append(s)
            elif scope == "student_targeted":
                targets = s.target_student_ids or []
                if isinstance(targets, str):
                    try:
                        targets = json.loads(targets)
                    except Exception:
                        targets = [targets]
                if student_id in targets:
                    authorized.append(s)
        return authorized

    def record_assessment_attempt(self, attempt: AssessmentAttempt) -> AssessmentAttempt:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO assessment_attempts (
                    id, assessment_id, student_id, score, passed, started_at, completed_at,
                    assignment_id, attempt_number, status, time_spent_seconds, max_score,
                    percentage, current_difficulty, answers, item_results, ai_grading_summary,
                    teacher_review, reassessment_recommendations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    attempt.id,
                    attempt.assessment_id,
                    attempt.student_id,
                    attempt.score,
                    1 if attempt.passed else 0,
                    attempt.started_at,
                    attempt.completed_at,
                    attempt.assignment_id,
                    attempt.attempt_number,
                    attempt.status,
                    attempt.time_spent_seconds,
                    attempt.max_score,
                    attempt.percentage,
                    attempt.current_difficulty,
                    json.dumps(attempt.answers),
                    json.dumps(attempt.item_results),
                    json.dumps(attempt.ai_grading_summary),
                    json.dumps(attempt.teacher_review),
                    json.dumps(attempt.reassessment_recommendations),
                ),
            )
        return attempt

    def get_assessment_attempt(self, attempt_id: str) -> Optional[AssessmentAttempt]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM assessment_attempts WHERE id = ?;", (attempt_id,)).fetchone()
            if r:
                return AssessmentAttempt(
                    id=r["id"],
                    assessment_id=r["assessment_id"],
                    student_id=r["student_id"],
                    score=float(r["score"]),
                    passed=bool(r["passed"]),
                    started_at=r["started_at"],
                    completed_at=r["completed_at"],
                    assignment_id=r["assignment_id"] if "assignment_id" in r.keys() else None,
                    attempt_number=int(r["attempt_number"]) if "attempt_number" in r.keys() else 1,
                    status=r["status"] if "status" in r.keys() else "in_progress",
                    time_spent_seconds=int(r["time_spent_seconds"]) if "time_spent_seconds" in r.keys() else 0,
                    max_score=float(r["max_score"]) if "max_score" in r.keys() else 100.0,
                    percentage=float(r["percentage"]) if "percentage" in r.keys() else 0.0,
                    current_difficulty=int(r["current_difficulty"]) if "current_difficulty" in r.keys() else 1,
                    answers=json.loads(r["answers"]) if "answers" in r.keys() and r["answers"] else {},
                    item_results=json.loads(r["item_results"]) if "item_results" in r.keys() and r["item_results"] else {},
                    ai_grading_summary=json.loads(r["ai_grading_summary"]) if "ai_grading_summary" in r.keys() and r["ai_grading_summary"] else {},
                    teacher_review=json.loads(r["teacher_review"]) if "teacher_review" in r.keys() and r["teacher_review"] else {},
                    reassessment_recommendations=json.loads(r["reassessment_recommendations"]) if "reassessment_recommendations" in r.keys() and r["reassessment_recommendations"] else [],
                )
            return None

    def get_assessment_attempts_for_student(self, student_id: str, limit: int = 50) -> List[AssessmentAttempt]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM assessment_attempts WHERE student_id = ? ORDER BY started_at DESC LIMIT ?;",
                (student_id, limit),
            ).fetchall()
            return [
                AssessmentAttempt(
                    id=r["id"],
                    assessment_id=r["assessment_id"],
                    student_id=r["student_id"],
                    score=float(r["score"]),
                    passed=bool(r["passed"]),
                    started_at=r["started_at"],
                    completed_at=r["completed_at"],
                    assignment_id=r["assignment_id"] if "assignment_id" in r.keys() else None,
                    attempt_number=int(r["attempt_number"]) if "attempt_number" in r.keys() else 1,
                    status=r["status"] if "status" in r.keys() else "in_progress",
                    time_spent_seconds=int(r["time_spent_seconds"]) if "time_spent_seconds" in r.keys() else 0,
                    max_score=float(r["max_score"]) if "max_score" in r.keys() else 100.0,
                    percentage=float(r["percentage"]) if "percentage" in r.keys() else 0.0,
                    current_difficulty=int(r["current_difficulty"]) if "current_difficulty" in r.keys() else 1,
                    answers=json.loads(r["answers"]) if "answers" in r.keys() and r["answers"] else {},
                    item_results=json.loads(r["item_results"]) if "item_results" in r.keys() and r["item_results"] else {},
                    ai_grading_summary=json.loads(r["ai_grading_summary"]) if "ai_grading_summary" in r.keys() and r["ai_grading_summary"] else {},
                    teacher_review=json.loads(r["teacher_review"]) if "teacher_review" in r.keys() and r["teacher_review"] else {},
                    reassessment_recommendations=json.loads(r["reassessment_recommendations"]) if "reassessment_recommendations" in r.keys() and r["reassessment_recommendations"] else [],
                )
                for r in rows
            ]

    def create_reassessment(self, reassessment: Reassessment) -> Reassessment:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reassessments (
                    id, original_attempt_id, student_id, course_id, generated_assessment_id,
                    target_concepts, status, target_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    reassessment.id,
                    reassessment.original_attempt_id,
                    reassessment.student_id,
                    reassessment.course_id,
                    reassessment.generated_assessment_id,
                    json.dumps(reassessment.target_concepts),
                    reassessment.status,
                    reassessment.target_score,
                    reassessment.created_at,
                ),
            )
        return reassessment

    def get_reassessment(self, reassessment_id: str) -> Optional[Reassessment]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM reassessments WHERE id = ?;", (reassessment_id,)).fetchone()
            if r:
                return Reassessment(
                    id=r["id"],
                    original_attempt_id=r["original_attempt_id"],
                    student_id=r["student_id"],
                    course_id=r["course_id"],
                    generated_assessment_id=r["generated_assessment_id"],
                    target_concepts=json.loads(r["target_concepts"]) if "target_concepts" in r.keys() and r["target_concepts"] else [],
                    status=r["status"],
                    target_score=float(r["target_score"]),
                    created_at=r["created_at"],
                )
            return None

    def list_reassessments_for_student(self, student_id: str) -> List[Reassessment]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM reassessments WHERE student_id = ? ORDER BY created_at DESC;",
                (student_id,),
            ).fetchall()
            return [
                Reassessment(
                    id=r["id"],
                    original_attempt_id=r["original_attempt_id"],
                    student_id=r["student_id"],
                    course_id=r["course_id"],
                    generated_assessment_id=r["generated_assessment_id"],
                    target_concepts=json.loads(r["target_concepts"]) if "target_concepts" in r.keys() and r["target_concepts"] else [],
                    status=r["status"],
                    target_score=float(r["target_score"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    # ── 7. Teacher Directives & Interventions ────────────────────────────────

    def _row_to_teacher_instruction(self, r: Any) -> TeacherInstructionRecord:
        keys = r.keys()
        audit_trail = []
        if "audit_trail_json" in keys and r["audit_trail_json"]:
            try:
                audit_trail = json.loads(r["audit_trail_json"])
            except Exception as exc:
                logger.warning("Failed to decode instruction audit trail JSON: %s", exc)
        return TeacherInstructionRecord(
            id=r["id"],
            teacher_id=r["teacher_id"],
            student_id=r["student_id"],
            course_id=r["course_id"],
            instruction_text=r["instruction_text"],
            concept_scope=r["concept_scope"] if "concept_scope" in keys else "ALL",
            priority=int(r["priority"]),
            is_active=bool(r["is_active"]),
            organization_id=r["organization_id"] if "organization_id" in keys else None,
            course_version_id=r["course_version_id"] if "course_version_id" in keys else None,
            class_id=r["class_id"] if "class_id" in keys else None,
            session_id=r["session_id"] if "session_id" in keys else None,
            scope_type=r["scope_type"] if "scope_type" in keys and r["scope_type"] else "COURSE",
            status=r["status"] if "status" in keys and r["status"] else "ACTIVE",
            safety_status=r["safety_status"] if "safety_status" in keys and r["safety_status"] else "VALIDATED",
            safety_reasons=[],
            start_at=r["start_at"] if "start_at" in keys else None,
            expires_at=r["expires_at"] if "expires_at" in keys else None,
            version=int(r["version"]) if "version" in keys and r["version"] is not None else 1,
            audit_trail=audit_trail,
            created_at=r["created_at"],
            updated_at=r["updated_at"] if "updated_at" in keys else None,
        )

    def create_teacher_instruction(self, inst: TeacherInstructionRecord) -> TeacherInstructionRecord:
        with self._get_connection() as conn:
            scope_val = inst.scope_type.value if hasattr(inst.scope_type, "value") else str(inst.scope_type or "COURSE")
            status_val = inst.status.value if hasattr(inst.status, "value") else str(inst.status or "ACTIVE")
            safety_val = inst.safety_status.value if hasattr(inst.safety_status, "value") else str(inst.safety_status or "VALIDATED")
            audit_json = json.dumps(inst.audit_trail) if isinstance(inst.audit_trail, list) else str(inst.audit_trail or "[]")
            conn.execute(
                """
                INSERT INTO teacher_instructions (
                    id, teacher_id, student_id, course_id, instruction_text, concept_scope,
                    priority, is_active, organization_id, course_version_id, class_id,
                    session_id, scope_type, status, safety_status, start_at, expires_at,
                    version, audit_trail_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    teacher_id=excluded.teacher_id,
                    student_id=excluded.student_id,
                    course_id=excluded.course_id,
                    instruction_text=excluded.instruction_text,
                    concept_scope=excluded.concept_scope,
                    priority=excluded.priority,
                    is_active=excluded.is_active,
                    organization_id=excluded.organization_id,
                    course_version_id=excluded.course_version_id,
                    class_id=excluded.class_id,
                    session_id=excluded.session_id,
                    scope_type=excluded.scope_type,
                    status=excluded.status,
                    safety_status=excluded.safety_status,
                    start_at=excluded.start_at,
                    expires_at=excluded.expires_at,
                    version=excluded.version,
                    audit_trail_json=excluded.audit_trail_json,
                    updated_at=excluded.updated_at;
                """,
                (
                    inst.id, inst.teacher_id, inst.student_id, inst.course_id, inst.instruction_text,
                    inst.concept_scope, inst.priority, 1 if inst.is_active else 0, inst.organization_id,
                    inst.course_version_id, inst.class_id, inst.session_id, scope_val, status_val,
                    safety_val, inst.start_at, inst.expires_at, inst.version, audit_json,
                    inst.created_at, inst.updated_at,
                ),
            )
        return inst

    def get_teacher_instruction(self, instruction_id: str) -> Optional[TeacherInstructionRecord]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM teacher_instructions WHERE id = ?;", (instruction_id,)).fetchone()
            return self._row_to_teacher_instruction(r) if r else None

    def delete_teacher_instruction(self, instruction_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM teacher_instructions WHERE id = ?;", (instruction_id,))
            return cursor.rowcount > 0

    def get_teacher_instructions(
        self,
        course_id: Optional[str] = None,
        student_id: Optional[str] = None,
        only_active: bool = True,
    ) -> List[TeacherInstructionRecord]:
        with self._get_connection() as conn:
            conditions = []
            params: list[Any] = []
            if course_id:
                conditions.append("course_id = ?")
                params.append(course_id)
            if only_active:
                conditions.append("is_active = 1")
            if student_id:
                conditions.append("(student_id = ? OR student_id = 'all')")
                params.append(student_id)

            where_str = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"SELECT * FROM teacher_instructions {where_str} ORDER BY priority DESC, created_at DESC;"
            rows = conn.execute(sql, tuple(params)).fetchall()
            recs = [self._row_to_teacher_instruction(r) for r in rows]
            if only_active:
                now = datetime.now(timezone.utc)
                active_recs = []
                for rec in recs:
                    if rec.expires_at:
                        try:
                            exp_dt = datetime.fromisoformat(rec.expires_at.replace("Z", "+00:00"))
                            if exp_dt.tzinfo is None:
                                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                            if now > exp_dt:
                                continue
                        except Exception as _parse_exc:
                            # Malformed expires_at: fail-safe — treat as expired rather than serving stale instruction
                            logger.warning(
                                "Instruction %s has unparseable expires_at %r — treating as expired: %s",
                                getattr(rec, "id", "?"),
                                rec.expires_at,
                                _parse_exc,
                            )
                            continue
                    active_recs.append(rec)
                return active_recs
            return recs

    def get_teacher_instructions_for_course(self, course_id: str) -> List[TeacherInstructionRecord]:
        """Retrieve all active teacher instructions scoped to a course."""
        return self.get_teacher_instructions(course_id=course_id, only_active=True)

    def get_hierarchical_teacher_instructions(
        self,
        course_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        class_id: Optional[str] = None,
        student_id: Optional[str] = None,
        session_id: Optional[str] = None,
        only_active: bool = True,
    ) -> List[TeacherInstructionRecord]:
        with self._get_connection() as conn:
            conditions = []
            params: list[Any] = []

            if only_active:
                conditions.append("is_active = 1")
                conditions.append("LOWER(status) = 'active'")
                conditions.append("LOWER(safety_status) = 'validated'")

            # Build scope conditions across hierarchy
            scope_clauses = []
            if organization_id:
                scope_clauses.append("(scope_type = 'ORGANIZATION' AND (organization_id = ? OR organization_id IS NULL))")
                params.append(organization_id)
            if course_id:
                scope_clauses.append("(scope_type = 'COURSE' AND (course_id = ? OR course_id = 'all'))")
                params.append(course_id)
            if class_id:
                scope_clauses.append("(scope_type = 'CLASS' AND class_id = ?)")
                params.append(class_id)
            if student_id:
                scope_clauses.append("(scope_type = 'STUDENT' AND (student_id = ? OR student_id = 'all'))")
                params.append(student_id)
            if session_id:
                scope_clauses.append("(scope_type = 'SESSION' AND session_id = ?)")
                params.append(session_id)

            if scope_clauses:
                conditions.append(f"({' OR '.join(scope_clauses)})")
            elif course_id:
                conditions.append("(course_id = ? OR course_id = 'all')")
                params.append(course_id)

            where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = f"SELECT * FROM teacher_instructions {where_sql} ORDER BY priority DESC, created_at DESC;"
            rows = conn.execute(sql, tuple(params)).fetchall()
            recs = [self._row_to_teacher_instruction(r) for r in rows]
            if only_active:
                now = datetime.now(timezone.utc)
                active_recs = []
                for rec in recs:
                    if rec.expires_at:
                        try:
                            exp_dt = datetime.fromisoformat(rec.expires_at.replace("Z", "+00:00"))
                            if exp_dt.tzinfo is None:
                                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                            if now > exp_dt:
                                continue
                        except Exception as _parse_exc:
                            # Malformed expires_at: fail-safe — treat as expired rather than serving stale instruction
                            logger.warning(
                                "Hierarchical instruction %s has unparseable expires_at %r — treating as expired: %s",
                                getattr(rec, "id", "?"),
                                rec.expires_at,
                                _parse_exc,
                            )
                            continue
                    active_recs.append(rec)
                return active_recs
            return recs

    def create_intervention(self, alert: InterventionRecord) -> InterventionRecord:
        with self._get_connection() as conn:
            sev_val = alert.severity.value if isinstance(alert.severity, AlertSeverity) else str(alert.severity)
            stat_val = alert.status.value if isinstance(alert.status, AlertStatus) else str(alert.status)
            conn.execute(
                "INSERT OR REPLACE INTO interventions (id, student_id, course_id, severity, alert_type, message, status, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (alert.id, alert.student_id, alert.course_id, sev_val, alert.alert_type, alert.message, stat_val, alert.created_at, alert.resolved_at),
            )
        return alert

    def resolve_intervention(self, alert_id: str) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE interventions SET status = 'resolved', resolved_at = ? WHERE id = ?;",
                (now_iso, alert_id),
            )
            return cursor.rowcount > 0

    def get_interventions(self, course_id: str, active_only: bool = True) -> List[InterventionRecord]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM interventions WHERE course_id = ?"
            if active_only:
                sql += " AND status != 'resolved'"
            sql += " ORDER BY created_at DESC;"
            rows = conn.execute(sql, (course_id,)).fetchall()
            return [
                InterventionRecord(
                    id=r["id"],
                    student_id=r["student_id"],
                    course_id=r["course_id"],
                    severity=AlertSeverity(r["severity"]),
                    alert_type=r["alert_type"],
                    message=r["message"],
                    status=AlertStatus(r["status"]),
                    created_at=r["created_at"],
                    resolved_at=r["resolved_at"],
                )
                for r in rows
            ]

    def get_interventions_for_student(self, student_id: str, active_only: bool = False) -> List[InterventionRecord]:
        with self._get_connection() as conn:
            sql = "SELECT * FROM interventions WHERE student_id = ?"
            if active_only:
                sql += " AND status != 'resolved'"
            sql += " ORDER BY created_at DESC;"
            rows = conn.execute(sql, (student_id,)).fetchall()
            return [
                InterventionRecord(
                    id=r["id"],
                    student_id=r["student_id"],
                    course_id=r["course_id"],
                    severity=AlertSeverity(r["severity"]),
                    alert_type=r["alert_type"],
                    message=r["message"],
                    status=AlertStatus(r["status"]),
                    created_at=r["created_at"],
                    resolved_at=r["resolved_at"],
                )
                for r in rows
            ]

    def create_notification(self, notif: Notification) -> Notification:
        with self._get_connection() as conn:
            meta_json = json.dumps(notif.metadata) if isinstance(notif.metadata, dict) else "{}"
            conn.execute(
                """INSERT OR REPLACE INTO notifications 
                (id, recipient_id, title, message, channel, status, is_read, retry_count, max_retries, backoff_seconds, next_retry_at, delivered_at, error_message, provider_message_id, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    notif.id,
                    notif.recipient_id,
                    notif.title,
                    notif.message,
                    notif.channel,
                    notif.status,
                    1 if notif.is_read else 0,
                    notif.retry_count,
                    notif.max_retries,
                    notif.backoff_seconds,
                    notif.next_retry_at,
                    notif.delivered_at,
                    notif.error_message,
                    notif.provider_message_id,
                    meta_json,
                    notif.created_at,
                ),
            )
        return notif

    def get_notification(self, notification_id: str) -> Optional[Notification]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM notifications WHERE id = ?;", (notification_id,)).fetchone()
            if r:
                return self._row_to_notification(r)
            return None

    def get_notifications(
        self,
        recipient_id: str,
        unread_only: bool = False,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]:
        with self._get_connection() as conn:
            query = "SELECT * FROM notifications WHERE recipient_id = ?"
            params: list = [recipient_id]
            if unread_only:
                query += " AND is_read = 0"
            if channel:
                query += " AND channel = ?"
                params.append(channel)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])
            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._row_to_notification(r) for r in rows]

    def update_notification(self, notif: Notification) -> Notification:
        return self.create_notification(notif)

    def mark_notification_read(self, notification_id: str, recipient_id: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            if recipient_id:
                res = conn.execute(
                    "UPDATE notifications SET is_read = 1 WHERE id = ? AND recipient_id = ?;",
                    (notification_id, recipient_id),
                )
            else:
                res = conn.execute(
                    "UPDATE notifications SET is_read = 1 WHERE id = ?;",
                    (notification_id,),
                )
            return res.rowcount > 0

    def mark_all_notifications_read(self, recipient_id: str) -> int:
        with self._get_connection() as conn:
            res = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE recipient_id = ? AND is_read = 0;",
                (recipient_id,),
            )
            return res.rowcount

    def get_pending_notifications(self, limit: int = 100) -> List[Notification]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notifications WHERE status IN ('created', 'queued', 'retried') ORDER BY created_at ASC LIMIT ?;",
                (limit,),
            ).fetchall()
            return [self._row_to_notification(r) for r in rows]

    def _row_to_notification(self, r: sqlite3.Row) -> Notification:
        keys = r.keys()
        meta = json.loads(r["metadata"]) if "metadata" in keys and r["metadata"] else {}
        return Notification(
            id=r["id"],
            recipient_id=r["recipient_id"],
            title=r["title"],
            message=r["message"],
            channel=r["channel"] if "channel" in keys else "in_app",
            status=r["status"] if "status" in keys else "delivered",
            is_read=bool(r["is_read"]),
            retry_count=int(r["retry_count"]) if "retry_count" in keys else 0,
            max_retries=int(r["max_retries"]) if "max_retries" in keys else 3,
            backoff_seconds=float(r["backoff_seconds"]) if "backoff_seconds" in keys else 1.0,
            next_retry_at=r["next_retry_at"] if "next_retry_at" in keys else None,
            delivered_at=r["delivered_at"] if "delivered_at" in keys else None,
            error_message=r["error_message"] if "error_message" in keys else None,
            provider_message_id=r["provider_message_id"] if "provider_message_id" in keys else None,
            metadata=meta,
            created_at=r["created_at"],
        )

    # ── 8. AI Governance, Observability & Auditing ───────────────────────────

    def create_ai_provider(self, provider: AIProvider) -> AIProvider:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ai_providers (id, name, provider_type, base_url, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                (provider.id, provider.name, provider.provider_type, provider.base_url, 1 if provider.is_active else 0, provider.created_at),
            )
        return provider

    def create_ai_model(self, model: AIModel) -> AIModel:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ai_models (id, provider_id, model_name, context_window, is_default, created_at) VALUES (?, ?, ?, ?, ?, ?);",
                (model.id, model.provider_id, model.model_name, model.context_window, 1 if model.is_default else 0, model.created_at),
            )
        return model

    def record_ai_execution(self, log: AIExecutionLog) -> AIExecutionLog:
        return self.record_ai_execution_log(log)

    def record_ai_execution_log(self, log: AIExecutionLog) -> AIExecutionLog:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_execution_logs (
                    id, model_id, request_id, provider, model, student_id, session_id,
                    course_id, task_type, prompt_tokens, completion_tokens, latency_ms,
                    status, error_class, estimated_cost_usd, fallback_used, prompt_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    model_id=excluded.model_id,
                    request_id=excluded.request_id,
                    provider=excluded.provider,
                    model=excluded.model,
                    student_id=excluded.student_id,
                    session_id=excluded.session_id,
                    course_id=excluded.course_id,
                    task_type=excluded.task_type,
                    prompt_tokens=excluded.prompt_tokens,
                    completion_tokens=excluded.completion_tokens,
                    latency_ms=excluded.latency_ms,
                    status=excluded.status,
                    error_class=excluded.error_class,
                    estimated_cost_usd=excluded.estimated_cost_usd,
                    fallback_used=excluded.fallback_used,
                    prompt_hash=excluded.prompt_hash,
                    created_at=excluded.created_at;
                """,
                (
                    log.id,
                    log.model_id or f"{log.provider}:{log.model}",
                    log.request_id,
                    log.provider,
                    log.model,
                    log.student_id,
                    log.session_id,
                    log.course_id,
                    log.task_type,
                    log.prompt_tokens,
                    log.completion_tokens,
                    log.latency_ms,
                    log.status,
                    log.error_class,
                    log.estimated_cost_usd,
                    1 if log.fallback_used else 0,
                    log.prompt_hash,
                    log.created_at,
                ),
            )
        return log

    def get_ai_execution_logs(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        student_id: Optional[str] = None,
        course_id: Optional[str] = None,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AIExecutionLog]:
        with self._get_connection() as conn:
            conditions = []
            params: List[Any] = []
            if provider:
                conditions.append("provider = ?")
                params.append(provider)
            if model:
                conditions.append("model = ?")
                params.append(model)
            if student_id:
                conditions.append("student_id = ?")
                params.append(student_id)
            if course_id:
                conditions.append("course_id = ?")
                params.append(course_id)
            if task_type:
                conditions.append("task_type = ?")
                params.append(task_type)
            if status:
                conditions.append("status = ?")
                params.append(status)

            where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"SELECT * FROM ai_execution_logs {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])

            rows = conn.execute(sql, params).fetchall()
            return [
                AIExecutionLog(
                    id=r["id"],
                    model_id=r["model_id"],
                    prompt_tokens=r["prompt_tokens"],
                    completion_tokens=r["completion_tokens"],
                    latency_ms=r["latency_ms"],
                    status=r["status"],
                    request_id=r["request_id"] if "request_id" in r.keys() else "",
                    provider=r["provider"] if "provider" in r.keys() else "",
                    model=r["model"] if "model" in r.keys() else "",
                    student_id=r["student_id"] if "student_id" in r.keys() else None,
                    session_id=r["session_id"] if "session_id" in r.keys() else None,
                    course_id=r["course_id"] if "course_id" in r.keys() else None,
                    task_type=r["task_type"] if "task_type" in r.keys() else "general",
                    error_class=r["error_class"] if "error_class" in r.keys() else None,
                    estimated_cost_usd=r["estimated_cost_usd"] if "estimated_cost_usd" in r.keys() else 0.0,
                    fallback_used=bool(r["fallback_used"]) if "fallback_used" in r.keys() else False,
                    prompt_hash=r["prompt_hash"] if "prompt_hash" in r.keys() else "",
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def get_ai_observability_metrics(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            r_total = conn.execute("SELECT count(*) as total_requests, sum(prompt_tokens) as total_prompt_tokens, sum(completion_tokens) as total_completion_tokens, sum(estimated_cost_usd) as total_cost, avg(latency_ms) as avg_latency FROM ai_execution_logs;").fetchone()
            r_success = conn.execute("SELECT count(*) as success_count FROM ai_execution_logs WHERE status = 'SUCCESS';").fetchone()
            r_fallback = conn.execute("SELECT count(*) as fallback_count FROM ai_execution_logs WHERE fallback_used = 1;").fetchone()

            total = r_total["total_requests"] or 0
            success = r_success["success_count"] or 0
            fallbacks = r_fallback["fallback_count"] or 0
            p_tokens = r_total["total_prompt_tokens"] or 0
            c_tokens = r_total["total_completion_tokens"] or 0
            cost = r_total["total_cost"] or 0.0
            avg_lat = r_total["avg_latency"] or 0.0

            # Provider breakdown
            provider_rows = conn.execute("SELECT provider, count(*) as count, sum(estimated_cost_usd) as cost, avg(latency_ms) as avg_latency FROM ai_execution_logs GROUP BY provider;").fetchall()
            providers_breakdown = {
                r["provider"] or "unknown": {
                    "count": r["count"],
                    "cost_usd": round(r["cost"] or 0.0, 4),
                    "avg_latency_ms": round(r["avg_latency"] or 0.0, 1),
                }
                for r in provider_rows
            }

            # Task breakdown
            task_rows = conn.execute("SELECT task_type, count(*) as count, sum(estimated_cost_usd) as cost FROM ai_execution_logs GROUP BY task_type;").fetchall()
            tasks_breakdown = {
                r["task_type"] or "general": {
                    "count": r["count"],
                    "cost_usd": round(r["cost"] or 0.0, 4),
                }
                for r in task_rows
            }

            return {
                "total_requests": total,
                "successful_requests": success,
                "failed_requests": max(0, total - success),
                "success_rate": round(success / total, 3) if total > 0 else 1.0,
                "fallback_count": fallbacks,
                "total_prompt_tokens": p_tokens,
                "total_completion_tokens": c_tokens,
                "total_tokens": p_tokens + c_tokens,
                "total_cost_usd": round(cost, 4),
                "avg_latency_ms": round(avg_lat, 2),
                "providers_breakdown": providers_breakdown,
                "tasks_breakdown": tasks_breakdown,
            }


    def record_audit_log(self, log: AuditLog) -> AuditLog:
        with self._get_connection() as conn:
            details_str = json.dumps(log.details) if isinstance(log.details, dict) else str(log.details)
            conn.execute(
                "INSERT OR REPLACE INTO audit_logs (id, organization_id, user_id, action, resource, details, ip_address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                (log.id, log.organization_id, log.user_id, log.action, log.resource, details_str, log.ip_address, log.created_at),
            )
        return log

    def get_audit_logs(self, organization_id: str) -> List[AuditLog]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE organization_id = ? ORDER BY created_at DESC;",
                (organization_id,),
            ).fetchall()
            return [
                AuditLog(
                    id=r["id"],
                    organization_id=r["organization_id"],
                    user_id=r["user_id"],
                    action=r["action"],
                    resource=r["resource"],
                    details=json.loads(r["details"]) if r["details"].startswith("{") else {},
                    ip_address=r["ip_address"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def _row_to_rag_source(self, r: sqlite3.Row) -> RAGSource:
        metadata = {}
        if r["metadata_json"]:
            try:
                metadata = json.loads(r["metadata_json"])
            except Exception as exc:
                logger.warning("Failed to decode RAG source metadata JSON: %s", exc)
        keys = r.keys()
        target_students = []
        if "target_student_ids" in keys and r["target_student_ids"]:
            try:
                target_students = json.loads(r["target_student_ids"]) if isinstance(r["target_student_ids"], str) else list(r["target_student_ids"])
            except Exception as exc:
                logger.warning("Failed to decode RAG source target student IDs JSON: %s", exc)
        return RAGSource(
            id=r["id"],
            organization_id=r["organization_id"],
            course_id=r["course_id"],
            subject=r["subject"],
            title=r["title"],
            source_type=r["source_type"],
            authority=r["authority"],
            version=r["version"],
            status=r["status"],
            checksum=r["checksum"] or "",
            metadata_json=metadata,
            chunk_count=r["chunk_count"],
            content_type=r["content_type"] if "content_type" in keys and r["content_type"] else "textbook",
            uploaded_by=r["uploaded_by"] if "uploaded_by" in keys else None,
            published_by=r["published_by"] if "published_by" in keys else None,
            published_at=r["published_at"] if "published_at" in keys else None,
            error_message=r["error_message"] if "error_message" in keys else None,
            course_version_id=r["course_version_id"] if "course_version_id" in keys else None,
            visibility_scope=r["visibility_scope"] if "visibility_scope" in keys and r["visibility_scope"] else "course",
            class_id=r["class_id"] if "class_id" in keys else None,
            target_student_ids=target_students,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def create_rag_source(self, source: RAGSource) -> RAGSource:
        with self._get_connection() as conn:
            metadata_str = json.dumps(source.metadata_json) if isinstance(source.metadata_json, dict) else str(source.metadata_json)
            status_val = source.status.value if isinstance(source.status, Enum) else str(source.status)
            content_type_val = source.content_type.value if isinstance(source.content_type, Enum) else str(source.content_type or "textbook")
            vis_scope_val = source.visibility_scope.value if isinstance(source.visibility_scope, Enum) else str(source.visibility_scope or "course")
            target_students_str = json.dumps(source.target_student_ids) if isinstance(source.target_student_ids, list) else str(source.target_student_ids or "[]")
            conn.execute(
                """
                INSERT INTO rag_sources (
                    id, organization_id, course_id, subject, title, source_type, authority,
                    version, status, checksum, metadata_json, chunk_count, content_type,
                    uploaded_by, published_by, published_at, error_message,
                    course_version_id, visibility_scope, class_id, target_student_ids,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    organization_id=excluded.organization_id,
                    course_id=excluded.course_id,
                    subject=excluded.subject,
                    title=excluded.title,
                    source_type=excluded.source_type,
                    authority=excluded.authority,
                    version=excluded.version,
                    status=excluded.status,
                    checksum=excluded.checksum,
                    metadata_json=excluded.metadata_json,
                    chunk_count=excluded.chunk_count,
                    content_type=excluded.content_type,
                    uploaded_by=excluded.uploaded_by,
                    published_by=excluded.published_by,
                    published_at=excluded.published_at,
                    error_message=excluded.error_message,
                    course_version_id=excluded.course_version_id,
                    visibility_scope=excluded.visibility_scope,
                    class_id=excluded.class_id,
                    target_student_ids=excluded.target_student_ids,
                    updated_at=excluded.updated_at;
                """,
                (
                    source.id,
                    source.organization_id,
                    source.course_id,
                    source.subject,
                    source.title,
                    source.source_type,
                    source.authority,
                    source.version,
                    status_val,
                    source.checksum,
                    metadata_str,
                    source.chunk_count,
                    content_type_val,
                    source.uploaded_by,
                    source.published_by,
                    source.published_at,
                    source.error_message,
                    source.course_version_id,
                    vis_scope_val,
                    source.class_id,
                    target_students_str,
                    source.created_at,
                    source.updated_at,
                ),
            )
        return source

    def get_rag_source(self, source_id: str) -> Optional[RAGSource]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM rag_sources WHERE id = ?;", (source_id,)).fetchone()
            if r:
                return self._row_to_rag_source(r)
            return None

    def list_rag_sources(
        self,
        course_id: Optional[str] = None,
        subject: Optional[str] = None,
        status: Optional[str] = None,
        authority: Optional[str] = None,
        content_type: Optional[str] = None,
        course_version_id: Optional[str] = None,
        visibility_scope: Optional[str] = None,
        class_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RAGSource]:
        with self._get_connection() as conn:
            conditions = []
            params: List[Any] = []
            if course_id:
                conditions.append("course_id = ?")
                params.append(course_id)
            if subject:
                conditions.append("subject = ?")
                params.append(subject)
            if status:
                conditions.append("LOWER(status) = ?")
                params.append(status.lower())
            if authority:
                conditions.append("authority = ?")
                params.append(authority)
            if content_type:
                conditions.append("LOWER(content_type) = ?")
                params.append(content_type.lower())
            if course_version_id:
                conditions.append("course_version_id = ?")
                params.append(course_version_id)
            if visibility_scope:
                conditions.append("LOWER(visibility_scope) = ?")
                params.append(visibility_scope.lower())
            if class_id:
                conditions.append("class_id = ?")
                params.append(class_id)

            where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"SELECT * FROM rag_sources {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])

            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_rag_source(r) for r in rows]



    def update_rag_source(self, source: RAGSource) -> RAGSource:
        source.updated_at = datetime.now(timezone.utc).isoformat()
        return self.create_rag_source(source)

    def delete_rag_source(self, source_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM rag_sources WHERE id = ?;", (source_id,))
            return cur.rowcount > 0

    def add_rag_chunks(self, chunks: List[RAGChunk]) -> int:
        if not chunks:
            return 0
        with self._get_connection() as conn:
            count = 0
            for chunk in chunks:
                emb_str = json.dumps(chunk.embedding_vector) if chunk.embedding_vector else "[]"
                meta_str = json.dumps(chunk.metadata_json) if chunk.metadata_json else "{}"
                vis_val = chunk.visibility_scope.value if isinstance(chunk.visibility_scope, Enum) else str(chunk.visibility_scope or "course")
                conn.execute(
                    """
                    INSERT INTO rag_chunks (
                        id, source_id, course_id, subject, chapter, topic, concept,
                        difficulty, page, section, content_type, text, clean_text,
                        embedding_vector, provenance_type, metadata_json,
                        course_version_id, visibility_scope, class_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        source_id=excluded.source_id,
                        course_id=excluded.course_id,
                        subject=excluded.subject,
                        chapter=excluded.chapter,
                        topic=excluded.topic,
                        concept=excluded.concept,
                        difficulty=excluded.difficulty,
                        page=excluded.page,
                        section=excluded.section,
                        content_type=excluded.content_type,
                        text=excluded.text,
                        clean_text=excluded.clean_text,
                        embedding_vector=excluded.embedding_vector,
                        provenance_type=excluded.provenance_type,
                        metadata_json=excluded.metadata_json,
                        course_version_id=excluded.course_version_id,
                        visibility_scope=excluded.visibility_scope,
                        class_id=excluded.class_id;
                    """,
                    (
                        chunk.id,
                        chunk.source_id,
                        chunk.course_id,
                        chunk.subject,
                        chunk.chapter,
                        chunk.topic,
                        chunk.concept,
                        chunk.difficulty,
                        chunk.page,
                        chunk.section,
                        chunk.content_type,
                        chunk.text,
                        chunk.clean_text,
                        emb_str,
                        chunk.provenance_type,
                        meta_str,
                        chunk.course_version_id,
                        vis_val,
                        chunk.class_id,
                        chunk.created_at,
                    ),
                )
                count += 1
            if chunks:
                source_id = chunks[0].source_id
                conn.execute(
                    "UPDATE rag_sources SET chunk_count = (SELECT count(*) FROM rag_chunks WHERE source_id = ?) WHERE id = ?;",
                    (source_id, source_id),
                )
            return count

    def get_rag_chunks(self, source_id: str, limit: int = 100, offset: int = 0) -> List[RAGChunk]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM rag_chunks WHERE source_id = ? ORDER BY page ASC, id ASC LIMIT ? OFFSET ?;",
                (source_id, limit, offset),
            ).fetchall()
            return [self._row_to_rag_chunk(r) for r in rows]

    def get_rag_chunks_by_course(
        self,
        course_id: str,
        subject: Optional[str] = None,
        concept: Optional[str] = None,
        only_published: bool = True,
        course_version_id: Optional[str] = None,
        class_id: Optional[str] = None,
        student_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[RAGChunk]:
        with self._get_connection() as conn:
            conditions = ["rc.course_id = ?"]
            params: List[Any] = [course_id]

            if only_published:
                conditions.append("LOWER(rs.status) = 'published'")
            if subject:
                conditions.append("rc.subject = ?")
                params.append(subject)
            if concept:
                conditions.append("(rc.concept = ? OR rc.concept = '' OR rc.concept IS NULL OR rc.concept = 'General' OR rc.concept = 'ALL')")
                params.append(concept)

            where_str = " AND ".join(conditions)
            sql = f"""
                SELECT rc.*,
                       rs.course_version_id as src_version_id,
                       rs.visibility_scope as src_visibility_scope,
                       rs.class_id as src_class_id,
                       rs.target_student_ids as src_target_student_ids
                FROM rag_chunks rc
                JOIN rag_sources rs ON rc.source_id = rs.id
                WHERE {where_str}
                ORDER BY rc.created_at ASC
                LIMIT ?;
            """
            params.append(limit * 3)
            rows = conn.execute(sql, params).fetchall()

            authorized_chunks = []
            for r in rows:
                keys = r.keys()
                # 1. Version check
                src_v = r["src_version_id"] if ("src_version_id" in keys and r["src_version_id"]) else (r["course_version_id"] if "course_version_id" in keys else None)
                if course_version_id and src_v:
                    if src_v != course_version_id:
                        continue

                # 2. Visibility scope check
                raw_scope = r["src_visibility_scope"] if "src_visibility_scope" in keys and r["src_visibility_scope"] else "course"
                scope = raw_scope.lower()
                src_cls = r["src_class_id"] if "src_class_id" in keys else None

                if scope == "class":
                    if not class_id or class_id != src_cls:
                        continue
                elif scope == "student_targeted":
                    if not student_id:
                        continue
                    targets_raw = r["src_target_student_ids"] if "src_target_student_ids" in keys else "[]"
                    targets = []
                    if targets_raw:
                        try:
                            targets = json.loads(targets_raw) if isinstance(targets_raw, str) else list(targets_raw)
                        except Exception:
                            targets = []
                    if student_id not in targets:
                        continue

                authorized_chunks.append(self._row_to_rag_chunk(r))
                if len(authorized_chunks) >= limit:
                    break

            return authorized_chunks

    def delete_rag_chunks_by_source(self, source_id: str) -> int:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM rag_chunks WHERE source_id = ?;", (source_id,))
            conn.execute("UPDATE rag_sources SET chunk_count = 0 WHERE id = ?;", (source_id,))
            return cur.rowcount

    def _row_to_rag_chunk(self, r: sqlite3.Row) -> RAGChunk:
        emb = []
        if r["embedding_vector"]:
            try:
                emb = json.loads(r["embedding_vector"])
            except Exception as exc:
                logger.warning("Failed to decode RAG chunk embedding vector JSON: %s", exc)
        metadata = {}
        if r["metadata_json"]:
            try:
                metadata = json.loads(r["metadata_json"])
            except Exception as exc:
                logger.warning("Failed to decode RAG chunk metadata JSON: %s", exc)
        keys = r.keys()
        return RAGChunk(
            id=r["id"],
            source_id=r["source_id"],
            course_id=r["course_id"],
            subject=r["subject"],
            chapter=r["chapter"],
            topic=r["topic"],
            concept=r["concept"] or "",
            difficulty=r["difficulty"],
            page=r["page"],
            section=r["section"] or "",
            content_type=r["content_type"],
            text=r["text"],
            clean_text=r["clean_text"],
            embedding_vector=emb,
            provenance_type=r["provenance_type"],
            metadata_json=metadata,
            course_version_id=r["course_version_id"] if "course_version_id" in keys else None,
            visibility_scope=r["visibility_scope"] if "visibility_scope" in keys and r["visibility_scope"] else "course",
            class_id=r["class_id"] if "class_id" in keys else None,
            created_at=r["created_at"],
        )


    # ── Fee Management Subsystem (Phase 30) ────────────────────────────────────

    def create_fee_structure(self, fs: FeeStructure) -> FeeStructure:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO fee_structures (id, org_id, name, code, description, amount, currency, frequency, is_active, created_at, updated_at, is_deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    fs.id, fs.org_id, fs.name, fs.code, fs.description, fs.amount, fs.currency,
                    fs.frequency.value if isinstance(fs.frequency, FeeFrequency) else fs.frequency,
                    int(fs.is_active), fs.created_at, fs.updated_at, int(fs.is_deleted), fs.deleted_at
                ),
            )
            return fs

    def get_fee_structure(self, fs_id: str) -> Optional[FeeStructure]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM fee_structures WHERE id = ? AND is_deleted = 0;", (fs_id,)).fetchone()
            if not r:
                return None
            return FeeStructure(
                id=r["id"], org_id=r["org_id"], name=r["name"], code=r["code"],
                description=r["description"] or "", amount=r["amount"], currency=r["currency"],
                frequency=FeeFrequency(r["frequency"]), is_active=bool(r["is_active"]),
                created_at=r["created_at"], updated_at=r["updated_at"],
                is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
            )

    def list_fee_structures(self, org_id: str) -> List[FeeStructure]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM fee_structures WHERE org_id = ? AND is_deleted = 0 ORDER BY created_at DESC;", (org_id,)).fetchall()
            return [
                FeeStructure(
                    id=r["id"], org_id=r["org_id"], name=r["name"], code=r["code"],
                    description=r["description"] or "", amount=r["amount"], currency=r["currency"],
                    frequency=FeeFrequency(r["frequency"]), is_active=bool(r["is_active"]),
                    created_at=r["created_at"], updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
                ) for r in rows
            ]

    def create_fee_plan(self, plan: FeePlan) -> FeePlan:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO fee_plans (id, org_id, name, description, total_amount, installments_count, fee_structure_ids_json, is_active, created_at, updated_at, is_deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    plan.id, plan.org_id, plan.name, plan.description, plan.total_amount,
                    plan.installments_count, json.dumps(plan.fee_structure_ids),
                    int(plan.is_active), plan.created_at, plan.updated_at, int(plan.is_deleted), plan.deleted_at
                ),
            )
            return plan

    def get_fee_plan(self, plan_id: str) -> Optional[FeePlan]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM fee_plans WHERE id = ? AND is_deleted = 0;", (plan_id,)).fetchone()
            if not r:
                return None
            return FeePlan(
                id=r["id"], org_id=r["org_id"], name=r["name"], description=r["description"] or "",
                total_amount=r["total_amount"], installments_count=r["installments_count"],
                fee_structure_ids=json.loads(r["fee_structure_ids_json"] or "[]"),
                is_active=bool(r["is_active"]), created_at=r["created_at"], updated_at=r["updated_at"],
                is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
            )

    def create_fee_account(self, account: FeeAccount) -> FeeAccount:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO fee_accounts (id, student_id, org_id, fee_plan_id, total_due, total_paid, total_discount, balance_due, status, created_at, updated_at, is_deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    account.id, account.student_id, account.org_id, account.fee_plan_id,
                    account.total_due, account.total_paid, account.total_discount, account.balance_due,
                    account.status, account.created_at, account.updated_at, int(account.is_deleted), account.deleted_at
                ),
            )
            return account

    def update_fee_account(self, account: FeeAccount) -> FeeAccount:
        account.updated_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE fee_accounts SET fee_plan_id = ?, total_due = ?, total_paid = ?, total_discount = ?, balance_due = ?, status = ?, updated_at = ?
                   WHERE id = ?;""",
                (account.fee_plan_id, account.total_due, account.total_paid, account.total_discount, account.balance_due, account.status, account.updated_at, account.id),
            )
            return account

    def get_fee_account(self, account_id: str) -> Optional[FeeAccount]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM fee_accounts WHERE id = ? AND is_deleted = 0;", (account_id,)).fetchone()
            if not r:
                return None
            return FeeAccount(
                id=r["id"], student_id=r["student_id"], org_id=r["org_id"], fee_plan_id=r["fee_plan_id"],
                total_due=r["total_due"], total_paid=r["total_paid"], total_discount=r["total_discount"],
                balance_due=r["balance_due"], status=r["status"], created_at=r["created_at"],
                updated_at=r["updated_at"], is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
            )

    def get_fee_account_by_student(self, student_id: str) -> Optional[FeeAccount]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM fee_accounts WHERE student_id = ? AND is_deleted = 0;", (student_id,)).fetchone()
            if not r:
                return None
            return FeeAccount(
                id=r["id"], student_id=r["student_id"], org_id=r["org_id"], fee_plan_id=r["fee_plan_id"],
                total_due=r["total_due"], total_paid=r["total_paid"], total_discount=r["total_discount"],
                balance_due=r["balance_due"], status=r["status"], created_at=r["created_at"],
                updated_at=r["updated_at"], is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
            )

    def create_invoice(self, invoice: Invoice) -> Invoice:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO invoices (id, fee_account_id, student_id, org_id, invoice_number, amount_due, amount_paid, due_date, status, notes, created_at, updated_at, is_deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    invoice.id, invoice.fee_account_id, invoice.student_id, invoice.org_id,
                    invoice.invoice_number, invoice.amount_due, invoice.amount_paid, invoice.due_date,
                    invoice.status.value if isinstance(invoice.status, InvoiceStatus) else invoice.status,
                    invoice.notes, invoice.created_at, invoice.updated_at, int(invoice.is_deleted), invoice.deleted_at
                ),
            )
            return invoice

    def update_invoice(self, invoice: Invoice) -> Invoice:
        invoice.updated_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE invoices SET amount_paid = ?, status = ?, notes = ?, updated_at = ? WHERE id = ?;""",
                (
                    invoice.amount_paid,
                    invoice.status.value if isinstance(invoice.status, InvoiceStatus) else invoice.status,
                    invoice.notes, invoice.updated_at, invoice.id
                ),
            )
            return invoice

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM invoices WHERE id = ? AND is_deleted = 0;", (invoice_id,)).fetchone()
            if not r:
                return None
            return Invoice(
                id=r["id"], fee_account_id=r["fee_account_id"], student_id=r["student_id"],
                org_id=r["org_id"], invoice_number=r["invoice_number"], amount_due=r["amount_due"],
                amount_paid=r["amount_paid"], due_date=r["due_date"], status=InvoiceStatus(r["status"]),
                notes=r["notes"] or "", created_at=r["created_at"], updated_at=r["updated_at"],
                is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
            )

    def list_invoices_for_account(self, fee_account_id: str) -> List[Invoice]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM invoices WHERE fee_account_id = ? AND is_deleted = 0 ORDER BY created_at DESC;", (fee_account_id,)).fetchall()
            return [
                Invoice(
                    id=r["id"], fee_account_id=r["fee_account_id"], student_id=r["student_id"],
                    org_id=r["org_id"], invoice_number=r["invoice_number"], amount_due=r["amount_due"],
                    amount_paid=r["amount_paid"], due_date=r["due_date"], status=InvoiceStatus(r["status"]),
                    notes=r["notes"] or "", created_at=r["created_at"], updated_at=r["updated_at"],
                    is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
                ) for r in rows
            ]

    def create_payment(self, payment: Payment) -> Payment:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO payments (id, invoice_id, fee_account_id, student_id, org_id, amount, payment_method, transaction_reference, status, payment_date, notes, created_at, updated_at, is_deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    payment.id, payment.invoice_id, payment.fee_account_id, payment.student_id, payment.org_id,
                    payment.amount, payment.payment_method.value if isinstance(payment.payment_method, PaymentMethod) else payment.payment_method,
                    payment.transaction_reference, payment.status.value if isinstance(payment.status, PaymentStatus) else payment.status,
                    payment.payment_date, payment.notes, payment.created_at, payment.updated_at, int(payment.is_deleted), payment.deleted_at
                ),
            )
            return payment

    def update_payment(self, payment: Payment) -> Payment:
        payment.updated_at = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE payments SET status = ?, updated_at = ? WHERE id = ?;""",
                (payment.status.value if isinstance(payment.status, PaymentStatus) else payment.status, payment.updated_at, payment.id),
            )
            return payment

    def get_payment(self, payment_id: str) -> Optional[Payment]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM payments WHERE id = ? AND is_deleted = 0;", (payment_id,)).fetchone()
            if not r:
                return None
            return Payment(
                id=r["id"], invoice_id=r["invoice_id"], fee_account_id=r["fee_account_id"],
                student_id=r["student_id"], org_id=r["org_id"], amount=r["amount"],
                payment_method=PaymentMethod(r["payment_method"]), transaction_reference=r["transaction_reference"] or "",
                status=PaymentStatus(r["status"]), payment_date=r["payment_date"], notes=r["notes"] or "",
                created_at=r["created_at"], updated_at=r["updated_at"],
                is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
            )

    def create_receipt(self, receipt: Receipt) -> Receipt:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO receipts (id, payment_id, receipt_number, amount, issued_to, issued_at, notes, created_at, updated_at, is_deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    receipt.id, receipt.payment_id, receipt.receipt_number, receipt.amount,
                    receipt.issued_to, receipt.issued_at, receipt.notes, receipt.created_at,
                    receipt.updated_at, int(receipt.is_deleted), receipt.deleted_at
                ),
            )
            return receipt

    def get_receipt_for_payment(self, payment_id: str) -> Optional[Receipt]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM receipts WHERE payment_id = ? AND is_deleted = 0;", (payment_id,)).fetchone()
            if not r:
                return None
            return Receipt(
                id=r["id"], payment_id=r["payment_id"], receipt_number=r["receipt_number"],
                amount=r["amount"], issued_to=r["issued_to"], issued_at=r["issued_at"],
                notes=r["notes"] or "", created_at=r["created_at"], updated_at=r["updated_at"],
                is_deleted=bool(r["is_deleted"]), deleted_at=r["deleted_at"]
            )

    def create_discount(self, discount: Discount) -> Discount:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO discounts (id, fee_account_id, invoice_id, code, discount_type, value, applied_amount, reason, created_at, updated_at, is_deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    discount.id, discount.fee_account_id, discount.invoice_id, discount.code,
                    discount.discount_type.value if isinstance(discount.discount_type, DiscountType) else discount.discount_type,
                    discount.value, discount.applied_amount, discount.reason, discount.created_at,
                    discount.updated_at, int(discount.is_deleted), discount.deleted_at
                ),
            )
            return discount

    def create_refund(self, refund: Refund) -> Refund:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO refunds (id, payment_id, fee_account_id, amount, reason, refund_date, status, created_at, updated_at, is_deleted, deleted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    refund.id, refund.payment_id, refund.fee_account_id, refund.amount,
                    refund.reason, refund.refund_date,
                    refund.status.value if isinstance(refund.status, RefundStatus) else refund.status,
                    refund.created_at, refund.updated_at, int(refund.is_deleted), refund.deleted_at
                ),
            )
            return refund

    # ── Phase 14 Sync Operations & Idempotency ───────────────────────

    def record_sync_operation(self, op: SyncOperationRecord) -> SyncOperationRecord:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO sync_operations (
                       operation_id, student_id, device_id, course_id,
                       synced_count, duplicate_count, failed_count,
                       acknowledged_ids_json, conflicts_resolved, status,
                       latest_mastery, server_timestamp, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(operation_id) DO UPDATE SET
                       synced_count = excluded.synced_count,
                       duplicate_count = excluded.duplicate_count,
                       failed_count = excluded.failed_count,
                       acknowledged_ids_json = excluded.acknowledged_ids_json,
                       conflicts_resolved = excluded.conflicts_resolved,
                       status = excluded.status,
                       latest_mastery = excluded.latest_mastery,
                       server_timestamp = excluded.server_timestamp;""",
                (
                    op.operation_id, op.student_id, op.device_id, op.course_id,
                    op.synced_count, op.duplicate_count, op.failed_count,
                    json.dumps(op.acknowledged_ids), op.conflicts_resolved, op.status,
                    op.latest_mastery, op.server_timestamp, op.created_at
                ),
            )
            return op

    def get_sync_operation(self, operation_id: str) -> Optional[SyncOperationRecord]:
        with self._get_connection() as conn:
            r = conn.execute("SELECT * FROM sync_operations WHERE operation_id = ?;", (operation_id,)).fetchone()
            if not r:
                return None
            try:
                ack_ids = json.loads(r["acknowledged_ids_json"])
            except Exception:
                ack_ids = []
            return SyncOperationRecord(
                operation_id=r["operation_id"],
                student_id=r["student_id"],
                device_id=r["device_id"],
                course_id=r["course_id"],
                synced_count=r["synced_count"],
                duplicate_count=r["duplicate_count"],
                failed_count=r["failed_count"],
                acknowledged_ids=ack_ids,
                conflicts_resolved=r["conflicts_resolved"] if "conflicts_resolved" in r.keys() else 0,
                status=r["status"],
                latest_mastery=float(r["latest_mastery"] or 0.0),
                server_timestamp=r["server_timestamp"],
                created_at=r["created_at"],
            )

    def get_sync_operations_for_student(self, student_id: str, limit: int = 50) -> List[SyncOperationRecord]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sync_operations WHERE student_id = ? ORDER BY created_at DESC LIMIT ?;",
                (student_id, limit),
            ).fetchall()
            results = []
            for r in rows:
                try:
                    ack_ids = json.loads(r["acknowledged_ids_json"])
                except Exception:
                    ack_ids = []
                results.append(
                    SyncOperationRecord(
                        operation_id=r["operation_id"],
                        student_id=r["student_id"],
                        device_id=r["device_id"],
                        course_id=r["course_id"],
                        synced_count=r["synced_count"],
                        duplicate_count=r["duplicate_count"],
                        failed_count=r["failed_count"],
                        acknowledged_ids=ack_ids,
                        conflicts_resolved=r["conflicts_resolved"] if "conflicts_resolved" in r.keys() else 0,
                        status=r["status"],
                        latest_mastery=float(r["latest_mastery"] or 0.0),
                        server_timestamp=r["server_timestamp"],
                        created_at=r["created_at"],
                    )
                )
            return results

    # --- Device Bindings ---

    def bind_device(
        self,
        device_id: str,
        student_id: str,
        organization_id: Optional[str] = None,
        device_name: Optional[str] = None,
        device_type: str = "desktop",
        force: bool = False,
    ) -> DeviceBinding:
        """Register or bind a device identifier to a student.

        Enforces device ownership security:
        A device already bound to student A cannot be rebound to student B without force authorization.
        """
        existing = self.get_device_binding(device_id)
        now_ts = datetime.now(timezone.utc).isoformat()
        if existing:
            if existing.student_id != student_id and not force:
                raise PermissionError(
                    f"Device '{device_id}' is already bound to student '{existing.student_id}'."
                )
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE device_bindings
                    SET student_id = ?, organization_id = COALESCE(?, organization_id),
                        device_name = COALESCE(?, device_name), device_type = ?,
                        status = 'ACTIVE', last_synced_at = ?
                    WHERE device_id = ?;
                    """,
                    (student_id, organization_id, device_name, device_type, now_ts, device_id),
                )
            return DeviceBinding(
                device_id=device_id,
                student_id=student_id,
                organization_id=organization_id or existing.organization_id,
                device_name=device_name or existing.device_name,
                device_type=device_type,
                status="ACTIVE",
                bound_at=existing.bound_at,
                last_synced_at=now_ts,
            )

        # Ensure student user exists to satisfy foreign key constraint
        if not self.get_user(student_id):
            org_id = organization_id or "org-default"
            if not self.get_organization(org_id):
                self.create_organization(
                    Organization(id=org_id, name="Default Organization", slug=f"slug-{org_id}")
                )
            self.create_user(
                User(
                    id=student_id,
                    email=f"{student_id}@student.gayatri.ai",
                    full_name=student_id,
                    role=UserRole.STUDENT,
                    organization_id=org_id,
                )
            )

        binding = DeviceBinding(
            device_id=device_id,
            student_id=student_id,
            organization_id=organization_id,
            device_name=device_name,
            device_type=device_type,
            status="ACTIVE",
            bound_at=now_ts,
            last_synced_at=now_ts,
        )
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO device_bindings (
                    device_id, student_id, organization_id, device_name,
                    device_type, status, bound_at, last_synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    binding.device_id,
                    binding.student_id,
                    binding.organization_id,
                    binding.device_name,
                    binding.device_type,
                    binding.status,
                    binding.bound_at,
                    binding.last_synced_at,
                ),
            )
        return binding

    def get_device_binding(self, device_id: str) -> Optional[DeviceBinding]:
        """Look up device registration by device hardware ID."""
        with self._get_connection() as conn:
            r = conn.execute(
                "SELECT * FROM device_bindings WHERE device_id = ?;", (device_id,)
            ).fetchone()
            if not r:
                return None
            return DeviceBinding(
                device_id=r["device_id"],
                student_id=r["student_id"],
                organization_id=r["organization_id"],
                device_name=r["device_name"],
                device_type=r["device_type"] if "device_type" in r.keys() else "desktop",
                status=r["status"] if "status" in r.keys() else "ACTIVE",
                bound_at=r["bound_at"],
                last_synced_at=r["last_synced_at"],
            )

    def get_devices_for_student(self, student_id: str) -> List[DeviceBinding]:
        """List all devices registered to a student."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM device_bindings WHERE student_id = ? ORDER BY bound_at ASC;",
                (student_id,),
            ).fetchall()
            return [
                DeviceBinding(
                    device_id=r["device_id"],
                    student_id=r["student_id"],
                    organization_id=r["organization_id"],
                    device_name=r["device_name"],
                    device_type=r["device_type"] if "device_type" in r.keys() else "desktop",
                    status=r["status"] if "status" in r.keys() else "ACTIVE",
                    bound_at=r["bound_at"],
                    last_synced_at=r["last_synced_at"],
                )
                for r in rows
            ]

    def unbind_device(self, device_id: str) -> bool:
        """Revoke a device binding."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM device_bindings WHERE device_id = ?;", (device_id,))
            return cur.rowcount > 0

    def update_device_sync_time(self, device_id: str, sync_time: Optional[str] = None) -> bool:
        """Update last synchronization timestamp for an active device."""
        ts = sync_time or datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE device_bindings SET last_synced_at = ? WHERE device_id = ?;",
                (ts, device_id),
            )
            return cur.rowcount > 0



