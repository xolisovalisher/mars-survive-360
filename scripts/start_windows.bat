@echo off
REM MARS SURVIVE 360 - start the web app (finds a free port, opens the browser, logs errors)
setlocal
cd /d "%~dp0\.."
if not exist logs mkdir logs
if not exist .venv\Scripts\activate.bat (
  echo [ERROR] Not installed yet. Run scripts\setup_windows.bat first.
  pause & exit /b 1
)
call .venv\Scripts\activate.bat
for /f %%p in ('python scripts\find_port.py') do set PORT=%%p
if "%PORT%"=="" set PORT=8501
echo Starting MARS SURVIVE 360 on http://localhost:%PORT%  (close this window to stop)
start "" http://localhost:%PORT%
python -m streamlit run app.py --server.port %PORT% --server.headless true 2>> logs\start_errors.log
if errorlevel 1 (
  echo [ERROR] The app stopped with an error. See logs\start_errors.log and logs\app.log
  pause
)
