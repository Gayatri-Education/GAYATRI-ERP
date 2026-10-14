# Phase 04 Implementation Plan — Session, Database & Persistence Integrity

## 1. Context and Objective
Resolve QA-010 and QA-011:
1. Ensure session writes are completely durable across normal shutdown, abnormal termination, and process restarts. Guarantee that asynchronous queue writes are flushed before process exit and provide explicit synchronous persistence methods (`save_session_sync`).
2. Remove hard-coded reliance on `local_user_1` identity in `core/session.py`, `core/conversation.py`, and `app/bridge/facade.py`. Introduce dynamic user identity abstraction while maintaining backwards compatibility with legacy local database records.
3. Validate session isolation across concurrent users and sessions.

## 2. Dependencies and Affected Modules
- Session Management: `core/session.py`
- Conversation State: `core/conversation.py`
- UI Bridge: `app/bridge/facade.py`
- Database helpers: `core/db.py`
- Tests: `tests/test_qa_phase04_session_persistence.py`

## 3. Scope of Tasks
1. **04.1 Map Persistence Ownership:**
   - Document authoritative stores for sessions, messages, tutor context, learning events, and profiles.
2. **04.2 Async Writer Durability & Flush Guarantees (QA-010):**
   - In `core/session.py`:
     - Guarantee `shutdown()` calls `flush()` to write all queued tasks before terminating the writer thread.
     - Add `atexit.register(self.shutdown)` to guarantee flush on interpreter shutdown.
     - Add `save_session_sync()` for immediate durability when needed (e.g. at lesson milestones or logout).
     - Add context manager support (`__enter__` and `__exit__`).
3. **04.3 User Identity Abstraction (QA-011):**
   - Replace hard-coded string `local_user_1` with configurable `DEFAULT_LOCAL_USER_ID = "local_learner"`, supporting `GAYATRI_USER_ID` environment variable.
   - In `core/session.py`, support querying by specific user ID, with backward compatibility falling back to `local_user_1` when legacy records exist.
   - In `app/bridge/facade.py`, introduce dynamic `_user_id` attribute, slot `set_user_id()`, and `get_user_id()`.
4. **04.4 Multi-Session and Multi-User Concurrency & Isolation:**
   - Verify concurrent saves across multiple sessions/users do not leak messages or tutor context.
5. **04.5 Focused Tests & Regression Run:**
   - Execute focused test suite `tests/test_qa_phase04_session_persistence.py` and run full repository regression suite.

## 4. Regression Risks & Mitigations
- *Risk:* Legacy local sessions recorded under `local_user_1` may become invisible to UI.
  - *Mitigation:* `list_sessions()` will seamlessly include legacy `local_user_1` records when querying in default local mode.
