# ERP Feature Scope: Visitor & Campus Gate Pass Management (ERP-16)

**Feature ID:** `ERP-16`  
**Governing Contract:** `DEVELOPMENT.md` (§6.9, §7 Phase 06)  
**Parent Phase:** Phase 06 (Full ERP Expansion)  
**Status:** In Preparation  
**Last Updated:** 2026-10-15  

---

## 1. Business Purpose and Beneficiaries
- **Purpose:** Safeguard student security through formal front-desk visitor registration, host staff notification, visitor badge/pass issuance, and check-in/out timestamp logging.
- **Beneficiaries:**
  - **Security Guards / Receptionists:** Register visiting parents/vendors, print visitor pass.
  - **Campus Administration:** Audit visitor logs and emergency headcount records.

---

## 2. Personas and Access Matrix

| Role | Register Visitor | Check Out Visitor | View Visitor Log |
|---|---|---|---|
| **Security Guard** | ✅ | ✅ | ✅ |
| **Front Desk** | ✅ | ✅ | ✅ |
| **Org Admin** | ✅ | ✅ | ✅ |

---

## 3. Scope & Non-Scope
- **In-Scope:**
  - Visitor registration (name, phone, purpose, host staff member, badge/pass number).
  - Status transitions (`CHECKED_IN` -> `CHECKED_OUT` -> `EXPIRED` -> `REVOKED`).
  - Emergency log querying active visitors currently on premises.
- **Non-Scope:**
  - Biometric fingerprint scanner hardware integration.

---

## 4. Data Entities (Migration 014 candidate)
1. `campus_visitors` (id, organization_id, full_name, phone, id_proof_type, id_proof_number, created_at, updated_at).
2. `visitor_gate_passes` (id, organization_id, visitor_id, pass_number, purpose, host_staff_id, check_in_time, check_out_time, status, issued_by, created_at).
