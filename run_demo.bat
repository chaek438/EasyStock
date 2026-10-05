@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe start.py --demo
if errorlevel 1 goto failed
exit /b 0
:failed
echo Failed to start EasyStock. Check that Python 3.11+ is installed.
pause
exit /b 1
