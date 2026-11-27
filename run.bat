@echo off
setlocal
cd /d "%~dp0"
set "PATH=%~dp0bin;%~dp0python;%~dp0python\Scripts;%PATH%"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
if exist "%~dp0python\python.exe" (
    "%~dp0python\python.exe" "%~dp0app.py"
    if errorlevel 1 pause
) else (
    python "%~dp0app.py"
    if errorlevel 1 py "%~dp0app.py"
    if errorlevel 1 pause
)
