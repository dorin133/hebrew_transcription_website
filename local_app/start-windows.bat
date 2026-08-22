@echo off
REM Sets up dependencies on first run, then starts the transcriber UI.
REM
REM Keep this file ASCII-only, CRLF-terminated, and free of multi-line ( )
REM blocks: cmd.exe is unreliable about all three.
setlocal EnableExtensions

cd /d "%~dp0"

title Hebrew Transcriber

set "VENV_PY=.venv\Scripts\python.exe"
set "STAMP=.venv\setup-complete.txt"
set "FFMPEG_DIR=%CD%\tools\ffmpeg"

REM ------------------------------------------------------------------ Python --
REM PyTorch publishes wheels for a few Python versions only, and the "py"
REM launcher hands out the newest Python installed, so ask for versions by name
REM before falling back to whatever is on PATH.
set "PY="
for %%V in (3.12 3.11 3.10 3.13 3.9) do call :use_python "py -%%V"
call :use_python "py -3"
call :use_python "python"
call :use_python "python3"
if not defined PY call :use_any_python "py -3"
if not defined PY call :use_any_python "python"
if not defined PY goto :no_python

REM ------------------------------------------------------------------- Setup --
if not exist "%VENV_PY%" goto :setup
if not exist "%STAMP%" goto :setup
goto :check_ffmpeg

:setup
echo.
echo Setting up. This takes a few minutes, and only happens once.
echo.
%PY% -c "import os,sys;sys.exit(0 if len(os.getcwd()) in range(81) else 1)"
if errorlevel 1 call :warn_long_path
if exist "%STAMP%" del /q "%STAMP%"
if not exist "%VENV_PY%" call :make_venv
if not exist "%VENV_PY%" goto :venv_failed
echo Installing dependencies...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_failed
REM Only stamp the venv as usable once the imports really work, so a download
REM that died half way through gets retried instead of skipped forever.
"%VENV_PY%" -c "import flask, numpy, torch, transformers"
if errorlevel 1 goto :pip_failed
echo setup completed> "%STAMP%"
echo.
echo Setup finished.
echo.

REM ------------------------------------------------------------------ ffmpeg --
:check_ffmpeg
if exist "%FFMPEG_DIR%\ffmpeg.exe" set "PATH=%FFMPEG_DIR%;%PATH%"
where ffmpeg >nul 2>nul
if not errorlevel 1 goto :run

echo.
echo ffmpeg was not found. It is needed to read audio files.
where winget >nul 2>nul
if errorlevel 1 goto :ffmpeg_download
echo Installing ffmpeg with winget...
winget install --id Gyan.FFmpeg -e --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
REM winget puts portable packages behind a symlink that needs Developer Mode or
REM admin rights, so find the real ffmpeg.exe and use its folder directly.
call :find_winget_ffmpeg
where ffmpeg >nul 2>nul
if not errorlevel 1 goto :run

:ffmpeg_download
echo Downloading a portable ffmpeg build into tools\ffmpeg...
call :download_ffmpeg
if exist "%FFMPEG_DIR%\ffmpeg.exe" set "PATH=%FFMPEG_DIR%;%PATH%"
where ffmpeg >nul 2>nul
if errorlevel 1 goto :no_ffmpeg

REM --------------------------------------------------------------------- Run --
:run
echo.
echo Starting the transcriber. The page opens by itself in a moment.
echo Leave this window open while you use it.
echo.
"%VENV_PY%" app.py
if errorlevel 1 goto :app_failed
exit /b 0

REM --------------------------------------------------------------- Routines --

:use_python
REM Accept this interpreter only if it is a version PyTorch ships wheels for.
if defined PY goto :eof
%~1 -c "import sys;sys.exit(0 if sys.version_info[:2] in ((3,9),(3,10),(3,11),(3,12),(3,13)) else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set "PY=%~1"
goto :eof

:use_any_python
REM Last resort: a newer Python than we know about. pip may not find wheels for
REM torch, and if so :pip_failed explains what to install instead.
if defined PY goto :eof
%~1 -c "import sys;sys.exit(0 if sys.version_info[:2] >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set "PY=%~1"
echo WARNING: only an untested Python version was found (%~1).
echo If installing dependencies fails, install Python 3.12 and try again.
goto :eof

:make_venv
echo Creating a virtual environment with %PY%...
%PY% -m venv .venv
goto :eof

:find_winget_ffmpeg
for /f "delims=" %%F in ('dir /b /s "%LOCALAPPDATA%\Microsoft\WinGet\Packages\ffmpeg.exe" 2^>nul') do set "PATH=%%~dpF;%PATH%"
goto :eof

:download_ffmpeg
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $url='https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'; $zip=Join-Path $env:TEMP 'ffmpeg-win64.zip'; $tmp='tools\ffmpeg-unzip'; Invoke-WebRequest $url -OutFile $zip -UseBasicParsing; if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }; Expand-Archive $zip $tmp -Force; $bin=(Get-ChildItem $tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1).Directory.FullName; New-Item -ItemType Directory -Force -Path 'tools\ffmpeg' | Out-Null; Copy-Item (Join-Path $bin '*') 'tools\ffmpeg' -Recurse -Force; Remove-Item -Recurse -Force $tmp; Remove-Item -Force $zip"
goto :eof

:warn_long_path
echo WARNING: this folder is deep inside your drive. Installing PyTorch here can
echo fail on the 260-character Windows path limit. If setup fails, move the
echo folder to somewhere short such as C:\transcriber and run this file again.
echo.
goto :eof

REM ------------------------------------------------------------------ Errors --

:no_python
echo.
echo Python was not found.
echo Install Python 3.12 from https://www.python.org/downloads/windows/ and tick
echo "Add python.exe to PATH" in the installer, then run this file again.
where winget >nul 2>nul
if errorlevel 1 goto :bail
echo.
set "ANSWER="
set /p "ANSWER=Install Python 3.12 now with winget? [y/N] "
if /i not "%ANSWER%"=="y" goto :bail
winget install --id Python.Python.3.12 -e --source winget --accept-source-agreements --accept-package-agreements
echo.
echo Close this window and double-click start-windows.bat again, so that Windows
echo picks up the new Python.
goto :bail

:venv_failed
echo.
echo Could not create the virtual environment with %PY%.
echo If Windows opened the Microsoft Store instead, install Python from
echo https://www.python.org/downloads/windows/ and run this file again.
goto :bail

:pip_failed
echo.
echo Installing the dependencies failed. The messages above say why. The usual
echo causes on Windows are:
echo   - no wheels for this Python version. Install Python 3.12.
echo   - not enough free disk space. PyTorch needs about 3 GB.
echo   - the 260-character path limit. Move this folder to C:\transcriber.
echo Setup will start over the next time you run this file.
goto :bail

:no_ffmpeg
echo.
echo ffmpeg still was not found, so audio cannot be decoded. Install it by hand
echo from https://www.gyan.dev/ffmpeg/builds/ , put ffmpeg.exe in
echo   %FFMPEG_DIR%
echo and run this file again.
goto :bail

:app_failed
echo.
echo The transcriber stopped with an error. The messages above say why.
goto :bail

:bail
echo.
pause
exit /b 1
