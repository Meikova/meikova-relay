@echo off
setlocal EnableDelayedExpansion
title Titan Remote Host - Cài đặt máy trạm (Installer)
echo ==============================================================
echo        TITAN REMOTE ENTERPRISE - HOST AGENT INSTALLER
echo ==============================================================
echo.

cd /d "%~dp0.."

echo [1/4] Kiem tra moi truong Python...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python chua duoc cai dat tren he thong.
    echo Dang thu cai dat Python thong qua Windows winget...
    winget install Python.Python.3.13 --silent --accept-source-agreements --accept-package-agreements
    if %ERRORLEVEL% NEQ 0 (
        echo [X] Khong the tu dong cai dat Python. Vui long cai dat Python tai https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo [2/4] Khoi tao Virtual Environment (.venv)...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [X] Khong the tao virtual environment.
        pause
        exit /b 1
    )
)

echo [3/4] Cai dat thu vien can thiet vao .venv...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [X] Cai dat thu vien that bai.
    pause
    exit /b 1
)

echo [4/4] Tao loi tat khoi dong ngam va mo bang dieu khien...
set "VENV_PYW=%CD%\.venv\Scripts\pythonw.exe"
set "GUI_SCRIPT=%CD%\host_agent\gui_agent.py"

echo Khoi chay Titan Remote Control Panel...
start "" "%VENV_PYW%" "%GUI_SCRIPT%"

echo.
echo ==============================================================
echo   CAI DAT HOAN TAT!
echo   Vui long nhap Email/Username tai khoan Web cua ban vao
echo   o "Tai khoan lien ket", sau do nhan "KHOI DONG DICH VU".
echo   May se tu dong hien tren Dashboard Web de ket noi 1-click!
echo ==============================================================
echo.
pause
