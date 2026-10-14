# ERP Feature Scope: Public Institutional CMS & Web Content (ERP-18)

**Feature ID:** `ERP-18`  
**Governing Contract:** `DEVELOPMENT.md` (§6.10, §7 Phase 06)  
**Parent Phase:** Phase 06 (Full ERP Expansion)  
**Status:** In Preparation  
**Last Updated:** 2026-10-15  

---

## 1. Business Purpose and Beneficiaries
- **Purpose:** Publish school public website pages (About Us, Admissions Criteria, Curriculum, Faculty, Contact) and announcements/news posts with publication approval workflows.
- **Beneficiaries:**
  - **Prospective Parents & Students:** Browse school information, admission notices, events.
  - **School PR / Webmaster:** Author, edit, preview, and publish pages and news posts.

---

## 2. Personas and Access Matrix

| Role | Author Draft | Publish Page/Post | Unpublish / Archive | View Public Site |
|---|---|---|---|---|
| **Public Visitor** | ❌ | ❌ | ❌ | ✅ |
| **Webmaster / Content Editor** | ✅ | ❌ | ❌ | ✅ |
| **Org Admin** | ✅ | ✅ | ✅ | ✅ |

---

## 3. Scope & Non-Scope
- **In-Scope:**
  - CMS Pages (slug, title, content_html, status `DRAFT`/`PUBLISHED`/`ARCHIVED`).
  - CMS News / Blog Posts (title, slug, excerpt, content_html, publish_date).
  - Uniqueness of URL slugs within each organization.
  - Public endpoint requiring zero authentication, completely isolated from administrative API routes.
- **Non-Scope:**
  - Full-blown headless external WordPress plugin ecosystem.

---

## 4. Data Entities (Migration 014 candidate)
1. `cms_pages` (id, organization_id, title, slug, content_html, status, published_at, created_at, updated_at, UNIQUE(organization_id, slug)).
2. `cms_posts` (id, organization_id, title, slug, excerpt, content_html, status, published_at, author_name, created_at, updated_at, UNIQUE(organization_id, slug)).
