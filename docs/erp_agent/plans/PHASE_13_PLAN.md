# Phase 13 Plan — Public Institution CMS and Protected Forms

**Document:** `docs/erp_agent/plans/PHASE_13_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 13 — Public Institution CMS and Protected Forms  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 13 verifies the public school website/CMS, page creation, post publication, content sanitization, and public lead/contact form ingestion:
1. **CMS Page & Post Management:** Institutional pages (Vision, Mission, Leadership, Academics) and news/events in `CampusService`.
2. **Draft, Publish & Archive Lifecycle:** Content starts in `DRAFT`; publication (`publish_page`, `publish_post`) transitions to `PUBLISHED` and populates the unauthenticated public endpoints.
3. **HTML Sanitization & Anti-XSS Protection:** Script tag stripping, event handler removal, and safe URL scheme validation via `SecurityAuditor.sanitize_html()`.
4. **Public Form Ingestion:** Public website admission inquiry and contact forms submit directly to canonical CRM (`AdmissionsService`) with spam protection, rate limiting, and zero exposure of private tenant data.

---

## 2. Likely Files & Scope Boundary

- `central_platform/campus/service.py` (`CampusService`)
- `central_platform/models/campus.py` (`CMSPage`, `CMSPost`, `CMSStatus`)
- `central_platform/api/routes/cms.py`
- `central_platform/api/routes/admissions.py`
- `central_platform/security/auditor.py`
- `tests/test_qa_phase12_security_privacy_xss.py`
- `tests/test_qa_phase14_e2e_product_acceptance.py`

---

## 3. Targeted Test Scenarios

1. Creating CMS page persists in `DRAFT` status and is omitted from public page listings.
2. Publishing CMS page transitions status to `PUBLISHED` and becomes accessible via `/api/v1/cms/public/pages`.
3. HTML content with malicious `<script>` tags or inline `onload`/`onerror` handlers is sanitized.
4. Public admission inquiry submissions ingest safely into the CRM without requiring admin auth tokens.
5. Rate limiting prevents form spam or brute force submissions.

---

## 4. Exit Criteria (Binary Gate)

- [ ] CMS page and post draft-to-publish lifecycle verified.
- [ ] HTML sanitization and anti-XSS stripping verified.
- [ ] Public lead ingestion connected to canonical admissions CRM verified.
- [ ] Public endpoints verified to leak zero private/unauthorized tenant data.
- [ ] `docs/erp_agent/reports/PHASE_13_REPORT.md` and `docs/erp_agent/regressions/PHASE_13_REGRESSION.md` generated with passing evidence.
