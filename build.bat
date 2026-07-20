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
  exit /b 1
)

%PYCMD% "%~dp0scripts\build.py" %*
exit /b %errorlevel%
