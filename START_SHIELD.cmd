@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if exist ".venv312\Scripts\python.exe" (
  ".venv312\Scripts\python.exe" -c "import sys; assert (3,12) <= sys.version_info[:2] <= (3,14)" >nul 2>&1
  if not errorlevel 1 goto existing
)
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 goto py312
python -c "import sys; assert (3,12) <= sys.version_info[:2] <= (3,14)" >nul 2>&1
if not errorlevel 1 goto fallback
echo Python 3.12 x64 is required. Install it from https://www.python.org/downloads/windows/ and rerun this file.
pause
exit /b 1
:existing
".venv312\Scripts\python.exe" start_shield.py %*
goto finish
:py312
py -3.12 start_shield.py %*
goto finish
:fallback
python start_shield.py %*
:finish
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
