@echo off
rem Drop a folder of .bld files on this file. It renders them with your Building Architect (render_bld.ps1).
if "%~1"=="" (
  echo Drop a folder of .bld files on render_bld.cmd, or run: render_bld.cmd "C:\path\to\folder"
  pause
  exit /b 2
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0render_bld.ps1" %*
set rc=%errorlevel%
pause
exit /b %rc%
