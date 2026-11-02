@echo off
rem Rebuild laya-gateway:latest with the latest checkpoints from the Hub. Needs internet.
rem The latest commit goes in as the REVISION build arg: when it has not moved, Docker reuses the
rem cached layer and nothing is downloaded; a plain rebuild would keep an old model forever.
rem Set LAYA_REVISION to a commit SHA to build that one instead.
setlocal
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
    echo [error] Docker is not running. Start Docker Desktop and try again.
    goto :fail
)

if not "%LAYA_REVISION%"=="" goto :have_revision
for /f "delims=" %%S in ('powershell -NoProfile -Command "(curl.exe -fsS https://huggingface.co/api/models/convaiinnovations/laya | ConvertFrom-Json).sha"') do set "LAYA_REVISION=%%S"
if "%LAYA_REVISION%"=="" (
    echo [error] Could not read the latest revision from the Hub. Check the internet connection or proxy.
    goto :fail
)
:have_revision
echo Model revision: %LAYA_REVISION%

docker compose -f compose.yaml build
if errorlevel 1 goto :fail
echo.
echo Done. Run start_laya.bat to serve the new image; it replaces a running container.
pause
exit /b 0

:fail
pause
exit /b 1
