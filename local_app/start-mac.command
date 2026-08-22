#!/usr/bin/env bash
# Sets up dependencies on first run, then starts the transcriber UI.
set -euo pipefail

cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python)
STAMP=.venv/setup-complete.txt

# The stamp is written only after the imports work, so an install that died half
# way through is retried instead of being skipped forever.
if [ ! -x .venv/bin/python ] || [ ! -f "$STAMP" ]; then
    rm -f "$STAMP"
    if [ ! -x .venv/bin/python ]; then
        echo "Creating a virtual environment..."
        "$PY" -m venv .venv
    fi
    echo "Installing dependencies. This takes a few minutes the first time..."
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python -c "import flask, numpy, torch, transformers"
    echo done > "$STAMP"
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

# app.py opens the browser itself, once the port really answers.
exec .venv/bin/python app.py
