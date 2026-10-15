# Phase 02 Plan — Eliminate Synthetic Parent Data & Fake Dashboard Completeness (QA-002)

## 1. Context & Objectives
In Phase 01, we restored trustworthy CI and isolated production configuration tests.
In Phase 02, we address QA-002: eliminating synthetic parent data, hardcoded dashboard figures, and the absence of guardian-to-student authorization boundaries in the parent portal.

### Target Locations
- `app/portals/parent/controller.py`: Currently hardcodes `parent_001`, `child_001`, `overall_mastery_pct: 84`, `attendance_pct: 96.5`, `pending_assignments_count: 2`, and catches exceptions silently.
- `central_platform/portals/parent.py`: Contains hardcoded `parent_001` bypass and fallback metrics `84%`, `96.5%`, `child_101`.
- `central_platform/db.py`: Needs `get_guardian_students()` and `is_guardian_linked()` to query database-backed guardian links with portal access flags.

---

## 2. Gap Analysis & Root Causes
1. **Hardcoded Fallbacks:** Both `app/portals/parent/controller.py` and `central_platform/portals/parent.py` default to synthetic user IDs (`parent_001`, `child_001`/`child_101`) and operational figures (`84%`, `96.5%`, `2`).
2. **Missing Boundary Checks:** `ParentPortalController.get_dashboard_context()` has no tenant validation, no guardian-child link verification, and no active-user check.
3. **Permission Bypass:** `central_platform/portals/parent.py` had an explicit bypass `if parent_id is not None and parent_id != "parent_001":`, completely exempting `parent_001` from authorization.
4. **Exception Masking:** Database exceptions were caught with `logger.debug` and ignored, allowing the caller to receive plausible-looking fake data.

---

## 3. Remediation Architecture

### A. Database Enhancements (`central_platform/db.py`)
- Add `get_guardian_students(organization_id, guardian_id, can_access_portal_only=True)` to query `student_guardian_links` joined with `student_profiles`, `persons`, and `users`.
- Add `is_guardian_linked(organization_id, guardian_id, student_id, check_portal_access=True)` helper to verify relationship and tenant match.

### B. Core Portal Controller (`central_platform/portals/parent.py`)
- Eliminate production hardcoded values (84%, 96.5%, 2).
- Remove `parent_001` permission bypass.
- Gate legacy demo content strictly behind `not is_production_mode()` and explicit demo mode.
- In production mode, forbid demo data (`ValueError`).
- If no data exists, return honest empty values (0 mastery, 0.0 attendance, 0 assignments), never plausible placeholders.

### C. UI Portal Controller (`app/portals/parent/controller.py`)
- Require parent identity from session/auth; fail closed or report unauthenticated state (never default to `parent_001`).
- Enforce active account check (`user.is_active is not False`).
- Enforce tenant isolation and guardian link check:
  - If requested child is not linked to parent, raise `PermissionError`.
  - If requested child belongs to different organization, raise `PermissionError`.
- Load authentic domain metrics:
  - Mastery: Calculated from SLR mastery states; 0 if none.
  - Attendance: Calculated from attendance records / sessions; 0.0 if none.
  - Assignments: Count of real pending assignments; 0 if none.
  - Fees: Real fee balance or structured unavailable state.
- Implement honest error states: dependency exceptions produce explicit section-level error status (`{"status": "degraded", "error": str(exc)}`), never falling back to fake numbers.
- Provide `switch_child(parent_id, target_child_id, organization_id)` that resets state on failure so stale child data is never leaked.
- Gate demo mode behind `not is_production_mode()`; mark context with `is_demo: True` and visual banner; forbid in production.

---

## 4. Verification & Testing Strategy
Author `tests/test_phase02_parent_portal_remediation.py` covering:
1. Real values derived from database and domain services.
2. Empty DB returns honest zeros (0%, 0.0%, 0), not fake numbers.
3. Non-existent child returns 404 / NotFound / ValueError.
4. Unrelated parent-child relationship raises `PermissionError`.
5. Cross-tenant child access raises `PermissionError`.
6. Disabled or revoked parent account raises `PermissionError`.
7. Database / service exception returns explicit degraded status, no fake metrics.
8. Partially available domains return partial real data + explicit unavailable status.
9. Demo mode works in non-production with `is_demo=True` flag and banner.
10. Production mode strictly rejects demo mode (`ValueError`) and forbids sample metrics.
11. Child switching isolation ensures failed switch clears active context.
12. Read-back / restart verification confirms data persistence across DB re-initialization.

Regression Verification:
- `pytest tests/test_phase29_parent_portal_ui.py tests/test_phase34_parent_privacy.py tests/test_phase07_portal_ui.py tests/test_phase09_analytics_remediation.py -v`
- `pytest -v tests/architecture`
- Full headless suite smoke check.

---

## 5. Exit Criteria
- [ ] No synthetic operational metrics exist in production execution paths.
- [ ] Cross-tenant and unlinked child requests are rejected with `PermissionError`.
- [ ] UI / controller differentiates zero from missing data and actual errors.
- [ ] Data is verified from the database/service layer with restart/read-back verification.
- [ ] Architecture tests pass with zero violations.
- [ ] All existing and new tests pass without weakening any assertion.
