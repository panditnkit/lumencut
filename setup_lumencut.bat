@echo off
setlocal
cd /d "%~dp0"
title LumenCut Setup

set "PYTHON_CMD="
py -3.11-64 -c "import sysconfig; raise SystemExit(sysconfig.get_platform() != 'win-amd64')" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.11-64"
if not defined PYTHON_CMD (
  py -3.12-64 -c "import sysconfig; raise SystemExit(sysconfig.get_platform() != 'win-amd64')" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3.12-64"
)
if not defined PYTHON_CMD (
  python -c "import sysconfig; raise SystemExit(sysconfig.get_platform() != 'win-amd64')" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo Native Windows ARM Python does not have the required CTranslate2 wheel.
  echo Install x64 Python 3.11 or 3.12, or use the hosted backend described in README.md.
  pause
  exit /b 1
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env. Edit it now and set ADMIN_USERNAME, ADMIN_PASSWORD, and a random APP_SECRET.
  notepad ".env"
  echo Save .env, close Notepad, then run setup_lumencut.bat again.
  pause
  exit /b 1
)

for /f %%A in ('%PYTHON_CMD% -c "import sysconfig; print(sysconfig.get_platform())"') do set "TARGET_PLATFORM=%%A"

if not exist ".venv\Scripts\python.exe" (
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo Could not create the virtual environment. Install Python 3.11 and try again.
    pause
    exit /b 1
  )
)

for /f %%A in ('.venv\Scripts\python.exe -c "import sysconfig; print(sysconfig.get_platform())"') do set "VENV_PLATFORM=%%A"
if /I not "%VENV_PLATFORM%"=="%TARGET_PLATFORM%" (
  echo The existing .venv uses a different Python architecture.
  echo Remove the .venv folder and run setup_lumencut.bat again.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check your internet connection and Python version.
  pause
  exit /b 1
)

echo Setup complete. Run start_lumencut.bat to launch the app.
pause
