@echo off
cd /d "%~dp0"
echo ==============================================================
echo        TITAN REMOTE ENTERPRISE - BUILD EXECUTABLE & PACKAGES
echo ==============================================================
echo.

echo [1/3] Kiem tra moi truong Python & PyInstaller...
if not exist ".venv\Scripts\pyinstaller.exe" (
    echo Dang cai dat PyInstaller vao .venv...
    ".venv\Scripts\python.exe" -m pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo [X] Cai dat PyInstaller that bai.
        pause
        exit /b 1
    )
)

echo [2/3] Chay Build Script da nen tang (scripts\build.py)...
".venv\Scripts\python.exe" scripts\build.py --target windows

if %ERRORLEVEL% NEQ 0 (
    echo [X] Build executable that bai.
    pause
    exit /b 1
)

echo.
echo [3/3] Hoan tat! 
echo - File chay Standalone: dist\TitanRemoteHost.exe
echo - Goi Zip cai dat: dist\TitanRemoteHost-windows-x64.zip
echo ==============================================================
pause
