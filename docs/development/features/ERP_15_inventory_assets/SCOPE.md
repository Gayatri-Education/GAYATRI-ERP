# ERP Feature Scope: Inventory, Assets & Procurement (ERP-15)

**Feature ID:** `ERP-15`  
**Governing Contract:** `DEVELOPMENT.md` (§6.9, §7 Phase 06)  
**Parent Phase:** Phase 06 (Full ERP Expansion)  
**Status:** In Preparation  
**Last Updated:** 2026-10-15  

---

## 1. Business Purpose and Beneficiaries
- **Purpose:** Track school physical assets and consumable supplies (textbooks, lab consumables, sports gear, uniforms), manage vendors, generate purchase orders, and record append-only stock movements.
- **Beneficiaries:**
  - **Store Manager / Estate Officer:** Track current stock balances, record receipts and issues.
  - **Accountant / Purchase Officer:** Maintain approved vendor catalog, issue purchase orders.

---

## 2. Personas and Access Matrix

| Role | Create PO | Receive Goods | Issue Stock to Department | View Inventory Balances |
|---|---|---|---|---|
| **Department Head** | ❌ | ❌ | ❌ | ✅ |
| **Store Manager** | ✅ | ✅ | ✅ | ✅ |
| **Org Admin** | ✅ | ✅ | ✅ | ✅ |

---

## 3. Scope & Non-Scope
- **In-Scope:**
  - Stock item master with SKU, category, reorder level, and unit of measurement.
  - Vendor directory with contact and GST details.
  - Purchase Orders (`DRAFT` -> `ORDERED` -> `PARTIALLY_RECEIVED` -> `RECEIVED` -> `CANCELLED`).
  - Stock movements (`INWARD`, `OUTWARD`, `ADJUSTMENT`) keeping inventory balance auditable.
- **Non-Scope:**
  - Automated barcode laser scanning conveyor belts.

---

## 4. Data Entities (Migration 014 candidate)
1. `inventory_items` (id, organization_id, name, sku, category, unit, quantity_on_hand, reorder_level, unit_price, created_at, updated_at).
2. `inventory_vendors` (id, organization_id, name, code, contact_person, phone, email, address, is_active, created_at, updated_at).
3. `inventory_purchase_orders` (id, organization_id, po_number, vendor_id, total_amount, order_date, expected_date, status, created_by, approved_by, created_at, updated_at).
4. `inventory_stock_movements` (id, organization_id, item_id, movement_type, quantity, unit_cost, reference_id, department_name, remarks, created_at).
