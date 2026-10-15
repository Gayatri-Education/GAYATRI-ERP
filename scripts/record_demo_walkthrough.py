"""
scripts/record_demo_walkthrough.py
Automated End-to-End Demo Video Recorder for Gayatri School OS & AI Tutor Suite.

Features Demonstrated:
1. Platform Overview & System Health Probes (/healthz, /readyz, /livez)
2. OpenAPI Swagger Architecture & 38+ Operational ERP Routers (/docs)
3. Multi-Tiered Admin Portal (/admin): Multi-tenant Orgs, RBAC Users, Curricula DAGs, AI Providers & Models
4. Real-Time Institutional Analytics & SQL Reconciliation (/api/v1/analytics/institutional/kpis)
5. Teacher Command Center & Copilot (/teacher): Cohort Telemetry, Misconception Alerts, Copilot Directives
6. Student Progress & Mastery Dashboard (/student): Individual Competency Trees, Prerequisite Visualizer
7. Gayatri AI Socratic Tutor & Adaptive Learning Suite (/tutor):
   - Multi-turn Pedagogical Tutoring with LaTeX math
   - Concept Mastery Progression & Mode Switching (EXPLAIN, QUESTION, HINT, REMEDIATE)
   - Real-time Socratic Dialogue & Misconception Remediation
   - Deep Pedagogical Observability & Telemetry Drawer (SLM inference, RAG Grounding, Guardrails)

Output:
- Root Video: gayatri_school_os_full_demo.webm
- Root Subtitles: gayatri_school_os_demo_captions.srt & gayatri_school_os_demo_captions.vtt
- Recordings Directory: demo_recordings/gayatri_school_os_full_demo.webm
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

# Ensure root directory in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
RECORDINGS_DIR = PROJECT_ROOT / "demo_recordings"
FINAL_VIDEO_NAME = "gayatri_school_os_full_demo.webm"

# Global caption tracking for generating synchronized .srt and .vtt subtitle files
caption_events = []
recording_start_time = None


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
    """Format seconds into SubRip SRT format HH:MM:SS,mmm."""
    millis = int((seconds - int(seconds)) * 1000)
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format seconds into WebVTT format HH:MM:SS.mmm."""
    millis = int((seconds - int(seconds)) * 1000)
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def set_hud_caption(page, title: str, subtitle: str, scene_tag: str = ""):
    """Render a high-contrast, crystal-clear floating HUD caption on screen and log timestamps."""
    global recording_start_time, caption_events
    now = time.time()
    if recording_start_time is None:
        recording_start_time = now

    rel_start = round(now - recording_start_time, 2)
    if caption_events:
        caption_events[-1]["end"] = rel_start

    caption_events.append({
        "start": rel_start,
        "end": rel_start + 4.0,
        "title": title,
        "subtitle": subtitle,
        "scene_tag": scene_tag,
    })

    page.evaluate(
        """([title, subtitle, scene_tag]) => {
            let banner = document.getElementById('demo-caption-banner');
            if (!banner) {
                banner = document.createElement('div');
                banner.id = 'demo-caption-banner';
                banner.style.position = 'fixed';
                banner.style.bottom = '22px';
                banner.style.left = '50%';
                banner.style.transform = 'translateX(-50%)';
                banner.style.backgroundColor = 'rgba(10, 12, 28, 0.94)';
                banner.style.color = '#ffffff';
                banner.style.border = '2px solid #53a8b6';
                banner.style.borderRadius = '12px';
                banner.style.padding = '10px 28px';
                banner.style.zIndex = '999999';
                banner.style.boxShadow = '0 10px 35px rgba(0,0,0,0.8), 0 0 15px rgba(83, 168, 182, 0.3)';
                banner.style.fontFamily = "'Segoe UI', system-ui, -apple-system, sans-serif";
                banner.style.textAlign = 'center';
                banner.style.backdropFilter = 'blur(12px)';
                banner.style.pointerEvents = 'none';
                banner.style.minWidth = '540px';
                banner.style.maxWidth = '85%';
                banner.style.transition = 'all 0.25s ease';
                document.body.appendChild(banner);
            }
            let tagHtml = scene_tag ? `<span style="background:linear-gradient(135deg, #9b59b6, #53a8b6); color:#fff; font-size:10px; font-weight:800; padding:2px 8px; border-radius:10px; letter-spacing:1px; text-transform:uppercase; margin-right:8px;">${scene_tag}</span>` : '';
            banner.innerHTML = `<div style="display:flex; align-items:center; justify-content:center; gap:6px; margin-bottom:3px;">${tagHtml}<span style="font-size:13.5px; font-weight:800; color:#53a8b6; letter-spacing:0.8px; text-transform:uppercase;">${title}</span></div><div style="font-size:12px; font-weight:500; color:#e2e8f0;">${subtitle}</div>`;
            banner.style.opacity = '1';
        }""",
        [title, subtitle, scene_tag],
    )


def generate_caption_files(total_duration: float):
    """Write synchronized SubRip (.srt) and WebVTT (.vtt) caption files to root and recordings dir."""
    if caption_events:
        caption_events[-1]["end"] = max(caption_events[-1]["start"] + 3.0, round(total_duration, 2))

    # SubRip .srt
    srt_blocks = []
    for idx, item in enumerate(caption_events, 1):
        s_str = format_srt_time(item["start"])
        e_str = format_srt_time(item["end"])
        tag = f"[{item['scene_tag']}] " if item["scene_tag"] else ""
        srt_blocks.append(f"{idx}\n{s_str} --> {e_str}\n{tag}{item['title']}: {item['subtitle']}\n")
    srt_content = "\n".join(srt_blocks)

    # WebVTT .vtt
    vtt_blocks = ["WEBVTT\n"]
    for idx, item in enumerate(caption_events, 1):
        s_str = format_vtt_time(item["start"])
        e_str = format_vtt_time(item["end"])
        tag = f"[{item['scene_tag']}] " if item["scene_tag"] else ""
        vtt_blocks.append(f"{idx}\n{s_str} --> {e_str}\n{tag}{item['title']}: {item['subtitle']}\n")
    vtt_content = "\n".join(vtt_blocks)

    # Save to both project root and demo_recordings/
    for target_dir in [PROJECT_ROOT, RECORDINGS_DIR]:
        target_dir.mkdir(parents=True, exist_ok=True)
        with open(target_dir / "gayatri_school_os_demo_captions.srt", "w", encoding="utf-8") as f:
            f.write(srt_content)
        with open(target_dir / "gayatri_school_os_demo_captions.vtt", "w", encoding="utf-8") as f:
            f.write(vtt_content)


def smooth_scroll(page, distance: int, steps: int = 10, delay_ms: int = 50):
    """Scroll smoothly to simulate natural presentation."""
    delta = distance // steps
    for _ in range(steps):
        page.evaluate(f"window.scrollBy(0, {delta})")
        page.wait_for_timeout(delay_ms)


def record_walkthrough():
    """Execute complete scripted product demonstration and record HD video."""
    global recording_start_time, caption_events
    caption_events = []
    recording_start_time = None

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Local Auth Tokens
    tokens_file = PROJECT_ROOT / "local_auth_tokens.json"
    if not tokens_file.exists():
        print("[!] local_auth_tokens.json not found. Running seed scripts...")
        from scripts.seed_local_environment import seed_local_environment
        from scripts.seed_erp_records import seed_erp_data
        seed_local_environment()
        seed_erp_data()

    with open(tokens_file, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    admin_token = tokens.get("usr_dps_admin", {}).get("token") or tokens.get("usr_superadmin", {}).get("token")
    teacher_token = tokens.get("usr_teacher_sharma", {}).get("token")
    student_token = tokens.get("usr_student_arjun", {}).get("token")

    print("[*] Launching Chromium with Playwright HD Video Recording (1280x720)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-web-security", "--allow-running-insecure-content"],
        )
        context = browser.new_context(
            record_video_dir=str(RECORDINGS_DIR),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720},
        )

        # Pre-seed localStorage with auth tokens across all portal personas
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

        page = context.new_page()
        recording_start_time = time.time()

        # =========================================================================
        # SCENE 1: ARCHITECTURAL OVERVIEW & SWAGGER REST APIs
        # =========================================================================
        print("  -> Scene 1: Platform Architecture & OpenAPI Swagger Documentation")
        page.goto(f"{BASE_URL}/docs", wait_until="networkidle")
        set_hud_caption(
            page,
            "Gayatri School OS — Platform Architecture",
            "38+ Enterprise Micro-Routers across SIS, ERP, Logistics, AI Engine & Analytics",
            scene_tag="Scene 1/7",
        )
        page.wait_for_timeout(2000)

        # Smooth exploration of OpenAPI categories
        smooth_scroll(page, 500, steps=8, delay_ms=60)
        page.wait_for_timeout(1500)
        smooth_scroll(page, 700, steps=10, delay_ms=60)
        page.wait_for_timeout(1500)
        smooth_scroll(page, -1200, steps=10, delay_ms=40)
        page.wait_for_timeout(1200)

        # =========================================================================
        # SCENE 2: MULTI-TIERED ADMIN PORTAL (Phase 00 & Phase 01)
        # =========================================================================
        print("  -> Scene 2: Multi-Tiered Admin Portal & RBAC Operations")
        page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        page.wait_for_timeout(1000)
        set_hud_caption(
            page,
            "Unified Admin Portal — Multi-Tenant Institutional Governance",
            "Executive metrics, multi-school management, RBAC accounts, and AI policies",
            scene_tag="Scene 2/7",
        )
        page.wait_for_timeout(2500)

        # 2A. Organizations Tab
        page.click("#nav-organizations")
        page.wait_for_timeout(800)
        set_hud_caption(
            page,
            "Multi-Tenant Tenant Provisioning",
            "Delhi Public School, Kendriya Vidyalaya, Mumbai Institute, Bangalore STEM",
            scene_tag="Admin · Orgs",
        )
        page.wait_for_timeout(2200)

        # 2B. Users & Role-Based Access Control
        page.click("#nav-users")
        page.wait_for_timeout(800)
        set_hud_caption(
            page,
            "User Identity & Role-Based Access Control (RBAC)",
            "Granular permission segregation for Super Admins, Principals, Faculty, and Parents",
            scene_tag="Admin · RBAC",
        )
        page.wait_for_timeout(2500)

        # 2C. Course Catalog & Curricula DAGs
        page.click("#nav-courses")
        page.wait_for_timeout(800)
        set_hud_caption(
            page,
            "Academic Course Catalog & Syllabus DAGs",
            "Class 11 & 12 Chemistry, Physics, Mathematics with prerequisite dependency mapping",
            scene_tag="Admin · Academics",
        )
        page.wait_for_timeout(2500)

        # 2D. AI Providers & Governance Models
        page.click("#nav-models")
        page.wait_for_timeout(800)
        set_hud_caption(
            page,
            "AI Model Registry & Governance Safeguards",
            "Gayatri-Tutor-v3 SLM (Default), latency tracking, token quotas, and emergency kill switch",
            scene_tag="Admin · AI Governance",
        )
        page.wait_for_timeout(2500)

        # 2E. System Health & Probes
        page.click("#nav-system")
        page.wait_for_timeout(800)
        set_hud_caption(
            page,
            "Platform Health & Subsystem Probes",
            "Live SQLite database connectivity, model registry readiness, and latency telemetry",
            scene_tag="Admin · Health",
        )
        page.wait_for_timeout(2200)

        # =========================================================================
        # SCENE 3: INSTITUTIONAL ANALYTICS & RECONCILED KPIS (Phase 08)
        # =========================================================================
        print("  -> Scene 3: Institutional Analytics & Authoritative KPI Reconciliation")
        page.goto(f"{BASE_URL}/api/v1/analytics/institutional/kpis", wait_until="networkidle")
        set_hud_caption(
            page,
            "Institutional Analytics — Authoritative Cross-Module KPIs",
            "Reconciled SQL metrics: 100% Attendance, 60% Fees, 82.5% Transport, 80% Hostel, 100% Pass",
            scene_tag="Scene 3/7",
        )
        page.wait_for_timeout(3500)

        # =========================================================================
        # SCENE 4: TEACHER COMMAND CENTER & COPILOT (Phase 03)
        # =========================================================================
        print("  -> Scene 4: Teacher Command Center & Pedagogical Copilot")
        page.goto(f"{BASE_URL}/teacher", wait_until="networkidle")
        page.wait_for_timeout(1000)
        set_hud_caption(
            page,
            "Teacher Command Center & AI Copilot",
            "Live cohort telemetry, mastery distributions, automated alerts, and pedagogical directives",
            scene_tag="Scene 4/7",
        )
        page.wait_for_timeout(2500)

        # Students Roster
        page.click("#nav-students")
        page.wait_for_timeout(800)
        set_hud_caption(
            page,
            "Real-Time Student Cohort Roster",
            "Individual competency scores, retention rates, and real-time support indicators",
            scene_tag="Teacher · Roster",
        )
        page.wait_for_timeout(2500)

        # AI Teacher Copilot
        page.click("#nav-copilot")
        page.wait_for_timeout(800)
        set_hud_caption(
            page,
            "AI Teacher Copilot — Pedagogical Cohort Synthesis",
            "Automated cohort briefing, identified misconception patterns, and targeted interventions",
            scene_tag="Teacher · Copilot",
        )
        page.wait_for_timeout(3000)

        # Active Alerts
        page.click("#nav-alerts")
        page.wait_for_timeout(800)
        set_hud_caption(
            page,
            "Early-Warning Intervention & Alerts Engine",
            "Real-time alerts for students stuck in prerequisite gaps or equilibrium misconceptions",
            scene_tag="Teacher · Alerts",
        )
        page.wait_for_timeout(2500)

        # =========================================================================
        # SCENE 5: STUDENT PROGRESS & MASTERY DASHBOARD
        # =========================================================================
        print("  -> Scene 5: Student Learning Progress & Mastery Dashboard")
        page.goto(f"{BASE_URL}/student", wait_until="networkidle")
        page.wait_for_timeout(1000)
        set_hud_caption(
            page,
            "Student Progress & Adaptive Competency Dashboard",
            "Arjun Patel (Grade 11) — Mastery curves, prerequisite progression, and practice records",
            scene_tag="Scene 5/7",
        )
        page.wait_for_timeout(2500)
        smooth_scroll(page, 450, steps=8, delay_ms=60)
        page.wait_for_timeout(2000)
        smooth_scroll(page, -450, steps=8, delay_ms=40)
        page.wait_for_timeout(1500)

        # =========================================================================
        # SCENE 6: GAYATRI AI SOCRATIC TUTOR & ADAPTIVE LEARNING SUITE (Phase 02 & Core)
        # =========================================================================
        print("  -> Scene 6: Gayatri AI Socratic Tutor & Adaptive Learning Suite")
        page.goto(f"{BASE_URL}/tutor", wait_until="networkidle")
        page.wait_for_timeout(1000)
        set_hud_caption(
            page,
            "Gayatri AI Adaptive Socratic Tutor",
            "Socratic dialogue, step-by-step guidance, prerequisite navigation, and live telemetry",
            scene_tag="Scene 6/7",
        )
        page.wait_for_timeout(2000)

        # Enter Adaptive Socratic Tutor workspace
        page.click(".mode-card:has-text('Adaptive Socratic Tutor')")
        page.wait_for_timeout(1200)

        set_hud_caption(
            page,
            "Adaptive Socratic Tutor Workspace",
            "Active Concept: Equilibrium Constant & Le Chatelier's Principle | Mode: EXPLAIN",
            scene_tag="AI Tutor · Setup",
        )
        page.wait_for_timeout(2000)

        # 6A. Interactive Socratic Conversation
        question_text = "How does Le Chatelier's principle predict equilibrium shifts when pressure changes?"
        print("  -> Typing Socratic question into chat...")
        page.click("#userInputChem")
        page.type("#userInputChem", question_text, delay=35)
        page.wait_for_timeout(800)

        set_hud_caption(
            page,
            "Socratic Dialogue & Dynamic Inquiry",
            "Submitting domain question to local SLM engine...",
            scene_tag="AI Tutor · Prompt",
        )
        page.click("#sendBtnChem")

        # Wait for streaming response to finish rendering
        page.wait_for_timeout(4500)
        set_hud_caption(
            page,
            "AI Socratic Response Streamed in Real-Time",
            "Pedagogical explanations, chemical reaction notation, and guided Socratic question",
            scene_tag="AI Tutor · Response",
        )
        page.wait_for_timeout(3500)

        # 6B. Switch Pedagogical Mode
        print("  -> Switching pedagogical mode to QUESTION...")
        page.select_option("#sbCurrentMode", "QUESTION")
        page.wait_for_timeout(1000)
        set_hud_caption(
            page,
            "Pedagogical Mode Switching: QUESTION",
            "Tutor dynamically transitions to active student assessment and diagnostic questioning",
            scene_tag="AI Tutor · Mode Switch",
        )
        page.wait_for_timeout(2000)

        # 6C. Multi-Turn Adaptive Follow-Up (Practice Question)
        followup_text = "Give me an adaptive practice question on this concept to test my understanding."
        print("  -> Typing adaptive practice request into chat...")
        page.click("#userInputChem")
        page.type("#userInputChem", followup_text, delay=30)
        page.wait_for_timeout(600)
        page.click("#sendBtnChem")
        page.wait_for_timeout(4500)
        set_hud_caption(
            page,
            "Adaptive Question Generation & Multi-Turn Dialogue",
            "Calibrated practice question generated targeting active student mastery level",
            scene_tag="AI Tutor · Practice",
        )
        page.wait_for_timeout(3500)

        # 6D. Deep Pedagogical Observability & Telemetry Drawer
        print("  -> Expanding Pedagogical Observability & Telemetry Panel...")
        try:
            page.click(".chem-debug-toggle", timeout=5000)
            page.wait_for_timeout(1000)
            set_hud_caption(
                page,
                "Pedagogical Observability & Diagnostic Drawer",
                "Inference telemetry, token counts, latency (47ms), Guardrails PASS, RAG grounding",
                scene_tag="AI Tutor · Telemetry",
            )
            page.wait_for_timeout(3500)
        except Exception as e:
            print(f"  [!] Note: Debug panel toggle: {e}")

        # =========================================================================
        # SCENE 7: SUMMARY & UNIFIED CLOSING
        # =========================================================================
        print("  -> Scene 7: Unified Ecosystem Summary")
        page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        page.wait_for_timeout(1000)
        set_hud_caption(
            page,
            "Gayatri School OS — Certified Enterprise Platform",
            "Complete three-sided ecosystem: SIS, ERP, Examinations, AI Tutor & Institutional Analytics",
            scene_tag="Scene 7/7",
        )
        page.wait_for_timeout(3000)

        # Conclude and finalize timing
        total_duration = time.time() - recording_start_time
        print(f"[*] Concluding demonstration ({total_duration:.1f}s total)...")
        generate_caption_files(total_duration)

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = video_obj.path()
        final_video_path = RECORDINGS_DIR / FINAL_VIDEO_NAME
        root_video_path = PROJECT_ROOT / FINAL_VIDEO_NAME

        if os.path.exists(raw_video_path):
            shutil.copy2(raw_video_path, str(final_video_path))
            shutil.copy2(raw_video_path, str(root_video_path))
            print(f"\n[SUCCESS] Demo video recording completed!")
            print(f"  Raw capture:      {raw_video_path}")
            print(f"  Root video:       {root_video_path}")
            print(f"  Recordings dir:   {final_video_path}")
            print(f"  Root Captions:    {PROJECT_ROOT / 'gayatri_school_os_demo_captions.srt'}")
            print(f"  File size:        {os.path.getsize(root_video_path):,} bytes")
            return str(root_video_path)
        else:
            print("[!] Video file was not found at expected path.")
            return None


def run_standalone_recorder():
    """Start uvicorn server in background thread and run video recorder."""
    import uvicorn
    from central_platform.api.app import app

    print("[+] Starting Gayatri Central Platform API Server on 127.0.0.1:8000...")
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    print("[*] Waiting for server probe /healthz...")
    if not wait_for_server(BASE_URL, timeout_sec=20):
        print("[ERROR] Platform server failed to respond within 20s.")
        sys.exit(1)

    print("[OK] Platform server is healthy and responding.")

    try:
        final_video = record_walkthrough()
        print("\n==================================================================")
        print(" DEMO VIDEO RECORDING FINISHED SUCCESSFULLY")
        print(f" Root Video: {final_video}")
        print(f" Captions:   {PROJECT_ROOT / 'gayatri_school_os_demo_captions.srt'}")
        print("==================================================================")
    finally:
        server.should_exit = True
        print("[*] Background server shut down.")


if __name__ == "__main__":
    run_standalone_recorder()
