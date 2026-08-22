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

* Get the code with **Code → Download ZIP** and **extract it** before running
  anything. Batch files do not run from inside a zip preview window.
* Put the folder somewhere with a short path, such as `C:\transcriber`.
  Installing PyTorch under a long path can hit the 260-character limit.
* Windows may warn that the file came from the internet. Choose **More info →
  Run anyway**, or untick *Blocked* in the file's Properties.
* Python is not installed by default. The launcher offers to install it with
  `winget`, or get it from [python.org](https://www.python.org/downloads/windows/)
  and tick **Add python.exe to PATH**. Python 3.12 is the safest choice.
* If the launcher reports that PyTorch will not load, install the
  [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).
* If setup fails part way through, just run the launcher again — it retries the
  installation rather than starting a half-installed app.
* The window stays open on failure so you can read the error. If it closes
  instantly anyway, run `local_app\start-windows.bat` from a `cmd` window to keep
  the output.

## Running it by hand

```
cd local_app
python app.py
```

Set `PORT` to choose a port and `NO_BROWSER=1` to stop it opening a browser. If
the port is taken, or Windows has reserved it, the app picks a free one and
prints the address it is really using.
