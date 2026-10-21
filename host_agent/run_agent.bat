@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title Meikova Relay Desktop - Host Agent
echo ======================================================
echo           MEIKOVA RELAY DESKTOP - HOST AGENT
echo ======================================================
echo.
if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0..\.venv\Scripts\python.exe"
) else (
    set "PY_EXE=python"
)

echo Starting Host Agent...
"%PY_EXE%" "%~dp0host_service.py" %*
pause
