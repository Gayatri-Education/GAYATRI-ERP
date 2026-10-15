"""
scripts/capture_demo_previews.py
Generates high-resolution snapshot preview images for each demo video in docs/assets/demos/.
"""
import json
import threading
import time
import urllib.request
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DOCS_DEMO_DIR = PROJECT_ROOT / "docs" / "assets" / "demos"
DOCS_DEMO_DIR.mkdir(parents=True, exist_ok=True)

def wait_for_server(url: str, timeout_sec: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def generate_previews():
    import uvicorn
    from central_platform.api.app import app

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    if not wait_for_server("http://127.0.0.1:8000"):
        print("[!] Server failed to start")
        return

    tokens_file = PROJECT_ROOT / "local_auth_tokens.json"
    with open(tokens_file, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    admin_token = tokens.get("usr_dps_admin", {}).get("token") or tokens.get("usr_superadmin", {}).get("token")
    teacher_token = tokens.get("usr_teacher_sharma", {}).get("token")
    student_token = tokens.get("usr_student_arjun", {}).get("token")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Admin Master Preview
        ctx1 = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx1.add_init_script(f"localStorage.setItem('admin_token', '{admin_token}');")
        p1 = ctx1.new_page()
        p1.goto("http://127.0.0.1:8000/admin", wait_until="networkidle")
        p1.wait_for_timeout(1500)
        p1.screenshot(path=str(DOCS_DEMO_DIR / "preview_admin_master.png"))
        ctx1.close()
        print("[+] Captured preview_admin_master.png")

        # 2. Student Socratic Tutor Preview
        ctx2 = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx2.add_init_script(f"""
            localStorage.setItem('access_token', '{student_token}');
            localStorage.setItem('student_token', '{student_token}');
            localStorage.setItem('demo_student_id', 'usr_student_arjun');
            localStorage.setItem('active_course_id', 'crs_chem_101');
        """)
        p2 = ctx2.new_page()
        p2.goto("http://127.0.0.1:8000/tutor", wait_until="networkidle")
        p2.wait_for_timeout(1500)
        p2.evaluate("if (typeof switchTab === 'function') switchTab('chemistry');")
        p2.wait_for_timeout(1000)
        p2.screenshot(path=str(DOCS_DEMO_DIR / "preview_student_persona.png"))
        ctx2.close()
        print("[+] Captured preview_student_persona.png")

        # 3. Teacher Copilot Preview
        ctx3 = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx3.add_init_script(f"localStorage.setItem('teacher_token', '{teacher_token}');")
        p3 = ctx3.new_page()
        p3.goto("http://127.0.0.1:8000/teacher", wait_until="networkidle")
        p3.wait_for_timeout(1500)
        p3.screenshot(path=str(DOCS_DEMO_DIR / "preview_teacher_persona.png"))
        ctx3.close()
        print("[+] Captured preview_teacher_persona.png")

        # 4. Parent Portal Preview
        ctx4 = browser.new_context(viewport={"width": 1280, "height": 720})
        p4 = ctx4.new_page()
        p4.goto("http://127.0.0.1:8000/parent", wait_until="networkidle")
        p4.wait_for_timeout(1500)
        p4.screenshot(path=str(DOCS_DEMO_DIR / "preview_parent_persona.png"))
        ctx4.close()
        print("[+] Captured preview_parent_persona.png")

        browser.close()
        server.should_exit = True

if __name__ == "__main__":
    generate_previews()
