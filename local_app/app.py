"""
Local web UI for transcribe.py.

Serves a page with three buttons and runs the real transcribe.py behind them,
as a subprocess, with the same interpreter that is running this server. Nothing
about the transcription is reimplemented here -- this is only a front end.

Usage:
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:8000 in a browser.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

# transcribe.py lives one directory up, next to this app's folder.
REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIBE_SCRIPT = Path(os.environ.get("TRANSCRIBE_SCRIPT", REPO_ROOT / "transcribe.py"))

ALLOWED_SUFFIXES = {".m4a", ".mp3", ".mp4", ".wav", ".aac", ".flac", ".ogg", ".webm", ".m4b"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024**3  # 4 GB, enough for long recordings

# Recordings handed over by the browser, keyed by an opaque id so the client
# never sends us a filesystem path of its own choosing.
UPLOAD_DIR = Path(tempfile.gettempdir()) / "transcribe_web_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
uploads: dict[str, Path] = {}


def downloads_dir() -> Path:
    """The user's Downloads folder, which is where transcripts are written."""
    if sys.platform == "win32":
        # Downloads can be relocated on Windows; the registry knows where.
        try:
            import winreg

            key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                value, _ = winreg.QueryValueEx(handle, "{374DE290-123F-4565-9164-39C4925E467B}")
                if value:
                    return Path(os.path.expandvars(value))
        except OSError:
            pass
    candidate = Path.home() / "Downloads"
    return candidate if candidate.is_dir() else Path.home()


def unique_output_path(stem: str) -> Path:
    """Pick <Downloads>/<stem>.txt, adding a counter rather than overwriting."""
    target = downloads_dir() / f"{stem}.txt"
    counter = 2
    while target.exists():
        target = downloads_dir() / f"{stem} ({counter}).txt"
        counter += 1
    return target


def sse(event: str, **payload) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def stream_subprocess(command: list[str], cwd: Path):
    """
    Run a command and yield its output as Server-Sent Events, line by line, so
    the browser sees the same progress the script prints to a terminal.
    """
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
    except OSError as error:
        yield sse("failed", message=f"Could not start Python: {error}")
        return

    # Reading in a thread lets us emit keepalives while the model is busy and
    # printing nothing, which stops proxies and browsers from timing out.
    lines: queue.Queue = queue.Queue()

    def reader():
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line.rstrip("\n"))
        process.stdout.close()
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()

    while True:
        try:
            line = lines.get(timeout=15)
        except queue.Empty:
            yield ": keepalive\n\n"
            continue
        if line is None:
            break
        if line.strip():
            yield sse("log", line=line)

    code = process.wait()
    if code == 0:
        yield sse("succeeded")
    else:
        yield sse("failed", message=f"{Path(command[1]).name} exited with code {code}")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/environment")
def environment():
    """Report the things transcribe.py needs, so problems surface up front."""
    problems = []
    if not TRANSCRIBE_SCRIPT.is_file():
        problems.append(f"transcribe.py not found at {TRANSCRIBE_SCRIPT}")
    if shutil.which("ffmpeg") is None:
        problems.append("ffmpeg is not on PATH. transcribe.py needs it to read audio.")

    device = "cpu"
    try:
        import torch

        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
    except ImportError:
        problems.append("PyTorch is not installed. Run: pip install -r requirements.txt")

    return jsonify(
        problems=problems,
        device=device,
        downloads=str(downloads_dir()),
        script=str(TRANSCRIBE_SCRIPT),
    )


@app.post("/api/recording")
def upload_recording():
    """Save the chosen recording to a temp file and hand back an id for it."""
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="No file was sent."), 400

    original = Path(uploaded.filename).name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        return jsonify(error=f"Unsupported file type '{suffix}'. Allowed: {allowed}"), 400

    token = uuid.uuid4().hex
    destination = UPLOAD_DIR / f"{token}{suffix}"
    uploaded.save(destination)
    uploads[token] = destination

    return jsonify(token=token, name=original, size=destination.stat().st_size)


@app.get("/api/transcribe")
def transcribe():
    """
    Run transcribe.py on the uploaded recording, writing the transcript to the
    user's Downloads folder. This is the same command line you would type:

        python transcribe.py <recording> --out <Downloads>/<name>.txt
    """
    token = request.args.get("token", "")
    language = request.args.get("language", "he")
    source = uploads.get(token)
    if source is None or not source.is_file():
        return jsonify(error="That recording is no longer available. Choose it again."), 400
    if not language.replace("-", "").isalpha() or len(language) > 8:
        return jsonify(error="Invalid language code."), 400

    display_name = request.args.get("name") or source.name
    output_path = unique_output_path(Path(display_name).stem)

    command = [
        sys.executable,
        "-u",
        str(TRANSCRIBE_SCRIPT),
        str(source),
        "--out",
        str(output_path),
        "--language",
        language,
    ]

    def generate():
        yield sse("started", command=" ".join(command), output=str(output_path))
        succeeded = False
        for chunk in stream_subprocess(command, REPO_ROOT):
            if chunk.startswith("event: succeeded"):
                succeeded = True
                continue
            yield chunk
        if succeeded:
            yield sse("finished", output=str(output_path), name=output_path.name)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/transcript")
def transcript():
    """Read back a finished transcript so the page can show it."""
    name = Path(request.args.get("name", "")).name
    path = downloads_dir() / name
    if not name.endswith(".txt") or not path.is_file():
        return jsonify(error="Transcript not found."), 404
    return jsonify(text=path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"\n  Transcriber UI:  http://127.0.0.1:{port}")
    print(f"  Using script:    {TRANSCRIBE_SCRIPT}")
    print(f"  Transcripts to:  {downloads_dir()}\n")
    # Bound to localhost on purpose: this server runs local commands and must
    # not be reachable from the network.
    app.run(host="127.0.0.1", port=port, threaded=True)
