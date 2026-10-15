<div align="center">

<img src="gai3.png" alt="Gayatri AI" width="120"/>

# Gayatri AI Platform

**Curriculum-Free Adaptive AI Tutor · CBSE/NCERT Classes 9–12**

[![CI](https://github.com/Gayatri-Education/GAYATRI-ERP/actions/workflows/ci.yml/badge.svg)](https://github.com/Gayatri-Education/GAYATRI-ERP/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE.md)
[![Version](https://img.shields.io/badge/version-3.0.1-orange.svg)](VERSION)
[![DBERT](https://img.shields.io/badge/Built%20at-DBERT%20Internship%20Program-blueviolet)](https://dbert.online/startups/portfolio/gayatri-ai)

</div>

---

Gayatri is an **open, curriculum-free AI tutoring platform** — any school, institute, or teacher can upload their own course material and the platform turns it into an intelligent, personalized, and trackable tutoring experience. It runs entirely on-device via local SLMs (**no cloud required, no student data leaves the device**), and optionally syncs with a central server for teacher oversight, analytics, and institution-level reporting.

> **Built at [DBERT](https://dbert.online/startups/portfolio/gayatri-ai) · Internship Program · Batch Aug–Oct 2026**  
> *Digital Blinc Education Research & Technology — India's AI Venture Studio, Delhi*

---

## 🎯 What Makes It Different

| | Gayatri | Typical EdTech |
|---|---|---|
| **Curriculum** | Any subject, any institution uploads their own | Fixed content only |
| **AI runs on** | Your device (llama-cpp-python, no internet) | Cloud APIs |
| **Student data** | Never leaves the device | Sent to cloud |
| **Works offline** | Fully, with sync when online | No |
| **Per-student tracking** | Mastery, spaced review, learning events | Basic progress |
| **Teacher control** | 5-tier instruction cascade | Limited |
| **Deployment** | Desktop, local server, or cloud | Cloud only |

---

## ✨ Features

### For Institutions
- 📂 **Plug-in any curriculum** — upload PDF, DOCX, or JSON; the platform chunks, indexes, and activates it for RAG-based tutoring automatically
- 🏫 **Multi-tenant** — multiple schools and orgs on one platform, fully isolated
- 📊 **Institution-level analytics** — mastery distribution, cohort health, intervention queue
- 💸 **Fee management** — Razorpay/UPI with HMAC webhook verification

### For Teachers
- 👨‍🏫 **5-tier instruction cascade** — Org → Course → Class → Student → Session (highest to lowest priority)
- 📋 **Teacher Copilot** — AI-generated diagnostic briefings, lesson plan suggestions, class analytics
- 🔔 **Notification system** — alerts for struggling students, mastery milestones, intervention flags

### For Students
- 🧠 **Adaptive tutoring** — Socratic questioning, not answers. 16-step pedagogical turn lifecycle
- 📚 **Multi-subject** — Classes 9–12, any subject added by the institution (NCERT/CBSE or custom)
- 🔄 **Spaced review scheduler** — Ebbinghaus-decay-based review reminders
- 🌐 **8-language UI** — English, Hindi, and 6 regional Indian languages

### For Parents
- 👪 **Parent portal** — progress feed, privacy controls, screen-time visibility
- 🔒 **4 privacy tiers** — Full transparency / Summary only / Restricted / Blocked

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Desktop App (PySide6)                      │
│  Student Portal │ Teacher Portal │ Parent Portal │ Fee Admin │
│                     Admin Portal                             │
└───────────────────────┬──────────────────────────────────────┘
                        │  QWebChannel Bridge
┌───────────────────────▼──────────────────────────────────────┐
│              Central Platform (FastAPI)                      │
│  /api/v1 — modular API routers · Auth · Students · Teachers  │
│  Courses · Sessions · RAG · Assessment · Analytics           │
│  Notifications · Sync · Fees · Payments · i18n              │
└─────────────┬──────────────────────────┬─────────────────────┘
              │                          │
┌─────────────▼──────────┐  ┌────────────▼────────────────────┐
│   SQLite (WAL mode)    │  │   Local SLM (llama-cpp-python)  │
│   50+ tables, 8 migs   │  │   Qwen2.5-0.5B · no Ollama     │
│   offline-first        │  │   runs on CPU, 1GB RAM           │
└────────────────────────┘  └─────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────┐
│            Offline Sync (when online)                      │
│   LocalSyncOutbox → SyncService → Central DB               │
└────────────────────────────────────────────────────────────┘
```

**Core modules:**
- [`central_platform/`](central_platform/) — FastAPI server, 21 API routers, auth, db, sync engine
- [`central_platform/tutor/orchestrator.py`](central_platform/tutor/orchestrator.py) — 16-step GenericTutorOrchestrator
- [`central_platform/ai/`](central_platform/ai/) — AI gateway, model router, adapters, policy engine
- [`central_platform/rag/`](central_platform/rag/) — Scoped RAG, hybrid retrieval, version-pinned knowledge
- [`app/`](app/) — PySide6 desktop shell, portal controllers, WebEngine bridge
- [`local_runtime/`](local_runtime/) — Standalone offline runtime (course cache, RAG cache, sync outbox)
- [`migrations/`](migrations/) — 8 SQL DDL migrations (001–008) with reversible down-scripts
- [`data/`](data/) — Bundled NCERT curriculum and RAG seed data
- [`scripts/`](scripts/) — Database migration, seeding, inspection, and ops utilities

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- Git

### 1. Clone & Install

```bash
git clone https://github.com/Gayatri-Education/GAYATRI-ERP.git
cd Gayatri-ERP

# Windows (recommended)
setup.bat          # creates .venv, installs deps, runs migrations, launches app

# Or manually:
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the repo root:

```env
# Database
GAYATRI_DB_PATH=gayatri_local.db
GAYATRI_ENV=development          # or 'production'

# AI (optional — omit to run in mock/dev mode)
GAYATRI_LOCAL_MODEL_PATH=models/qwen2.5-0.5b-instruct-q4_k_m.gguf

# Cloud fallback keys (all optional)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Security — CHANGE THIS IN PRODUCTION
JWT_SECRET_KEY=dev-secret-key-change-in-production-32-bytes-min
GAYATRI_ENCRYPTION_KEY=
```

### 3. Initialize Database

```bash
python scripts/migrate_db.py up --db-path gayatri_local.db
# Or via Python:
python -c "from central_platform.db import PlatformDatabase; db = PlatformDatabase(); print('Ready. Tables:', len(db.get_table_names()))"
```

Runs all 8 migrations automatically (001–008).

### 4. Download a Local Model (Optional)

```bash
# Recommended — 400MB, runs on any CPU with 1GB RAM
python install_llama.py
```

Or manually download from [HuggingFace](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) and place in `models/`.

Without a model, the platform uses `MockAIAdapter` — fully functional for development and testing.

### 5. Start the Platform

```bash
# Desktop application (Windows)
run.bat
# or
python -m app.main

# REST API server only
python -m uvicorn central_platform.api.server:app --host 0.0.0.0 --port 8000

# Local dev environment (API + seed data)
python scripts/launch_local_environment.py
```

**Once running:**
- 📖 **Swagger UI**: `http://localhost:8000/docs`
- 📋 **ReDoc**: `http://localhost:8000/redoc`
- ✅ **Liveness**: `GET /healthz`
- ✅ **Readiness**: `GET /readyz`

---

## 🏫 Adding a Curriculum

Gayatri is curriculum-free by design. To add a new course for your institution:

1. **Prepare your material** — PDF, DOCX, or structured JSON
2. **Upload via Admin Portal** — the platform chunks, embeds, and indexes it into the RAG pipeline
3. **Publish a course version** — goes through an approval workflow before students see it
4. **Students enroll** — and the tutor immediately works with your content

The same Socratic tutoring engine, mastery tracking, and teacher controls work for any subject added this way.

See [`docs/operations/deployment-guide.md`](docs/operations/deployment-guide.md) for institution setup.

---

## 🧪 Running Tests

**1,765+ automated non-GUI tests, all passing.** CI enforces this on every push.

```bash
# Full suite (~90 seconds)
python -m pytest -q -m "not gui"

# Key areas
python -m pytest tests/test_phase01_auth_identity_remediation.py -v      # Auth & security
python -m pytest tests/test_phase06_scoped_rag_authorization.py -v       # RAG & curriculum
python -m pytest tests/test_phase22_security_privacy_isolation_audit.py -v  # Privacy
python -m pytest tests/test_phase25_performance_capacity_verification.py -v  # Performance
python -m pytest tests/test_phase43_production_readiness_gate.py -v      # Release gate
```

---

## 🔐 Security

- **Zero-trust auth** — JWT with JTI revocation list. Every API route requires a valid bearer token
- **Tenant isolation** — Cross-organisation requests blocked at both API and DB query levels
- **Answer leakage prevention** — AI responses scanned for exact solution strings before delivery to students
- **Prompt injection defense** — Multi-stage sanitization at QWebChannel bridge and API ingress
- **Local-only by default** — Student data never transmitted to cloud providers (`LOCAL_ONLY` privacy mode)
- **HMAC payment verification** — Razorpay webhook signatures verified with constant-time comparison
- **Audit trail** — All AI executions logged with telemetry in `ai_execution_logs` table

See [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) · [`docs/security/RBAC_POLICY_V4.md`](docs/security/RBAC_POLICY_V4.md)

---

## 📁 Project Structure

```
Gayatri/
├── app/                        # PySide6 desktop shell
│   ├── bridge/                 # QWebChannel facade bridge
│   ├── portals/                # Portal controllers (student, teacher, parent, admin)
│   └── main.py                 # Desktop entry point
├── central_platform/           # FastAPI server + all platform logic
│   ├── ai/                     # AI gateway, model router, adapters, policy engine
│   ├── api/routes/             # 21 REST routers (students, courses, RAG, sessions…)
│   ├── auth/                   # JWT auth, RBAC, dependency injection
│   ├── tutor/orchestrator.py   # 16-step GenericTutorOrchestrator ← primary engine
│   ├── rag/                    # Scoped RAG, hybrid vector+BM25 retrieval
│   ├── courses/                # Course domain model, versioning, enrollment
│   ├── learning/               # Mastery engine, canonical state, DAG graph
│   ├── assessment/             # EvaluatorRegistry, rubrics, anti-leakage
│   ├── teacher/                # 5-tier instruction cascade
│   ├── sync/                   # Bi-directional sync + conflict resolution
│   ├── fees/                   # Fee accounts, invoicing
│   ├── payments/               # Razorpay, UPI, mock adapters
│   ├── i18n/                   # 8-language internationalisation
│   ├── recovery/               # FailureRecoveryManager, resilience contracts
│   └── db.py                   # PlatformDatabase (SQLite WAL, 50 tables, 8 migrations)
├── core/                       # Legacy tutor engine + provider base
│   ├── providers/              # LLM provider base classes and registry
│   └── orchestrator.py         # Original single-subject tutor (legacy)
├── local_runtime/              # Offline-first engine (cache, sync outbox, session)
├── migrations/                 # SQL DDL 001–008 + down-scripts
├── data/                       # Bundled NCERT curriculum and RAG seed data
├── scripts/                    # Ops scripts: migrate, seed, inspect, benchmark, verify
├── hooks/                      # PyInstaller hooks for llama_cpp
├── packaging/                  # Windows installer (PyInstaller + Inno Setup)
├── training/                   # SLM prompt contracts, fine-tuning scripts, and alignment data
├── docs/                       # Architecture, security, and operations docs
├── tests/                      # 1,252 tests across 43 verification phases
├── model_manifest.json         # Local SLM registry (Qwen2.5-0.5B, GGUF Q4_K_M)
├── setup.bat                   # One-click Windows setup & launch
├── run.bat                     # Silent desktop launch
└── pyproject.toml              # Project config, pytest settings, linting
```

---

## 📚 Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, 16-step orchestrator, data flows |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | 50 database tables, relations, dataclasses |
| [SECURITY_MODEL.md](docs/SECURITY_MODEL.md) | Security invariants, threat model |
| [RBAC Policy](docs/security/RBAC_POLICY_V4.md) | Role permissions, audit findings |
| [LEARNING_GRAPH.md](docs/LEARNING_GRAPH.md) | Mastery model, Ebbinghaus decay, prerequisites |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production and institution deployment guide |
| [PRIVACY_CONTRACT.md](docs/PRIVACY_CONTRACT.md) | Student data privacy guarantees |
| [TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md) | Test architecture and coverage strategy |
| [API Contract](docs/architecture/api-contract.md) | OpenAPI route specification |
| [Deployment Guide](docs/operations/deployment-guide.md) | Institution onboarding and curriculum setup |

---

## 🤝 Contributing

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Ensure **all tests pass**: `python -m pytest -q -m "not gui"`
4. Open a Pull Request to `main` — CI must be green

See [CONTRIBUTING.md](CONTRIBUTING.md) for code style, tool guidelines, and cooperative cancellation requirements.

---

## 🏢 Built at DBERT

Gayatri AI was designed, built, and shipped by the engineering squad at **[DBERT](https://dbert.online/startups/portfolio/gayatri-ai)** — India's AI Venture Studio based in Delhi.

**DBERT** (Digital Blinc Education Research & Technology) incubates AI startups for equity, ships enterprise SaaS, and trains engineers through a production-grade fellowship program. Gayatri is one of the ventures built under the **DBERT Internship Program, Batch Aug–Oct 2026**.

- 🌐 [dbert.online](https://dbert.online)
- 📂 [Startup Portfolio](https://dbert.online/startups/portfolio)
- 🎓 [DBERT Fellowship Program](https://dbert.online/learners/fellowship)
- 💼 [Internship Portal](https://internship.dbert.online)

---

## 📄 License

MIT License — see [LICENSE.md](LICENSE.md) for details.

---

<div align="center">
<sub>
Built with ❤️ for Indian students · Classes 9–12 · Curriculum-free · Privacy-first<br/>
<a href="https://dbert.online/startups/portfolio/gayatri-ai">DBERT Internship Program · Batch Aug–Oct 2026</a>
</sub>
</div>
