@echo off
title StarLight Scanner V3 - Created by DELTASTB
echo.
echo  ============================================
echo    StarLight Scanner V3
echo    Created by DELTASTB
echo  ============================================
echo.
echo  [*] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [!] Python not found! Please install Python 3.8+ from:
    echo      https://www.python.org/downloads/
    echo.
    echo  [!] Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b
)
echo  [*] Installing dependencies...
pip install -q requests customtkinter urllib3 >nul 2>&1
echo  [*] Launching StarLight Scanner V3...
echo.
python "%~dp0starlight_scanner_gui.py"
if errorlevel 1 (
    echo.
    echo  [!] Error running scanner. Check above for details.
    pause
)
