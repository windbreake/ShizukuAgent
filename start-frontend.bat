@echo off
cd /d "%~dp0"
title ShizukuClaw Frontend

set "NODE="
if exist "C:\nvm4w\nodejs\node.exe" set "NODE=C:\nvm4w\nodejs\node.exe"
if not defined NODE (
  node -v >nul 2>nul
  if not errorlevel 1 set "NODE=node"
)
if not defined NODE (
  echo [ERROR] Node.js not found.
  pause
  exit /b 1
)

echo Using Node: %NODE%
"%NODE%" scripts\auto-install.js
if errorlevel 1 (
  echo [ERROR] frontend dependency install failed.
  pause
  exit /b 1
)

cd frontend
echo Starting frontend http://127.0.0.1:5173
call npm run dev
echo.
echo Frontend stopped.
pause
