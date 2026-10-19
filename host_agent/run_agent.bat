@echo off
title Titan Remote Desktop - Host Agent
echo ======================================================
echo           TITAN REMOTE DESKTOP - HOST AGENT
echo ======================================================
echo.
echo Starting Host Agent...
python "%~dp0host_service.py" %*
pause
