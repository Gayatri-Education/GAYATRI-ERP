# Phase 11 Plan — Document/ID Card Visual Designer and QR Verification

**Document:** `docs/erp_agent/plans/PHASE_11_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 11 — Document/ID Card Visual Designer and QR Verification  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 11 verifies and validates the document design, certificate generation, and cryptographic QR verification engine:
1. **Official Certificate Types:** Generation of Transfer Certificates (TC), Bonafide certificates, Character certificates, Merit awards, Student IDs, and Staff IDs in `CampusService`.
2. **Cryptographic QR Verification:**
   - Server-side opaque verification codes (`verification_code`).
   - Absolute prohibition against clear-text personal identity data in QR payloads.
   - Public/authenticated verification endpoint (`/api/v1/campus/certificates/{id}/verify`).
3. **Revocation & Tampering Defense:** Revoked certificates immediately return `status = 'REVOKED'`, preventing fraudulent reuse of printed physical certificates.
4. **Receipt & Invoice Layouts:** Formal receipt issuance linking payments to students and accounts.

---

## 2. Likely Files & Scope Boundary

- `central_platform/campus/service.py` (`CampusService.issue_certificate`, `verify_certificate`, `revoke_certificate`)
- `central_platform/models/campus.py` (`OfficialCertificate`, `CertificateType`, `CertificateStatus`)
- `central_platform/finance/service.py` (`get_receipt`)
- `central_platform/api/routes/campus.py`
- `central_platform/ui/design_system.py`
- `tests/test_qa_phase14_e2e_product_acceptance.py`
- `tests/test_phase24_shared_ui_design_system.py`

---

## 3. Targeted Test Scenarios

1. Issuing a certificate generates an opaque verification code and persists metadata.
2. Validating a certificate via `verify_certificate()` confirms status `ISSUED` and returns safe public fields.
3. Revoking a certificate via `revoke_certificate()` updates status to `REVOKED` with reason and revoker ID.
4. Subsequent verification of a revoked certificate truthfully returns `REVOKED` status.
5. Verification codes are non-sequential and prevent brute-force enumeration.

---

## 4. Exit Criteria (Binary Gate)

- [ ] All official certificate types (`STUDENT_ID`, `TRANSFER_CERTIFICATE`, `BONAFIDE`, `MERIT`) verified.
- [ ] Cryptographic/opaque QR verification code generation verified.
- [ ] Certificate revocation workflow verified.
- [ ] Receipt retrieval and document layout contracts verified.
- [ ] `docs/erp_agent/reports/PHASE_11_REPORT.md` and `docs/erp_agent/regressions/PHASE_11_REGRESSION.md` generated with passing evidence.
