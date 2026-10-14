#!/usr/bin/env bash
# Gayatri AI — Linux / POSIX Environment Setup & Migration Bootstrap (Phase 11)
set -euo pipefail

echo "=================================================================="
echo "  GAYATRI AI — LINUX ENVIRONMENT SETUP & DATABASE BOOTSTRAP"
echo "=================================================================="

# 1. Verify Python availability
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python 3.12+ is required but neither python3 nor python was found."
    exit 1
fi

PY_VER=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[*] Detected Python: $PY_VER ($PYTHON_CMD)"

# 2. Install pinned dependencies from lock file (GQA-014)
if [ -f "requirements.lock" ]; then
    echo "[*] Installing dependencies from pinned requirements.lock..."
    $PYTHON_CMD -m pip install --upgrade pip --quiet
    $PYTHON_CMD -m pip install -r requirements.lock --quiet
elif [ -f "requirements.txt" ]; then
    echo "[WARN] requirements.lock not found; falling back to requirements.txt..."
    $PYTHON_CMD -m pip install -r requirements.txt --quiet
fi

# 3. Verify dependency lock integrity
if [ -f "scripts/verify_dependency_lock.py" ]; then
    echo "[*] Reconciling dependency lock integrity..."
    $PYTHON_CMD scripts/verify_dependency_lock.py
fi

# 4. Bootstrap and migrate database schema
echo "[*] Running database migrations..."
$PYTHON_CMD scripts/migrate_db.py up

# 5. Compilation hygiene check
echo "[*] Verifying bytecode compilation hygiene..."
$PYTHON_CMD -m compileall app core central_platform scripts -q

echo "=================================================================="
echo "  GAYATRI AI SETUP COMPLETE — READY TO LAUNCH"
echo "=================================================================="
