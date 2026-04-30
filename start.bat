@echo off
title ResearchForm Dev Server
set NODE_DIR=C:\Users\HP\Documents\ResearchForm_Codebase\nodejs\node-v20.19.0-win-x64
set FRONTEND=%~dp0frontend
set BACKEND=%~dp0backend
set PATH=%NODE_DIR%;%PATH%

echo.
echo  ============================================
echo   ResearchForm - Starting Development Server
echo  ============================================
echo.

:: --- Cleanup ---
echo [*] Cleaning up dangling processes...
taskkill /F /IM node.exe >nul 2>&1
taskkill /FI "WINDOWTITLE eq ResearchForm Backend" >nul 2>&1
if exist "%FRONTEND%\.next" (
    echo [*] Clearing Next.js cache...
    rmdir /s /q "%FRONTEND%\.next"
)

:: --- Backend Setup ---
echo [*] Checking Backend...
if not exist "%BACKEND%\venv" (
    echo [*] Creating Python Virtual Environment...
    cd /d "%BACKEND%"
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    python dev_db.py
)
echo [*] Starting FastAPI Backend on port 8000...
start "ResearchForm Backend" cmd /c "cd /d "%BACKEND%" && call venv\Scripts\activate.bat && uvicorn main:app --reload --host 127.0.0.1 --port 8000"

:: --- Frontend Setup ---
echo [*] Checking Frontend...
if not exist "%FRONTEND%\node_modules\next" (
    echo [*] Installing npm packages...
    cd /d "%FRONTEND%"
    npm install --no-audit --no-fund --legacy-peer-deps
)

echo [*] Starting Next.js frontend on http://localhost:3000
echo.
echo  Open your browser to: http://localhost:3000/login
echo.
echo  Demo login:
echo    Email:    demo@researchform.app
echo    Password: demo1234
echo.

cd /d "%FRONTEND%"
node node_modules\next\dist\bin\next dev
