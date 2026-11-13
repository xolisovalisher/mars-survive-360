@echo off
REM MARS SURVIVE 360 - one-time setup on Windows 10/11 (Python 3.10-3.13 from python.org, "Add to PATH")
setlocal
cd /d "%~dp0\.."
if not exist logs mkdir logs
set LOG=logs\setup.log
echo [%date% %time%] setup started > "%LOG%"

where py >nul 2>&1 && (set PY=py -3) || (set PY=python)
%PY% -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,13), sys.version" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.10-3.13 not found. Install from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  echo See %LOG%
  pause & exit /b 1
)

if not exist .venv (
  echo Creating virtual environment .venv ...
  %PY% -m venv .venv >> "%LOG%" 2>&1 || (echo [ERROR] venv failed, see %LOG% & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
echo Installing packages (first time: 3-10 minutes) ...
python -m pip install --upgrade pip >> "%LOG%" 2>&1
python -m pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [ERROR] pip install failed - check internet/proxy. Details: %LOG%
  pause & exit /b 1
)
if not exist .env copy .env.example .env >nul

set /p OPT="Install optional ML/GIS packages (PyTorch CPU ~250 MB, GeoPandas)? [y/N] "
if /i "%OPT%"=="y" (
  echo Installing PyTorch CPU and GeoPandas ...
  python -m pip install torch --index-url https://download.pytorch.org/whl/cpu >> "%LOG%" 2>&1 || echo [WARN] PyTorch not installed - the neural network falls back to scikit-learn MLP
  python -m pip install geopandas >> "%LOG%" 2>&1 || echo [WARN] GeoPandas not installed - GIS export disabled
)

python scripts\check_system.py
if errorlevel 1 (echo [WARN] some checks failed - see above) else (echo [OK] Setup complete.)
echo Optional: python scripts\download_data.py   (real Jezero DEM, ~87 MB)
echo Start the app with scripts\start_windows.bat
pause
