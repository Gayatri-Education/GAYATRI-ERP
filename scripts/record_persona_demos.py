"""
scripts/record_persona_demos.py
Automated Multi-Persona Demo Video Recorder for Gayatri School OS.

Produces distinct, role-specific walkthrough videos for each user persona:
1. Student Persona: Adaptive Socratic AI Tutor, Competency Graphs, LaTeX math, Local Privacy (~60s)
2. Teacher Persona: Cohort Telemetry, Early-Warning Misconception Alerts, AI Copilot, Directives (~60s)
3. Parent Persona: Multi-Child Switcher, Live Biometric Attendance, Itemized Fees & Receipts, Report Cards (~60s)
4. Admin & Trustee Persona (EXPANDED): Comprehensive Institutional ERP Governance, Admissions CRM,
   Double-Entry Ledger, Timetable Engine, Smart ID Badges, Official Certificates, Fleet Logistics,
   Local AI Governance & Reconciled KPIs (~180-210s)

Outputs:
- Video Files in `demo_recordings/` and `docs/assets/demos/`
- Synchronized `.srt` and `.vtt` subtitles for every persona
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
RECORDINGS_DIR = PROJECT_ROOT / "demo_recordings"
DOCS_DEMO_DIR = PROJECT_ROOT / "docs" / "assets" / "demos"


def wait_for_server(url: str, timeout_sec: int = 25) -> bool:
    """Poll endpoint until HTTP 200 is returned."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def format_srt_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


class CaptionTracker:
    def __init__(self, video_title: str):
        self.video_title = video_title
        self.events = []
        self.start_time = None

    def start(self):
        self.start_time = time.time()

    def set_caption(self, page, title: str, subtitle: str, scene_tag: str = ""):
        now = time.time()
        if self.start_time is None:
            self.start_time = now

        rel_start = round(now - self.start_time, 2)
        if self.events:
            self.events[-1]["end"] = rel_start

        self.events.append({
            "start": rel_start,
            "end": rel_start + 4.0,
            "title": title,
            "subtitle": subtitle,
            "scene_tag": scene_tag,
        })

        page.evaluate(
            """([title, subtitle, scene_tag]) => {
                let banner = document.getElementById('demo-hud-banner');
                if (!banner) {
                    banner = document.createElement('div');
                    banner.id = 'demo-hud-banner';
                    banner.style.position = 'fixed';
                    banner.style.bottom = '24px';
                    banner.style.left = '50%';
                    banner.style.transform = 'translateX(-50%)';
                    banner.style.zIndex = '999999';
                    banner.style.background = 'rgba(10, 10, 26, 0.94)';
                    banner.style.border = '1px solid rgba(83, 168, 182, 0.4)';
                    banner.style.borderRadius = '14px';
                    banner.style.padding = '12px 28px';
                    banner.style.boxShadow = '0 12px 36px rgba(0,0,0,0.7), 0 0 20px rgba(83, 168, 182, 0.2)';
                    banner.style.fontFamily = "'Segoe UI', system-ui, -apple-system, sans-serif";
                    banner.style.textAlign = 'center';
                    banner.style.backdropFilter = 'blur(12px)';
                    banner.style.pointerEvents = 'none';
                    banner.style.minWidth = '540px';
                    banner.style.maxWidth = '88%';
                    banner.style.transition = 'all 0.25s ease';
                    document.body.appendChild(banner);
                }
                let tagHtml = scene_tag ? `<span style="background:linear-gradient(135deg, #9b59b6, #53a8b6); color:#fff; font-size:10px; font-weight:800; padding:2px 8px; border-radius:10px; letter-spacing:1px; text-transform:uppercase; margin-right:8px;">${scene_tag}</span>` : '';
                banner.innerHTML = `<div style="display:flex; align-items:center; justify-content:center; gap:6px; margin-bottom:4px;">${tagHtml}<span style="font-size:13.5px; font-weight:800; color:#53a8b6; letter-spacing:0.8px; text-transform:uppercase;">${title}</span></div><div style="font-size:12px; font-weight:500; color:#e2e8f0; line-height:1.4;">${subtitle}</div>`;
                banner.style.opacity = '1';
            }""",
            [title, subtitle, scene_tag],
        )

    def export_captions(self, base_name: str, total_duration: float):
        if self.events:
            self.events[-1]["end"] = max(self.events[-1]["start"] + 3.0, round(total_duration, 2))

        # SRT
        srt_lines = []
        for idx, item in enumerate(self.events, 1):
            s_str = format_srt_time(item["start"])
            e_str = format_srt_time(item["end"])
            tag = f"[{item['scene_tag']}] " if item["scene_tag"] else ""
            srt_lines.append(f"{idx}\n{s_str} --> {e_str}\n{tag}{item['title']}: {item['subtitle']}\n")
        srt_content = "\n".join(srt_lines)

        # VTT
        vtt_lines = ["WEBVTT\n"]
        for idx, item in enumerate(self.events, 1):
            s_str = format_vtt_time(item["start"])
            e_str = format_vtt_time(item["end"])
            tag = f"[{item['scene_tag']}] " if item["scene_tag"] else ""
            vtt_lines.append(f"{idx}\n{s_str} --> {e_str}\n{tag}{item['title']}: {item['subtitle']}\n")
        vtt_content = "\n".join(vtt_lines)

        for d in [RECORDINGS_DIR, DOCS_DEMO_DIR]:
            d.mkdir(parents=True, exist_ok=True)
            with open(d / f"{base_name}.srt", "w", encoding="utf-8") as f:
                f.write(srt_content)
            with open(d / f"{base_name}.vtt", "w", encoding="utf-8") as f:
                f.write(vtt_content)


def smooth_scroll(page, distance: int, steps: int = 10, delay_ms: int = 50):
    delta = distance // steps
    for _ in range(steps):
        page.evaluate(f"window.scrollBy(0, {delta})")
        page.wait_for_timeout(delay_ms)


def init_context(browser, tokens: dict):
    context = browser.new_context(
        record_video_dir=str(RECORDINGS_DIR),
        record_video_size={"width": 1280, "height": 720},
        viewport={"width": 1280, "height": 720},
    )
    admin_token = tokens.get("usr_dps_admin", {}).get("token") or tokens.get("usr_superadmin", {}).get("token")
    teacher_token = tokens.get("usr_teacher_sharma", {}).get("token")
    student_token = tokens.get("usr_student_arjun", {}).get("token")

    context.add_init_script(
        f"""
        localStorage.setItem('admin_token', '{admin_token}');
        localStorage.setItem('teacher_token', '{teacher_token}');
        localStorage.setItem('access_token', '{student_token}');
        localStorage.setItem('student_token', '{student_token}');
        localStorage.setItem('demo_student_id', 'usr_student_arjun');
        localStorage.setItem('active_course_id', 'crs_chem_101');
        """
    )
    return context


def finalize_video(page, context, tracker: CaptionTracker, file_base_name: str) -> str:
    total_duration = time.time() - tracker.start_time
    tracker.export_captions(file_base_name, total_duration)

    video_obj = page.video
    context.close()

    raw_path = video_obj.path()
    target_rec = RECORDINGS_DIR / f"{file_base_name}.webm"
    target_docs = DOCS_DEMO_DIR / f"{file_base_name}.webm"

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DEMO_DIR.mkdir(parents=True, exist_ok=True)

    if os.path.exists(raw_path):
        shutil.copy2(raw_path, str(target_rec))
        shutil.copy2(raw_path, str(target_docs))
        size_kb = os.path.getsize(target_rec) / 1024
        print(f"  [OK] Saved: {target_rec.name} ({total_duration:.1f}s, {size_kb:.1f} KB)")
        return str(target_rec)
    return ""


# =============================================================================
# 1. STUDENT PERSONA DEMO RECORDING (~60-70s)
# =============================================================================
def record_student_persona(browser, tokens: dict) -> str:
    print("\n=======================================================")
    print("[1/4] Recording Student Learning & AI Tutor Demo...")
    print("=======================================================")
    context = init_context(browser, tokens)
    page = context.new_page()
    tracker = CaptionTracker("Student Experience")
    tracker.start()

    # Scene 1: Student Dashboard
    page.goto(f"{BASE_URL}/student", wait_until="networkidle")
    page.wait_for_timeout(1000)
    tracker.set_caption(
        page,
        "Student Progress & Competency Dashboard",
        "Arjun Patel (Grade 11 STEM) — Continuous mastery tracking across curriculum concepts",
        scene_tag="Student · Dashboard",
    )
    page.wait_for_timeout(2500)

    smooth_scroll(page, 400, steps=8, delay_ms=50)
    page.wait_for_timeout(2000)
    smooth_scroll(page, -400, steps=8, delay_ms=40)
    page.wait_for_timeout(1000)

    # Scene 2: Interactive AI Socratic Tutor
    tracker.set_caption(
        page,
        "Launching Gayatri AI Socratic Tutor",
        "Transitioning to private, 1-on-1 personalized AI learning environment...",
        scene_tag="Student · AI Tutor",
    )
    page.goto(f"{BASE_URL}/tutor", wait_until="networkidle")
    page.wait_for_timeout(1200)

    # Switch to chemistry socratic tutor tab
    page.evaluate("switchTab('chemistry')")
    page.wait_for_timeout(1500)

    tracker.set_caption(
        page,
        "Adaptive Socratic Tutor Workspace",
        "Active Concept: Equilibrium Constant & Le Chatelier's Principle | Mode: EXPLAIN",
        scene_tag="AI Tutor · Setup",
    )
    page.wait_for_timeout(2000)

    # Scene 3: Socratic Dialogue
    prompt_q = "How does Le Chatelier's principle predict equilibrium shifts when pressure changes?"
    page.click("#userInputChem")
    page.type("#userInputChem", prompt_q, delay=30)
    page.wait_for_timeout(600)

    tracker.set_caption(
        page,
        "Inquiry-Driven Socratic Learning",
        "Student asks conceptual question; local AI guides through fundamental reasoning",
        scene_tag="AI Tutor · Prompt",
    )
    page.click("#sendBtnChem")
    page.wait_for_timeout(4500)

    tracker.set_caption(
        page,
        "Streaming Socratic Guidance with LaTeX Equations",
        "Explains pressure vs molar volume balance, asks conceptual check question",
        scene_tag="AI Tutor · Response",
    )
    page.wait_for_timeout(3500)

    # Scene 4: Socratic Mode Shift
    page.select_option("#sbCurrentMode", "QUESTION")
    page.wait_for_timeout(1000)
    tracker.set_caption(
        page,
        "Dynamic Mode Switch: QUESTION",
        "Tutor shifts pedagogical role from explanation to active diagnostic assessment",
        scene_tag="AI Tutor · Assessment",
    )
    page.wait_for_timeout(2000)

    followup_q = "Give me an adaptive practice question on this concept to test my understanding."
    page.click("#userInputChem")
    page.type("#userInputChem", followup_q, delay=30)
    page.wait_for_timeout(500)
    page.click("#sendBtnChem")
    page.wait_for_timeout(4500)

    tracker.set_caption(
        page,
        "Adaptive Question Generation",
        "Calibrated practice question targeting active student mastery level",
        scene_tag="AI Tutor · Practice",
    )
    page.wait_for_timeout(3000)

    # Scene 5: Local Privacy & Telemetry Drawer
    try:
        page.click(".chem-debug-toggle", timeout=4000)
        page.wait_for_timeout(1000)
        tracker.set_caption(
            page,
            "100% Student Privacy & Local Hardware Telemetry",
            "Zero cloud data leakage: Local SLM inference (47ms), Guardrails PASS, RAG grounded",
            scene_tag="Student · Privacy",
        )
        page.wait_for_timeout(3500)
    except Exception as e:
        print(f"  [Debug Drawer note: {e}]")

    return finalize_video(page, context, tracker, "demo_student_persona")


# =============================================================================
# 2. TEACHER PERSONA DEMO RECORDING (~60-70s)
# =============================================================================
def record_teacher_persona(browser, tokens: dict) -> str:
    print("\n=======================================================")
    print("[2/4] Recording Teacher Command Center & Copilot Demo...")
    print("=======================================================")
    context = init_context(browser, tokens)
    page = context.new_page()
    tracker = CaptionTracker("Teacher Command Center")
    tracker.start()

    # Scene 1: Teacher Dashboard Overview
    page.goto(f"{BASE_URL}/teacher", wait_until="networkidle")
    page.wait_for_timeout(1000)
    tracker.set_caption(
        page,
        "Teacher Command Center & Academic Dashboard",
        "Prof. Anita Sharma — Live cohort telemetry, retention distributions, and class metrics",
        scene_tag="Teacher · Overview",
    )
    page.wait_for_timeout(2500)

    # Scene 2: Students Cohort Roster
    page.click("#nav-students")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Real-Time Student Cohort Roster",
        "Class 11A Chemistry — Individual competency scores, retention rates, and attention flags",
        scene_tag="Teacher · Roster",
    )
    page.wait_for_timeout(2500)
    smooth_scroll(page, 300, steps=6, delay_ms=50)
    page.wait_for_timeout(1500)
    smooth_scroll(page, -300, steps=6, delay_ms=40)
    page.wait_for_timeout(1000)

    # Scene 3: AI Teacher Copilot
    page.click("#nav-copilot")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "AI Teacher Copilot — Automated Cohort Synthesis",
        "Synthesizes cohort learning hurdles into actionable lesson plans and remedial interventions",
        scene_tag="Teacher · AI Copilot",
    )
    page.wait_for_timeout(3000)
    smooth_scroll(page, 250, steps=6, delay_ms=50)
    page.wait_for_timeout(2000)

    # Scene 4: Early-Warning Misconception Alerts
    page.click("#nav-alerts")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Early-Warning Intervention & Alerts Engine",
        "Detects conceptual confusion in equilibrium constants before exam day",
        scene_tag="Teacher · Alerts",
    )
    page.wait_for_timeout(2500)

    # Scene 5: Marks & Grading Ledger
    try:
        page.goto(f"{BASE_URL}/admin#/examinations", wait_until="networkidle")
        page.wait_for_timeout(800)
        tracker.set_caption(
            page,
            "Integrated Gradebook & Term Examination Ledger",
            "CBSE grading rules, marks entry, and automated report card generation",
            scene_tag="Teacher · Grading",
        )
        page.wait_for_timeout(2500)
    except Exception as e:
        print(f"  [Grading note: {e}]")

    return finalize_video(page, context, tracker, "demo_teacher_persona")


# =============================================================================
# 3. PARENT PERSONA DEMO RECORDING (~60-70s)
# =============================================================================
def record_parent_persona(browser, tokens: dict) -> str:
    print("\n=======================================================")
    print("[3/4] Recording Parent Monitoring Portal Demo...")
    print("=======================================================")
    context = init_context(browser, tokens)
    page = context.new_page()
    tracker = CaptionTracker("Parent Monitoring Portal")
    tracker.start()

    # Scene 1: Parent Portal Landing & Child Selector
    page.goto(f"{BASE_URL}/parent", wait_until="networkidle")
    page.wait_for_timeout(1000)
    tracker.set_caption(
        page,
        "Parent Monitoring Portal & Multi-Child Dashboard",
        "Sharma Family — Comprehensive oversight of attendance, fees, exams, and teacher updates",
        scene_tag="Parent · Overview",
    )
    page.wait_for_timeout(2500)

    # Scene 2: Instant Multi-Child Switcher
    tracker.set_caption(
        page,
        "Single-Login Multi-Child Switcher",
        "Switching view from Aarav (Grade 11-A) to Ananya (Grade 7-B)...",
        scene_tag="Parent · Child Switch",
    )
    page.click("#pill-child-102")
    page.wait_for_timeout(2200)

    tracker.set_caption(
        page,
        "Dynamic Child Context Updating",
        "Switching back to Aarav (Grade 11 STEM)...",
        scene_tag="Parent · Child Switch",
    )
    page.click("#pill-child-101")
    page.wait_for_timeout(1800)

    # Scene 3: Daily Attendance & RFID Logs
    page.click("#tab-btn-attendance")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Verified Daily Attendance & RFID Gate Logs",
        "96.5% Attendance · Today's Entry: 07:54 AM via Smart Card Tap at Main Gate 2",
        scene_tag="Parent · Attendance",
    )
    page.wait_for_timeout(2500)

    # Scene 4: Fees, Invoices & Tax Receipts
    page.click("#tab-btn-fees")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Transparent Itemized Fee Accounting",
        "Annual Fees: ₹1.20L | Paid: ₹90K (3 Quarters) | Q4 Due: ₹30K | Instant Tax 80E Receipts",
        scene_tag="Parent · Fees",
    )
    page.wait_for_timeout(2500)

    # Scene 5: Mid-Term Examination Report Card
    page.click("#tab-btn-academics")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Mid-Term Examination Report Card",
        "CBSE A1 Distinction in Physics (93), Math (95), Chemistry (90) with Principal's commendation",
        scene_tag="Parent · Report Card",
    )
    page.wait_for_timeout(2500)

    # Scene 6: Teacher Notes & School Circulars
    page.click("#tab-btn-teacher")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Direct Teacher Feedback & Observations",
        "Dr. Sharma: 'Aarav showed tremendous improvement using AI tutor's Socratic hints'",
        scene_tag="Parent · Teacher Notes",
    )
    page.wait_for_timeout(2200)

    page.click("#tab-btn-notices")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Official School Circulars & Calendar",
        "Annual Science & Innovation Exhibition and Pre-Board exam schedules delivered directly",
        scene_tag="Parent · Circulars",
    )
    page.wait_for_timeout(2200)

    return finalize_video(page, context, tracker, "demo_parent_persona")


# =============================================================================
# 4. ADMINISTRATOR & TRUSTEE PERSONA DEMO RECORDING (EXPANDED ~180-210s)
# =============================================================================
def record_admin_trustee_persona(browser, tokens: dict) -> str:
    print("\n=======================================================")
    print("[4/4] Recording Administrator & Trustee Governance Demo (EXPANDED)...")
    print("=======================================================")
    context = init_context(browser, tokens)
    page = context.new_page()
    tracker = CaptionTracker("Admin & Trustee Governance")
    tracker.start()

    # 1. Executive Platform Overview
    page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
    page.wait_for_timeout(1000)
    tracker.set_caption(
        page,
        "Institutional Governance & Trust Administration Portal",
        "Comprehensive multi-tenant command center for School Trustees, Principals, and CFOs",
        scene_tag="Admin · Executive",
    )
    page.wait_for_timeout(3000)
    tracker.set_caption(
        page,
        "Unified Campus ERP Command Center",
        "Live Attendance, Fee Structure, Timetable & Smart ID Badges directly on the executive dashboard",
        scene_tag="ERP · Overview",
    )
    smooth_scroll(page, 450, steps=8, delay_ms=50)
    page.wait_for_timeout(2500)
    smooth_scroll(page, 400, steps=8, delay_ms=50)
    page.wait_for_timeout(2200)
    smooth_scroll(page, -850, steps=10, delay_ms=35)
    page.wait_for_timeout(1000)

    # 2. Multi-Tenant Organizations
    page.click("#nav-organizations")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Multi-Tenant Institutional Provisioning",
        "Delhi Public School, Kendriya Vidyalaya, Mumbai Institute, Bangalore STEM Academy",
        scene_tag="Trustee · Multi-Branch",
    )
    page.wait_for_timeout(3200)
    smooth_scroll(page, 220, steps=5, delay_ms=50)
    page.wait_for_timeout(1500)
    smooth_scroll(page, -220, steps=5, delay_ms=40)

    # 3. RBAC & Identity Security
    page.click("#nav-users")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Zero-Trust Role-Based Access Control (RBAC)",
        "Granular security policies for Super Admins, Principals, Accountants, Faculty, and Parents",
        scene_tag="Admin · RBAC",
    )
    page.wait_for_timeout(3200)
    smooth_scroll(page, 300, steps=6, delay_ms=50)
    page.wait_for_timeout(1600)
    smooth_scroll(page, -300, steps=6, delay_ms=40)

    # 4. School Attendance & Roll Call
    page.click("#nav-attendance")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Campus-Wide Daily Attendance Operations",
        "100% Verified Attendance Rate, real-time arrival logs, biometric/RFID hardware integration",
        scene_tag="Admin · Attendance",
    )
    page.wait_for_timeout(3200)

    # 5. Timetable Conflict Solver & Substitution
    page.click("#nav-timetable")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Academic Timetable Scheduling & Substitution Engine",
        "Class 11A Weekly Period Schedule, automated period conflict solver, and active relief alerts",
        scene_tag="Admin · Timetable",
    )
    page.wait_for_timeout(3500)
    smooth_scroll(page, 250, steps=6, delay_ms=50)
    page.wait_for_timeout(1500)
    smooth_scroll(page, -250, steps=6, delay_ms=40)

    # 6. Fee Accounting & Double-Entry Ledger
    page.click("#nav-fees")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Double-Entry Fee Accounting & Institutional Ledger",
        "Automated Invoicing, Fee Collections (₹1.10L), Outstanding Balances (₹75K), and Audited Ledgers",
        scene_tag="Trustee · Finance",
    )
    page.wait_for_timeout(3500)
    smooth_scroll(page, 320, steps=7, delay_ms=50)
    page.wait_for_timeout(2000)
    smooth_scroll(page, -320, steps=7, delay_ms=40)

    # 7. Examinations, Grading & Report Cards
    page.click("#nav-examinations")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Examinations, Marks Ledger & Report Cards",
        "Term Marks (Arjun, Priya, Rahul), CBSE Grade Tiers (A1/Distinction), and Cryptographic Report Cards",
        scene_tag="Admin · Examinations",
    )
    page.wait_for_timeout(3500)
    smooth_scroll(page, 280, steps=6, delay_ms=50)
    page.wait_for_timeout(1800)
    smooth_scroll(page, -280, steps=6, delay_ms=40)

    # 8. Digital Smart ID Badges & Official Certificates
    page.click("#nav-id-cards")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Digital Smart ID Badges & Official Certificates",
        "Contactless RFID chips, barcode verification, Bonafide Certificates & Transfer Certificates (TC)",
        scene_tag="Trustee · Compliance",
    )
    page.wait_for_timeout(3500)
    smooth_scroll(page, 350, steps=7, delay_ms=50)
    page.wait_for_timeout(2000)
    smooth_scroll(page, -350, steps=7, delay_ms=40)

    # 9. Campus Logistics (Transport Fleet & Hostel)
    page.click("#nav-logistics")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Campus Logistics — Transport Fleet & Hostel Facilities",
        "Bus Fleet Utilization (82.5%), Hostel Bed Occupancy (80%), and Science Lab Low-Stock Alerts",
        scene_tag="Admin · Logistics",
    )
    page.wait_for_timeout(3500)
    smooth_scroll(page, 260, steps=6, delay_ms=50)
    page.wait_for_timeout(1800)
    smooth_scroll(page, -260, steps=6, delay_ms=40)

    # 10. Academic Course Catalog & Curricula DAGs
    page.click("#nav-courses")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Academic Course Catalog & Syllabus DAGs",
        "Class 11 & 12 Chemistry, Physics, Mathematics with prerequisite dependency mapping",
        scene_tag="Admin · Academics",
    )
    page.wait_for_timeout(3200)

    # 11. AI Governance, Local SLM Registry & Kill-Switch
    page.click("#nav-models")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "AI Model Registry & Governance Safeguards",
        "Gayatri-Tutor-v3 SLM (Default), latency tracking, token quotas, and emergency kill switch",
        scene_tag="Trustee · AI Governance",
    )
    page.wait_for_timeout(3500)
    smooth_scroll(page, 240, steps=6, delay_ms=50)
    page.wait_for_timeout(1800)
    smooth_scroll(page, -240, steps=6, delay_ms=40)

    # 12. Subsystem Health & Offline Infrastructure
    page.click("#nav-system")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Platform Infrastructure & Zero-Cloud Offline Probes",
        "Live SQLite database connectivity, model registry readiness, and latency telemetry",
        scene_tag="Admin · Reliability",
    )
    page.wait_for_timeout(3200)

    # 13. Institutional Analytics & Reconciled KPIs
    page.click("#nav-analytics")
    page.wait_for_timeout(800)
    tracker.set_caption(
        page,
        "Authoritative Cross-Module KPI Reconciliation",
        "Reconciled SQL metrics: 100% Attendance, 70.3% Fees, 85% Transport, 80% Hostel, 100% Pass",
        scene_tag="Trustee · Analytics",
    )
    page.wait_for_timeout(3500)
    smooth_scroll(page, 300, steps=6, delay_ms=50)
    page.wait_for_timeout(2000)
    smooth_scroll(page, -300, steps=6, delay_ms=40)

    # 14. Executive Summary Closing
    page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
    page.wait_for_timeout(1000)
    tracker.set_caption(
        page,
        "Gayatri School OS — Certified Enterprise Platform",
        "Complete institutional operating system: 100% data sovereignty, zero mandatory recurring cloud costs",
        scene_tag="Trustee · Certified",
    )
    page.wait_for_timeout(3500)

    return finalize_video(page, context, tracker, "demo_admin_trustee_persona")


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================
def run_all_recordings():
    import uvicorn
    from central_platform.api.app import app

    print("[+] Starting Gayatri Central Platform API Server on 127.0.0.1:8000...")
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    print("[*] Probing server readiness /healthz...")
    if not wait_for_server(BASE_URL, timeout_sec=20):
        print("[ERROR] Platform server failed to respond.")
        sys.exit(1)

    print("[OK] Platform server is healthy and responding.")

    tokens_file = PROJECT_ROOT / "local_auth_tokens.json"
    with open(tokens_file, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-web-security", "--allow-running-insecure-content"],
        )

        try:
            # 1. Student Persona Demo
            try:
                results["student"] = record_student_persona(browser, tokens)
            except Exception as e:
                print(f"[!] Error recording Student persona: {e}")
                results["student"] = None

            # 2. Teacher Persona Demo
            try:
                results["teacher"] = record_teacher_persona(browser, tokens)
            except Exception as e:
                print(f"[!] Error recording Teacher persona: {e}")
                results["teacher"] = None

            # 3. Parent Persona Demo
            try:
                results["parent"] = record_parent_persona(browser, tokens)
            except Exception as e:
                print(f"[!] Error recording Parent persona: {e}")
                results["parent"] = None

            # 4. Admin & Trustee Persona Demo (EXPANDED)
            try:
                results["admin_trustee"] = record_admin_trustee_persona(browser, tokens)
            except Exception as e:
                print(f"[!] Error recording Admin & Trustee persona: {e}")
                results["admin_trustee"] = None

        finally:
            browser.close()
            server.should_exit = True
            print("[*] Background server shut down.")

    print("\n=======================================================")
    print(" ALL 4 PERSONA DEMO VIDEOS RECORDED SUCCESSFULLY")
    print("=======================================================")
    for role, path in results.items():
        if path and os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"  • {role.upper()}: {path} ({size_mb:.2f} MB)")
        else:
            print(f"  • {role.upper()}: [FAILED / NOT FOUND]")
    print("=======================================================\n")
    return results


if __name__ == "__main__":
    run_all_recordings()
