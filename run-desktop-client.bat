@echo off
title Titan Remote Desktop Client
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" -m client_desktop.desktop_client %*
) else (
    start "" python -m client_desktop.desktop_client %*
)
