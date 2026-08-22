# Hebrew Transcriber — local web UI

A web page with two buttons that runs transcription on your own computer.
Nothing is uploaded anywhere!

## Setup and use

**Windows** — double-click `local_app\start-windows.bat`.
**macOS** — double-click `local_app/start-mac.command`.

The first run creates a virtual environment, installs dependencies, installs
ffmpeg if it is missing, and opens the page by itself. Later runs start in a
couple of seconds.

Then, in the page:

1. **Choose Recording** — pick an `.m4a`, `.mp3`, or other audio file.
2. **Transcribe** — the transcript is written to your **Downloads** folder, named
   after the recording. Progress from the script streams into the page. On the
   first run the model (`ivrit-ai/whisper-large-v3`, several GB) downloads first
   and is reused offline afterwards.

If you have an NVIDIA GPU, install the CUDA build of torch before first use, otherwise
you will silently get the slow CPU build:

```
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## Windows notes

* Extract the ZIP first, to a short path like `C:\transcriber` — PyTorch trips
  over the 260-character path limit.
* Needs Python. The launcher offers to install it, or get 3.12 from
  [python.org](https://www.python.org/downloads/windows/) and tick **Add
  python.exe to PATH**.
* If anything fails, run the launcher again. It retries, and the window stays
  open with the error.

## Running it by hand

```
cd local_app
python app.py
```

Set `PORT` to choose a port and `NO_BROWSER=1` to stop it opening a browser. If
the port is taken, or Windows has reserved it, the app picks a free one and
prints the address it is really using.
