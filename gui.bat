@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYCMD="
where py >nul 2>&1
if not errorlevel 1 (
  set "PYCMD=py"
) else (
  where python >nul 2>&1
  if not errorlevel 1 set "PYCMD=python"
)
if not defined PYCMD (
  echo ERROR: Python was not found in PATH.
  echo Install Python 3.10+ ^(https://www.python.org/downloads/^), check
  echo "Add python.exe to PATH" during install, then re-run this script.
  exit /b 1
)

%PYCMD% "%~dp0scripts\build_gui.py"
exit /b %errorlevel%
