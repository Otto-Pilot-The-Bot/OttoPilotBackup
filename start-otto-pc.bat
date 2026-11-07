@echo off
REM Start Otto Pilot on this PC so the Mac and phone can open it over Tailscale. Double-click this file.
REM The access token is NOT stored here or anywhere in the project: it lives in the Windows user variable SPROCKET_TOKEN
REM (set once with:  setx SPROCKET_TOKEN "your-long-secret"  and then open a new window).
REM Open it from any device on your Tailscale network at  http://<this PC's Tailscale address>:8765/?token=<the token>  the first time;
REM after that the browser remembers it for 30 days, so the plain address is enough.
cd /d "%~dp0"
if "%SPROCKET_TOKEN%"=="" (
  echo SPROCKET_TOKEN is not set. Run:  setx SPROCKET_TOKEN "a-long-secret"  then start this file again.
  pause
  exit /b 1
)
if "%SPROCKET_HOST%"=="" for /f %%i in ('tailscale ip -4 2^>nul') do set SPROCKET_HOST=%%i
if "%SPROCKET_HOST%"=="" (
  echo Could not find the Tailscale address. Is Tailscale running?
  pause
  exit /b 1
)
REM His brain. To go back to the small model, change this to gemma4:e4b (or delete the line) and run: powershell -File tools\server.ps1 restart
set SPROCKET_MODEL=gemma4:12b
set SPROCKET_NUM_CTX=8192
set SPROCKET_KEEP_ALIVE=30m
REM A machine-wide OLLAMA_HOST of 0.0.0.0 makes Otto's connection fail; this one is for Otto only.
set OLLAMA_HOST=http://127.0.0.1:11434
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
echo Otto Pilot will be at  http://%SPROCKET_HOST%:8765/
call "%~dp0run.bat"
