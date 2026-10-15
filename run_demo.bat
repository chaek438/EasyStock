@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto path_failed
if exist ".venv\Scripts\python.exe" goto check_environment

py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 goto create_with_py
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 goto create_with_python
echo Python 3.11 or newer was not found. Install Python with pip enabled.
goto failed

:create_with_py
py -3 -m venv --without-pip ".venv"
if errorlevel 1 goto environment_failed
goto check_environment

:create_with_python
python -m venv --without-pip ".venv"
if errorlevel 1 goto environment_failed

:check_environment
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto environment_failed
".venv\Scripts\python.exe" -m pip --version >nul 2>&1
if not errorlevel 1 goto install_dependencies
echo pip is missing. Restoring it with the bundled ensurepip module...
".venv\Scripts\python.exe" -m ensurepip --upgrade --default-pip
if errorlevel 1 goto pip_failed
".venv\Scripts\python.exe" -m pip --version
if errorlevel 1 goto pip_failed

:install_dependencies
echo Installing EasyStock dependencies...
".venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto dependencies_failed
echo Starting EasyStock at http://127.0.0.1:5000
".venv\Scripts\python.exe" start.py --demo
if errorlevel 1 goto server_failed
exit /b 0

:path_failed
echo Cannot open the project folder. Extract the ZIP before starting.
goto failed
:environment_failed
echo The project .venv is incomplete or does not run Python 3.11+.
echo Rename only the .venv folder and run this file again to recreate it.
goto failed
:pip_failed
echo Could not restore pip. Use the Python installer to repair Python with pip enabled.
goto failed
:dependencies_failed
echo Dependency installation failed. Check the pip error above and your Internet connection.
goto failed
:server_failed
echo The server stopped with an error. Check the message above.
:failed
pause
exit /b 1
