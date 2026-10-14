# ERP Feature Scope: Transport & Fleet Operations (ERP-13)

**Feature ID:** `ERP-13`  
**Governing Contract:** `DEVELOPMENT.md` (§6.9, §7 Phase 06)  
**Parent Phase:** Phase 06 (Full ERP Expansion)  
**Status:** In Preparation  
**Last Updated:** 2026-10-15  

---

## 1. Business Purpose and Beneficiaries
- **Purpose:** Manage school bus routes, designated pickup/drop stops, vehicle fleet compliance, driver assignments, and student route seat allocations with capacity enforcement.
- **Beneficiaries:**
  - **Transport Manager:** Manage fleet, assign drivers to vehicles, configure stops and schedules.
  - **Parents / Students:** View designated stop timing, bus number, and driver contact info.

---

## 2. Personas and Access Matrix

| Role | Configure Routes/Stops | Assign Vehicles/Drivers | Allocate Student Seat | View Transport Schedule |
|---|---|---|---|---|
| **Student** | ❌ | ❌ | ❌ | ✅ (Assigned) |
| **Parent** | ❌ | ❌ | ❌ | ✅ (Ward) |
| **Transport Manager** | ✅ | ✅ | ✅ | ✅ |
| **Org Admin** | ✅ | ✅ | ✅ | ✅ |

---

## 3. Scope & Non-Scope
- **In-Scope:**
  - Route planning with ordered stops and morning/evening pickup times.
  - Vehicle fleet tracking (registration number, seating capacity, fitness expiry).
  - Driver & attendant assignment with contact details.
  - Student transport allocation validating seat capacity.
- **Non-Scope:**
  - Real-time CAN bus telemetry hardware diagnostics.

---

## 4. Terms and Canonical Records
- **Transport Route:** Fixed circuit traversed by a bus.
- **Route Stop:** Geographical embarkation/debarkation point.
- **Vehicle:** Registered school bus, van, or contracted transport.
- **Student Allocation:** Active student assignment to a stop and vehicle.

---

## 5. Data Entities (Migration 014 candidate)
1. `transport_routes` (id, organization_id, name, code, start_point, end_point, is_active, created_at, updated_at).
2. `transport_stops` (id, organization_id, route_id, name, stop_order, morning_pickup_time, evening_drop_time, fare_amount, created_at).
3. `transport_vehicles` (id, organization_id, registration_number, vehicle_type, seating_capacity, driver_name, driver_phone, is_active, created_at, updated_at).
4. `student_transport_allocations` (id, organization_id, student_id, route_id, stop_id, vehicle_id, academic_year_id, status, created_at, updated_at, UNIQUE(student_id, academic_year_id)).
