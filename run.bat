@echo off
REM Start Otto Pilot on Windows:   run.bat        (then open http://127.0.0.1:8765, or the address you set with SPROCKET_HOST)
REM Headless terminal only:       run.bat run
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
  .venv\Scripts\pip install -q -r requirements.txt
)
if "%~1"=="" (
  .venv\Scripts\python -m sprocket serve
) else (
  .venv\Scripts\python -m sprocket %*
)
