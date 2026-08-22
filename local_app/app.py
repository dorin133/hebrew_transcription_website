"""
Local web UI for transcribe.py.

Serves a page with two buttons and runs the real transcribe.py behind them,
as a subprocess, with the same interpreter that is running this server. Nothing
about the transcription is reimplemented here -- this is only a front end.

Usage:
    pip install -r requirements.txt
    python app.py

It prints the address it is serving, and opens a browser there.
"""

import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from pathlib import Path

# Checked before importing Flask, which fails with a much less obvious message
# on Pythons this old.
if sys.version_info < (3, 9):
    raise SystemExit(
        f"This app needs Python 3.9 or newer, but is running on "
        f"{sys.version.split()[0]}. Install a newer Python and try again."
    )

# Hebrew paths and transcripts are printed below. On Windows a redirected stdout
# defaults to the system code page, which cannot encode them, so pin UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from flask import Flask, Response, jsonify, render_template, request  # noqa: E402

# transcribe.py lives one directory up, next to this app's folder.
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
TRANSCRIBE_SCRIPT = Path(os.environ.get("TRANSCRIBE_SCRIPT", REPO_ROOT / "transcribe.py"))

# The Windows launcher can drop a portable ffmpeg here when the system has none.
# Put it on PATH for us and for the transcribe.py we spawn.
BUNDLED_FFMPEG = APP_DIR / "tools" / "ffmpeg"
if BUNDLED_FFMPEG.is_dir():
    os.environ["PATH"] = f"{BUNDLED_FFMPEG}{os.pathsep}{os.environ.get('PATH', '')}"

ALLOWED_SUFFIXES = {".m4a", ".mp3", ".mp4", ".wav", ".aac", ".flac", ".ogg", ".webm", ".m4b"}

# Names Windows refuses to create a file under, whatever the extension.
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{n}" for n in range(1, 10)),
    *(f"LPT{n}" for n in range(1, 10)),
}

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


def safe_stem(name: str) -> str:
    """
    Turn a name the browser gave us into one every filesystem accepts. Windows
    is the strict one: it bans several punctuation marks, trailing dots and
    spaces, and a handful of device names.
    """
    stem = Path(name.replace("\\", "/")).name
    stem = Path(stem).stem
    for character in '<>:"/\\|?*':
        stem = stem.replace(character, "-")
    stem = "".join(c for c in stem if c.isprintable()).rstrip(". ").strip()
    if not stem or stem.upper() in WINDOWS_RESERVED:
        stem = f"transcript-{stem}" if stem else "transcript"
    return stem[:120]


def unique_output_path(stem: str) -> Path:
    """Pick <Downloads>/<stem>.txt, adding a counter rather than overwriting."""
    folder = downloads_dir()
    target = folder / f"{stem}.txt"
    counter = 2
    while target.exists():
        target = folder / f"{stem} ({counter}).txt"
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
        yield sse("failed", message=f"לא הצלחתי להריץ את Python: {error}")
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
        # command is [python, -u, script, ...], so name the script, not a flag.
        script = next((Path(a).name for a in command if a.endswith(".py")), "התהליך")
        yield sse("failed", message=f"{script} נעצר עם קוד {code}")


def detect_device() -> tuple[str, list[str]]:
    """
    Work out which device transcribe.py will use, and turn a broken PyTorch
    install into a readable sentence. On Windows `import torch` raises OSError
    rather than ImportError when a DLL it needs is missing, so catch everything.
    """
    try:
        import torch
    except Exception as error:  # noqa: BLE001 - any failure here is a user problem
        hint = "PyTorch לא נטען. הריצו: pip install -r requirements.txt"
        if sys.platform == "win32" and isinstance(error, OSError):
            hint = (
                "PyTorch לא נטען. בוויندוס זה קורה כשחסר Microsoft Visual C++ "
                "Redistributable. התקינו אותו מ-https://aka.ms/vs/17/release/vc_redist.x64.exe "
                "ונסו שוב."
            )
        return "cpu", [f"{hint} ({type(error).__name__}: {error})"]

    try:
        if torch.cuda.is_available():
            return "cuda", []
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps", []
    except Exception as error:  # noqa: BLE001 - a probe must never 500 the page
        return "cpu", [f"בדיקת הכרטיס הגרפי נכשלה: {type(error).__name__}: {error}"]
    return "cpu", []


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/environment")
def environment():
    """Report the things transcribe.py needs, so problems surface up front."""
    problems = []
    if not TRANSCRIBE_SCRIPT.is_file():
        problems.append(f"transcribe.py לא נמצא בנתיב {TRANSCRIBE_SCRIPT}")
    if shutil.which("ffmpeg") is None:
        problems.append("ffmpeg לא נמצא ב-PATH. transcribe.py צריך אותו כדי לקרוא שמע.")

    device, device_problems = detect_device()
    problems.extend(device_problems)

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
        return jsonify(error="לא נשלח קובץ."), 400

    original = Path(uploaded.filename).name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        return jsonify(error=f"סוג הקובץ '{suffix}' לא נתמך. אפשר: {allowed}"), 400

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
        return jsonify(error="ההקלטה הזו לא זמינה יותר. בחרו אותה מחדש."), 400
    if not language.replace("-", "").isalpha() or len(language) > 8:
        return jsonify(error="קוד שפה לא תקין."), 400

    display_name = request.args.get("name") or source.name
    output_path = unique_output_path(safe_stem(display_name))

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
        return jsonify(error="התמליל לא נמצא."), 404
    return jsonify(text=path.read_text(encoding="utf-8"))


def free_port(preferred: int) -> int:
    """
    Return a port we can actually bind. Windows reserves whole ranges for
    Hyper-V and WSL, and 8000 is often inside one, which makes bind() fail with
    WinError 10013 instead of anything obvious. Fall back to any free port.
    """
    for candidate in (preferred, 0):
        try:
            # No SO_REUSEADDR here: on Windows it would let two servers bind the
            # same port, which is exactly the clash we are testing for.
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", candidate))
                return probe.getsockname()[1]
        except OSError:
            continue
    return preferred


def open_when_ready(url: str, port: int) -> None:
    """
    Open the browser once the server answers. Opening it up front, as the
    launchers used to, showed a connection error on slower machines because
    importing Flask can take several seconds on a cold Windows disk.
    """
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    else:
        return
    webbrowser.open(url)


if __name__ == "__main__":
    port = free_port(int(os.environ.get("PORT", "8000")))
    url = f"http://127.0.0.1:{port}"
    print(f"\n  Transcriber UI:  {url}")
    print(f"  Using script:    {TRANSCRIBE_SCRIPT}")
    print(f"  Transcripts to:  {downloads_dir()}")
    print(f"  ffmpeg:          {shutil.which('ffmpeg') or 'לא נמצא'}\n")

    if os.environ.get("NO_BROWSER") != "1":
        threading.Thread(target=open_when_ready, args=(url, port), daemon=True).start()

    # Bound to localhost on purpose: this server runs local commands and must
    # not be reachable from the network.
    app.run(host="127.0.0.1", port=port, threaded=True)
