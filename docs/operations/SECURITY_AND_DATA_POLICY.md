# Gayatri School OS — Security, Privacy, and Data Governance Policy

**Version:** 1.0.0  
**Phase:** 09 Production Release Gate  
**Governing Standard:** `DEVELOPMENT.md` (§7 Phase 09)

---

## 1. Authentication & Session Security

1. **Bearer Token Issuance:** JWTs signed with HMAC-SHA256 using `GAYATRI_JWT_SECRET` (minimum 32-character entropy).
2. **Token Lifetime:**
   - Access tokens: Maximum 15 minutes.
   - Refresh tokens: Maximum 7 days, stored in HTTP-only, `Secure`, `SameSite=Strict` cookies.
3. **Revocation & Epoch Tracking:** Token blacklisting table and user token epoch tracking allow immediate instant revocation across all devices.
4. **Zero Default Credentials:** System refuses to boot if default or weak passwords (`admin`, `123456`, `changeme`, etc.) are detected.

---

## 2. Multi-Tenant Data Isolation & Privacy Policy

1. **Strict Organization Scoping:** Every query, filter, insert, and update enforces `organization_id` boundaries.
2. **Parent Privacy Tiers:**
   - `STANDARD`: Guardian sees full official student identity, academic marks, and itemized billing ledger.
   - `RESTRICTED`: Contact numbers, address, and medical records are masked.
   - `ANONYMIZED`: Student name replaced with pseudonym, admission number masked, balance due directs parent to institutional bursar.
   - `BLOCKED`: Access strictly forbidden due to legal custody orders or administrative block.
3. **Tabular Export Isolation:** All exports (CSV/JSON) are filtered strictly by requesting user's tenant token. Cross-tenant queries return zero records.

---

## 3. Data Protection At Rest & In Transit

1. **In-Transit Protection:** Mandatory TLS 1.3 encryption on all public endpoints. HSTS header enabled with minimum 1-year duration.
2. **At-Rest Protection:**
   - Sensitive columns (financial details, guardian contact info, biometric templates) encrypted via AES-256-GCM / DPAPI.
   - Database backups encrypted prior to cloud offsite transit.
3. **Secret Redaction in Operations:** All loggers, diagnostics, crash dumps, and API error handlers sanitize keys matching `password`, `secret`, `token`, `key`, `authorization`, `database_url`.

---

## 4. Data Retention & Archival

1. **Academic Ledgers:** Permanent retention for student transcripts, examination report cards, and issued certificates.
2. **Attendance & Biometric Logs:** Retained locally on edge devices for 30 days; synced to central server for 3 years.
3. **Financial Records:** Retained in immutable append-only ledger for 7 years according to statutory compliance.
4. **Visitor Gate Passes:** Automatically archived after 90 days.
