@echo off
title Traffic System Launcher & Deployer
echo ===================================================
echo    🚦 Starting AI Traffic Control System 🚦
echo ===================================================
echo.

:: Navigate to the repository root directory
cd /d "%~dp0\.."

:: Step 1: Start Flask server in a separate window
echo [1/2] Starting Flask server (app.py) in a new window...
start "Flask AI Backend" cmd /k "python app.py"
timeout /t 3 >nul

:: Step 2: Search for Ngrok in system PATH or current directory
echo [2/2] Checking for Ngrok tunnel client...
where ngrok >nul 2>nul
if %errorlevel% equ 0 (
    echo.
    echo ✅ Ngrok found! Starting public tunnel on port 5000...
    echo Close the Ngrok window to stop public access.
    echo.
    start "Ngrok Tunnel" cmd /k "ngrok http 5000"
) else (
    echo.
    echo ⚠️ Ngrok was not found in your system path.
    echo.
    echo To access your project from outside your Lab (from Home/Cellular data):
    echo 1. Download Ngrok from: https://ngrok.com/download
    echo 2. Setup your authtoken in your terminal.
    echo 3. Run: ngrok http 5000
    echo.
    echo Press any key to open the Ngrok download page...
    pause >nul
    explorer "https://ngrok.com/download"
)
