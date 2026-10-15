"""
scripts/record_admin_master_demo.py
Authoritative, Comprehensive Master Walkthrough Video Recorder for Gayatri Admin & Trustee Persona.

Key Demonstrations:
1. Executive Campus Command Center & Live Institutional KPIs
2. Daily Student Attendance, Biometric Roll Call, Mark All Present
3. Weekly Timetable Scheduling & Teacher Substitution Slot Editing
4. Fee Structure, Invoicing, Active Balance Collection (UPI) & Double-Entry Ledger
5. Campus Transport Fleet, Real-Time Student Route Allocation & Live Passenger Manifest
6. Curriculum Library Subsystem, RFID Circulation & Book Issuance
7. Digital Smart Student ID Badges & Cryptographic Certificate Issuance
8. Platform-Wide Telemetry, Subsystem Health & In-Portal Reconciled Analytics (Zero 401 Errors)
9. System Diagnostics & AI Emergency Kill Switch Governance
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8008"
RECORDINGS_DIR = PROJECT_ROOT / "demo_recordings"
DOCS_DEMO_DIR = PROJECT_ROOT / "docs" / "assets" / "demos"


def wait_for_server(url: str, timeout_sec: int = 25) -> bool:
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
                    banner.style.background = 'rgba(10, 10, 26, 0.95)';
                    banner.style.border = '1px solid rgba(83, 168, 182, 0.5)';
                    banner.style.borderRadius = '14px';
                    banner.style.padding = '12px 28px';
                    banner.style.boxShadow = '0 12px 36px rgba(0,0,0,0.7), 0 0 20px rgba(83, 168, 182, 0.25)';
                    banner.style.fontFamily = "'Segoe UI', system-ui, -apple-system, sans-serif";
                    banner.style.textAlign = 'center';
                    banner.style.backdropFilter = 'blur(12px)';
                    banner.style.pointerEvents = 'none';
                    banner.style.minWidth = '580px';
                    banner.style.maxWidth = '90%';
                    banner.style.transition = 'all 0.25s ease';
                    document.body.appendChild(banner);
                }
                let tagHtml = scene_tag ? `<span style="background:linear-gradient(135deg, #9b59b6, #53a8b6); color:#fff; font-size:10px; font-weight:800; padding:2px 8px; border-radius:10px; letter-spacing:1px; text-transform:uppercase; margin-right:8px;">${scene_tag}</span>` : '';
                banner.innerHTML = `<div style="display:flex; align-items:center; justify-content:center; gap:6px; margin-bottom:4px;">${tagHtml}<span style="font-size:14px; font-weight:800; color:#53a8b6; letter-spacing:0.8px; text-transform:uppercase;">${title}</span></div><div style="font-size:12.5px; font-weight:500; color:#e2e8f0; line-height:1.4;">${subtitle}</div>`;
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


def smooth_scroll(page, distance: int, steps: int = 8, delay_ms: int = 40):
    delta = distance // steps
    for _ in range(steps):
        page.evaluate(f"window.scrollBy(0, {delta})")
        page.wait_for_timeout(delay_ms)


def record_admin_master_demo():
    print("[+] Starting Gayatri Central Platform API Server for Admin Walkthrough Recording...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "central_platform.api.app:create_app", "--factory", "--port", "8008", "--host", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
    )

    if not wait_for_server(BASE_URL, timeout_sec=20):
        server_process.terminate()
        raise RuntimeError("FastAPI server failed to start on port 8008")

    # Fetch demo tokens
    tokens = {}
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/v1/auth/demo-tokens") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tokens = data.get("data", {})
    except Exception as e:
        print(f"[!] Warning: Could not fetch demo tokens: {e}")

    superadmin_token = tokens.get("superadmin", {}).get("token") or "demo-superadmin-token"

    for d in [RECORDINGS_DIR, DOCS_DEMO_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    print("[+] Launching Playwright browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--enable-font-antialiasing", "--disable-gpu-sandbox"],
        )
        context = browser.new_context(
            record_video_dir=str(RECORDINGS_DIR),
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080},
        )

        context.add_init_script(f"""
            localStorage.setItem('admin_token', '{superadmin_token}');
            localStorage.setItem('auth_token', '{superadmin_token}');
            localStorage.setItem('user_role', 'SUPER_ADMIN');
        """)

        page = context.new_page()
        tracker = CaptionTracker("Master Administrator & Trustee Executive Walkthrough")
        tracker.start()

        # Dialog handler for prompt/confirm interactions
        def handle_dialog(dialog):
            msg = dialog.message.lower()
            if "student" in msg:
                dialog.accept("Arjun Patel")
            elif "type" in msg or "certificate" in msg:
                dialog.accept("Bonafide Student Certificate")
            elif "kill switch" in msg:
                dialog.accept()
            else:
                dialog.accept()

        page.on("dialog", handle_dialog)

        # =========================================================================
        # SCENE 1: Executive Command Center & Dashboard
        # =========================================================================
        print("[*] Recording Scene 1: Executive Command Center...")
        page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        page.wait_for_timeout(1500)

        tracker.set_caption(
            page,
            "Gayatri ERP: Multi-Tiered Institution Administration & Executive Portal",
            "Authoritative command center for Trustees, Principals, Accountants, and System Administrators",
            scene_tag="Executive · Command Center",
        )
        page.wait_for_timeout(4000)
        smooth_scroll(page, 240, steps=8, delay_ms=45)
        page.wait_for_timeout(2500)
        smooth_scroll(page, -240, steps=8, delay_ms=45)
        page.wait_for_timeout(1000)

        # =========================================================================
        # SCENE 2: Biometric Attendance & Daily Roll Call
        # =========================================================================
        print("[*] Recording Scene 2: Attendance Operations...")
        page.click("#nav-attendance")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Campus-Wide Daily Attendance & Smart Biometric Roll Call",
            "Class 11A synchronized attendance roster, RFID hardware taps, and arrival timestamps",
            scene_tag="Admin · Attendance",
        )
        page.wait_for_timeout(3500)

        # Action 2a: Toggle individual status
        tracker.set_caption(
            page,
            "Action: Toggle Student Attendance Status (Biometric Override)",
            "Audited status toggle for Rohan Gupta (11A-05) from LATE to PRESENT with timestamp",
            scene_tag="Admin · Attendance Toggle",
        )
        toggle_btn = page.locator("#attendanceTableBody tr:nth-child(5) button:has-text('Toggle Status')")
        toggle_btn.click()
        page.wait_for_timeout(2500)

        # Action 2b: Mark All Present
        tracker.set_caption(
            page,
            "Action: Batch Roll Call Synchronization — Mark All Present",
            "Instantly records 100% verified attendance across the entire Class 11A cohort",
            scene_tag="Admin · Batch Attendance",
        )
        page.click("button:has-text('Mark All Present')")
        page.wait_for_timeout(3500)
        smooth_scroll(page, 240, steps=6, delay_ms=40)
        page.wait_for_timeout(2000)
        smooth_scroll(page, -240, steps=6, delay_ms=40)

        # =========================================================================
        # SCENE 3: Academic Timetable & Slot Editing
        # =========================================================================
        print("[*] Recording Scene 3: Timetable Management & Slot Editing...")
        page.click("#nav-timetable")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Academic Timetable Scheduling & Teacher Relief Engine",
            "CBSE Class 11A Weekly Period Schedule with active teacher substitution alerts",
            scene_tag="Admin · Timetable",
        )
        page.wait_for_timeout(3500)

        # Action: Edit Timetable Slot
        tracker.set_caption(
            page,
            "Action: Edit Timetable Period Slot & Assign Teacher Relief",
            "Assigning Dr. S. Rao to Period 3 Physics Lab in Room 204 with substitution endorsement",
            scene_tag="Admin · Timetable Action",
        )
        page.click("button:has-text('Edit Timetable Slot')")
        page.wait_for_timeout(1500)

        page.select_option("#ttDaySelect", "Monday")
        page.select_option("#ttPeriodSelect", "p3")
        page.fill("#ttSubjectInput", "Physics Lab (Advanced Mechanics)")
        page.fill("#ttFacultyInput", "Dr. S. Rao")
        page.fill("#ttRoomInput", "Room 204 (Science Wing)")
        page.check("#ttSubstitutionCheck")
        page.wait_for_timeout(1500)

        page.click("#modalEditTimetable button:has-text('Save Timetable Slot')")
        page.wait_for_timeout(3500)
        smooth_scroll(page, 220, steps=6, delay_ms=40)
        page.wait_for_timeout(2000)
        smooth_scroll(page, -220, steps=6, delay_ms=40)

        # =========================================================================
        # SCENE 4: Fee Structure, Payment Collection & Double-Entry Ledger
        # =========================================================================
        print("[*] Recording Scene 4: Fee Accounting & Payment Collection...")
        page.click("#nav-fees")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Double-Entry Fee Accounting & Institutional General Ledger",
            "Real-time fee collection KPIs, student fee invoices, outstanding balances, and audited ledgers",
            scene_tag="Trustee · Finance",
        )
        page.wait_for_timeout(3500)

        # Action: Collect Fee Payment on Pending Invoice
        tracker.set_caption(
            page,
            "Action: Collect Student Fee Balance via UPI Gateway",
            "Collecting ₹20,000 balance for Arjun Patel (INV-2026-001) with cryptographic reference",
            scene_tag="Admin · Fee Collection Action",
        )
        collect_btn = page.locator("#feesTableBody tr:first-child button:has-text('Collect')")
        collect_btn.click()
        page.wait_for_timeout(1500)

        page.fill("#feeAmountInput", "20000")
        page.select_option("#feePaymentModeSelect", "Razorpay UPI")
        page.fill("#feeRefInput", "UPI/2026/GAYATRI/98712")
        page.wait_for_timeout(1500)

        page.click("#modalCollectFee button:has-text('Confirm & Record Payment')")
        page.wait_for_timeout(3500)

        tracker.set_caption(
            page,
            "Payment Settled: Invoice Marked PAID & Appended to Audited Ledger",
            "General ledger automatically appends credit transaction with immutable SHA-256 integrity",
            scene_tag="Trustee · Audited Ledger",
        )
        smooth_scroll(page, 340, steps=8, delay_ms=40)
        page.wait_for_timeout(2500)
        smooth_scroll(page, -340, steps=8, delay_ms=40)

        # =========================================================================
        # SCENE 5: Transport Fleet, Route Allocation & Passenger Manifest
        # =========================================================================
        print("[*] Recording Scene 5: Transport Fleet & Passenger Allocation...")
        page.click("#nav-logistics")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Campus Transport Fleet, Hostel Facilities & Inventory Logistics",
            "Real-time GPS tracking, 40-seat AC bus routes, hostel room occupancy, and stock alerts",
            scene_tag="Admin · Logistics",
        )
        page.wait_for_timeout(3500)

        # Action: Allocate Student to Route
        tracker.set_caption(
            page,
            "Action: Allocate Student to Bus Route & Update Live Manifest",
            "Assigning Ananya Verma to Route RTE-NORTH-01 at Sector 14 Rohini boarding point",
            scene_tag="Admin · Transport Action",
        )
        page.click("button:has-text('Allocate Student to Route')")
        page.wait_for_timeout(1500)

        page.select_option("#trStudentSelect", "Ananya Verma")
        page.select_option("#trStopSelect", "Sector 14 Rohini")
        page.fill("#trContactInput", "+91-9811002233")
        page.wait_for_timeout(1500)

        page.click("#modalAllocateTransport button:has-text('Allocate to Route')")
        page.wait_for_timeout(3500)

        tracker.set_caption(
            page,
            "Passenger Manifest Updated: 34 / 40 Seats Utilized (85.0%)",
            "Live student manifest and emergency parent contacts updated across mobile bus conductor units",
            scene_tag="Admin · Passenger Manifest",
        )
        smooth_scroll(page, 300, steps=7, delay_ms=40)
        page.wait_for_timeout(2200)
        smooth_scroll(page, -300, steps=7, delay_ms=40)

        # =========================================================================
        # SCENE 6: Curriculum Library & Automated Book Circulation
        # =========================================================================
        print("[*] Recording Scene 6: Library Subsystem & Book Issuance...")
        page.click("#nav-library")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Curriculum Library Catalog & Automated RFID Circulation Desk",
            "1,450 accredited NCERT & CBSE volumes, active lending ledger, and return due tracking",
            scene_tag="Admin · Library Subsystem",
        )
        page.wait_for_timeout(3500)

        # Action: Issue Library Book
        tracker.set_caption(
            page,
            "Action: Issue Physics Textbook to Student Borrower",
            "Lending 'Concepts of Physics Vol 1' to Arjun Patel (11A-01) with automated 30-day return due date",
            scene_tag="Admin · Book Issuance Action",
        )
        page.click("button:has-text('Issue Book to Student')")
        page.wait_for_timeout(1500)

        page.select_option("#libStudentSelect", "Arjun Patel (11A-01)")
        page.select_option("#libBookSelect", "Concepts of Physics Vol 1 - Dr. H.C. Verma")
        page.wait_for_timeout(1500)

        page.click("#modalIssueBook button:has-text('Issue Book to Student')")
        page.wait_for_timeout(3500)

        tracker.set_caption(
            page,
            "Book Issued & Circulation Record Sealed",
            "Active borrowing ledger immediately updated with barcode RFID timestamp and due alert",
            scene_tag="Admin · Circulation Desk",
        )
        smooth_scroll(page, 280, steps=6, delay_ms=40)
        page.wait_for_timeout(2000)
        smooth_scroll(page, -280, steps=6, delay_ms=40)

        # =========================================================================
        # SCENE 7: Smart ID Badges & Official Cryptographic Certificates
        # =========================================================================
        print("[*] Recording Scene 7: ID Cards & Certificates...")
        page.click("#nav-id-cards")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Student Smart Identity Badges & Cryptographic Certificates",
            "Contactless RFID/NFC student ID cards, verifiable QR barcodes, and official Bonafide certificates",
            scene_tag="Trustee · Digital Credentials",
        )
        page.wait_for_timeout(3500)

        # Action: Issue Official Certificate
        tracker.set_caption(
            page,
            "Action: Issue Cryptographically Sealed Bonafide Certificate",
            "Generating verified Bonafide Student Certificate for Arjun Patel with SHA-256 seal",
            scene_tag="Admin · Certificate Issuance",
        )
        page.click("button:has-text('Issue Certificate')")
        page.wait_for_timeout(3500)

        smooth_scroll(page, 280, steps=6, delay_ms=40)
        page.wait_for_timeout(2200)
        smooth_scroll(page, -280, steps=6, delay_ms=40)

        # =========================================================================
        # SCENE 8: Reconciled Institutional Analytics (100% Error-Free)
        # =========================================================================
        print("[*] Recording Scene 8: In-Portal Institutional Analytics...")
        page.click("#nav-analytics")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Executive Institutional Intelligence & Reconciled KPIs",
            "Authoritative SQL aggregate metrics: 100% Attendance, 70.3% Fee Ratio, 85% Fleet, 100% Pass",
            scene_tag="Trustee · Executive Analytics",
        )
        page.wait_for_timeout(4000)
        smooth_scroll(page, 300, steps=7, delay_ms=40)
        page.wait_for_timeout(2500)
        smooth_scroll(page, -300, steps=7, delay_ms=40)

        # =========================================================================
        # SCENE 9: Subsystem Diagnostics & AI Emergency Governance
        # =========================================================================
        print("[*] Recording Scene 9: System Telemetry & AI Kill Switch...")
        page.click("#nav-system")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Infrastructure Health & AI Safety Kill Switch Governance",
            "Zero-cloud local operation, database integrity probes, and instantaneous emergency circuit breaker",
            scene_tag="Trustee · AI Governance",
        )
        page.wait_for_timeout(3000)

        # Action: Ping Diagnostics
        tracker.set_caption(
            page,
            "Action: Run Subsystem Diagnostics & Live Health Probes",
            "Pinging API server, database layer, AI inference gateway, and sync services",
            scene_tag="Admin · System Diagnostics",
        )
        page.click("button:has-text('Ping Diagnostics')")
        page.wait_for_timeout(3500)

        # =========================================================================
        # SCENE 10: Return to Dashboard for Grand Closing
        # =========================================================================
        print("[*] Recording Scene 10: Grand Closing...")
        page.click("#nav-dashboard")
        page.wait_for_timeout(1200)
        tracker.set_caption(
            page,
            "Gayatri AI — Production Multi-Tiered Institution ERP",
            "100% sovereign campus operating system: complete reliability, privacy, and zero SaaS lock-in",
            scene_tag="Certified · Gayatri ERP",
        )
        page.wait_for_timeout(4500)

        # Finalize Video
        print("[+] Finalizing video recording...")
        page.close()
        video = page.video
        video_path = video.path()
        context.close()
        browser.close()

    server_process.terminate()
    server_process.wait()

    target_webm = RECORDINGS_DIR / "demo_admin_master_walkthrough.webm"
    docs_webm = DOCS_DEMO_DIR / "demo_admin_master_walkthrough.webm"

    if os.path.exists(video_path):
        shutil.move(video_path, str(target_webm))
        shutil.copy2(str(target_webm), str(docs_webm))
        print(f"[SUCCESS] Video saved to: {target_webm}")
        print(f"[SUCCESS] Copied to docs: {docs_webm}")

    # Export captions
    total_duration = time.time() - tracker.start_time if tracker.start_time else 160.0
    tracker.export_captions("demo_admin_master_walkthrough", total_duration)
    print(f"[SUCCESS] Captions exported (SRT and VTT) for total duration: {total_duration:.1f}s")


if __name__ == "__main__":
    record_admin_master_demo()
