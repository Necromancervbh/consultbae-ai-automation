@echo off
echo ======================================================================
echo  ConsultBae AI Automation Platform - Starting Local Server
echo ======================================================================

set PYTHONPATH=.

if exist "C:\Users\EXCEL\python311\python.exe" (
    set PY_EXE=C:\Users\EXCEL\python311\python.exe
) else (
    set PY_EXE=python
)

echo [1/2] Running Task 1 Ingestion Pipeline...
%PY_EXE% -m pipeline.ingest

echo.
echo [2/2] Launching Web Application on http://localhost:8000 ...
echo Press Ctrl+C to stop the server.
echo.

%PY_EXE% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
