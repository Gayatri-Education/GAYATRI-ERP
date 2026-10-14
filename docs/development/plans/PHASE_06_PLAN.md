# Phase 06 Plan: Full ERP Expansion (Staff, Payroll, Transport, Hostel, Inventory, Visitors, Certificates & CMS)

## Status
- [ ] NOT_STARTED
- [ ] IN_PROGRESS
- [x] PASSED
- [ ] FAILED
- [ ] BLOCKED

---

## 1. Objective and User Value

Deliver the full institutional operations suite of Gayatri School OS across 8 vital functional domains:
1. **6A: Staff & HR (ERP-11):** Staff leave applications, overlapping date validation, approvals, and daily staff attendance tracking.
2. **6B: Payroll Preparation (ERP-12):** Deterministic payroll runs, allowances/deductions, itemized employee payslips, and dual approval release.
3. **6C: Transport & Fleet (ERP-13):** Routes, ordered stops, vehicle fleet, driver assignments, and student seat allocation with capacity limits.
4. **6D: Hostel & Boarding (ERP-14):** Residential buildings, rooms, bed capacity enforcement, room allocations, and warden leave outpasses.
5. **6E: Inventory & Assets (ERP-15):** Item master, vendor directory, purchase orders, and append-only stock movement journals.
6. **6F: Visitors & Gate Pass (ERP-16):** Secure visitor registration, host staff assignment, visitor badges, and check-in/out timestamps.
7. **6G: Certificates (ERP-17):** Transfer, bonafide, and character certificates with cryptographic SHA-256 tamper-evident verification hashes.
8. **6H: Public CMS (ERP-18):** Unauthenticated public pages and news posts with draft/publish approval gates and isolated admin APIs.

All state persists in SQLite/PostgreSQL through Migration 014 with strict multi-tenant isolation (`organization_id`).

---

## 2. Scope & Data Entities (Migration 014)

1. `staff_leave_requests`
2. `staff_attendance_records`
3. `payroll_periods`
4. `payroll_runs`
5. `payslips`
6. `transport_routes`
7. `transport_stops`
8. `transport_vehicles`
9. `student_transport_allocations`
10. `hostel_buildings`
11. `hostel_rooms`
12. `hostel_allocations`
13. `hostel_leave_passes`
14. `inventory_items`
15. `inventory_vendors`
16. `inventory_purchase_orders`
17. `inventory_stock_movements`
18. `campus_visitors`
19. `visitor_gate_passes`
20. `official_certificates`
21. `cms_pages`
22. `cms_posts`

---

## 3. Implementation Sequence

1. Author focused test suite `tests/test_phase06_full_erp_expansion.py` covering all 8 submodules.
2. Author Migration 014 forward and reversible down SQL scripts.
3. Create domain models across HR, Transport, Hostel, Inventory, and Campus domains.
4. Implement domain services (`HRService`, `TransportService`, `HostelService`, `InventoryService`, `CampusService`).
5. Implement API routes and mount under `/api/v1/*`.
6. Run focused test suite, migration hardening tests, and full platform regression suite.
7. Document evidence and certify Phase 06 exit gate.

---

## 4. Exit Criteria

- [ ] `test_phase06_full_erp_expansion.py` passes 100% across all 8 submodules.
- [ ] Migration 014 applies cleanly and rolls back cleanly.
- [ ] Leave requests validate overlapping dates and state transitions.
- [ ] Payroll runs compute deterministic payslips with allowances and deductions.
- [ ] Transport and Hostel allocations strictly enforce capacity bounds.
- [ ] Inventory stock movements update on-hand quantities correctly.
- [ ] Visitor check-in/out and certificates cryptographic hashing verified.
- [ ] Public CMS pages and posts render safely without authentication.
- [ ] Full platform regression suite remains 100% green.

---

## 5. Execution Evidence

- Evidence file: `docs/development/evidence/phase06/phase06_test_execution.log`

---

## 6. Final Result

*Pending execution.*
