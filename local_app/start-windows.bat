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
    echo.
    echo WARNING: ffmpeg was not found on PATH. Transcription will fail without it.
    echo Install it with:  winget install Gyan.FFmpeg
    echo Then close this window and open a new one.
    echo.
    pause
)

start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" app.py
goto :eof

:error
echo.
echo Setup failed. Check the messages above.
pause
