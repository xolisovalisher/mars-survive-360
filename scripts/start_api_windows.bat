@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
echo REST API: http://localhost:8601/docs
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8601
