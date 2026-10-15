@echo off
title Gayatri AI Tutor
cd /d "%~dp0"

set "PYTHON=python"
if exist .venv\Scripts\python.exe set "PYTHON=.venv\Scripts\python.exe"

set "MODE=%~1"
if "%MODE%"=="" set "MODE=desktop"

if /i "%MODE%"=="server" (
    echo [*] Starting Gayatri AI Central Platform Server on port 8000...
    %PYTHON% -m central_platform.api.app
    if errorlevel 1 exit /b 1
    goto :eof
)

if /i "%MODE%"=="smoke" (
    echo [*] Running post-install smoke test...
    %PYTHON% scripts\smoke_test_install.py
    if errorlevel 1 exit /b 1
    goto :eof
)

echo ============================================================
echo   GAYATRI AI TUTOR - Launching Application
echo ============================================================
echo.

REM Verify model existence via Python
%PYTHON% -c "from core.providers.local import LocalProvider; import sys; sys.exit(0 if LocalProvider.MODEL_PATH.exists() else 1)" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Local GGUF model file not found.
    echo       Expected model location: GayatriAI\models\gayatri
    echo.
)

REM Launch desktop application
echo Starting Gayatri AI Desktop...
%PYTHON% -m app.main %*
if errorlevel 1 (
    echo.
    echo [ERROR] App crashed or closed with error code %errorlevel%.
    echo Check logs at: %LOCALAPPDATA%\GayatriAI\logs\gayatri.log
    pause
    exit /b %errorlevel%
)
