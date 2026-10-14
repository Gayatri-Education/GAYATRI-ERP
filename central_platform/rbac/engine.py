"""RBAC permission matrix, resource-scoping rules, and server-side policy enforcement engine (Phase 04).

Master Plan Section 13:
- 5 Canonical Roles: SUPER_ADMIN, ORG_ADMIN, COURSE_ADMIN, TEACHER, STUDENT
- Granular permission matrix
- Multi-tenant organization scoping
- Student self-access isolation
- Teacher cohort-scoped access
- PBKDF2-HMAC-SHA256 password hashing with 100,000 iterations and 16-byte random salts
"""

from __future__ import annotations

import hashlib
import os
import secrets
from typing import Optional, Set, Union

from central_platform.models.schema import UserRole


class Permission(str):
    # Student permissions
    STUDENT_LEARN = "student.learn"
    STUDENT_VIEW_OWN_PROGRESS = "student.view_own_progress"
    STUDENT_VIEW_OWN_SLR = "student.view_own_slr"
    STUDENT_ATTEMPT_ASSESSMENT = "student.attempt_assessment"

    # Teacher permissions
    VIEW_STUDENT_PROGRESS = "teacher.view_student_progress"
    CREATE_ASSIGNMENT = "teacher.create_assignment"
    WRITE_AI_INSTRUCTION = "teacher.write_ai_instruction"
    VIEW_STUDENT_SESSIONS = "teacher.view_student_sessions"
    VIEW_TEACHER_DASHBOARD = "teacher.view_teacher_dashboard"
    MANAGE_INTERVENTIONS = "teacher.manage_interventions"

    # Course Admin permissions
    MANAGE_COURSES = "course_admin.manage_courses"
    MANAGE_CURRICULA = "course_admin.manage_curricula"

    # Org Admin permissions
    MANAGE_ORGANIZATION = "org_admin.manage_organization"
    MANAGE_USERS = "org_admin.manage_users"
    VIEW_ORG_ANALYTICS = "org_admin.view_org_analytics"

    # Parent permissions
    PARENT_VIEW_CHILD_PROGRESS = "parent.view_child_progress"
    PARENT_VIEW_CHILD_ATTENDANCE = "parent.view_child_attendance"
    PARENT_VIEW_CHILD_INVOICES = "parent.view_child_invoices"
    PARENT_VIEW_TEACHER_UPDATES = "parent.view_teacher_updates"

    # Super Admin permissions
    GLOBAL_SYSTEM_CONTROL = "super_admin.global_system_control"
    MANAGE_ALL_ORGANIZATIONS = "super_admin.manage_all_organizations"
    AI_PROVIDER_CONFIG = "super_admin.ai_provider_config"


ROLE_PERMISSIONS: dict[UserRole, Set[str]] = {
    UserRole.SUPER_ADMIN: {
        Permission.GLOBAL_SYSTEM_CONTROL,
        Permission.MANAGE_ALL_ORGANIZATIONS,
        Permission.AI_PROVIDER_CONFIG,
        Permission.MANAGE_ORGANIZATION,
        Permission.MANAGE_USERS,
        Permission.VIEW_ORG_ANALYTICS,
        Permission.MANAGE_COURSES,
        Permission.MANAGE_CURRICULA,
        Permission.VIEW_STUDENT_PROGRESS,
        Permission.CREATE_ASSIGNMENT,
        Permission.WRITE_AI_INSTRUCTION,
        Permission.VIEW_STUDENT_SESSIONS,
        Permission.VIEW_TEACHER_DASHBOARD,
        Permission.MANAGE_INTERVENTIONS,
        Permission.STUDENT_LEARN,
        Permission.STUDENT_VIEW_OWN_PROGRESS,
        Permission.STUDENT_VIEW_OWN_SLR,
        Permission.STUDENT_ATTEMPT_ASSESSMENT,
        Permission.PARENT_VIEW_CHILD_PROGRESS,
        Permission.PARENT_VIEW_CHILD_ATTENDANCE,
        Permission.PARENT_VIEW_CHILD_INVOICES,
        Permission.PARENT_VIEW_TEACHER_UPDATES,
    },
    UserRole.ORG_ADMIN: {
        Permission.MANAGE_ORGANIZATION,
        Permission.MANAGE_USERS,
        Permission.VIEW_ORG_ANALYTICS,
        Permission.MANAGE_COURSES,
        Permission.MANAGE_CURRICULA,
        Permission.VIEW_STUDENT_PROGRESS,
        Permission.CREATE_ASSIGNMENT,
        Permission.VIEW_TEACHER_DASHBOARD,
        Permission.VIEW_STUDENT_SESSIONS,
    },
    UserRole.COURSE_ADMIN: {
        Permission.MANAGE_COURSES,
        Permission.MANAGE_CURRICULA,
        Permission.VIEW_STUDENT_PROGRESS,
        Permission.CREATE_ASSIGNMENT,
    },
    UserRole.TEACHER: {
        Permission.VIEW_STUDENT_PROGRESS,
        Permission.CREATE_ASSIGNMENT,
        Permission.WRITE_AI_INSTRUCTION,
        Permission.VIEW_STUDENT_SESSIONS,
        Permission.VIEW_TEACHER_DASHBOARD,
        Permission.MANAGE_INTERVENTIONS,
    },
    UserRole.STUDENT: {
        Permission.STUDENT_LEARN,
        Permission.STUDENT_VIEW_OWN_PROGRESS,
        Permission.STUDENT_VIEW_OWN_SLR,
        Permission.STUDENT_ATTEMPT_ASSESSMENT,
    },
    UserRole.PARENT: {
        Permission.PARENT_VIEW_CHILD_PROGRESS,
        Permission.PARENT_VIEW_CHILD_ATTENDANCE,
        Permission.PARENT_VIEW_CHILD_INVOICES,
        Permission.PARENT_VIEW_TEACHER_UPDATES,
    },
}


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Hash password using PBKDF2 with SHA-256 (100,000 iterations)."""
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return key.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    """Verify password against stored PBKDF2 hash using constant-time comparison."""
    try:
        salt = bytes.fromhex(salt_hex)
        key, _ = hash_password(password, salt)
        return secrets.compare_digest(key, password_hash)
    except Exception:
        return False


def normalize_role(role: Union[UserRole, str]) -> UserRole:
    """Normalize string or UserRole into standard UserRole enum."""
    if isinstance(role, UserRole):
        return role
    role_str = str(role).lower().strip()
    if role_str == "admin":
        return UserRole.ORG_ADMIN
    return UserRole(role_str)


def has_permission(role: Union[UserRole, str], permission: str) -> bool:
    """Check if role has given permission."""
    try:
        norm_role = normalize_role(role)
        return permission in ROLE_PERMISSIONS.get(norm_role, set())
    except (ValueError, KeyError):
        return False


def check_resource_access(
    actor_role: Union[UserRole, str],
    actor_org_id: Optional[str],
    actor_user_id: str,
    target_org_id: Optional[str] = None,
    target_student_id: Optional[str] = None,
    assigned_student_ids: Optional[Set[str]] = None,
) -> bool:
    """Enforce Section 13 resource-level authorization boundaries.
    
    Returns True if access is permitted, False otherwise.
    """
    try:
        norm_role = normalize_role(actor_role)
    except (ValueError, KeyError):
        return False

    # 1. Super Admin has unrestricted system-wide access
    if norm_role == UserRole.SUPER_ADMIN:
        return True

    # 2. Multi-tenant Organization Scope:
    # All non-super admins are strictly bounded to their own organization
    if target_org_id and actor_org_id and target_org_id != actor_org_id:
        return False

    # 3. Student Scope:
    # Students can only access their own student records, sessions, and SLRs
    if norm_role == UserRole.STUDENT:
        if target_student_id and target_student_id != actor_user_id:
            return False
        return True

    # 4. Parent Scope:
    # Parents can access records of their linked children
    if norm_role == UserRole.PARENT:
        if target_student_id:
            if assigned_student_ids is not None:
                if target_student_id not in assigned_student_ids and target_student_id != actor_user_id:
                    return False
        return True

    # 5. Teacher Scope:
    # Teachers can access students assigned to their courses/cohorts
    if norm_role == UserRole.TEACHER:
        if target_student_id and assigned_student_ids is not None:
            if target_student_id not in assigned_student_ids and target_student_id != "all":
                return False
        return True

    # 6. Org Admin & Course Admin Scope:
    # Bounded to organization (verified in check #2 above)
    if norm_role in (UserRole.ORG_ADMIN, UserRole.COURSE_ADMIN):
        return True

    return False
