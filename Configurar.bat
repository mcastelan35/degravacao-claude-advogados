@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Degravacao - configurar
if not exist ".venv\Scripts\python.exe" (
  echo A ferramenta ainda nao foi instalada. De dois cliques em Degravar.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" degravar.py configurar
echo.
pause
