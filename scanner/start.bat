@echo off
cd /d "%~dp0"
title Iris
echo Starting Iris... (close this window to stop)
".venv\Scripts\python.exe" run.py
pause
