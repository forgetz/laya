@echo off
rem Start the Laya API gateway (app.py) offline, from the checkpoints in weights\.
rem Usage: start_laya.bat [port]      (default: LAYA_PORT, then 8080)
rem Settings (environment): LAYA_CHECK_LATEST=1, LAYA_BIND_ADDRESS, LAYA_MODELS, LAYA_DEVICE, LAYA_API_KEY, LAYA_WEIGHTS
setlocal
cd /d "%~dp0"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=%LAYA_PORT%"
if "%PORT%"=="" set "PORT=8080"
rem Loopback by default, as in compose.yaml: the API has no auth until LAYA_API_KEY is set.
if "%LAYA_BIND_ADDRESS%"=="" set "LAYA_BIND_ADDRESS=127.0.0.1"
if "%LAYA_MODELS%"=="" set "LAYA_MODELS=english,multilingual"
if "%LAYA_WEIGHTS%"=="" set "LAYA_WEIGHTS=%~dp0weights"

if not exist ".venv\Scripts\python.exe" (
    echo [error] .venv not found. Run update_model.bat on a machine with internet first.
    goto :fail
)
".venv\Scripts\python.exe" -c "import laya, fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [error] .venv is missing laya, fastapi or uvicorn. Run update_model.bat first.
    goto :fail
)
rem Checks the files only, so a missing checkpoint is reported here without loading torch.
".venv\Scripts\python.exe" download_model.py --verify --out "%LAYA_WEIGHTS%" --models "%LAYA_MODELS%"
if errorlevel 1 (
    echo [error] Checkpoints are incomplete. Run update_model.bat on a machine with internet.
    goto :fail
)

rem Opt-in, because it needs internet: refuse to serve checkpoints that are behind the Hub.
if not "%LAYA_CHECK_LATEST%"=="1" goto :checked
set "HF_HUB_OFFLINE="
".venv\Scripts\python.exe" download_model.py --check --out "%LAYA_WEIGHTS%" --models "%LAYA_MODELS%"
if errorlevel 1 (
    echo [error] Could not confirm these are the latest checkpoints. See the messages above.
    goto :fail
)
:checked

rem Must be set before laya is imported: a missing file then fails instead of reaching for the Hub.
set "HF_HUB_OFFLINE=1"
set "PYTHONUTF8=1"
if not "%LAYA_BIND_ADDRESS%"=="127.0.0.1" if "%LAYA_API_KEY%"=="" echo [warning] Listening on %LAYA_BIND_ADDRESS% with no LAYA_API_KEY: anyone who can reach it can call /predict.

echo Laya gateway: http://localhost:%PORT%/health   (Ctrl+C to stop)
".venv\Scripts\python.exe" -m uvicorn app:app --host %LAYA_BIND_ADDRESS% --port %PORT%
if errorlevel 1 goto :fail
exit /b 0

:fail
pause
exit /b 1
