# Gayatri School OS — Unified Analytics Data Dictionary (Phase 08)

**Document Version:** 1.0.0  
**Phase:** Phase 08 — Unified Analytics, Quality, Accessibility and Institution Pilot  
**Governing Contract:** `DEVELOPMENT.md` (§6.10, §8, §11)  
**Date:** 2026-10-15  

---

## 1. Principles of Unified Analytics

1. **Zero Placeholder Figures:** Every metric displayed on student, teacher, bursar, or executive dashboards is directly derived and reconciled against authoritative SQL tables. Mock or synthetic figures are strictly forbidden.
2. **Deterministic Consistency Window:** Every calculation includes `calculated_at` and `data_freshness_iso` metadata reflecting the exact timestamp of source table querying.
3. **Tenant & Role Privacy Boundaries:** All queries are filtered strictly by `organization_id`. Student records are scoped by guardian linkage and role permission policies.
4. **Parent Privacy Levels:** Guardian analytics views strictly enforce parent privacy settings (`STANDARD`, `RESTRICTED`, `ANONYMIZED`, `BLOCKED`). Sensitive internal behavioral logs and confidential medical notes are redacted before rendering.

---

## 2. Institutional KPI Definitions

### 2.1 Student Attendance Rate (`KPI_ATTENDANCE_RATE`)
- **Description:** Percentage of scheduled instructional days marked as `PRESENT` or `LATE` for enrolled students.
- **Source Table:** `student_attendance_records` (JOIN `enrollments`)
- **Formula:** `(COUNT(status IN ('PRESENT', 'LATE')) / NULLIF(COUNT(*), 0)) * 100.0`
- **Time Window:** Academic term, month, or custom date range (`start_date` to `end_date`).
- **Tenant Scope:** `organization_id`
- **Parent Privacy:** Visible to linked parents under `STANDARD` or `RESTRICTED` levels; unexcused absence reasons masked if configured.

### 2.2 Fee Invoicing & Collection Rate (`KPI_FEE_COLLECTION_RATE`)
- **Description:** Percentage of invoiced fee amounts collected and settled.
- **Source Tables:** `invoices`, `financial_ledger_entries`
- **Formula:** `(SUM(paid_amount) / NULLIF(SUM(total_amount), 0)) * 100.0`
- **Denominator:** Total gross invoiced fees within selected billing cycle.
- **Tenant Scope:** `organization_id`
- **Privacy Boundary:** Executive & Bursar/Accountant roles only. Never visible to students or other parents.

### 2.3 Total Fee Arrears / Outstanding Balance (`KPI_TOTAL_OUTSTANDING_FEES`)
- **Description:** Total net outstanding unpaid balance across all active student fee accounts.
- **Source Tables:** `fee_accounts`
- **Formula:** `SUM(current_balance)`
- **Tenant Scope:** `organization_id`
- **Privacy Boundary:** School Admin, Finance Officer, Bursar.

### 2.4 Staff Leave Utilization Rate (`KPI_STAFF_LEAVE_RATE`)
- **Description:** Total approved staff leave days taken relative to active faculty headcount.
- **Source Tables:** `staff_leave_requests` (WHERE `status = 'APPROVED'`), `users` (WHERE `role IN ('teacher', 'staff')`)
- **Formula:** `SUM(total_days) / NULLIF(COUNT(DISTINCT staff_id), 0)`
- **Tenant Scope:** `organization_id`
- **Privacy Boundary:** Principal, HR Admin, Org Admin.

### 2.5 Transport Fleet Capacity Utilization (`KPI_TRANSPORT_CAPACITY_UTILIZATION`)
- **Description:** Ratio of allocated student bus seats to total registered vehicle fleet seating capacity.
- **Source Tables:** `student_transport_allocations`, `transport_vehicles`
- **Formula:** `(COUNT(student_transport_allocations.id) / NULLIF(SUM(transport_vehicles.capacity), 0)) * 100.0`
- **Tenant Scope:** `organization_id`
- **Privacy Boundary:** Transport Manager, Org Admin.

### 2.6 Hostel Bed Occupancy Rate (`KPI_HOSTEL_OCCUPANCY_RATE`)
- **Description:** Percentage of dormitory beds currently allocated to resident students.
- **Source Tables:** `hostel_allocations` (WHERE `status = 'ACTIVE'`), `hostel_rooms`
- **Formula:** `(COUNT(hostel_allocations.id) / NULLIF(SUM(hostel_rooms.bed_capacity), 0)) * 100.0`
- **Tenant Scope:** `organization_id`
- **Privacy Boundary:** Hostel Warden, Org Admin.

### 2.7 Academic Exam Pass Percentage (`KPI_EXAM_PASS_PERCENTAGE`)
- **Description:** Percentage of exam entries where scored marks met or exceeded the passing threshold.
- **Source Tables:** `exam_marks` (JOIN `exam_schedules`)
- **Formula:** `(COUNT(CASE WHEN exam_marks.marks_obtained >= exam_schedules.pass_marks THEN 1 END) / NULLIF(COUNT(*), 0)) * 100.0`
- **Tenant Scope:** `organization_id`
- **Privacy Boundary:** Teacher, Academic Coordinator, Org Admin.

### 2.8 Low Inventory Stock Alerts (`KPI_INVENTORY_LOW_STOCK_COUNT`)
- **Description:** Count of consumable inventory items whose quantity on hand is at or below reorder threshold.
- **Source Tables:** `inventory_items`
- **Formula:** `COUNT(CASE WHEN quantity_on_hand <= reorder_level THEN 1 END)`
- **Tenant Scope:** `organization_id`
- **Privacy Boundary:** Storekeeper, Procurement Admin, Org Admin.

---

## 3. Parent Privacy Enforcement Rules

| Privacy Level | Academic Grades / Report Cards | Daily Attendance Times | Fee Balances | Discipline / Incident Notes |
|---|---|---|---|---|
| **STANDARD** | Fully Visible | Fully Visible | Own Student Balance Only | Summary Remark Only |
| **RESTRICTED** | Letter Grades Only | Presence/Absence Only (No Timestamps) | Own Student Balance Only | Redacted / Hidden |
| **ANONYMIZED** | Cohort Percentile Only | Masked | Contact Bursar Prompt | Redacted / Hidden |
| **BLOCKED** | Access Denied (403) | Access Denied (403) | Access Denied (403) | Access Denied (403) |
