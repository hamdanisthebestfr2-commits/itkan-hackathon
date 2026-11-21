@echo off
cd /d "%~dp0"
echo Starting FlatRate Health... (close this window to stop)
".venv\Scripts\python.exe" run.py
pause
