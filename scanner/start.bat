@echo off
cd /d "%~dp0"
echo Starting Intake Card Scanner... (close this window to stop)
".venv\Scripts\python.exe" run.py
pause
