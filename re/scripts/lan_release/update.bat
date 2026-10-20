@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sc3_update.ps1" %*
pause
