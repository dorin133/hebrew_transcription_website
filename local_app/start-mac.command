#!/usr/bin/env bash
# Sets up dependencies on first run, then starts the transcriber UI.
set -euo pipefail

cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python)

if [ ! -d .venv ]; then
    echo "Creating a virtual environment..."
    "$PY" -m venv .venv
    echo "Installing dependencies. This takes a few minutes the first time..."
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
        echo "ffmpeg was not found. Installing it with Homebrew..."
        brew install ffmpeg
    else
        echo
        echo "WARNING: ffmpeg was not found on PATH, and Homebrew is not installed."
        echo "Install Homebrew (https://brew.sh), then re-run this script, or install"
        echo "ffmpeg some other way and make sure it is on PATH."
        echo
    fi
fi

(sleep 2 && open http://127.0.0.1:8000) &
exec .venv/bin/python app.py
