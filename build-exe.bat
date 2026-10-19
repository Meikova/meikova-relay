@echo off
cd /d "%~dp0"
echo ==============================================================
echo        TITAN REMOTE ENTERPRISE - BUILD EXECUTABLE
echo ==============================================================
echo.

echo [1/3] Kiem tra PyInstaller trong .venv...
if not exist ".venv\Scripts\pyinstaller.exe" (
    echo Dang cai dat PyInstaller vao .venv...
    ".venv\Scripts\python.exe" -m pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo [X] Cai dat PyInstaller that bai.
        pause
        exit /b 1
    )
)

echo [2/3] Build Titan Remote Host Executable...
".venv\Scripts\pyinstaller.exe" --noconfirm --onedir --windowed --name "TitanRemoteHost" ^
    --add-data "host_agent;host_agent" ^
    --hidden-import "websockets" ^
    --hidden-import "websockets.legacy" ^
    --hidden-import "websockets.legacy.client" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL.Image" ^
    --hidden-import "tkinter" ^
    "host_agent\gui_agent.py"

if %ERRORLEVEL% NEQ 0 (
    echo [X] Build executable that bai.
    pause
    exit /b 1
)

echo.
echo [3/3] Hoan tat! File chay: dist\TitanRemoteHost\TitanRemoteHost.exe
echo ==============================================================
pause
