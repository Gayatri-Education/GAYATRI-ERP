# Phase 15 Plan: Repository Cleanup and Documentation Consolidation

**Phase:** PHASE-15  
**Status:** IN_PLANNING  
**Date:** 2026-10-15  
**Author:** AI Pair Programmer  

---

## 1. Goal & Scope
Phase 15 performs disciplined repository hygiene, documentation consolidation, and README verification strictly following Section 4 (PHASE-15) of `GAYATRI_ERP_DEVELOPMENT_GUIDE.md`. The objective is to ensure that the repository presents an authoritative, accurate, and maintainable structure without removing any runtime, test, ops, or canonical documentation dependencies.

---

## 2. Invariants & Standards
1. **Safety First (Zero Destructive Deletions without Verification)**:
   - Every file evaluated must be formally classified in `docs/qa/FILE_CLEANUP_REPORT.md`:
     `KEEP_RUNTIME`, `KEEP_TEST`, `KEEP_OPS`, `KEEP_DOCS`, `CONSOLIDATE`, `REMOVE_CANDIDATE`, `UNKNOWN_BLOCKED`.
   - Preserve all tests, dependency manifests, migrations, operations runbooks, recovery assets, and licenses.
2. **Authoritative `README.md` Accuracy**:
   - Correct repository clone URL to `https://github.com/Gayatri-Education/GAYATRI-ERP.git` and clone folder `Gayatri-ERP`.
   - Correct migration execution commands (fix `python -m python` syntax error).
   - Update test counts and architectural claims to reflect current verified reality (>1,760 tests, verified SQLite WAL persistence).
   - Clearly delineate verified core features vs experimental integrations.
   - Prohibit exposure of production secrets or unsafe production defaults.
3. **Documentation Consolidation**:
   - Ensure all internal cross-references and documentation links resolve to existing markdown files on disk.
   - Synchronize root trackers and issue registers with `docs/qa/`.

---

## 3. Implementation Plan
1. **Audit & Classify Repository Files**:
   - Review candidate files and update `docs/qa/FILE_CLEANUP_REPORT.md` and `GAYATRI_ERP_FILE_CLEANUP_REPORT.md`.
2. **Remediate `README.md` and `GAYATRI_ERP_README.md`**:
   - Fix clone URL, directory name, CLI migration commands, and verified metrics.
3. **Author Phase 15 Verification Suite (`tests/test_qa_phase15_repo_cleanup_and_docs.py`)**:
   - Verify `README.md` references valid paths.
   - Verify CLI commands in `README.md` are syntactically valid.
   - Verify absence of production credentials in documentation.
4. **Execute targeted Phase 15 suite & full non-GUI regression suite (`python -m pytest -q -m "not gui"`)**.
5. **Certify Phase 15 in `docs/qa/phase-logs/PHASE_15_LOG.md`, update trackers, and commit**.
