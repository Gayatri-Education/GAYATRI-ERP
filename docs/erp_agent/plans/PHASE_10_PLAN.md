# Phase 10 Plan — Campus Facilities

**Document:** `docs/erp_agent/plans/PHASE_10_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 10 — Campus Facilities  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 10 verifies the institutional campus operations and auxiliary facility domains:
1. **Fleet & Transport:** Vehicle registry, driver assignments, route pickup stops, and student bus pass assignments in `TransportService`.
2. **Hostel Administration:** Buildings, rooms, bed capacity, and conflict-safe student allocations in `HostelService`.
3. **Inventory & Store Operations:** Item categories, inventory catalogs, stock transactions (`IN`, `OUT`, `ADJUSTMENT`), and purchase orders in `InventoryService`.
4. **Campus Security & Gate Passes:** Visitor registrations, time-bound gate pass issuance (`CHECKED_IN`), host staff notification, and checkout (`CHECKED_OUT`) in `CampusService`.
5. **Canonical Finance Linkage:** Any chargeable facility transaction (transport fee, hostel fee, library fines) connects directly to the canonical billing and ledger subsystem (`FinanceService`).

---

## 2. Likely Files & Scope Boundary

- `central_platform/transport/service.py` (`TransportService`)
- `central_platform/hostel/service.py` (`HostelService`)
- `central_platform/inventory/service.py` (`InventoryService`)
- `central_platform/campus/service.py` (`CampusService`)
- `central_platform/models/transport.py`, `models/hostel.py`, `models/inventory.py`, `models/campus.py`
- `central_platform/api/routes/transport.py`, `routes/campus.py`
- `tests/test_qa_phase14_e2e_product_acceptance.py`
- `tests/test_qa_phase12_integrated_journeys.py`

---

## 3. Targeted Test Scenarios

1. Adding fleet vehicles, routes, and stops preserves geographical and route sequence ordering.
2. Bed allocation validates available capacity and prevents duplicate student allocation.
3. Inventory stock adjustments update available balance and prevent negative stock levels.
4. Gate pass issuance records check-in timestamp; checkout transitions status to `CHECKED_OUT` and records check-out timestamp.
5. All sensitive campus actions record tenant-isolated audit log events.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Transport vehicle, route, and stop management verified.
- [ ] Hostel building, room, and bed allocation verified.
- [ ] Inventory items, stock movements, and POs verified.
- [ ] Visitor check-in, gate pass, and checkout verified.
- [ ] `docs/erp_agent/reports/PHASE_10_REPORT.md` and `docs/erp_agent/regressions/PHASE_10_REGRESSION.md` generated with passing evidence.
