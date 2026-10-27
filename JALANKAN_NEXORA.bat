@echo off
setlocal
title NEXORA AI
cd /d "%~dp0"

if not exist "NEXORA_Desktop.py" (
    echo.
    echo [ERROR] File NEXORA_Desktop.py tidak ditemukan.
    echo Pastikan file ini berada di folder yang sama dengan NEXORA_Desktop.py.
    echo.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] Python tidak ditemukan.
    echo Install Python dari https://www.python.org/downloads/
    echo Saat instalasi, centang "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo Membuka NEXORA AI...
python "NEXORA_Desktop.py"
if errorlevel 1 (
    echo.
    echo NEXORA berhenti kerana ada error. Catat pesan error di atas.
    echo.
    pause
)
endlocal
