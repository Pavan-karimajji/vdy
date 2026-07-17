@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage
set "PROJECT=%~1"
set "TARGET=%~2"
set "PLATFORM=%~3"
set "CLEAN=%~4"

if /I not "%TARGET%"=="sil" if /I not "%TARGET%"=="gtest" (
  echo ERROR: Unknown target "%TARGET%"
  goto :usage
)

set "CFG_PRESET=%TARGET%-%PLATFORM%"
set "BLD_PRESET=%TARGET%-%PLATFORM%"
set "BUILD_DIR=%~dp0build-%TARGET%-%PLATFORM%"

set "BUILD_TYPE=Release"
echo %PLATFORM%| findstr /e /c:"_debug" >nul 2>&1
if not errorlevel 1 set "BUILD_TYPE=Debug"

where conan >nul 2>&1
if errorlevel 1 (
  echo ERROR: Conan is not installed or not in PATH.
  exit /b 1
)

if exist "%USERPROFILE%\.conan2\profiles\default" (
  findstr /b /c:"compiler=" "%USERPROFILE%\.conan2\profiles\default" >nul 2>&1
  if errorlevel 1 (
    echo WARNING: No C++ compiler entry found in the Conan default profile.
    echo If Visual Studio is already installed, this may just be a stale
    echo profile - continuing anyway. The conan install step below will
    echo report the real error if a toolchain genuinely cannot be found.
  )
)

if /I "%CLEAN%"=="clean" (
  echo Cleaning %BUILD_DIR% ...
  if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
)

echo Installing Conan dependencies...
set "ADAS_PROJECT=%PROJECT%"
set "ADAS_PART=%TARGET%"
conan install . --output-folder "%BUILD_DIR%" --build=missing -s build_type=%BUILD_TYPE%
if errorlevel 1 exit /b 1

echo Configuring preset %CFG_PRESET% (project=%PROJECT%) ...
cmake --preset %CFG_PRESET% -DADAS_PROJECT=%PROJECT%
if errorlevel 1 exit /b 1

echo Building preset %BLD_PRESET% ...
cmake --build --preset %BLD_PRESET%
if errorlevel 1 exit /b 1

if /I "%TARGET%"=="gtest" (
  echo Running tests...
  ctest --preset %BLD_PRESET%
  if errorlevel 1 exit /b 1
)

echo.
echo Build finished for target: %TARGET% (platform: %PLATFORM%, project: %PROJECT%)
exit /b 0

:usage
echo Usage: build.bat ^<project^> ^<sil^|gtest^> ^<platform^> [clean]
echo   e.g. build.bat base sil vs2026
echo        build.bat proj_alpha sil vs2026
echo        build.bat base gtest vs2026
exit /b 1
