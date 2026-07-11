@echo off
cd /d "%~dp0"

echo Checking if Inam Medical Chat Bot server is already running...
powershell -NoProfile -Command "(Test-NetConnection -ComputerName localhost -Port 8501 -WarningAction SilentlyContinue).TcpTestSucceeded" | findstr /i "True" >nul
if %errorlevel%==0 (
    echo Server already running on port 8501.
) else (
    echo Starting Inam Medical Chat Bot server...
    start "Inam Medical Chat Bot - Server" cmd /k ".venv\Scripts\streamlit.exe run app.py --server.port 8501"
    echo Waiting for the server to come up...
    ping -n 7 127.0.0.1 >nul
)

start "" "%~dp0index.html"
