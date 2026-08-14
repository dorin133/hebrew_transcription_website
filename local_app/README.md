# Hebrew Transcriber — local web UI

A web page with three buttons that runs `transcribe.py` on your own computer.
Nothing is uploaded anywhere; the page is served by a small Flask server
running on your machine.

## Setup and use

**Windows** — double-click `start-windows.bat`.
**macOS** — double-click `start-mac.command`.

The first run creates a virtual environment, installs dependencies, and opens
the page at <http://127.0.0.1:8000>. Later runs start in a couple of seconds.

`transcribe.py` needs **ffmpeg** on your PATH to read audio. The launcher
installs it automatically if it's missing (via winget on Windows, Homebrew on
macOS). On Windows, if it just installed ffmpeg, close the window and
double-click `start-windows.bat` again so PATH picks it up.

Then, in the page:

1. **Choose Recording** — pick an `.m4a`, `.mp3`, or other audio file.
2. **Download Model** — fetches `ivrit-ai/whisper-large-v3` into the Hugging
   Face cache. Several GB, once; reused offline afterwards. Skippable — step 3
   downloads it if you have not.
3. **Transcribe** — the transcript is written to your **Downloads** folder, named
   after the recording. Progress from the script streams into the page.

If you have an NVIDIA GPU, install the CUDA build of torch before first use, or
you will silently get the slow CPU build:

```
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu121
```
