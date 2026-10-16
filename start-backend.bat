@echo off
cd /d "%~dp0"
title ShizukuClaw Backend

set "PY="
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PY (
  py -3 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python not found.
  pause
  exit /b 1
)

echo Using Python: %PY%
%PY% -c "import fastapi,uvicorn,pydantic,yaml" >nul 2>nul
if errorlevel 1 (
  echo Installing backend deps...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
  )
)

echo Starting backend. Port is auto-picked if 8000 is busy.
%PY% scripts\run_backend.py
echo.
echo Backend stopped.
pause
