# Phase 16 Plan — Desktop and Responsive Admin/Teacher/Student/Parent Portals

**Document:** `docs/erp_agent/plans/PHASE_16_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 16 — Admin, Teacher, Student, Parent Portals and Desktop UX  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 16 verifies the desktop application shell, design system, portal bridges, and role-based UI controllers:
1. **Application Shell Architecture:** Application shell manager, responsive sidebar/topbar navigation, role-aware routing, language selector, and session/auth lifecycle.
2. **Shared UI Design System:** Design system registry, dark/light theme semantic tokens, 19 core UI component specifications (buttons, modals, drawers, toasts, cards, tables, chat, skeletons, status indicators).
3. **Student Portal UI & Real API Wiring:** Dashboard metrics, curriculum tree, review queue, activity stream, and real backend action dispatching (`startReview`).
4. **Teacher Portal UI & Copilot Integration:** Roster table, class overview grid, student health records, interventions, and AI briefing/copilot dispatching.
5. **Parent Portal UI & Child Switching:** Multi-child switcher, privacy isolation, attendance/progress views, and authorized guardian linkages.
6. **Finance & Admin Bridges:** Real API wiring for monthly billing generation, outstanding report export (CSV), and receipt printing verification.
7. **Anti-XSS & Client-Side Escaping:** Contextual HTML sanitization in JavaScript bridges preventing inline script execution.

---

## 2. Likely Files & Scope Boundary

- `app/` (PySide6 desktop shell, portal controllers, static assets)
  - `app/shell/` (`AppShellManager`, `shell.css`, `shell.js`)
  - `app/portals/student/` (`StudentPortalController`, `student.css`, `student.js`)
  - `app/portals/teacher/` (`TeacherPortalController`, `teacher.css`, `teacher.js`)
  - `app/portals/parent/` (`ParentPortalController`, `parent.css`, `parent.js`)
  - `app/design_system/` (`DesignSystemRegistry`, `tokens.css`, `components.css`, `components.js`)
- `tests/test_qa_phase05_ui_bridges_contracts.py`
- `tests/test_phase25_application_shell.py`
- `tests/test_phase27_student_portal_ui.py`
- `tests/test_phase28_teacher_portal_ui.py`
- `tests/test_phase29_parent_portal_ui.py`
- `tests/test_phase24_shared_ui_design_system.py`
- `tests/test_qa_phase07_portal_contracts.py`

---

## 3. Targeted Test Scenarios

1. Verify real API endpoint wiring for fee generation, billing, and exports (`test_fee_admin_controller_generate_monthly_billing`).
2. Verify teacher copilot action invokes backend AI briefing endpoint (`test_teacher_copilot_briefing_endpoint`).
3. Verify student review action submits real learning action to backend (`test_student_review_action_endpoint`).
4. Verify application shell asset completeness and controller routing (`test_shell_files_exist`, `test_app_shell_portal_routing`).
5. Verify student, teacher, and parent portal tab controllers and model summaries.
6. Verify design system semantic tokens completeness and component coverage (`test_theme_tokens_completeness`, `test_css_component_specs_coverage`).
7. Verify parent portal privacy and child isolation boundaries (`test_parent_portal_privacy_and_child_isolation`).

---

## 4. Exit Criteria (Binary Gate)

- [ ] Zero synthetic mock fallbacks in production UI bridges; real API wiring verified.
- [ ] Application shell navigation, role-based routing, and theme tokens verified.
- [ ] Student, Teacher, Parent, and Admin portals verified.
- [ ] Multi-child switcher and guardian privacy boundaries verified.
- [ ] `docs/erp_agent/reports/PHASE_16_REPORT.md` and `docs/erp_agent/regressions/PHASE_16_REGRESSION.md` generated with passing evidence.
