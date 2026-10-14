# ERP Feature Scope: Official Certificates & Document Issuance (ERP-17)

**Feature ID:** `ERP-17`  
**Governing Contract:** `DEVELOPMENT.md` (§6.10, §7 Phase 06)  
**Parent Phase:** Phase 06 (Full ERP Expansion)  
**Status:** In Preparation  
**Last Updated:** 2026-10-15  

---

## 1. Business Purpose and Beneficiaries
- **Purpose:** Issue official institutional certificates (Transfer Certificates, Bonafide Certificates, Character Certificates, Sports Merit) with cryptographic SHA-256 tamper-evident verification hashes.
- **Beneficiaries:**
  - **School Administration / Registrar:** Issue, verify, or revoke official student certificates.
  - **Students / Parents:** Obtain verified certificates required for college admissions or transfers.

---

## 2. Personas and Access Matrix

| Role | Issue Certificate | Revoke Certificate | Verify Certificate Hash | View Certificate |
|---|---|---|---|---|
| **Student** | ❌ | ❌ | ✅ | ✅ (Self) |
| **Registrar** | ✅ | ✅ | ✅ | ✅ |
| **Org Admin** | ✅ | ✅ | ✅ | ✅ |

---

## 3. Scope & Non-Scope
- **In-Scope:**
  - Certificate types: `TRANSFER_CERTIFICATE`, `BONAFIDE`, `CHARACTER`, `MERIT`.
  - Certificate lifecycle: `ISSUED` -> `REVOKED`.
  - Cryptographic verification hash (`document_hash`) allowing public verification of document authenticity.
- **Non-Scope:**
  - Physical holographic sticker printing machines.

---

## 4. Data Entities (Migration 014 candidate)
1. `official_certificates` (id, organization_id, student_id, certificate_type, certificate_number, issue_date, valid_until, status, document_hash, payload_json, issued_by, revoked_by, revocation_reason, created_at, updated_at).
