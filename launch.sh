#!/usr/bin/env bash
# Gayatri AI — Linux / POSIX Application Launcher (Phase 11)
set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python 3.12+ is required to launch Gayatri AI."
    exit 1
fi

# Detect headless environment and configure offscreen Qt rendering
if [ -z "${DISPLAY:-}" ]; then
    echo "[INFO] No DISPLAY detected. Running in headless mode (QT_QPA_PLATFORM=offscreen)."
    export QT_QPA_PLATFORM="offscreen"
fi

export PYTHONPATH=".:${PYTHONPATH:-}"

MODE="${1:-desktop}"
if [ "$MODE" = "server" ]; then
    echo "[*] Starting Gayatri AI Central Platform Server on port 8000..."
    exec $PYTHON_CMD -m central_platform.api.app
elif [ "$MODE" = "smoke" ]; then
    echo "[*] Running post-install smoke test..."
    exec $PYTHON_CMD scripts/smoke_test_install.py
else
    echo "[*] Launching Gayatri AI Application..."
    exec $PYTHON_CMD -m app.main "$@"
fi
