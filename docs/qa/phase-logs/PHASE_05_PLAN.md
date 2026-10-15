# Phase 05 Plan: Student, Teacher, Admin, and Fee UI-to-API Wiring (No Toast-Only Success)

**Phase:** PHASE-05  
**Status:** IN_PROGRESS  
**Date:** 2026-10-15  
**Target Findings:** ERP-007, ERP-008, ERP-009, ERP-011, ERP-018 (and ERP-010)

---

## 1. Problem Analysis & Objectives

### 1.1 ERP-007: Billing Generation UI Is Toast-Only
- **Current Behavior:**
  - In `app/ui/design_system/fee_admin.js`, `generateMonthlyBilling(monthYear)` only calls `window.GayatriUI.showToast(...)` with a success message.
  - No backend request is dispatched. No invoices, billing batch, or ledger transactions are created or persisted.
- **Required Behavior:**
  - Implement authoritative backend method `FeeAdminController.generate_monthly_billing(org_id, month_year, db)`.
  - Expose authenticated REST endpoint `POST /api/v1/finance/billing/generate` requiring `ORG_ADMIN` or `SUPER_ADMIN` authorization.
  - Wire `fee_admin.js` `generateMonthlyBilling(monthYear)` to call `POST /api/v1/finance/billing/generate`.
  - Success toast must only be displayed after the backend confirms creation with the count of generated invoices. On error, display an error toast.

### 1.2 ERP-008: Outstanding Report CSV Export Is Toast-Only
- **Current Behavior:**
  - In `app/ui/design_system/fee_admin.js`, `exportOutstandingReport()` only displays an informational toast without downloading or requesting data.
- **Required Behavior:**
  - Expose authenticated REST endpoints:
    - `GET /api/v1/finance/reports/outstanding` returning structured outstanding report items.
    - `GET /api/v1/finance/reports/outstanding/export` returning the CSV file with `Content-Disposition: attachment; filename="outstanding_fee_report.csv"`.
  - Wire `fee_admin.js` `exportOutstandingReport()` to fetch the CSV endpoint, trigger a browser download via Blob URL, and show a success toast upon completion.

### 1.3 ERP-009: Receipt Printing Persisted Verification
- **Current Behavior:**
  - `printReceipt(receiptId)` in `fee_admin.js` was wired to `GET /api/v1/finance/receipts/{receiptId}` during Phase 03.
- **Required Verification:**
  - Add end-to-end assertions in Phase 05 test suite verifying that invalid/unpersisted receipts trigger an error toast and do not print, while valid receipts confirm before printing.

### 1.4 ERP-011: Teacher Copilot Action Does Not Call Backend
- **Current Behavior:**
  - In `app/ui/design_system/teacher.js`, `triggerCopilotAnalysis()` displays a toast without invoking backend services.
- **Required Behavior:**
  - Wire `triggerCopilotAnalysis(courseId)` to call `GET /api/v1/teachers/copilot/briefing` or `POST /api/v1/teachers/copilot/query`.
  - Render analysis findings / recommendations into the `.copilot-panel` / DOM and show a success toast only after successful backend response. On failure, show an error toast.

### 1.5 ERP-010: Student Review Action Is Toast-Only
- **Current Behavior:**
  - In `app/ui/design_system/student.js`, `startReview(conceptId)` only displays a toast.
- **Required Behavior:**
  - Wire `startReview(conceptId, studentId, courseId)` to submit an action to `POST /api/v1/students/{studentId}/action` with `action_type="review_start"`.
  - Display success toast only after server acknowledgment.

### 1.6 ERP-018: Dynamic `innerHTML` and Inline Event Interpolation Vulnerabilities
- **Current Behavior:**
  - In `app/ui/design_system/student.js`, `renderReviewQueue` interpolates `${item.concept_id}` directly into an `onclick="..."` string attribute: `<button onclick="window.GayatriStudent.startReview('${item.concept_id}')">`. Malicious or unexpected characters can break out and execute arbitrary JavaScript (XSS).
  - In `app/ui/design_system/components.js`, `escapeHtml` omits single quotes (`'`), leaving single-quoted attributes vulnerable to injection.
- **Required Behavior:**
  - Harden `escapeHtml` in `components.js` to escape `'` as `&#39;`.
  - Refactor `renderReviewQueue` to use safe data attributes (`data-concept-id="..."`) with event listeners or sanitized attribute escaping.
  - Enforce strict type conversions (numbers) on numeric metrics in `renderDashboardStats` and `renderClassOverview`.

---

## 2. Implementation Plan

1. **Reproduction & Regression Suite:**
   - Author `tests/test_qa_phase05_ui_bridges_contracts.py` testing:
     - `POST /api/v1/finance/billing/generate` authentication, role-scoping, and durable invoice batch generation.
     - `GET /api/v1/finance/reports/outstanding` and `/export` endpoints.
     - Student review action dispatch and persistence.
     - Teacher copilot analysis briefing dispatch and response contract.
     - JS controllers: verify `fee_admin.js`, `student.js`, and `teacher.js` contain the async API calls and lack raw unescaped inline onclick injection.
     - XSS prevention: prove `escapeHtml` escapes single quotes (`&#39;`) and double quotes (`&quot;`).

2. **Backend Services & Endpoints:**
   - In `central_platform/portals/fee_admin.py`:
     - Implement `generate_monthly_billing(org_id, month_year, db=None)`.
   - In `central_platform/api/routes/finance.py`:
     - Add `POST /api/v1/finance/billing/generate`.
     - Add `GET /api/v1/finance/reports/outstanding`.
     - Add `GET /api/v1/finance/reports/outstanding/export`.

3. **Frontend Hardening:**
   - In `app/ui/design_system/components.js`:
     - Harden `escapeHtml` to escape `'` (`&#39;`).
   - In `app/ui/design_system/fee_admin.js`:
     - Update `generateMonthlyBilling(monthYear)` to perform authenticated fetch to `/api/v1/finance/billing/generate`.
     - Update `exportOutstandingReport()` to fetch `/api/v1/finance/reports/outstanding/export` and trigger download.
   - In `app/ui/design_system/teacher.js`:
     - Update `triggerCopilotAnalysis(courseId)` to call `/api/v1/teachers/copilot/briefing` and update copilot UI elements.
   - In `app/ui/design_system/student.js`:
     - Update `startReview(conceptId, studentId, courseId)` to call `/api/v1/students/{student_id}/action`.
     - Update `renderReviewQueue(items)` to eliminate inline string-interpolated `onclick` handler, using `data-concept-id` with safe event delegation.
     - Sanitize numeric attributes in `renderDashboardStats`.

4. **Verification & Regression:**
   - Run `tests/test_qa_phase05_ui_bridges_contracts.py`.
   - Run UI regression suites: `tests/test_phase27_student_portal_ui.py`, `tests/test_phase28_teacher_portal_ui.py`, `tests/test_phase31_fee_admin_ui.py`.
   - Run full automated regression suite (`pytest -q -m "not gui"`).
   - Update `PROGRESS_TRACKER.yaml`, `ISSUE_REGISTER.md`, and log `PHASE_05_LOG.md`.
