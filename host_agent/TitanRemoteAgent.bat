@echo off
if exist "%~dp0..\.venv\Scripts\pythonw.exe" (
    start "" "%~dp0..\.venv\Scripts\pythonw.exe" "%~dp0gui_agent.py"
) else (
    start "" pythonw "%~dp0gui_agent.py"
)
