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
    echo
    echo "WARNING: ffmpeg was not found on PATH. Transcription will fail without it."
    echo "Install it with:  brew install ffmpeg"
    echo
fi

(sleep 2 && open http://127.0.0.1:8000) &
exec .venv/bin/python app.py
