<div align="center">

<img src="gai3.png" alt="Gayatri AI" width="120"/>

# Gayatri AI Platform

**Adaptive AI Tutor for CBSE/NCERT Classes 11 & 12**

[![CI](https://github.com/Gayatri-Education/Gayatri/actions/workflows/ci.yml/badge.svg)](https://github.com/Gayatri-Education/Gayatri/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE.md)
[![Version](https://img.shields.io/badge/version-3.0.1-orange.svg)](VERSION)

</div>

---

Gayatri is a **local-first, privacy-preserving AI tutoring platform** for Indian high school students. It runs entirely on-device using small language models (SLMs) — no cloud required, no data leaves the device. When connectivity is available, it syncs with a central platform to enable teacher oversight, analytics, and curriculum management.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🧠 **Adaptive Tutoring** | 16-step pedagogical turn lifecycle — explains, evaluates, adapts per student |
| 📚 **Multi-Subject** | Physics, Chemistry, Mathematics, Biology — NCERT/CBSE aligned |
| 🔒 **Local-First & Private** | Runs on-device SLMs (Ollama). Student data never leaves the device |
| 🏫 **Multi-Tenant** | Full tenant isolation — multiple schools, orgs, and roles on one platform |
| 👨‍🏫 **Teacher Copilot** | 5-tier instruction cascade (Org → Course → Class → Student → Session) |
| 📊 **Learning Analytics** | Mastery tracking, spaced review scheduler, learning event telemetry |
| 🔄 **Offline Sync** | Bi-directional sync with conflict resolution, works offline-first |
| 🌐 **Multi-Language** | 8-language i18n support across all portals |
| 💸 **Fee Management** | Razorpay/UPI payment gateway with HMAC signature verification |
| 🖥️ **Desktop App** | PySide6 + WebEngine unified UI shell |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Desktop App (PySide6)               │
│   Student Portal │ Teacher Portal │ Parent Portal    │
│                  │ Admin Portal   │ Fee Admin        │
└────────────────────────┬────────────────────────────┘
                         │ QWebChannel Bridge
┌────────────────────────▼────────────────────────────┐
│              Central Platform (FastAPI)              │
│  /api/v1 — 16 modular routers, 182+ routes          │
│  Auth · Students · Teachers · Courses · Sessions    │
│  RAG · Assessment · Analytics · Notifications · Sync │
└───────┬─────────────────────────┬───────────────────┘
        │                         │
┌───────▼──────────┐   ┌──────────▼──────────┐
│  SQLite (Local)  │   │  Local SLM (Ollama)  │
│  WAL-mode, 50    │   │  Llama 3.2 / Gemma3  │
│  tables, 8 migs  │   │  Phi-4 / Mistral     │
└──────────────────┘   └─────────────────────┘
```

**Core subsystems:**
- **[`central_platform/`](central_platform/)** — FastAPI server, 16 routers, auth, db, sync
- **[`app/`](app/)** — PySide6 desktop shell, portal controllers, WebEngine bridge
- **[`courses/`](courses/)** — Curriculum domain model, concept graphs, RAG adapters
- **[`core/`](core/)** — Providers, orchestrator, assessments, offline runtime
- **[`migrations/`](migrations/)** — 8 SQL DDL migration scripts (001–008) with down-scripts

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com/) installed and running locally
- Git

### 1. Clone & Install

```bash
git clone https://github.com/Gayatri-Education/Gayatri.git
cd Gayatri

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the repo root:

```env
# Database
GAYATRI_DB_PATH=gayatri_local.db
GAYATRI_ENV=production

# AI Provider (local by default)
GAYATRI_DEFAULT_PROVIDER=local
GAYATRI_LOCAL_MODEL=llama3.2:3b

# Optional cloud fallback
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Security
JWT_SECRET_KEY=<your-32-byte-secret-change-in-production>
GAYATRI_ENCRYPTION_KEY=
```

### 3. Initialize Database

```bash
python -c "from central_platform.db import PlatformDatabase; db = PlatformDatabase(); print('Ready. Tables:', len(db.get_table_names()))"
```

This automatically runs all 8 migrations (001–008).

### 4. Start the Platform

```bash
# REST API server (port 8000)
python -m uvicorn central_platform.api.server:app --host 0.0.0.0 --port 8000

# Desktop application
python app/main.py

# Or use the Windows launcher
run.bat
```

**API endpoints once running:**
- 📖 **Swagger UI**: `http://localhost:8000/docs`
- 📋 **ReDoc**: `http://localhost:8000/redoc`
- ✅ **Liveness**: `GET /healthz`
- ✅ **Readiness**: `GET /readyz`

---

## 🧪 Running Tests

The platform has **1,252 passing tests** enforced by CI. All tests must pass before any merge.

```bash
# Full test suite (~90 seconds)
python -m pytest -q -m "not gui"

# Specific areas
python -m pytest tests/test_phase01_auth_identity_remediation.py -v   # Auth & security
python -m pytest tests/test_phase22_security_privacy_isolation_audit.py -v  # Privacy
python -m pytest tests/test_phase25_performance_capacity_verification.py -v  # Performance
python -m pytest tests/test_phase41_deployment_validation.py -v  # Deployment
python -m pytest tests/test_phase43_production_readiness_gate.py -v  # Release gate
```

---

## 🔐 Security

- **Zero trust auth**: JWT with JTI revocation. All API routes require a valid bearer token
- **Tenant isolation**: Cross-org requests rejected at both API and database query boundaries
- **Answer leakage prevention**: AI responses scanned for exact solution strings before delivery
- **Prompt injection defense**: Input sanitization at the QWebChannel bridge and API ingress
- **Local-only by default**: Student conversation data never transmitted to cloud providers
- **HMAC payment verification**: Razorpay webhook signatures verified with constant-time comparison

See [`docs/SECURITY_MODEL.md`](docs/SECURITY_MODEL.md) and [`docs/security/RBAC_POLICY_V4.md`](docs/security/RBAC_POLICY_V4.md).

---

## 📦 Local Model Setup

Gayatri uses [Ollama](https://ollama.com/) to run SLMs locally:

```bash
# Install a model (choose based on your hardware)
ollama pull llama3.2:3b      # Recommended — 2GB, fast
ollama pull gemma3:4b        # 2.5GB, excellent reasoning
ollama pull phi4-mini        # 2.5GB, strong STEM
ollama pull mistral:7b       # 4.5GB, best quality
```

Or use the bundled installer script:
```bash
python install_llama.py
```

The platform auto-selects the best available model from [`model_manifest.json`](model_manifest.json).

---

## 📁 Project Structure

```
Gayatri/
├── app/                    # PySide6 desktop shell + portal controllers
├── central_platform/       # FastAPI server + 16 API routers
│   ├── api/routes/         # Students, teachers, courses, sessions, RAG, ...
│   ├── auth/               # JWT auth, RBAC, dependency injection
│   ├── db.py               # PlatformDatabase (SQLite, WAL, 8 migrations)
│   └── deployment/         # Deployment validator
├── core/                   # AI providers, orchestrator, assessment engine
│   ├── providers/          # Ollama, OpenAI, Anthropic, Gemini adapters
│   └── orchestrator.py     # 16-step tutor turn lifecycle
├── courses/                # Curriculum domain model, RAG, adapters
├── migrations/             # SQL DDL 001–008 + down-scripts
├── packaging/              # Windows installer (PyInstaller + Inno Setup)
├── docs/                   # Architecture, security, deployment docs
├── tests/                  # 1,252 tests across 43 phases
├── model_manifest.json     # Supported SLM registry
├── pyproject.toml          # Project config, pytest settings
├── requirements.txt        # Runtime dependencies
└── requirements.lock       # Pinned dependency lockfile
```

---

## 📚 Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, 16-step orchestrator, data flows |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | 50 database tables, relations, dataclasses |
| [SECURITY_MODEL.md](docs/SECURITY_MODEL.md) | Security invariants, threat model |
| [RBAC Policy](docs/security/RBAC_POLICY_V4.md) | Role permissions and audit findings |
| [LEARNING_GRAPH.md](docs/LEARNING_GRAPH.md) | Mastery model, Ebbinghaus decay, prerequisites |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment guide |
| [PRIVACY_CONTRACT.md](docs/PRIVACY_CONTRACT.md) | Data privacy guarantees |
| [TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md) | Test architecture and coverage strategy |
| [API Contract](docs/architecture/api-contract.md) | OpenAPI route specification |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Ensure **all 1,252 tests pass**: `pytest -q -m "not gui"`
4. Open a Pull Request — CI must be green before review

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE.md](LICENSE.md) for details.

---

<div align="center">
<sub>Built with ❤️ for Indian students | CBSE/NCERT Class 11 & 12 | Privacy-first AI Education</sub>
</div>
