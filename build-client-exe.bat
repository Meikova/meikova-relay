@echo off
title Build Titan Remote Desktop Client EXE
cd /d "%~dp0"

echo [1/2] Compiling TitanRemoteClient.exe via PyInstaller...
if exist ".venv\Scripts\pyinstaller.exe" (
    ".venv\Scripts\pyinstaller.exe" --noconfirm client_desktop/client.spec
) else (
    pyinstaller --noconfirm client_desktop/client.spec
)

if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    exit /b %errorlevel%
)

echo [2/2] Build completed successfully: dist\TitanRemoteClient.exe
