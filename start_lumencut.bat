@echo off
setlocal
cd /d "%~dp0"
title LumenCut

if not exist ".venv\Scripts\python.exe" (
  goto dashboard_only
)

".venv\Scripts\python.exe" -c "import sysconfig" >nul 2>nul
if errorlevel 1 goto dashboard_only
for /f %%A in ('.venv\Scripts\python.exe -c "import sysconfig; print(sysconfig.get_platform())"') do set "PYTHON_PLATFORM=%%A"
if /I "%PYTHON_PLATFORM%"=="win-arm64" goto dashboard_only

if not exist ".env" (
  echo Missing .env configuration for the local backend.
  echo Copy .env.example to .env and set ADMIN_USERNAME, ADMIN_PASSWORD, and APP_SECRET.
  pause
  exit /b 1
)

echo Starting LumenCut at http://localhost:3000
start "" http://localhost:3000
".venv\Scripts\python.exe" server.py
pause
exit /b

:dashboard_only
echo Running dashboard-only mode. Video processing needs a configured hosted backend.
echo Set window.LUMENCUT_API_URL in config.js after deploying the backend.
start "" http://localhost:3000
python -m http.server 3000 --bind 127.0.0.1
