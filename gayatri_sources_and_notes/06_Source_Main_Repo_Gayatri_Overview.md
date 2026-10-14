# Source: Core Main Repo Overview (Gayatri-Education/Gayatri)

**Repository:** `https://github.com/Gayatri-Education/Gayatri`  
**Description:** Open, curriculum-free AI tutoring platform and sovereign intelligence platform running both on-device and enterprise on-premise.

## Key Technical Highlights
* **Curriculum-Free Architecture:** Accepts institutionally uploaded materials (PDF, DOCX, JSON) and converts them into RAG-indexed tutoring assets.
* **On-Device / Zero-Data-Egress:** Runs locally via SLMs (`llama-cpp-python`, Qwen2.5-0.5B) without requiring external cloud APIs.
* **5-Tier Instruction Cascade:** Org → Course → Class → Student → Session priority hierarchy for teacher controls.
* **Core Stack:**
  * **Frontend Desktop Shell:** PySide6 + QWebChannel Bridge.
  * **Backend API:** FastAPI (21 REST routers under `central_platform/`).
  * **Database:** SQLite in WAL mode (50 tables, 8 DDL migrations).
  * **RAG & Tutor Engine:** 16-step `GenericTutorOrchestrator`, hybrid vector + BM25 retrieval.
* **Verification & Testing:** 1,252 unit and integration tests across 43 verification phases.
