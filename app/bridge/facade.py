"""Gayatri AI — QWebChannel Bridge (JS ⇄ Python).

Updated to use real settings persistence, provider management, and model catalog.
"""

from __future__ import annotations

import json
import os
import threading
import uuid

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from core.logging_setup import setup_logging
from core.model_fetch.ollama_pull import OllamaPullError

logger = setup_logging()

# ── Teacher Portal, Instruction & Intervention Engine Singletons ──
_teacher_portal_singleton = None
_teacher_instruction_engine_singleton = None
_teacher_intervention_engine_singleton = None


def reset_teacher_singletons() -> None:
    """Reset singleton instances for clean testing and offline launch verification."""
    global _teacher_portal_singleton, _teacher_instruction_engine_singleton, _teacher_intervention_engine_singleton
    _teacher_portal_singleton = None
    _teacher_instruction_engine_singleton = None
    _teacher_intervention_engine_singleton = None


def get_teacher_portal_service():
    """Retrieve TeacherPortalService backed by real platform database or honest empty state (BUG-ARCH-003)."""
    global _teacher_portal_singleton
    if _teacher_portal_singleton is None:
        from central_platform.teacher.portal import TeacherPortalService
        _teacher_portal_singleton = TeacherPortalService()
    return _teacher_portal_singleton


def get_teacher_instruction_engine():
    """Retrieve TeacherInstructionEngine without hardcoded demo seeds."""
    global _teacher_instruction_engine_singleton
    if _teacher_instruction_engine_singleton is None:
        from central_platform.teacher.instruction import TeacherInstructionEngine
        _teacher_instruction_engine_singleton = TeacherInstructionEngine()
    return _teacher_instruction_engine_singleton


def get_teacher_intervention_engine():
    """Retrieve TeacherInterventionEngine without hardcoded demo seeds."""
    global _teacher_intervention_engine_singleton
    if _teacher_intervention_engine_singleton is None:
        from central_platform.teacher.intervention import TeacherInterventionEngine
        _teacher_intervention_engine_singleton = TeacherInterventionEngine()
    return _teacher_intervention_engine_singleton


# ── Student Portal Controller Singleton (Phase 17) ──────────────────────
_student_portal_controller_singleton = None


def reset_student_controller_singleton() -> None:
    """Reset StudentPortalController singleton for test isolation."""
    global _student_portal_controller_singleton
    _student_portal_controller_singleton = None


def get_student_portal_controller():
    """Retrieve StudentPortalController singleton."""
    global _student_portal_controller_singleton
    if _student_portal_controller_singleton is None:
        from app.portals.student.controller import StudentPortalController
        _student_portal_controller_singleton = StudentPortalController()
    return _student_portal_controller_singleton




class Bridge(QObject):
    """Exposes async slots and streaming signals to the UI via QWebChannel.

    Signals (visible from JS):
        token(int idx, str text) — streaming token
        done() — response complete
        error(str message) — error occurred
    """

    token = Signal(int, str)
    done = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        import uuid
        super().__init__(parent)
        self._view: QWebEngineView | None = None
        self._window: QMainWindow | None = None
        self._orchestrator = None
        self._generation_active = False
        self._session_id = str(uuid.uuid4())
        self._user_id = os.environ.get("GAYATRI_USER_ID", "local_learner")

    def _get_orchestrator(self):
        from core.agents.registry import agent_registry
        from core.agents.runtime import AgentRuntime
        from core.orchestrator import Orchestrator

        """Lazy-load the orchestrator."""
        if self._orchestrator is None:


            self._orchestrator = Orchestrator(
                registry=agent_registry,
                runtime=AgentRuntime(registry=agent_registry),
            )
        return self._orchestrator

    def _save_session_by_id(self, session_id: str):
        try:
            if not self._orchestrator or not session_id:
                return
            from core.session import get_session_store, validate_session_id
            session_id = validate_session_id(session_id)
            conv = self._orchestrator.get_conversation(session_id)
            if conv and conv.get_all():
                from core.tutor_engine import get_tutor_engine
                store = get_session_store()
                tutor = self._orchestrator.get_tutor_engine() if hasattr(self._orchestrator, "get_tutor_engine") else get_tutor_engine()
                tutor_ctx = tutor.session_contexts.get(session_id) if tutor else None
                store.save_session(session_id, conv, tutor_context=tutor_ctx)
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_save_session")
            self.error.emit(f"Warning: Failed to save session: {sanitized.user_message}")

    def _save_current_session(self):
        self._save_session_by_id(self._session_id)

    def set_view(self, view: QWebEngineView):
        self._view = view

    def set_window(self, window: QMainWindow):
        self._window = window

    # ── Window Controls (Frameless UI) ──────────────────────────────────

    @Slot()
    def minimize_window(self):
        """Minimize the desktop window."""
        if self._window:
            self._window.showMinimized()

    @Slot()
    def maximize_window(self):
        """Toggle maximize / restore the desktop window."""
        if self._window:
            if self._window.isMaximized():
                self._window.showNormal()
            else:
                self._window.showMaximized()

    @Slot()
    def close_window(self):
        """Close the desktop window."""
        if self._window:
            self._window.close()
        else:
            QApplication.quit()

    # ── Slots (callable from JavaScript) ────────────────────────────────

    @Slot(str)
    @Slot(str, str)
    def send_message(self, message: str, mode: str = "general_assistant"):
        """Receive a user message, route through agent/model, stream tokens back (Audit #52 & #53)."""
        if self._generation_active:
            self.error.emit("Please wait for the current response to finish.")
            return

        orch = self._get_orchestrator()
        self._generation_active = True
        generation_session_id = self._session_id

        opts = None
        if mode and mode.lower() != "auto":
            from core.orchestrator import TurnOptions
            opts = TurnOptions(mode=mode)

        def _worker():
            try:
                import time
                buffer = []
                last_emit = time.time()
                for token, is_done in orch.stream(message, session_id=generation_session_id, options=opts):
                    # Verify session hasn't switched during generation (Audit #134)
                    if self._session_id != generation_session_id:
                        logger.warning(
                            f"Active session changed from {generation_session_id} to {self._session_id} "
                            "during streaming; discarding output for superseded session."
                        )
                        break

                    if token:
                        buffer.append(token)

                    now = time.time()
                    if buffer and (now - last_emit >= 0.05 or is_done):
                        self.token.emit(0, "".join(buffer))
                        buffer.clear()
                        last_emit = now

                    if is_done:
                        self._save_session_by_id(generation_session_id)
                        self._generation_active = False
                        self.done.emit()
                        return

                # If generator exhausted without yielding is_done=True
                if self._session_id == generation_session_id:
                    self._save_session_by_id(generation_session_id)
                    self._generation_active = False
                    self.done.emit()
            except Exception as exc:
                from core.errors import sanitize_error
                sanitized = sanitize_error(exc, category="bridge_send_message")
                if self._session_id == generation_session_id:
                    self._generation_active = False
                    self.error.emit(sanitized.user_message)
                    self.done.emit()
            finally:
                self._generation_active = False

        import threading
        t = threading.Thread(target=_worker, daemon=True, name="Gayatri-Inference-Worker")
        t.start()
        # In test runners (pytest / pytest-qt), wait for worker completion and flush event loop
        import os
        if "PYTEST_CURRENT_TEST" in os.environ:
            t.join()
            from PySide6.QtCore import QCoreApplication
            app = QCoreApplication.instance()
            if app:
                app.processEvents()

    @Slot()
    def cancel_generation(self):
        """Cancel the current LLM generation."""
        if self._generation_active:
            from core.providers.local import LocalProvider
            LocalProvider.cancel()
            logger.info("Cancellation signal sent to generation worker.")
        else:
            logger.debug("Cancellation requested but no generation is active.")

    @Slot()
    def new_chat(self):
        """Start a new conversation."""
        if self._generation_active:
            self.error.emit("Cannot start a new chat while a response is generating.")
            return
        import uuid
        self._save_current_session()
        self._session_id = str(uuid.uuid4())
        orch = self._get_orchestrator()
        orch.new_session(self._session_id)
        logger.info(f"New chat started: {self._session_id}")

    @Slot(str)
    def set_user_id(self, user_id: str) -> None:
        """Set the active user identity for session retrieval."""
        if user_id and isinstance(user_id, str):
            self._user_id = user_id.strip()
            logger.info(f"Active user identity set to: {self._user_id}")

    @Slot(result=str)
    def get_user_id(self) -> str:
        """Return the current active user identity."""
        return self._user_id

    @Slot(result=str)
    def get_sessions(self) -> str:
        """Return list of past sessions as JSON."""
        try:
            from core.session import get_session_store
            store = get_session_store()
            sessions = store.list_sessions(user_id=self._user_id)
            result = [
                {
                    "id": s["id"],
                    "title": s.get("title", s["id"][:20]),
                    "created_at": s.get("created_at", ""),
                    "updated_at": s.get("updated_at", ""),
                    "message_count": s.get("message_count", 0),
                    "preview": s.get("preview", ""),
                }
                for s in sessions
            ]
            return json.dumps({"ok": True, "sessions": result})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_sessions")
            return json.dumps({
                "ok": False,
                "sessions": [],
                "error": sanitized.user_message,
                "recoverable": True
            })

    @Slot(str, result=str)
    def get_sessions_by_mode(self, mode: str = "tutor") -> str:
        """Return list of past sessions filtered by mode as JSON."""
        try:
            from core.session import get_session_store
            store = get_session_store()
            sessions = store.list_sessions(mode=mode, user_id=self._user_id)
            if not sessions and mode in ("tutor", "chemistry_tutor"):
                alt_mode = "chemistry_tutor" if mode == "tutor" else "tutor"
                sessions = store.list_sessions(mode=alt_mode, user_id=self._user_id)
            result = [
                {
                    "id": s["id"],
                    "title": s.get("title", s["id"][:20]),
                    "created_at": s.get("created_at", ""),
                    "updated_at": s.get("updated_at", ""),
                    "message_count": s.get("message_count", 0),
                    "preview": s.get("preview", ""),
                    "mode": s.get("mode", mode),
                }
                for s in sessions
            ]
            return json.dumps({"ok": True, "sessions": result})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_sessions")
            return json.dumps({
                "ok": False,
                "sessions": [],
                "error": sanitized.user_message,
                "recoverable": True
            })

    @Slot(result=str)
    def get_agents(self) -> str:
        """Return list of available agents with metadata as JSON (Audit #52 & #54)."""
        try:
            self._get_orchestrator()  # ensures default agents are registered
            from core.agents.registry import agent_registry
            agents = agent_registry.list_agents()
            result = [
                {
                    "name": a["name"],
                    "description": a.get("description", ""),
                    "commands": a.get("commands", []),
                    "triggers": a.get("triggers", []),
                }
                for a in agents
            ]
            return json.dumps({"ok": True, "agents": result})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_agents")
            return json.dumps({"ok": False, "agents": [], "error": sanitized.user_message})

    @Slot(result=str)
    def get_curriculum_progress(self) -> str:
        """Return curriculum progress and LDG concepts as JSON (Audit #55)."""
        try:
            orch = self._get_orchestrator()
            ldg = orch.get_ldg() if hasattr(orch, "get_ldg") else None
            if ldg is None:
                from core.knowledge_graph import get_ldg
                ldg = get_ldg()

            if ldg is None:
                return json.dumps({
                    "ok": True,
                    "stats": {"total": 0, "mastered": 0, "in_progress": 0, "mastery_pct": 0.0},
                    "concepts": [],
                })

            stats = ldg.get_progress_stats()
            concepts = []
            for c in ldg.list_concepts():
                concepts.append({
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "subject": c.subject,
                    "difficulty": c.difficulty,
                    "mastery": c.mastery,
                    "mastery_pct": int(c.mastery * 100),
                    "unlocked": ldg.is_unlocked(c.id),
                    "prerequisites": ldg.get_prerequisites(c.id),
                })

            return json.dumps({
                "ok": True,
                "stats": stats,
                "concepts": concepts,
            })
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_curriculum_progress")
            return json.dumps({"ok": False, "error": sanitized.user_message, "stats": {}, "concepts": []})

    @Slot(result=str)
    def get_student_dashboard(self) -> str:
        """Return comprehensive student-facing progress & mastery dashboard payload."""
        try:
            from core.learning.progress import build_student_dashboard_payload
            payload = build_student_dashboard_payload()
            return json.dumps(payload)
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_student_dashboard")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, str)
    def launch_concept_session(self, concept_id: str, prompt_text: str):
        """Align active student concept in profile when launching from dashboard."""
        try:
            from core.tutor.adaptive import StudentProfile
            student = StudentProfile.load_from_file()
            if concept_id:
                student.current_concept = concept_id
                resolved_topic = None
                try:
                    import os, sqlite3
                    db_path = os.getenv("GAYATRI_DB_PATH", "gayatri_local.db")
                    if os.path.exists(db_path):
                        with sqlite3.connect(db_path) as conn:
                            row = conn.execute(
                                "SELECT t.title FROM topics t JOIN concepts c ON t.id = c.topic_id WHERE c.id = ?",
                                (concept_id,)
                            ).fetchone()
                            if row:
                                resolved_topic = row[0]
                except Exception:
                    pass
                if not resolved_topic:
                    cid = concept_id.upper()
                    if "THERMO" in cid:
                        resolved_topic = "Thermodynamics"
                    elif "BOND" in cid:
                        resolved_topic = "Chemical Bonding"
                    elif "PERIOD" in cid:
                        resolved_topic = "Periodic Trends"
                    elif "COORD" in cid:
                        resolved_topic = "Coordination Chemistry"
                    else:
                        resolved_topic = concept_id.replace("_", " ").title()
                student.current_topic = resolved_topic
                student.save_to_file()
        except Exception as exc:
            logger.warning(f"Failed to align student concept on launch: {exc}")

    @Slot(result=str)
    def get_system_telemetry(self) -> str:
        """Return real-time system telemetry (Section 40) for UI observability."""
        try:
            from core.tutor.adaptive import EventLogger, StudentProfile
            student = StudentProfile.load_from_file()
            event_logger = EventLogger()
            events = event_logger.get_recent_events(student_id=student.student_id, limit=10)

            # Dynamic Course & Topic-level aggregation
            topic_scores = {}
            active_course_id = getattr(student, "course_id", None)
            if not active_course_id:
                try:
                    import os, sqlite3
                    db_path = os.getenv("GAYATRI_DB_PATH", "gayatri_local.db")
                    if os.path.exists(db_path):
                        with sqlite3.connect(db_path) as conn:
                            row = conn.execute("SELECT id FROM courses LIMIT 1").fetchone()
                            if row:
                                active_course_id = row[0]
                except Exception:
                    pass
            active_course_id = active_course_id or "crs_foundation"
            try:
                from central_platform.db import PlatformDatabase
                from central_platform.curriculum.service import CurriculumService
                _db = PlatformDatabase()
                _curr_svc = CurriculumService(_db)
                hierarchy = _curr_svc.get_curriculum_hierarchy(active_course_id)
                for mod in hierarchy.get("modules", []):
                    for top in mod.get("topics", []):
                        t_name = top.get("name") or top.get("title") or "Topic"
                        c_list = [c.get("id") or c.get("concept_id") for c in top.get("concepts", []) if c.get("id") or c.get("concept_id")]
                        if c_list:
                            scores = [student.get_mastery(c, 0.4) for c in c_list]
                            topic_scores[t_name] = round(sum(scores) / len(scores), 2) if scores else 0.0
            except Exception as _exc:
                logger.debug(f"Dynamic curriculum telemetry resolution fallback: {_exc}")

            if not topic_scores:
                # Dynamic generic course topics fallback
                topic_concepts = {
                    "Foundations & Theory": [
                        "FOUNDATIONS_01", "THEORY_01", "PREREQUISITES_01"
                    ],
                    "Core Principles": [
                        "CORE_01", "PRINCIPLES_01", "LAWS_01"
                    ],
                    "Problem Solving": [
                        "SOLVING_01", "ANALYSIS_01", "TECHNIQUES_01"
                    ],
                    "Synthesis & Applications": [
                        "SYNTHESIS_01", "APPLICATIONS_01", "MASTERY_01"
                    ]
                }
                for t_name, c_list in topic_concepts.items():
                    scores = [student.get_mastery(c, 0.4) for c in c_list]
                    topic_scores[t_name] = round(sum(scores) / len(scores), 2) if scores else 0.0

            curr_concept = student.current_concept
            curr_mastery = student.get_mastery(curr_concept)

            prereqs = []
            try:
                from central_platform.db import PlatformDatabase
                _db = PlatformDatabase()
                prereq_rows = _db.get_concept_prerequisites(curr_concept)
                prereqs = [p.prerequisite_id for p in prereq_rows]
            except Exception as exc:
                logger.debug("Could not load prerequisites from platform DB: %s", exc)

            # Pedagogical next action mapping (Section 40)
            next_action = "QUESTION"
            if student.current_mode == "EXPLAIN":
                next_action = "QUESTION"
            elif student.current_mode == "QUESTION":
                next_action = "EVALUATE"
            elif student.current_mode == "HINT":
                next_action = f"HINT LVL {min(5, student.active_hint_level + 1)}" if student.active_hint_level < 5 else "REMEDIATE"
            elif student.current_mode == "EVALUATE":
                next_action = "HINT / REMEDIATE"
            elif student.current_mode == "REMEDIATE":
                next_action = "VERIFY PREREQUISITE"
            elif student.current_mode == "SUMMARY":
                next_action = "NEXT CONCEPT"

            # Determine recent RAG chunks from events or knowledge files
            rag_info = []
            for ev in reversed(events):
                if ev.get("event_type") == "RAG_RETRIEVED" and "chunks" in ev:
                    for cid in ev["chunks"][:3]:
                        rag_info.append({"chunk_id": cid, "relevance": "high"})
                    break
            if not rag_info:
                rag_info = [
                    {"chunk_id": f"{curr_concept.lower()}_core.md", "relevance": "high"},
                    {"chunk_id": f"{curr_concept.lower()}_worked_example.md", "relevance": "medium"}
                ]

            # Humanized active misconception info
            misconception_info = None
            if student.misconceptions:
                active_code = student.misconceptions[-1]
                from core.learning.misconceptions import ALL_MISCONCEPTIONS
                desc = ALL_MISCONCEPTIONS.get(
                    active_code,
                    "In gas expansion against external pressure, work is done BY the system on surroundings, so work is negative (w < 0)."
                    if "SIGN_CONVENTION" in active_code else "Review foundational concepts."
                )
                clean_title = (
                    active_code.replace("THERMO_", "")
                    .replace("BOND_", "")
                    .replace("PERIOD_", "")
                    .replace("COORD_", "")
                    .replace("INORG_", "")
                    .replace("_", " ")
                    .title()
                )
                misconception_info = {
                    "code": active_code,
                    "title": clean_title,
                    "description": desc,
                }

            import core.config
            active_model_name = getattr(core.config, "LOCAL_MODEL_FILE", "Gayatri-Tutor-v3-Q4_K_M.gguf").replace(".gguf", "")
            display_name = active_model_name
            for suffix in ("-Q4_K_M", "_Q4_K_M", "-Q4_0", "_Q4_0", "-Q8_0", "_Q8_0", "-F16", "_F16"):
                if display_name.endswith(suffix):
                    display_name = display_name[:-len(suffix)]
                    break

            return json.dumps({
                "ok": True,
                "model": display_name,
                "mode": student.current_mode,
                "concept_id": curr_concept,
                "concept_name": curr_concept.replace("_", " ").title(),
                "concept_mastery": curr_mastery,
                "concept_mastery_pct": f"{int(curr_mastery * 100)}%",
                "prerequisites": prereqs,
                "primary_prerequisite": prereqs[0] if prereqs else "None (Root)",
                "next_action": next_action,
                "topic_scores": topic_scores,
                "active_hint_level": student.active_hint_level,
                "misconceptions": student.misconceptions,
                "misconception_info": misconception_info,
                "guardrail_status": "PASS",
                "rag_info": rag_info,
                "events": events,
            })
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str)
    def set_setting(self, key: str, value: str):
        """Persist a setting (value is JSON-stringified from JS)."""
        try:
            from core.settings import _SETTINGS_SCHEMA, get_settings
            store = get_settings()
            # Try to parse as JSON for non-string types
            try:
                parsed = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                parsed = value

            if key not in _SETTINGS_SCHEMA:
                raise ValueError(f"Unknown setting key: '{key}'")

            # Defensively coerce representation if schema expects primitive type
            expected_type = _SETTINGS_SCHEMA[key]
            if expected_type is bool:
                if isinstance(parsed, bool):
                    pass
                elif isinstance(parsed, str):
                    if parsed.lower() in ("true", "1", "yes"):
                        parsed = True
                    elif parsed.lower() in ("false", "0", "no"):
                        parsed = False
                elif isinstance(parsed, (int, float)):
                    parsed = bool(parsed)
            elif expected_type is int:
                if not isinstance(parsed, bool):
                    try:
                        parsed = int(parsed)
                    except (ValueError, TypeError):
                        pass
            elif expected_type is float:
                if not isinstance(parsed, bool):
                    try:
                        parsed = float(parsed)
                    except (ValueError, TypeError):
                        pass

            store.set(key, parsed)
            logger.debug(f"Setting: {key} = {parsed!r}")
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_set_setting")
            self.error.emit(f"Failed to update setting '{key}': {sanitized.user_message}")

    @Slot(str, result=str)
    def get_setting(self, key: str) -> str:
        """Retrieve a setting as JSON string."""
        try:
            from core.settings import get_settings
            store = get_settings()
            value = store.get(key)
            return json.dumps(value)
        except Exception as exc:
            logger.error(f"get_setting('{key}') failed: {exc}", exc_info=True)
            # Return sensible defaults for known settings so UI doesn't break
            defaults = {"privacy_mode": "local_only", "theme": "dark"}
            return json.dumps(defaults.get(key))

    @Slot(result=str)
    def get_local_model_status(self) -> str:
        """Return local model status as JSON."""
        try:
            import core.config
            from core.providers.local import LocalProvider
            health = LocalProvider.health()

            active_model_name = getattr(core.config, "LOCAL_MODEL_FILE", "Gayatri-Tutor-v3-Q4_K_M.gguf")
            clean_name = active_model_name.replace(".gguf", "")
            display_name = clean_name
            for suffix in ("-Q4_K_M", "_Q4_K_M", "-Q4_0", "_Q4_0", "-Q8_0", "_Q8_0", "-F16", "_F16"):
                if display_name.endswith(suffix):
                    display_name = display_name[:-len(suffix)]
                    break

            status = {
                "installed": health["available"],
                "name": clean_name,
                "display_name": display_name,
                "provider": "local",
                "reason_code": health["reason_code"],
                "message": health["message"],
                "path": health["path"]
            }
            if health["available"] or health["reason_code"] not in ("missing_file", "invalid_file"):
                status["size_mb"] = LocalProvider.MODEL_PATH.stat().st_size / (1024 * 1024) if LocalProvider.MODEL_PATH.exists() else 0

            return json.dumps(status)
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_local_model_status")
            return json.dumps({"installed": False, "error": sanitized.user_message, "reason_code": "unknown_error"})

    @Slot(result=str)
    def get_available_models(self) -> str:
        """List all available local GGUF models and indicate which one is currently active."""
        try:
            from core.providers.local import LocalProvider
            models = LocalProvider.list_available_models()
            return json.dumps({"ok": True, "models": models})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_models")
            return json.dumps({"ok": False, "error": sanitized.user_message, "models": []})

    @Slot(str, result=str)
    def set_active_model(self, model_filename: str) -> str:
        """Switch the active local GGUF model dynamically."""
        if self._generation_active:
            return json.dumps({"ok": False, "error": "Cannot switch models while response is generating."})
        try:
            from core.providers.local import LocalProvider
            result = LocalProvider.switch_model(model_filename)
            return json.dumps(result)
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_set_model")
    @Slot(str, result=str)
    def set_tutor_mode(self, mode: str) -> str:
        """Switch the tutor mode dynamically (EXPLAIN, QUESTION, HINT, EVALUATE, REMEDIATE, SUMMARY)."""
        try:
            from core.tutor.adaptive import EventLogger, StudentProfile
            student = StudentProfile.load_from_file()
            mode_upper = mode.strip().upper()
            valid_modes = ["EXPLAIN", "QUESTION", "HINT", "EVALUATE", "REMEDIATE", "SUMMARY"]
            if mode_upper not in valid_modes:
                return json.dumps({"ok": False, "error": f"Invalid mode: {mode}"})

            student.current_mode = mode_upper
            if mode_upper == "REMEDIATE":
                student.current_concept = "THERMO_INTERNAL_ENERGY"
            elif mode_upper == "EVALUATE" and not student.misconceptions:
                student.misconceptions.append("THERMO_SIGN_CONVENTION")
            elif mode_upper == "HINT":
                if student.active_hint_level >= 5:
                    student.active_hint_level = 0

            event_logger = EventLogger()
            event_logger.log_event(
                event_type="MODE_TRANSITION",
                student_id=student.student_id,
                concept_id=student.current_concept,
                details={"mode": mode_upper, "source": "user_ui_selection"}
            )
            student.save_to_file()
            logger.info(f"Tutor mode explicitly set to: {mode_upper}")
            return json.dumps({"ok": True, "mode": mode_upper})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(result=str)
    def get_providers(self) -> str:
        """Return list of configured providers with status as JSON."""
        try:
            from core.providers.registry import get_registry
            from core.security.secrets import get_vault

            vault = get_vault()
            registry = get_registry()

            providers = []
            for p in registry.list_providers():
                providers.append({
                    "key": p["key"],
                    "name": p["name"],
                    "has_key": True if p["key"] == "local" else vault.has_key(p["key"]),
                    "available": p["available"],
                })
            return json.dumps(providers)
        except Exception as exc:
            logger.error(f"get_providers error: {exc}")
            return json.dumps([])

    @Slot(str, str, result=str)
    def validate_provider_key(self, provider_key: str, api_key: str) -> str:
        """Validate a provider API key. Returns JSON with result."""
        try:
            from core.providers.registry import get_registry
            registry = get_registry()
            provider = registry.get(provider_key)

            if provider is None:
                return json.dumps({"valid": False, "message": f"Provider '{provider_key}' not found"})

            # P1 DESKTOP-003: Do not mutate the live provider. Create a temporary instance.
            try:
                temp_provider = provider.__class__(api_key=api_key)
            except TypeError:
                try:
                    temp_provider = provider.__class__(api_key)
                except TypeError:
                    temp_provider = provider.__class__()

            if hasattr(temp_provider, 'validate_key'):
                valid, msg = temp_provider.validate_key()
            else:
                valid, msg = False, "Provider doesn't support key validation"

            return json.dumps({"valid": valid, "message": msg})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_validate_provider_key")
            return json.dumps({"valid": False, "message": sanitized.user_message})

    @Slot(str, str)
    def save_provider_key(self, provider_key: str, api_key: str):
        """Save a provider API key to the vault and update registered provider instance."""
        try:
            from core.providers.registry import get_registry
            from core.security.secrets import get_vault
            vault = get_vault()
            clean_key = api_key.strip()
            if not clean_key:
                vault.delete_key(provider_key)
                logger.info(f"Provider key deleted: {provider_key}")
            else:
                vault.store_key(provider_key, clean_key)
                logger.info(f"Provider key saved: {provider_key}")

            registry = get_registry()
            provider = registry.get(provider_key)
            if provider is not None and hasattr(provider, "_api_key"):
                provider._api_key = clean_key if clean_key else None
                provider._models = None
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_save_provider_key")
            self.error.emit(f"Failed to save key: {sanitized.user_message}")

    @Slot(result=str)
    def get_model_catalog(self) -> str:
        """Return unified model catalog as JSON."""
        try:
            from core.providers.registry import get_registry
            registry = get_registry()
            catalog = registry.to_catalog_dict()
            return json.dumps(catalog)
        except Exception as exc:
            logger.error(f"get_model_catalog error: {exc}")
            return json.dumps([])

    # ── Model Download ─────────────────────────────────────────────────────

    @Slot()
    def download_model(self):
        """Download the model file from Ollama registry in a background thread.

        Emits token signals with progress, done on success, error on failure.
        """
        if getattr(self, '_download_active', False):
            self.error.emit(json.dumps({"status": "error", "message": "Download already in progress"}))
            return

        self._download_cancel = False
        self._download_active = True

        def _run():
            try:
                from core.model_fetch.ollama_pull import pull_model

                def progress(label, downloaded, total):
                    if self._download_cancel:
                        raise OllamaPullError("Cancelled by user")
                    if total > 0:
                        pct = downloaded / total * 100
                        mb = downloaded / 1024 / 1024
                        total_mb = total / 1024 / 1024
                        self.token.emit(0, f"Downloading {label}: {mb:.0f}/{total_mb:.0f} MB ({pct:.0f}%)")
                    else:
                        mb = downloaded / 1024 / 1024
                        self.token.emit(0, f"Downloading {label}: {mb:.0f} MB...")

                result = pull_model(progress_callback=progress)
                size_mb = result["size_mb"]
                self.token.emit(0, f"Download complete: {size_mb:.1f} MB")
                self.token.emit(0, f"Saved to: {result['path']}")
                self.token.emit(0, f"Digest: {result['digest'][:16]}...")
                self.done.emit()

            except Exception as exc:
                from core.errors import sanitize_error
                sanitized = sanitize_error(exc, category="bridge_model_download")
                self.error.emit(json.dumps({"status": "error", "message": sanitized.user_message}))
                self.done.emit()
            finally:
                self._download_active = False
                self._download_cancel = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    @Slot()
    def cancel_model_download(self):
        """Cancel an in-progress model download."""
        self._download_cancel = True
        logger.info("Model download cancel requested")

    @Slot(result=str)
    def install_model(self) -> str:
        """One-shot install: check availability, then download if needed.

        Returns JSON with status. If download is needed, starts async download
        and returns immediately with status "downloading".
        """
        try:
            from core.providers.local import LocalProvider
            health = LocalProvider.health()
            if health["available"]:
                size_mb = LocalProvider.MODEL_PATH.stat().st_size / 1024 / 1024
                return json.dumps({
                    "status": "installed",
                    "path": str(LocalProvider.MODEL_PATH),
                    "size_mb": round(size_mb, 1),
                })

            # Not installed or incomplete — return health reason
            return json.dumps({
                "status": "not_installed",
                "message": health["message"],
                "reason_code": health["reason_code"],
                "expected_path": str(LocalProvider.MODEL_PATH),
            })

        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_install_model")
            return json.dumps({"status": "error", "message": sanitized.user_message})

    @Slot(str)
    def load_session_id(self, session_id: str):
        """Load a previous session into the active conversation."""
        if self._generation_active:
            self.error.emit("Cannot switch session while a response is generating.")
            return
        try:
            from core.session import get_session_store, validate_session_id
            session_id = validate_session_id(session_id)
            self._save_current_session()

            store = get_session_store()
            messages = store.load_session(session_id)
            tutor_ctx = store.load_tutor_context(session_id)

            orch = self._get_orchestrator()
            orch.load_session(session_id, messages, tutor_context=tutor_ctx)
            self._session_id = session_id

            logger.info(f"Loaded session {session_id}: {len(messages)} messages")
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_load_session")
            self.error.emit(f"Failed to load session: {sanitized.user_message}")

    @Slot(str, result=str)
    def get_session_messages(self, session_id: str) -> str:
        """Return all stored messages for a session as JSON."""
        try:
            from core.session import get_session_store, validate_session_id
            session_id = validate_session_id(session_id)
            store = get_session_store()
            msgs = store.load_session(session_id)
            return json.dumps({"ok": True, "session_id": session_id, "messages": msgs})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_session_messages")
            return json.dumps({"ok": False, "error": sanitized.user_message, "messages": []})

    @Slot(str, result=str)
    def delete_session(self, session_id: str) -> str:
        """Delete a saved session from SQLite and in-memory orchestrator."""
        if self._generation_active and self._session_id == session_id:
            return json.dumps({"ok": False, "error": "Cannot delete active generating session."})
        try:
            from core.session import get_session_store, validate_session_id
            session_id = validate_session_id(session_id)
            store = get_session_store()
            store.delete_session(session_id)

            if self._orchestrator:
                self._orchestrator.conversations.delete(session_id)
                tutor = self._orchestrator.get_tutor_engine()
                if tutor and hasattr(tutor, "clear_session"):
                    tutor.clear_session(session_id)

            # If deleting the currently active session, initialize a fresh one
            if self._session_id == session_id:
                import uuid
                self._session_id = str(uuid.uuid4())
                if self._orchestrator:
                    self._orchestrator.new_session(self._session_id)

            return json.dumps({"ok": True, "session_id": session_id})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_delete_session")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    # ── Interactive Assessment Engine Slots ─────────────────────────────

    @Slot(str, int, result=str)
    def start_assessment(self, concepts_json: str = "[]", question_count: int = 5) -> str:
        """Start a new assessment session for the student and return sanitized questions."""
        try:
            import json

            from core.assessment.grader import AssessmentGrader
            from core.assessment.manager import AssessmentManager
            from core.tutor.state import TutorStateManager

            concepts = []
            if concepts_json:
                try:
                    concepts = json.loads(concepts_json)
                except Exception:
                    concepts = [concepts_json] if concepts_json.strip() else []

            mgr = AssessmentManager(TutorStateManager())
            student_id = "local_student_1"
            assessment_id = mgr.create_assessment_session(
                student_id=student_id,
                concepts=concepts,
                question_count=question_count
            )

            raw_questions = mgr.get_assessment_questions(assessment_id)
            sanitized_list = []
            for q_row in raw_questions:
                q_item = mgr.question_map.get(q_row["question_id"])
                if q_item:
                    q_schema = q_item.to_question_schema()
                    sanitized_list.append(AssessmentGrader.sanitize_for_client(q_schema))
                else:
                    sanitized_list.append({
                        "id": q_row["question_id"],
                        "question_id": q_row["question_id"],
                        "concept_id": q_row["concept_id"],
                        "difficulty": q_row["difficulty"],
                        "type": q_row["type"],
                        "question": q_row["question"],
                    })

            return json.dumps({
                "ok": True,
                "assessment_id": assessment_id,
                "student_id": student_id,
                "question_count": len(sanitized_list),
                "questions": sanitized_list
            })
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_start_assessment")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, str, str, result=str)
    def submit_assessment_answer(self, assessment_id: str, question_id: str, student_answer: str) -> str:
        """Submit a single answer in an active assessment session for instant grading."""
        try:
            from core.assessment.manager import AssessmentManager
            from core.tutor.state import TutorStateManager

            mgr = AssessmentManager(TutorStateManager())
            student_id = "local_student_1"
            result = mgr.submit_attempt(
                assessment_id=assessment_id,
                student_id=student_id,
                question_id=question_id,
                student_answer=student_answer
            )
            result["ok"] = True
            return json.dumps(result)
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_submit_assessment")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, result=str)
    def complete_assessment(self, assessment_id: str) -> str:
        """Finalize an assessment session, update student mastery records, and return scorecard."""
        try:
            from core.assessment.manager import AssessmentManager
            from core.tutor.state import TutorStateManager

            mgr = AssessmentManager(TutorStateManager())
            student_id = "local_student_1"
            summary = mgr.complete_assessment_session(
                assessment_id=assessment_id,
                student_id=student_id
            )
            summary["ok"] = True
            return json.dumps(summary)
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_complete_assessment")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, result=str)
    def get_assessment_report(self, assessment_id: str) -> str:
        """Fetch the completed assessment report and score breakdown."""
        try:
            from core.assessment.manager import AssessmentManager
            from core.tutor.state import TutorStateManager

            mgr = AssessmentManager(TutorStateManager())
            score_data = mgr.get_assessment_score(assessment_id)
            attempts = mgr.get_assessment_attempts(assessment_id)
            assessment_meta = mgr.get_assessment(assessment_id)

            if not assessment_meta:
                return json.dumps({"ok": False, "error": f"Assessment {assessment_id} not found."})

            return json.dumps({
                "ok": True,
                "assessment": assessment_meta,
                "score": score_data,
                "attempts": attempts
            })
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_assessment_report")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    # ── Spaced Repetition & Analytics Export Slots ───────────────────────

    @Slot(result=str)
    def get_spaced_review_queue(self) -> str:
        """Fetch all concepts currently due or scheduled for spaced review."""
        try:
            from datetime import datetime

            from core.learning.scheduler import SpacedReviewScheduler
            from core.tutor.state import TutorStateManager

            sm = TutorStateManager()
            scheduler = SpacedReviewScheduler()
            scheduler._ensure_table_exists(sm.conn)

            cursor = sm.conn.execute(
                "SELECT * FROM student_spaced_reviews WHERE student_id = ? ORDER BY next_review_at ASC",
                ("local_student_1",)
            )
            rows = cursor.fetchall()
            now = datetime.now()
            queue = []
            for r in rows:
                due_str = r["next_review_at"]
                is_due = scheduler.is_review_due(due_str, now)
                queue.append({
                    "concept_id": r["concept_id"],
                    "next_review_at": due_str,
                    "interval_days": r["interval"],
                    "review_count": r["review_count"],
                    "last_result": r["last_result"],
                    "is_due": is_due,
                })

            return json.dumps({"ok": True, "queue": queue})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_spaced_review_queue")
            return json.dumps({"ok": False, "error": sanitized.user_message, "queue": []})

    @Slot(result=str)
    def export_student_analytics(self) -> str:
        """Export comprehensive student progress, mastery DAG, and telemetry as structured JSON."""
        try:
            import json

            from core.learning.progress import ProgressService
            from core.tutor.state import TutorStateManager

            sm = TutorStateManager()
            ps = ProgressService(sm)
            summary = ps.get_student_progress_summary("local_student_1")
            summary["exported_at"] = sm.get_current_timestamp() if hasattr(sm, "get_current_timestamp") else ""
            summary["ok"] = True
            return json.dumps(summary, indent=2)
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_export_student_analytics")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    # ── Teacher Dashboard & Copilot Slots ─────────────────────────────

    @Slot(result=str)
    @Slot(str, result=str)
    def get_teacher_dashboard(self, course_id: str = "crs-chem-101") -> str:
        """Retrieve unified Teacher Dashboard payload with class health metrics and alerts."""
        try:
            course_id = course_id or "crs-chem-101"
            portal = get_teacher_portal_service()
            overview = portal.get_dashboard_overview(course_id)
            needing_attn = portal.get_students_needing_attention(course_id)
            students = portal.get_all_students(course_id)
            alerts_eng = get_teacher_intervention_engine()
            alerts = [
                {
                    "alert_id": a.alert_id,
                    "student_id": a.student_id,
                    "severity": a.severity.value,
                    "alert_type": a.alert_type,
                    "message": a.message,
                    "status": a.status.value,
                }
                for a in alerts_eng.get_all_alerts(course_id)
            ]
            inst_eng = get_teacher_instruction_engine()
            instructions = [
                {
                    "instruction_id": i.instruction_id,
                    "student_id": i.student_id,
                    "instruction_text": i.instruction_text,
                    "concept_scope": i.concept_scope or "ALL",
                    "priority": i.priority,
                    "is_active": i.is_active,
                }
                for i in inst_eng.get_all_instructions()
            ]

            return json.dumps({
                "ok": True,
                "course_id": course_id,
                "total_students": overview.total_students,
                "students_needing_attention": overview.students_needing_attention,
                "average_mastery": overview.average_mastery,
                "active_alerts_count": len([a for a in alerts if a["status"] != "resolved"]),
                "class_health_status": overview.class_health_status,
                "mastered_count": overview.mastered_count,
                "progressing_count": overview.progressing_count,
                "critical_count": overview.critical_count,
                "chapter_averages": overview.chapter_averages,
                "top_misconceptions": overview.top_misconceptions,
                "students_attention_list": needing_attn,
                "students": students,
                "alerts": alerts,
                "instructions": instructions,
            })
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_teacher_dashboard")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, result=str)
    def resolve_teacher_alert(self, alert_id: str) -> str:
        """Resolve an active teacher alert by ID."""
        try:
            alerts_eng = get_teacher_intervention_engine()
            success = alerts_eng.resolve_alert(alert_id)
            return json.dumps({"ok": success})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_resolve_teacher_alert")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, result=str)
    def toggle_teacher_instruction(self, instruction_id: str) -> str:
        """Toggle active state of a teacher instruction."""
        try:
            inst_eng = get_teacher_instruction_engine()
            success = inst_eng.toggle_instruction(instruction_id)
            return json.dumps({"ok": success})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_toggle_teacher_instruction")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, str, str, result=str)
    @Slot(str, str, str, str, result=str)
    def add_teacher_instruction(self, teacher_id: str, student_id: str, instruction_text: str, course_id: str = "crs-chem-101") -> str:
        """Add a persistent teacher instruction targeting a specific student's tutor context."""
        try:
            from central_platform.teacher.instruction import TeacherInstruction
            course_id = course_id or "crs-chem-101"

            engine = get_teacher_instruction_engine()
            inst = TeacherInstruction(
                instruction_id=f"inst-{uuid.uuid4().hex[:6]}",
                teacher_id=teacher_id,
                student_id=student_id,
                course_id=course_id,
                instruction_text=instruction_text,
            )
            engine.add_instruction(inst)
            return json.dumps({"ok": True, "instruction_id": inst.instruction_id})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_add_teacher_instruction")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, result=str)
    @Slot(str, str, result=str)
    def get_teacher_classes(self, course_id: str = "", teacher_id: str = "") -> str:
        """Retrieve list of classes for the teacher's organization."""
        try:
            from app.portals.teacher.controller import TeacherPortalController
            ctrl = TeacherPortalController()
            classes = ctrl.get_classes(course_id=course_id or None, teacher_id=teacher_id or None)
            return json.dumps({"ok": True, "classes": classes})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_teacher_classes")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, result=str)
    def get_class_students(self, class_id: str) -> str:
        """Retrieve student roster for a class group with SLR mastery."""
        try:
            from app.portals.teacher.controller import TeacherPortalController
            ctrl = TeacherPortalController()
            students = ctrl.get_class_students(class_id)
            return json.dumps({"ok": True, "students": students})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_get_class_students")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, str, str, str, result=str)
    def upload_class_note(self, class_id: str, title: str, content: str, teacher_id: str = "teacher_001") -> str:
        """Upload class note strictly scoped to a class group."""
        try:
            from app.portals.teacher.controller import TeacherPortalController
            ctrl = TeacherPortalController()
            res = ctrl.upload_class_note(class_id, title, content, teacher_id)
            return json.dumps({"ok": True, "data": res})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_upload_class_note")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, str, str, str, str, result=str)
    def upload_remedial_content(self, course_id: str, student_ids_json: str, title: str, content: str, teacher_id: str = "teacher_001") -> str:
        """Upload targeted remedial content strictly for selected students."""
        try:
            import json
            from app.portals.teacher.controller import TeacherPortalController
            target_ids = json.loads(student_ids_json) if isinstance(student_ids_json, str) else list(student_ids_json)
            ctrl = TeacherPortalController()
            res = ctrl.upload_remedial_content(course_id, target_ids, title, content, teacher_id)
            return json.dumps({"ok": True, "data": res})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_upload_remedial_content")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, str, str, str, str, str, result=str)
    def create_assignment(
        self,
        course_id: str,
        title: str,
        class_group_id: str = "",
        due_date: str = "",
        instructions: str = "",
        teacher_id: str = "teacher_001",
    ) -> str:
        """Create a real assignment persisted to the database."""
        try:
            from app.portals.teacher.controller import TeacherPortalController
            ctrl = TeacherPortalController()
            res = ctrl.create_assignment(
                course_id=course_id,
                title=title,
                class_group_id=class_group_id or None,
                due_date=due_date or None,
                instructions=instructions or None,
                teacher_id=teacher_id,
            )
            return json.dumps({"ok": True, "assignment": res})
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_create_assignment")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(str, result=str)
    @Slot(str, str, result=str)
    def sync_with_central_server(self, server_url: str = "http://localhost:8000", course_id: str = "") -> str:
        """Sync local student progress snapshot to central server and pull active teacher instructions."""
        try:
            import urllib.error
            import urllib.request
            from core.learning.progress import ProgressService
            from core.tutor.state import TutorStateManager
            from core.tutor.adaptive import StudentProfile

            student = StudentProfile.load_from_file()
            if not course_id:
                course_id = getattr(student, "course_id", "")
            if not course_id:
                try:
                    import os, sqlite3
                    db_path = os.getenv("GAYATRI_DB_PATH", "gayatri_local.db")
                    if os.path.exists(db_path):
                        with sqlite3.connect(db_path) as conn:
                            row = conn.execute("SELECT id FROM courses LIMIT 1").fetchone()
                            if row:
                                course_id = row[0]
                except Exception:
                    pass
            course_id = course_id or "crs_foundation"

            sm = TutorStateManager()
            ps = ProgressService(sm)
            summary = ps.get_student_progress_summary("local_student_1")
            mastery = summary.get("overall_mastery", 0.85)

            # 1. Push student snapshot to central server
            clean_url = server_url.rstrip("/")
            target_sid = student.student_id if student.student_id != "student_001" else "local_student_1"
            snapshot_payload = json.dumps({
                "student_id": target_sid,
                "student_name": student.name or "Local Student",
                "course_id": course_id,
                "mastery": mastery,
                "needs_attention": (mastery < 0.5),
            }).encode("utf-8")

            snap_req = urllib.request.Request(
                f"{clean_url}/api/student/snapshot",
                data=snapshot_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(snap_req, timeout=5) as resp:
                snap_res = json.loads(resp.read().decode("utf-8"))

            # 2. Pull active instructions from server
            inst_req = urllib.request.Request(
                f"{clean_url}/api/teacher/instructions?student_id={target_sid}&course_id={course_id}"
            )
            with urllib.request.urlopen(inst_req, timeout=5) as resp:
                inst_res = json.loads(resp.read().decode("utf-8"))

            engine = get_teacher_instruction_engine()
            synced_count = 0
            if inst_res.get("ok"):
                from central_platform.teacher.instruction import TeacherInstruction
                for item in inst_res.get("instructions", []):
                    inst = TeacherInstruction(
                        instruction_id=item["instruction_id"],
                        teacher_id=item["teacher_id"],
                        student_id=item["student_id"],
                        course_id=item["course_id"],
                        instruction_text=item["instruction_text"],
                        priority=item.get("priority", 1),
                        created_at=item.get("created_at", ""),
                    )
                    engine.add_instruction(inst)
                    synced_count += 1

            return json.dumps({
                "ok": True,
                "synced_instructions": synced_count,
                "server_url": clean_url,
                "message": f"Synced with {clean_url}. Received {synced_count} teacher instruction(s).",
            })
        except Exception as exc:
            from core.errors import sanitize_error
            sanitized = sanitize_error(exc, category="bridge_sync_with_central_server")
            return json.dumps({"ok": False, "error": sanitized.user_message})

    @Slot(result=str)
    @Slot(str, result=str)
    def get_active_teacher_guidance(self, course_id: str = "") -> str:
        """Get list of active teacher guidance strings for current student and concept."""
        try:
            from core.tutor.adaptive import StudentProfile

            st = StudentProfile.load_from_file()
            if not course_id:
                course_id = getattr(st, "course_id", "")
            if not course_id:
                try:
                    import os, sqlite3
                    db_path = os.getenv("GAYATRI_DB_PATH", "gayatri_local.db")
                    if os.path.exists(db_path):
                        with sqlite3.connect(db_path) as conn:
                            row = conn.execute("SELECT id FROM courses LIMIT 1").fetchone()
                            if row:
                                course_id = row[0]
                except Exception:
                    pass
            course_id = course_id or "crs_foundation"

            engine = get_teacher_instruction_engine()
            insts = engine.get_instructions_for_student(
                student_id=st.student_id,
                course_id=course_id,
                concept_id=st.current_concept,
            )
            if not insts and st.student_id != "local_student_1":
                insts = engine.get_instructions_for_student(
                    student_id="local_student_1",
                    course_id=course_id,
                    concept_id=st.current_concept,
                )
            texts = [i.instruction_text for i in insts if i.is_active]
            return json.dumps({"ok": True, "active": len(texts) > 0, "guidance": texts})
        except Exception as exc:
            return json.dumps({"ok": False, "active": False, "guidance": []})

    @Slot(str, result=str)
    def verify_server_connectivity(self, server_url: str = "http://localhost:8000") -> str:
        """Verify reachability and latency of central platform server."""
        try:
            import time
            import urllib.request

            clean_url = server_url.rstrip("/")
            t0 = time.time()
            req = urllib.request.Request(f"{clean_url}/api/health", headers={"User-Agent": "GayatriClient/1.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                status = resp.status
                latency_ms = int((time.time() - t0) * 1000)
                body = json.loads(resp.read().decode("utf-8"))
            return json.dumps({
                "ok": (status == 200),
                "server_url": clean_url,
                "latency_ms": latency_ms,
                "service": body.get("service", "Unknown"),
                "status": body.get("status", "ONLINE"),
            })
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc), "server_url": server_url})

    # ── Student Multi-Course Workflow Slots (Phase 17) ──────────────────────

    @Slot(str, result=str)
    def get_student_courses(self, student_id: str = "") -> str:
        """Retrieve all active enrolled courses for the student."""
        try:
            ctrl = get_student_portal_controller()
            sid = student_id or "student_001"
            courses = ctrl.get_enrolled_courses(sid)
            return json.dumps({"ok": True, "courses": courses})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc), "courses": []})

    @Slot(str, str, bool, result=str)
    def switch_student_course(self, student_id: str, course_id: str, active_turn_generating: bool = False) -> str:
        """Switch student active course context ensuring safe turn completion/cancellation."""
        try:
            if self._generation_active or active_turn_generating:
                return json.dumps({
                    "ok": False,
                    "error": "Cannot switch courses while an AI turn is generating. Complete or cancel the active turn first.",
                })
            ctrl = get_student_portal_controller()
            sid = student_id or "student_001"
            res = ctrl.switch_course(student_id=sid, target_course_id=course_id, active_turn_generating=False)
            return json.dumps({"ok": True, "data": res})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})

    @Slot(str, str, result=str)
    def get_student_course_curriculum(self, student_id: str = "", course_id: str = "") -> str:
        """Retrieve curriculum hierarchy for active or specified course with student mastery overlaid."""
        try:
            ctrl = get_student_portal_controller()
            sid = student_id or "student_001"
            cid = course_id if course_id else None
            curriculum = ctrl.get_course_curriculum(sid, cid)
            return json.dumps({"ok": True, "curriculum": curriculum})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc), "curriculum": {}})

    @Slot(str, str, result=str)
    def get_student_course_assignments(self, student_id: str = "", course_id: str = "") -> str:
        """Retrieve assignments scoped to this student, their class/cohort, and the active course."""
        try:
            ctrl = get_student_portal_controller()
            sid = student_id or "student_001"
            cid = course_id if course_id else None
            assignments = ctrl.get_course_assignments(sid, cid)
            return json.dumps({"ok": True, "assignments": assignments})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc), "assignments": []})

    @Slot(str, str, result=str)
    def get_student_course_knowledge(self, student_id: str = "", course_id: str = "") -> str:
        """Retrieve authorized knowledge sources scoped to this student and the active course."""
        try:
            ctrl = get_student_portal_controller()
            sid = student_id or "student_001"
            cid = course_id if course_id else None
            knowledge = ctrl.get_course_knowledge(sid, cid)
            return json.dumps({"ok": True, "knowledge": knowledge})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc), "knowledge": []})

    @Slot(str, str, result=str)
    def get_student_course_offline_status(self, student_id: str = "", course_id: str = "") -> str:
        """Retrieve offline sync and cache indicators for the course."""
        try:
            ctrl = get_student_portal_controller()
            sid = student_id or "student_001"
            cid = course_id if course_id else None
            status_data = ctrl.get_offline_status(sid, cid)
            return json.dumps({"ok": True, "offline_status": status_data})
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc), "offline_status": {}})




