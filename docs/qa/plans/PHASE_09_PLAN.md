# Remediation Phase 09 Plan: Genuine UI-to-API-to-Database E2E Workflows & Disconnected Button Elimination (QA-009)

**Phase:** Phase 09  
**Issue Code:** QA-009  
**Contract Ref:** [`GAYATRI_ERP_QA_REMEDIATION_GOAL.md`](file:///c:/Users/user/Desktop/gayatri/Gayatri-ERP/GAYATRI_ERP_QA_REMEDIATION_GOAL.md) Section 12  
**Status:** IN_PROGRESS (Step 2: Plan)  
**Execution Date:** 2026-10-15  
**Branch:** `qa/production-readiness-remediation`  

---

## 1. Objectives & Invariants
1. **Prove Full-Stack E2E Connectivity:** For all 12 core workflows defined in Section 12 of `GAYATRI_ERP_QA_REMEDIATION_GOAL.md`, verify the entire lifecycle from UI action payload through central API routes down to durable database persistence and post-mutation state verification.
2. **Eliminate Disconnected Buttons and Toast-Only Fakes:**
   - No business action button may simply fire a cosmetic toast (`AdminApp.toast(...)`) without executing backend logic or updating authoritative state.
   - Any feature whose backend is pending or simulated must be visibly labeled (`[SIMULATED DEMO]` or disabled with a helpful tooltip) rather than deceiving the user with fake confirmation messages.
3. **Refetch Authoritative Postconditions:**
   - After a mutation (e.g. invoice generation, attendance marking, certificate generation, course enrollment), UI must re-fetch authoritative server state rather than blindly incrementing local counters.
4. **Enforce Complete Test Suite:**
   - Author `tests/test_phase09_ui_api_db_e2e.py` covering:
     1. Identity & Auth Lifecycle E2E (Org provision -> User provision -> Login -> Protected access -> Revocation).
     2. Admissions to SIS Conversion E2E (Inquiry -> Application -> Acceptance -> Conversion to Student Profile + Guardian Link + Class Enrollment).
     3. Attendance Lifecycle E2E (Create session -> Mark records -> Retrieve -> Audit-logged correction).
     4. Financial Invoicing & Webhook E2E (Billing batch -> Invoice -> Payment Webhook -> Verified Receipt -> Ledger credit).
     5. Examinations & Report Card E2E (Series -> Schedule -> Marks submission -> Locking -> Grade calculation -> Published Report Card).
     6. Teacher Copilot & Instruction Lifecycle E2E (Instruction create -> Copilot briefing -> Retrieval).
     7. Student Learning & Spaced Review E2E (Session start -> Event ingestion -> Mastery update -> Spaced review queue).
     8. UI Contract Audit (Verifying no cosmetic toast buttons exist without backend confirmation or truthful simulation labels).

---

## 2. Code Areas Under Review
- `app/ui/admin_portal.html`:
  - Buttons currently invoking `AdminApp.toast(...)`:
    - Line 913: `➕ Generate Invoices` -> wire to `AdminApp.triggerInvoiceGeneration()` calling `/api/v1/finance/billing/generate`.
    - Line 965: `🖨️ Print Batch Badges` -> wire to real printable view or `window.print()`.
    - Line 972: `➕ Issue Certificate` -> wire to `AdminApp.issueCertificate()` calling `/api/v1/reports/generate`.
    - Line 1023: `➕ Reorder Stock` -> mark as `[SIMULATED DEMO]` with disabled status or simulated modal disclosure.
    - Line 1774: `Toggle Status` -> wire to `/api/v1/attendance/records/{id}/correct`.
    - Line 1781: `markAllPresent()` -> wire to `/api/v1/attendance/sessions/{id}/records`.
    - Line 1863: `📜 View Report Card` -> wire to `/api/v1/reports/{id}` or report modal.
    - Line 1919: `renderLogistics()` -> load routes from `/api/v1/transport/routes` and render truthful status.
- `app/ui/design_system/student.js` & `teacher.js`:
  - Ensure UI functions handle network errors gracefully, display loading states, and refresh container data from API.

---

## 3. Step-by-Step Execution Plan
1. **Step 1 (Inspect):** Map all UI buttons in `admin_portal.html` and UI design system files.
2. **Step 2 (Plan):** Document in this plan file.
3. **Step 3 (Reproduce):** Author `tests/test_phase09_ui_api_db_e2e.py` testing the full E2E workflow chains and contract checks.
4. **Step 4 (Implement):**
   - Refactor `app/ui/admin_portal.html` to eliminate all cosmetic toast substitutions.
   - Bind invoice generation, attendance marking, certificate generation, and report viewing to live API endpoints.
   - Clearly mark unbacked hardware/inventory stock reordering as `[SIMULATED DEMO]`.
5. **Step 5 (Test):** Run `pytest -v tests/test_phase09_ui_api_db_e2e.py`.
6. **Step 6 (Debug):** Resolve any discrepancies or schema mismatches.
7. **Step 7 (Review):** Run full regression suite across Phases 01 through 09.
8. **Step 8 (Record):** Author `docs/qa/phase-logs/REMEDIATION_PHASE_09_LOG.md`, update tracker and register.
9. **Step 9 (Commit):** Commit Phase 09 changes.
10. **Step 10 (Advance):** Proceed to Phase 10.
