# ERP Feature Scope: Hostel & Boarding Operations (ERP-14)

**Feature ID:** `ERP-14`  
**Governing Contract:** `DEVELOPMENT.md` (§6.9, §7 Phase 06)  
**Parent Phase:** Phase 06 (Full ERP Expansion)  
**Status:** In Preparation  
**Last Updated:** 2026-10-15  

---

## 1. Business Purpose and Beneficiaries
- **Purpose:** Manage residential boarding facilities, hostel blocks/buildings, room bed capacities, student allocations preventing double-booking, and warden gate leave passes.
- **Beneficiaries:**
  - **Hostel Warden / Administrator:** Manage room allocations, approve night/weekend outpasses.
  - **Boarding Students / Parents:** Request outpasses, view room details and warden contact info.

---

## 2. Personas and Access Matrix

| Role | Allocate Bed | Request Outpass | Approve Outpass | View Occupancy |
|---|---|---|---|---|
| **Boarder / Student** | ❌ | ✅ | ❌ | ❌ |
| **Warden** | ✅ | ❌ | ✅ | ✅ |
| **Org Admin** | ✅ | ❌ | ✅ | ✅ |

---

## 3. Scope & Non-Scope
- **In-Scope:**
  - Buildings / Blocks (e.g. Boys Hostel A, Girls Hostel B).
  - Rooms with bed capacities (e.g. Room 101, Capacity 3).
  - Bed allocations ensuring `current_occupancy <= bed_capacity`.
  - Student Leave Outpasses (`PENDING` -> `APPROVED` -> `CHECKED_OUT` -> `CHECKED_IN` -> `REJECTED`).
- **Non-Scope:**
  - Automated facial recognition turnstile door lock electronics.

---

## 4. Data Entities (Migration 014 candidate)
1. `hostel_buildings` (id, organization_id, name, code, gender_type, warden_name, warden_phone, created_at, updated_at).
2. `hostel_rooms` (id, organization_id, building_id, room_number, floor_number, bed_capacity, current_occupancy, created_at, updated_at).
3. `hostel_allocations` (id, organization_id, student_id, room_id, academic_year_id, bed_identifier, allocation_date, status, created_at, updated_at, UNIQUE(student_id, academic_year_id)).
4. `hostel_leave_passes` (id, organization_id, student_id, leave_type, departure_date, expected_return_date, actual_return_date, reason, status, approved_by, created_at, updated_at).
