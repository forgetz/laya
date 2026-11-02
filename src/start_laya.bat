@echo off
rem Build laya-gateway:latest with the latest checkpoints, then start a new container from it.
rem Layers that have not changed come from Docker's cache, so a repeat run is quick.
rem With no internet, or with no compose.yaml next to this file, it starts from the existing image.
rem Usage: start_laya.bat [port]      (default: LAYA_PORT, then 8080)
rem Stop:  docker compose -f compose.run.yaml down
rem Settings (environment or .env): LAYA_REVISION, LAYA_IMAGE, LAYA_BIND_ADDRESS, LAYA_MODELS,
rem LAYA_API_KEY. See the headers of compose.yaml and compose.run.yaml.
setlocal
cd /d "%~dp0"

if not "%~1"=="" set "LAYA_PORT=%~1"
if "%LAYA_PORT%"=="" set "LAYA_PORT=8080"
if "%LAYA_IMAGE%"=="" set "LAYA_IMAGE=laya-gateway:latest"

docker info >nul 2>&1
if errorlevel 1 (
    echo [error] Docker is not running. Start Docker Desktop and try again.
    goto :fail
)

if not exist "compose.yaml" goto :no_build
rem The latest commit goes in as the REVISION build arg: when it has not moved, the cached model
rem layer is reused and nothing is downloaded; a plain rebuild would keep an old model forever.
if not "%LAYA_REVISION%"=="" goto :have_revision
for /f "delims=" %%S in ('powershell -NoProfile -Command "(curl.exe -fsS https://huggingface.co/api/models/convaiinnovations/laya | ConvertFrom-Json).sha"') do set "LAYA_REVISION=%%S"
if "%LAYA_REVISION%"=="" goto :no_build
:have_revision
echo Model revision: %LAYA_REVISION%
docker compose -f compose.yaml build
if errorlevel 1 goto :fail
goto :run

:no_build
docker image inspect "%LAYA_IMAGE%" >nul 2>&1
if errorlevel 1 (
    echo [error] Cannot build, and image %LAYA_IMAGE% not found. Load it with: docker load -i laya-gateway.tar
    goto :fail
)
echo [warning] Not building. Starting the existing image %LAYA_IMAGE%, which may not have the latest model.

:run
rem compose.run.yaml is what a host that only has the image runs, so this machine tests the same thing.
docker compose -f compose.run.yaml up -d --force-recreate --wait --wait-timeout 300
if errorlevel 1 (
    docker compose -f compose.run.yaml logs --tail 30
    echo [error] The gateway did not become healthy. See the log above.
    goto :fail
)
echo.
echo Laya gateway: http://localhost:%LAYA_PORT%/health
echo Running in the background. Stop it with: docker compose -f compose.run.yaml down
exit /b 0

:fail
pause
exit /b 1
