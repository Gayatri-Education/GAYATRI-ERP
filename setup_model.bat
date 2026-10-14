@echo off
title Gayatri Chemistry Tutor — Model Setup
cd /d "%~dp0"
echo.
echo ============================================================
echo   GAYATRI CHEMISTRY TUTOR — Model Setup
echo ============================================================
echo.

set "MODEL_DIR=%~dp0models"
set "MODEL_GAYATRI_DIR=%~dp0models\gayatri"
set "CANONICAL_MODEL=%MODEL_DIR%\qwen2.5-0.5b-instruct-q4_k_m.gguf"
set "LEGACY_MODEL=%MODEL_GAYATRI_DIR%\Gayatri-Tutor-SLM-Q4_K_M.gguf"

REM Create model directories if they do not exist
if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"
if not exist "%MODEL_GAYATRI_DIR%" mkdir "%MODEL_GAYATRI_DIR%"

REM Check if canonical model already installed
if exist "%CANONICAL_MODEL%" (
    echo [OK] Authoritative model already installed:
    echo      %CANONICAL_MODEL%
    echo.
    echo Ready to launch! Double-click Gayatri_Chemistry_Tutor.exe
    pause
    exit /b 0
)

REM Check if legacy model already installed
if exist "%LEGACY_MODEL%" (
    echo [OK] Model already installed:
    echo      %LEGACY_MODEL%
    echo.
    echo Ready to launch! Double-click Gayatri_Chemistry_Tutor.exe
    pause
    exit /b 0
)

REM Search common candidate paths for canonical model
set "SRC="
if exist "%USERPROFILE%\Downloads\qwen2.5-0.5b-instruct-q4_k_m.gguf" set "SRC=%USERPROFILE%\Downloads\qwen2.5-0.5b-instruct-q4_k_m.gguf"
if not defined SRC if exist "%MODEL_GAYATRI_DIR%\qwen2.5-0.5b-instruct-q4_k_m.gguf" set "SRC=%MODEL_GAYATRI_DIR%\qwen2.5-0.5b-instruct-q4_k_m.gguf"
if not defined SRC if exist "%USERPROFILE%\Desktop\gayatri\models\qwen2.5-0.5b-instruct-q4_k_m.gguf" set "SRC=%USERPROFILE%\Desktop\gayatri\models\qwen2.5-0.5b-instruct-q4_k_m.gguf"

REM Search common candidate paths for legacy model
if not defined SRC if exist "%USERPROFILE%\Downloads\Gayatri-Tutor-SLM-Q4_K_M.gguf" set "SRC=%USERPROFILE%\Downloads\Gayatri-Tutor-SLM-Q4_K_M.gguf"
if not defined SRC if exist "%USERPROFILE%\Desktop\gayatri\Gayatri Chem Tutor\release_staging\Gayatri-Tutor-SLM-Q4_K_M.gguf" set "SRC=%USERPROFILE%\Desktop\gayatri\Gayatri Chem Tutor\release_staging\Gayatri-Tutor-SLM-Q4_K_M.gguf"
if not defined SRC if exist "%USERPROFILE%\Desktop\gayatri\Gayatri Chem Tutor\GayatriAI\models\gayatri\Gayatri-Tutor-SLM-Q4_K_M.gguf" set "SRC=%USERPROFILE%\Desktop\gayatri\Gayatri Chem Tutor\GayatriAI\models\gayatri\Gayatri-Tutor-SLM-Q4_K_M.gguf"
if not defined SRC if exist "%USERPROFILE%\Desktop\gayatri\test_portable_v301\models\gayatri\Gayatri-Tutor-SLM-Q4_K_M.gguf" set "SRC=%USERPROFILE%\Desktop\gayatri\test_portable_v301\models\gayatri\Gayatri-Tutor-SLM-Q4_K_M.gguf"

if defined SRC (
    echo [FOUND] Model detected at:
    echo         %SRC%
    echo         Installing to application directory...
    copy "%SRC%" "%CANONICAL_MODEL%"
    if errorlevel 1 (
        echo [ERROR] Copy failed. Please manually copy:
        echo         From: %SRC%
        echo         To:   %CANONICAL_MODEL%
        pause
        exit /b 1
    )
    echo [OK] Model installed successfully!
    echo.
    echo Ready to launch! Double-click Gayatri_Chemistry_Tutor.exe
    pause
    exit /b 0
)

REM Model not found — show instructions
echo [INFO] Model file not found. Please complete setup:
echo.
echo  1. Download the authoritative model file (379 MB) from Hugging Face:
echo     https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
echo     or GitHub Releases:
echo     https://github.com/Gayatri-Education/Gayatri-Tutor-ChemistryDemo/releases/latest
echo     File: qwen2.5-0.5b-instruct-q4_k_m.gguf
echo     SHA-256: 74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db
echo.
echo  2. Place the downloaded file here:
echo     %CANONICAL_MODEL%
echo.
echo  3. Launch the app (or run this script to verify).
echo.
echo ============================================================
pause
exit /b 0
