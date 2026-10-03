# Gayatri AI — Open Release Blockers

**Target Release Date:** 7 October 2026  
**Current Audit Status:** 8 Blockers Open  

---

### P0-01: Production Login Contains Mock / Integration Fallback
- **Severity:** P0 (Release Blocker)
- **Component:** `central_platform/api/routes/auth.py`
- **Symptom:** When a user is not found in the database, `login()` falls back to `MOCK_USERS` or dynamically constructs a synthetic student identity (`usr-{username}`) and issues a valid JWT.
- **Requirement:** In production mode, authentication must be strictly DB-authoritative. Unknown users must receive HTTP 401 Unauthorized.
- **Resolution Phase:** Phase 2 (Authentication & Identity Remediation)

---

### P0-02: Model Manifest Checksum Must Match Shipped GGUF Model
- **Severity:** P0 (Release Blocker)
- **Component:** `model_manifest.json`, `core/providers/local.py`
- **Symptom:** The `checksum` field in `model_manifest.json` is set to `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty string SHA-256) and is never validated against actual model files at startup.
- **Requirement:** Manifest must store the exact SHA-256 of the production model artifact. Runtime must verify the model file checksum before loading and reject corrupted or missing artifacts.
- **Resolution Phase:** Phase 5 (Model Artifact & Manifest Integrity)

---

### P0-03: Production Must Never Fall Back to Mock AI
- **Severity:** P0 (Release Blocker)
- **Component:** `central_platform/ai/adapters.py`, `central_platform/ai/gateway.py`
- **Symptom:** `MockAIAdapter` generates deterministic pedagogical responses. Although `is_production_mode()` checks exist in `MockAIAdapter`, the full execution path across `AIGatewayService`, `ModelRouter`, and fallback chains must guarantee that production failures never synthesize fake answers or award false mastery.
- **Requirement:** Real model failure must trigger controlled 503 Service Unavailable / Degraded response without mutating student mastery.
- **Resolution Phase:** Phase 4 (AI Gateway & Model Routing Hardening)

---

### P0-04: Production Model Identity Is Inconsistent Across Codebase
- **Severity:** P0 (Release Blocker)
- **Component:** `core/config.py`, `model_manifest.json`, `central_platform/ai/gateway.py`, `scripts/check_model.py`
- **Symptom:** `model_manifest.json` advertises `gayatri-chem-qwen2.5-0.5b-v4` (Qwen 0.5B). `gateway.py` lists `Gayatri-Tutor-v3-Q4_K_M` and `Qwen2.5-3B`. `scripts/check_model.py` checks for `Qwen2.5-3B-Instruct`. `core/providers/local.py` uses Gemma 2 turn formatting.
- **Requirement:** Align all components to one canonical production model definition with consistent identity, context length, chat template, and quantization profile.
- **Resolution Phase:** Phase 1 & Phase 4

---

### P0-05: Production CORS Is Too Permissive
- **Severity:** P0 (Release Blocker)
- **Component:** `central_platform/api/app.py`
- **Symptom:** `CORSMiddleware` is configured with `allow_origins=["*"]`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.
- **Requirement:** In production mode, CORS must restrict origins to explicitly configured hostnames.
- **Resolution Phase:** Phase 1 (Production Configuration Hardening)

---

### P0-06: Password Reset Must Use Verified One-Time Tokens
- **Severity:** P0 (Release Blocker)
- **Component:** `central_platform/api/routes/auth.py`
- **Symptom:** If `req.token` is omitted in `/password-reset`, the endpoint resets the password directly via `db.set_user_password(user.id, req.new_password)` for any provided email.
- **Requirement:** Password reset in production must strictly require a valid, non-expired, single-use signed/hashed reset token. Email-only password resets must be disallowed.
- **Resolution Phase:** Phase 2 (Authentication & Identity Remediation)

---

### P0-07: Packaging References Must Match Repository Contents
- **Severity:** P0 (Release Blocker)
- **Component:** `packaging/gayatri_demo.spec`
- **Symptom:** The PyInstaller spec bundles `training/prompts`, which is no longer part of the public repository, causing packaging builds to fail or depend on internal artifacts.
- **Requirement:** Update packaging specifications to include only active production assets, runtime prompts, and libraries.
- **Resolution Phase:** Phase 13 (Packaging & Clean-Machine Release)

---

### P0-08: Production Runtime Validation Must Not Rely on Synthetic Fixtures
- **Severity:** P0 (Release Blocker)
- **Component:** `scripts/validate_production_runtime.py`, test harnesses
- **Symptom:** Validation scripts spin up synthetic in-memory fixtures instead of testing against the packaged distribution and realistic persistent state.
- **Requirement:** Separate synthetic automated test validation from real packaged acceptance validation.
- **Resolution Phase:** Phase 16 (Real Product Acceptance Test)
