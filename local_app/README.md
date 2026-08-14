# Hebrew Transcriber — local web UI

A web page with three buttons that runs **the real `transcribe.py`** on your own
computer. Nothing is uploaded anywhere; the page is served by a small Flask
server running on your machine, and the transcription is the same command you
would otherwise type by hand.

Works on Windows and macOS.

## Setup and use

**Windows** — double-click `start-windows.bat`.
**macOS** — double-click `start-mac.command`.

The first run creates a virtual environment, installs dependencies, and opens
the page at <http://127.0.0.1:8000>. Later runs start in a couple of seconds.

You also need **ffmpeg** on your PATH, which `transcribe.py` uses to read audio.
The launcher warns you if it is missing:

```
Windows:  winget install Gyan.FFmpeg      (then open a new terminal)
macOS:    brew install ffmpeg
```

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

## What it actually runs

Nothing about the transcription is reimplemented here. Pressing **Transcribe**
runs, as a subprocess with the same Python interpreter serving the page:

```
python transcribe.py <your recording> --out "<Downloads>/<name>.txt" --language he
```

`transcribe.py` is used unmodified, at `../transcribe.py`. Same model, same
`torch_dtype`, same beam search, same sequential long-form decoding, same output.
Set the `TRANSCRIBE_SCRIPT` environment variable to point somewhere else.

**Download Model** runs `download_model.py`, which imports `MODEL_ID` from
`transcribe.py` — rather than repeating the string, so the two cannot drift — and
makes the same `AutoProcessor.from_pretrained` / 
`AutoModelForSpeechSeq2Seq.from_pretrained` calls. The weights land in the
ordinary Hugging Face cache, so `transcribe.py` finds them there with nothing
left to fetch, whether you run it from this page or from a terminal.

## Sharing it with others

Put this folder in a GitHub repo and tell people to download it and double-click
their platform's launcher. It cannot be hosted as a public web page: a page
served from the internet runs inside the browser sandbox, which cannot start
`python`, run `ffmpeg`, or write to your Downloads folder. Running locally is
what makes those things possible.

## Security

The server binds to `127.0.0.1` only, so it is not reachable from your network.
It runs `transcribe.py` on files you choose through the picker; uploads are
written to a temp directory and referenced by an opaque id, so the browser never
supplies a filesystem path. Do not expose this to a network or the internet — it
is a local tool by design.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Flask server; serves the page and runs the scripts |
| `download_model.py` | Pre-populates the Hugging Face cache for `transcribe.py` |
| `templates/index.html` | The three buttons |
| `static/app.js` | Uploads, streams script output, shows the transcript |
| `static/style.css` | Styling |
| `start-windows.bat`, `start-mac.command` | One-click setup and launch |

## Not to be confused with `../docs/`

`docs/` holds an earlier, different approach: a static page hostable on GitHub
Pages that runs a quantized ONNX model in the browser. It needs no install and
can be shared as a plain URL, but it uses `whisper-large-v3-turbo` at 4-bit
precision, not the `whisper-large-v3` that `transcribe.py` uses, so transcripts
are lower quality. Use this folder for quality, `docs/` for convenience.
