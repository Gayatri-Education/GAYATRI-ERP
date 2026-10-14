# Phase 11 Plan — Full End-to-End QA & Adversarial Validation

**Objective:** Perform comprehensive black-box and white-box validation across all critical user journeys, system failure modes, adversarial security attack vectors, data corruption scenarios, multi-threaded concurrency, and long-session continuity.

---

## 1. Scope & Targeted Scenarios

1. **Scenario 11.1: Complete End-to-End Learner Journey:**
   - Account provisioning -> Course discovery & enrollment -> Active tutoring session -> Concept inquiry -> NCERT RAG retrieval -> Model response generation -> Socratic answer evaluation -> Pedagogical adaptation & SLR update -> Database persistence.

2. **Scenario 11.2: Model Outage & Execution Provenance:**
   - Absent/unreachable model weights -> System detects unavailability -> Graceful degradation to safe pedagogical message -> Provenance recorded as `FAILED` or `DEGRADED_FALLBACK` (never falsely claiming `REAL_MODEL`).

3. **Scenario 11.3: RAG Failure & Anti-Fabrication:**
   - Vector database unavailable -> Degraded fallback to syllabus context -> Strict assertion that no fake citations, URLs, or non-existent passages are hallucinated.

4. **Scenario 11.4: Adversarial Security Attack Suite:**
   - Prompt injection (jailbreak / DAN / system prompt override).
   - IDOR (student accessing another student's session or record).
   - Multi-tenant organization breakout.
   - Path traversal (`../` directory escapes).
   - Dangerous file extension uploads (`.exe`, `.sh`).
   - SQL injection attempts in parameter inputs.
   - Cross-Site Scripting (XSS) payload sanitization.

5. **Scenario 11.5: Data Corruption Recovery:**
   - Malformed / truncated session records.
   - Corrupt JSON model responses repaired via self-healing regex/brace extractor.

6. **Scenario 11.6: Multi-Worker & Multi-Student Concurrency:**
   - Concurrent worker threads executing student evaluations and database writes simultaneously.
   - Assert zero race conditions, foreign key corruptions, or cross-student state bleed.

7. **Scenario 11.7: Multi-Turn Long Session Continuity:**
   - 10+ turn conversational progression in a single session.
   - Context window maintenance and persistence across turns.

---

## 2. Dev Loop Steps

1. **Plan Authoring:** Commit `docs/qa_agent/plans/PHASE_11_PLAN.md`.
2. **Focused Tests:**
   - Author `tests/test_qa_phase11_e2e_adversarial.py`.
   - Run focused suite (`pytest tests/test_qa_phase11_e2e_adversarial.py tests/test_phase24_e2e_journeys_real.py tests/test_phase22_security_hardening_master.py -v`).
3. **Full Regression:**
   - Run `pytest -q` across the entire codebase.
4. **Decisions & Reporting:**
   - Log `DEC-011` in `docs/qa_agent/decisions/DECISION_LOG.md`.
   - Write `docs/qa_agent/reports/PHASE_11_REPORT.md`.
   - Update `docs/qa_agent/MASTER_PROGRESS.md`.
