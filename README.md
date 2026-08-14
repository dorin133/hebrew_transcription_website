# Hebrew Transcriber — local web UI

A web page with two buttons that runs transcription on your own computer.
Nothing is uploaded anywhere!

## Setup and use

**Windows** — double-click `local_app/start-windows.bat`.
**macOS** — double-click `local_app/start-mac.command`.

The first run creates a virtual environment, installs dependencies, and opens
the page. Later runs start in a couple of seconds.

`transcribe.py` needs **ffmpeg** on your PATH to read audio. The launcher
installs it automatically if it's missing. On Windows, if it just installed ffmpeg, close the window and
double-click `start-windows.bat` again so PATH picks it up.

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
