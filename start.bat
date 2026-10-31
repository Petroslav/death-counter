@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 (
  pause
  exit /b 1
)
.venv\Scripts\python.exe app.py
pause
