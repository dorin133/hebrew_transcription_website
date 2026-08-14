@echo off
REM Sets up dependencies on first run, then starts the transcriber UI.
setlocal

cd /d "%~dp0"

where py >nul 2>nul && (set PY=py) || (set PY=python)

if not exist ".venv" (
    echo Creating a virtual environment...
    %PY% -m venv .venv || goto :error
    echo Installing dependencies. This takes a few minutes the first time...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

where ffmpeg >nul 2>nul || (
    where winget >nul 2>nul && (
        echo ffmpeg was not found. Installing it with winget...
        winget install --id Gyan.FFmpeg -e --source winget
        echo.
        echo ffmpeg was just installed. Close this window and double-click
        echo start-windows.bat again so PATH picks it up.
        echo.
        pause
        exit /b 0
    ) || (
        echo.
        echo WARNING: ffmpeg was not found on PATH, and winget is not available.
        echo Install ffmpeg manually and make sure it is on PATH.
        echo.
        pause
    )
)

start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" app.py
goto :eof

:error
echo.
echo Setup failed. Check the messages above.
pause
