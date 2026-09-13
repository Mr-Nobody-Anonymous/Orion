@echo off
rem ORION one-command launcher - Windows / Windows Server
rem (Linux + macOS: start.sh; any OS with Python 3.10+: python start.py)
rem Starts the whole platform: doctor -> status -> demo cycle -> web dashboard.

setlocal
cd /d "%~dp0"

rem Prefer the py launcher, but verify a Python 3 is actually registered.
set "ORION_PY="
py -3 -c "import sys" >nul 2>nul && set "ORION_PY=py -3"
if not defined ORION_PY (
    python -c "import sys" >nul 2>nul && set "ORION_PY=python"
)

if not defined ORION_PY (
    echo [fail] Python 3.10+ not found on this machine.
    echo        Install it, then re-run start.cmd:
    echo          winget install Python.Python.3.12
    echo          or https://www.python.org/downloads/ - tick "Add python.exe to PATH"
    pause
    exit /b 2
)

%ORION_PY% start.py %*
endlocal & exit /b %errorlevel%
