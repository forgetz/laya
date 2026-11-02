@echo off
rem Sync .venv with requirements.txt, then download the Laya checkpoints into weights\ or update
rem them to the latest Hub revision.
rem Files that have not changed are not downloaded again. Needs internet.
rem Usage: update_model.bat [download_model.py options]
rem    update_model.bat --models english,multilingual,typed-decisions
rem    update_model.bat --revision ^<commit-sha^>
setlocal
cd /d "%~dp0"

rem An offline setting left in this shell would turn the update into a cache lookup.
set "HF_HUB_OFFLINE="
set "PYTHONUTF8=1"

if exist ".venv\Scripts\python.exe" goto :have_venv
python -m venv .venv
if errorlevel 1 (
    echo [error] Could not create .venv. Install Python 3.10 or newer from python.org.
    goto :fail
)
:have_venv

rem Every run, not only on a new .venv: this is what moves laya when requirements.txt bumps the pin.
echo [setup] Syncing packages with requirements.txt ...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

".venv\Scripts\python.exe" download_model.py %*
if errorlevel 1 (
    echo [error] Download failed. If the gateway is running, stop it first: Windows locks loaded model files.
    goto :fail
)
echo.
echo Done. Restart start_laya.bat to serve the new checkpoints.
pause
exit /b 0

:fail
pause
exit /b 1
