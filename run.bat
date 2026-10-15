@echo off
title Gayatri School OS - Institutional Demo Platform
cd /d "%~dp0"

set "PYTHON=python"
if exist .venv\Scripts\python.exe set "PYTHON=.venv\Scripts\python.exe"

echo =====================================================================
echo   GAYATRI SCHOOL OS - INSTITUTIONAL DEMO & EVALUATION PLATFORM
echo =====================================================================
echo.
echo [*] Launching Gayatri Central Platform on http://127.0.0.1:8000...
echo.
echo Evaluation Portals:
echo   [1] Executive Admin Command Center : http://127.0.0.1:8000/admin
echo   [2] Teacher Academic Portal        : http://127.0.0.1:8000/teacher
echo   [3] Student Learning & AI Tutor    : http://127.0.0.1:8000/student
echo   [4] Parent Oversight Portal        : http://127.0.0.1:8000/parent
echo   [5] Interactive API Documentation  : http://127.0.0.1:8000/docs
echo.
echo Press Ctrl+C in this window to stop the server when done.
echo.

start "" "http://127.0.0.1:8000/admin"
%PYTHON% -m central_platform.api.app
