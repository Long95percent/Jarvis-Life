@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul 2>&1
title ShadowLink AI Platform

echo.
echo  ========================================
echo     ShadowLink AI Platform v3.0
echo     One-Click Launcher
echo  ========================================
echo.

REM ── Resolve project root (where this script lives) ──
set "ROOT=%~dp0"
set "AI_DIR=%ROOT%shadowlink-ai"
set "WEB_DIR=%ROOT%shadowlink-web"

REM ── Detect Python environment ──
set "PYTHON="

REM 1) Check the user's known conda environment
if exist "D:\software\study\Ana\envs\shadowlink\python.exe" (
    set "PYTHON=D:\software\study\Ana\envs\shadowlink\python.exe"
    goto :found_python
)

REM 2) Check for local .venv inside the AI directory
if exist "%AI_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON=%AI_DIR%\.venv\Scripts\python.exe"
    goto :found_python
)

REM 3) Check project root .venv
if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%.venv\Scripts\python.exe"
    goto :found_python
)

REM 4) Check common Anaconda/Miniconda locations
for %%D in (
    "%USERPROFILE%\anaconda3\envs\shadowlink\python.exe"
    "%USERPROFILE%\miniconda3\envs\shadowlink\python.exe"
    "C:\ProgramData\anaconda3\envs\shadowlink\python.exe"
    "C:\ProgramData\miniconda3\envs\shadowlink\python.exe"
) do (
    if exist %%D (
        set "PYTHON=%%~D"
        goto :found_python
    )
)

REM 5) Fallback: system PATH python
where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON=python"
    goto :found_python
)

echo  [ERROR] Python not found!
echo.
echo  Please do ONE of the following:
echo    1. Install Python 3.10+ and add to PATH
echo    2. Create a conda env: conda create -n shadowlink python=3.11
echo    3. Create a venv: python -m venv %AI_DIR%\.venv
echo.
pause
exit /b 1

:found_python
echo  [OK] Python: !PYTHON!

REM ── Detect Node.js ──
where node >nul 2>&1
if !errorlevel! neq 0 (
    echo  [ERROR] Node.js not found! Please install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>nul') do set "NODE_VER=%%v"
echo  [OK] Node.js: %NODE_VER%

REM ── Validate directories ──
if not exist "%AI_DIR%\app\main.py" (
    echo  [ERROR] Python AI service not found at %AI_DIR%
    pause
    exit /b 1
)
if not exist "%WEB_DIR%\package.json" (
    echo  [ERROR] Web frontend not found at %WEB_DIR%
    pause
    exit /b 1
)

REM ── Install Python dependencies if first run ──
if not exist "%AI_DIR%\.deps_ok" (
    echo.
    echo  [SETUP] Installing Python dependencies (first run)...
    "!PYTHON!" -m pip install -e "%AI_DIR%" --quiet 2>nul
    if !errorlevel! equ 0 (
        echo ok > "%AI_DIR%\.deps_ok"
        echo  [OK] Python dependencies installed.
    ) else (
        echo  [WARN] pip install had issues. Trying to continue...
    )
)

REM ── Install npm dependencies if first run ──
if not exist "%WEB_DIR%\node_modules\.package-lock.json" (
    echo.
    echo  [SETUP] Installing frontend dependencies (first run)...
    cd /d "%WEB_DIR%"
    call npm install --silent 2>nul
    if !errorlevel! equ 0 (
        echo  [OK] Frontend dependencies installed.
    ) else (
        echo  [WARN] npm install had issues. Trying to continue...
    )
)

echo.
echo  ---- Starting Services ----
echo.

REM ── Start Python AI service (port 8000) ──
echo  [1/2] Starting AI service on port 8000 ...
cd /d "%AI_DIR%"
start "ShadowLink-AI" cmd /c "title ShadowLink AI Service [port 8000] && color 0A && "!PYTHON!" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload && pause"

REM ── Start React frontend (port 3000) ──
echo  [2/2] Starting web frontend on port 3000 ...
cd /d "%WEB_DIR%"
start "ShadowLink-Web" cmd /c "title ShadowLink Web [port 3000] && color 0B && npx vite --port 3000 && pause"

REM ── Wait for services to initialize ──
echo.
echo  Waiting for services to start (10s) ...
timeout /t 10 /nobreak > nul

REM ── Open browser ──
echo  Opening browser ...
start "" "http://localhost:3000"

echo.
echo  ========================================
echo     ShadowLink AI is running!
echo.
echo     Frontend:  http://localhost:3000
echo     AI API:    http://localhost:8000
echo     API Docs:  http://localhost:8000/docs
echo.
echo     To configure LLM providers, go to
echo     Settings page in the web UI.
echo.
echo     Press any key to STOP all services.
echo  ========================================
echo.

pause > nul

echo.
echo  Stopping services ...
taskkill /fi "WINDOWTITLE eq ShadowLink AI*" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq ShadowLink Web*" /f >nul 2>&1
echo  Done. Goodbye!
timeout /t 2 /nobreak > nul