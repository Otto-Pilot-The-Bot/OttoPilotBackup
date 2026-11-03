@echo off
rem Opens the model reducer window (shrinks Meshy .glb models with Blender). Double-click me.
set PYTHONUTF8=1
cd /d "%~dp0.."
py -3 tools\model_reducer_gui.py
if errorlevel 1 pause
