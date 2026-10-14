-- ============================================================================
-- Rollback Migration 014: Full ERP Expansion
-- ============================================================================

DROP TABLE IF EXISTS cms_posts;
DROP TABLE IF EXISTS cms_pages;
DROP TABLE IF EXISTS official_certificates;
DROP TABLE IF EXISTS visitor_gate_passes;
DROP TABLE IF EXISTS campus_visitors;
DROP TABLE IF EXISTS inventory_stock_movements;
DROP TABLE IF EXISTS inventory_purchase_orders;
DROP TABLE IF EXISTS inventory_vendors;
DROP TABLE IF EXISTS inventory_items;
DROP TABLE IF EXISTS hostel_leave_passes;
DROP TABLE IF EXISTS hostel_allocations;
DROP TABLE IF EXISTS hostel_rooms;
DROP TABLE IF EXISTS hostel_buildings;
DROP TABLE IF EXISTS student_transport_allocations;
DROP TABLE IF EXISTS transport_vehicles;
DROP TABLE IF EXISTS transport_stops;
DROP TABLE IF EXISTS transport_routes;
DROP TABLE IF EXISTS payslips;
DROP TABLE IF EXISTS payroll_runs;
DROP TABLE IF EXISTS payroll_periods;
DROP TABLE IF EXISTS staff_attendance_records;
DROP TABLE IF EXISTS staff_leave_requests;
