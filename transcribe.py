"""
Standalone Hebrew long-form transcriber using ivrit-ai/whisper-large-v3.

Self-contained: does not depend on any repo layout. Give it an audio file and
it writes a .txt next to it (or to --out).

Requirements:
    pip install torch transformers numpy
    ffmpeg installed and on PATH  (e.g. `brew install ffmpeg`)

Usage:
    python transcribe_standalone.py recording.m4a
    python transcribe_standalone.py recording.mp3 --out transcript.txt
    python transcribe_standalone.py recording.wav --language en
"""

import argparse
import subprocess
import warnings
from pathlib import Path

import numpy as np
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq

warnings.filterwarnings("ignore")

MODEL_ID = "ivrit-ai/whisper-large-v3"
TARGET_SR = 16000
WINDOW_S = 30       # each decode window covers up to 30s of audio
PRINT_EVERY_S = 60  # print a progress line roughly every 60s of processed audio


def load_audio(path):
    """Decode any audio/video file to mono 16 kHz float32 samples via ffmpeg."""
    proc = subprocess.run(
        [
            "ffmpeg", "-nostdin", "-loglevel", "error",
            "-i", str(path),
            "-f", "s16le", "-ac", "1", "-ar", str(TARGET_SR),
            "-",
        ],
        check=True,
        capture_output=True,
    )
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe a long audio recording with ivrit-ai/whisper-large-v3."
    )
    parser.add_argument("audio", help="Path to the input audio/video file.")
    parser.add_argument("--out", default=None,
                        help="Output .txt path (default: same name as input, .txt extension).")
    parser.add_argument("--language", default="he",
                        help="Language code (default: he for Hebrew).")
    parser.add_argument("--device", default=None, choices=["cuda", "mps", "cpu"],
                        help="Force a device (default: best available).")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        raise SystemExit(f"Input file not found: {audio_path}")
    output_path = Path(args.out) if args.out else audio_path.with_suffix(".txt")

    device = args.device or ("mps" if torch.backends.mps.is_available() else (
        "cuda" if torch.cuda.is_available() else "cpu"))
    # fp16 only on CUDA. Whisper in fp16 on Apple's MPS backend returns empty or
    # repeated text, so MPS runs in fp32 despite the extra memory.
    dtype = torch.float16 if device == "cuda" else torch.float32

    print(f"Loading model {MODEL_ID} on {device} ({dtype})...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(MODEL_ID, torch_dtype=dtype)
    model.generation_config.forced_decoder_ids = None
    model.to(device)

    print(f"Loading audio: {audio_path}")
    audio = load_audio(audio_path)
    total_seconds = len(audio) / TARGET_SR
    print(f"Audio duration: {total_seconds / 60:.2f} min")

    # A silent or near-silent decode is the usual reason for an empty transcript,
    # so report the signal level before spending minutes on inference.
    peak = float(np.abs(audio).max()) if len(audio) else 0.0
    rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
    print(f"Signal level: peak {peak:.4f}, rms {rms:.4f}")
    if len(audio) == 0:
        raise SystemExit("ffmpeg produced no audio. Is this really an audio file?")
    if peak < 0.001:
        print("WARNING: this audio is effectively silent. Expect an empty transcript.")
    if total_seconds < 1:
        print("WARNING: audio is under a second long, too short to transcribe reliably.")

    inputs = processor(
        audio,
        sampling_rate=TARGET_SR,
        return_tensors="pt",
        truncation=False,
        padding="longest",
        return_attention_mask=True,
    )
    inputs = {k: v.to(device, dtype=dtype if v.dtype.is_floating_point else v.dtype)
              for k, v in inputs.items()}

    # Progress reporting: the encoder runs once per ~30s window. We count windows
    # to estimate how much audio has been processed and print time remaining.
    state = {"windows": 0, "next_print_s": PRINT_EVERY_S}

    def on_encoder(_module, _inputs, _output):
        state["windows"] += 1
        processed_s = min(state["windows"] * WINDOW_S, total_seconds)
        pct_done = min(99.0, 100 * processed_s / total_seconds)
        if pct_done < 99.0 and processed_s >= state["next_print_s"]:
            pct_left = 100 - pct_done
            print(f"  ~{processed_s:.0f}s / {total_seconds:.0f}s  "
                  f"({pct_done:.0f}% done, {pct_left:.0f}% left)")
            state["next_print_s"] += PRINT_EVERY_S

    hook = model.model.encoder.register_forward_hook(on_encoder)

    print("Transcribing (sequential long-form, conditioned on previous text)...")
    try:
        with torch.no_grad():
            pred_ids = model.generate(
                **inputs,
                language=args.language,
                task="transcribe",
                return_timestamps=True,
                condition_on_prev_tokens=True,
                compression_ratio_threshold=1.35,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6,
                temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
                num_beams=5,
            )
    finally:
        hook.remove()

    text = processor.batch_decode(
        pred_ids, skip_special_tokens=True, decode_with_timestamps=False)[0].strip()

    if text:
        print(f"\n--- transcription ({len(text)} chars) ---")
        print(text)
        print("--- end transcription ---\n")
    else:
        print("\nWARNING: the model returned no text.")
        print("The transcript file will be empty. Common causes:")
        print("  - the recording is silent, or speech is very quiet")
        print("  - the clip is only a few seconds long")
        print("  - --language does not match what is actually spoken")
        print("  - fp16 numerical issues; retry with --device cpu\n")

    output_path.write_text(text + "\n", encoding="utf-8")
    print(f"Done. Wrote transcription to {output_path}")


if __name__ == "__main__":
    main()
