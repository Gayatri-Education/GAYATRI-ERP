"""
scripts/seed_erp_records.py
Seed comprehensive ERP records into gayatri_local.db for Phase 02A / Phase 02B modules:
SIS, Admissions, Attendance, Timetable, Examinations, Transport, Hostel, Inventory, HR/Payroll.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def seed_erp_data(db_path: str = "gayatri_local.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    now = now_iso()
    org_id = "org_dps"

    print(f"[*] Seeding ERP operational records into {db_path} for organization '{org_id}'...")

    # 1. Academic Year & Term
    cur.execute("""
        INSERT OR IGNORE INTO academic_years (id, organization_id, name, code, start_date, end_date, is_current, status, created_at, updated_at)
        VALUES ('ay_2026_27', ?, 'Academic Year 2026-2027', 'AY-2026-27', '2026-04-01', '2027-03-31', 1, 'ACTIVE', ?, ?);
    """, (org_id, now, now))

    cur.execute("""
        INSERT OR IGNORE INTO academic_terms (id, organization_id, academic_year_id, name, code, start_date, end_date, status, created_at, updated_at)
        VALUES ('term_monsoon_2026', ?, 'ay_2026_27', 'Monsoon Term 1', 'TERM-1-2026', '2026-04-01', '2026-09-30', 'ACTIVE', ?, ?);
    """, (org_id, now, now))

    # 2. Persons & Student Profiles
    students = [
        ("usr_student_arjun", "Arjun", "Patel", "ADM-2026-001", "11A-01"),
        ("usr_student_priya", "Priya", "Sen", "ADM-2026-002", "11A-02"),
        ("usr_student_rahul", "Rahul", "Sharma", "ADM-2026-003", "11A-03"),
        ("usr_student_ananya", "Ananya", "Verma", "ADM-2026-004", "11A-04"),
        ("usr_student_rohan", "Rohan", "Gupta", "ADM-2026-005", "11A-05"),
        ("usr_student_tanvi", "Tanvi", "Deshmukh", "ADM-2026-006", "11A-06"),
        ("usr_student_aditya", "Aditya", "Kulkarni", "ADM-2026-007", "11A-07"),
        ("usr_student_sneha", "Sneha", "Nair", "ADM-2026-008", "11A-08"),
    ]

    for uid, fname, lname, adm_num, roll_num in students:
        pid = f"per_{uid}"
        cur.execute("""
            INSERT OR IGNORE INTO persons (id, organization_id, user_id, first_name, last_name, email, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (pid, org_id, uid, fname, lname, f"{uid}@dps.edu", now, now))

        cur.execute("""
            INSERT OR IGNORE INTO student_profiles (id, person_id, organization_id, admission_number, roll_number, admission_date, academic_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, '2026-04-01', 'ACTIVE', ?, ?);
        """, (f"sp_{uid}", pid, org_id, adm_num, roll_num, now, now))

    print(f"  [OK] Seeded {len(students)} Student Profiles & Person entities")

    # 3. Admissions Applications
    admissions = [
        ("app_001", "APP-2026-001", "Arjun Patel", "Grade 11", "ENROLLED", "usr_student_arjun"),
        ("app_002", "APP-2026-002", "Priya Sen", "Grade 11", "ENROLLED", "usr_student_priya"),
        ("app_003", "APP-2026-003", "Kabir Mehta", "Grade 11", "UNDER_REVIEW", None),
        ("app_004", "APP-2026-004", "Isha Chawla", "Grade 11", "OFFERED", None),
        ("app_005", "APP-2026-005", "Aryan Joshi", "Grade 11", "SUBMITTED", None),
    ]
    for aid, app_num, name, grade, status, conv_id in admissions:
        cur.execute("""
            INSERT OR IGNORE INTO admission_applications (
                id, organization_id, application_number, academic_year_id, applicant_name,
                target_grade, status, converted_student_id, created_at, updated_at
            ) VALUES (?, ?, ?, 'ay_2026_27', ?, ?, ?, ?, ?, ?);
        """, (aid, org_id, app_num, name, grade, status, conv_id, now, now))
    print(f"  [OK] Seeded {len(admissions)} Admissions Applications")

    # 4. Attendance Sessions & Records
    cur.execute("""
        INSERT OR IGNORE INTO attendance_sessions (
            id, organization_id, academic_year_id, class_id, date, session_type, status, taken_by, created_at, updated_at
        ) VALUES ('att_sess_today', ?, 'ay_2026_27', 'cls_11a', '2026-10-15', 'DAILY', 'COMPLETED', 'usr_teacher_sharma', ?, ?);
    """, (org_id, now, now))

    for idx, (uid, _, _, _, _) in enumerate(students):
        rec_status = "LATE" if idx == 4 else "PRESENT"
        cur.execute("""
            INSERT OR IGNORE INTO attendance_records (
                id, organization_id, session_id, student_id, status, arrival_time, created_at, updated_at
            ) VALUES (?, ?, 'att_sess_today', ?, ?, '08:00:00', ?, ?);
        """, (f"att_rec_{uid}", org_id, uid, rec_status, now, now))
    print(f"  [OK] Seeded Attendance Session & {len(students)} Student Records")

    # 5. Exam Series, Schedules & Marks
    cur.execute("""
        INSERT OR IGNORE INTO exam_series (
            id, organization_id, academic_year_id, academic_term_id, name, code, series_type, start_date, end_date, status, created_at, updated_at
        ) VALUES ('exam_midterm_2026', ?, 'ay_2026_27', 'term_monsoon_2026', 'Mid-Term Examinations 2026', 'MIDTERM-2026', 'TERM', '2026-09-15', '2026-09-25', 'COMPLETED', ?, ?);
    """, (org_id, now, now))

    cur.execute("""
        INSERT OR IGNORE INTO exam_schedules (
            id, organization_id, exam_series_id, class_id, subject_id, exam_date, start_time, end_time, max_marks, pass_marks, room_name, is_locked, created_at, updated_at
        ) VALUES ('sched_chem_midterm', ?, 'exam_midterm_2026', 'cls_11a', 'subj_chem', '2026-09-18', '09:00:00', '12:00:00', 100.0, 40.0, 'Hall A', 1, ?, ?);
    """, (org_id, now, now))

    student_marks = [
        ("usr_student_arjun", 78.5),
        ("usr_student_priya", 96.0),
        ("usr_student_rahul", 84.0),
        ("usr_student_ananya", 88.5),
        ("usr_student_rohan", 72.0),
        ("usr_student_tanvi", 91.5),
        ("usr_student_aditya", 95.0),
        ("usr_student_sneha", 89.0),
    ]
    for uid, marks in student_marks:
        cur.execute("""
            INSERT OR IGNORE INTO exam_student_marks (
                id, organization_id, schedule_id, student_id, marks_obtained, is_absent, is_exempt, status, entered_by, created_at, updated_at
            ) VALUES (?, ?, 'sched_chem_midterm', ?, ?, 0, 0, 'VERIFIED', 'usr_teacher_sharma', ?, ?);
        """, (f"mark_{uid}", org_id, uid, marks, now, now))
    print(f"  [OK] Seeded Exam Series, Schedules & {len(student_marks)} Graded Marks")

    # 6. Transport Fleet
    cur.execute("""
        INSERT OR IGNORE INTO transport_routes (
            id, organization_id, name, code, start_point, end_point, is_active, created_at, updated_at
        ) VALUES ('route_north', ?, 'North Delhi Campus Express', 'RTE-NORTH-01', 'Rohini Sector 9', 'DPS RKP Campus', 1, ?, ?);
    """, (org_id, now, now))

    cur.execute("""
        INSERT OR IGNORE INTO transport_vehicles (
            id, organization_id, registration_number, vehicle_type, seating_capacity, driver_name, driver_phone, is_active, created_at, updated_at
        ) VALUES ('veh_bus_08', ?, 'DL-1PB-4028', 'AC_BUS_40', 40, 'Mohan Singh', '+91-9811223344', 1, ?, ?);
    """, (org_id, now, now))

    for i in range(1, 33):
        cur.execute("""
            INSERT OR IGNORE INTO student_transport_allocations (
                id, organization_id, student_id, route_id, stop_id, vehicle_id, academic_year_id, status, created_at, updated_at
            ) VALUES (?, ?, ?, 'route_north', 'stop_main', 'veh_bus_08', 'ay_2026_27', 'ACTIVE', ?, ?);
        """, (f"alloc_bus_{i}", org_id, f"student_sim_{i}", now, now))
    print("  [OK] Seeded Transport Fleet (Route, Vehicle, 32 Allocations -> 80% Utilization)")

    # 7. Hostel Facilities
    cur.execute("""
        INSERT OR IGNORE INTO hostel_buildings (
            id, organization_id, name, code, gender_type, warden_name, warden_phone, created_at, updated_at
        ) VALUES ('bldg_ganga', ?, 'Ganga Senior Hostel', 'HST-GANGA', 'BOYS', 'Dr. S. K. Pathak', '+91-9876543210', ?, ?);
    """, (org_id, now, now))

    for r_num in [101, 102, 103, 104, 105]:
        cur.execute("""
            INSERT OR IGNORE INTO hostel_rooms (
                id, organization_id, building_id, room_number, floor_number, bed_capacity, current_occupancy, created_at, updated_at
            ) VALUES (?, ?, 'bldg_ganga', ?, 1, 4, 3, ?, ?);
        """, (f"room_{r_num}", org_id, str(r_num), now, now))

    for i in range(1, 17):
        cur.execute("""
            INSERT OR IGNORE INTO hostel_allocations (
                id, organization_id, student_id, room_id, academic_year_id, bed_identifier, allocation_date, status, created_at, updated_at
            ) VALUES (?, ?, ?, 'room_101', 'ay_2026_27', ?, '2026-04-01', 'ACTIVE', ?, ?);
        """, (f"h_alloc_{i}", org_id, f"student_hst_{i}", f"BED-{i}", now, now))
    print("  [OK] Seeded Hostel Facility (Building, 5 Rooms (20 beds), 16 Allocations -> 80% Occupancy)")

    # 8. Inventory Items & Stock
    inventory = [
        ("inv_chem_kits", "Digital Chemistry Titration Sensor", "SKU-CHEM-TITR-01", "SCIENCE_LAB", "UNIT", 45, 10, 3200.0),
        ("inv_soc_tablets", "Gayatri Socratic Tablet 10-inch", "SKU-TAB-SOC-02", "IT_HARDWARE", "UNIT", 120, 20, 14500.0),
        ("inv_reagents", "Organic Synthesis Catalyst Reagent Pack", "SKU-CHEM-REAG-09", "SCIENCE_LAB", "PACK", 3, 10, 1850.0),  # Low Stock!
    ]
    for iid, name, sku, cat, unit, qty, reorder, price in inventory:
        cur.execute("""
            INSERT OR IGNORE INTO inventory_items (
                id, organization_id, name, sku, category, unit, quantity_on_hand, reorder_level, unit_price, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (iid, org_id, name, sku, cat, unit, qty, reorder, price, now, now))
    print(f"  [OK] Seeded {len(inventory)} Inventory Items (including 1 low-stock alert)")

    # 9. Staff Leave Requests
    cur.execute("""
        INSERT OR IGNORE INTO staff_leave_requests (
            id, organization_id, staff_id, leave_type, start_date, end_date, total_days, reason, status, created_at, updated_at
        ) VALUES ('leave_001', ?, 'usr_teacher_verma', 'CASUAL', '2026-10-10', '2026-10-11', 2.0, 'Academic Conference', 'APPROVED', ?, ?);
    """, (org_id, now, now))
    print("  [OK] Seeded Approved Staff Leave Request")

    conn.commit()
    conn.close()
    print("[SUCCESS] All Phase 02A/B ERP operational records seeded successfully!\n")

if __name__ == "__main__":
    seed_erp_data()
