@echo off
setlocal
cd /d "%~dp0"
title AI Market Radar
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" -OpenBrowser %*
if errorlevel 1 (
  echo.
  echo Startup failed. Diagnostic logs: %~dp0.runtime\logs
  pause
)
