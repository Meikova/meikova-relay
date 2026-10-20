@echo off
title Titan Remote Desktop Client
cd /d "%~dp0"

if exist "dist\TitanRemoteClient.exe" (
    start "" "dist\TitanRemoteClient.exe" %*
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" -m client_desktop.desktop_client %*
) else (
    start "" python -m client_desktop.desktop_client %*
)
