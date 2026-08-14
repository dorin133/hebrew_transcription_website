"""
Pre-download the model that transcribe.py uses.

Pressing "Download Model" in the web UI runs this. It makes the same
from_pretrained calls transcribe.py makes, so the weights land in the normal
Hugging Face cache and transcribe.py finds them there with nothing to fetch.

    python download_model.py           # download (or verify) the weights
    python download_model.py --check   # exit 0 if already cached, 1 otherwise
"""

import sys
from pathlib import Path

# Import MODEL_ID from transcribe.py rather than repeating it, so this helper
# can never drift out of sync with the script it is caching for.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from transcribe import MODEL_ID  # noqa: E402


def is_cached() -> bool:
    """True if the weights are already in the local Hugging Face cache."""
    from huggingface_hub import snapshot_download

    try:
        snapshot = Path(snapshot_download(MODEL_ID, local_files_only=True))
    except Exception:
        return False
    if not (snapshot / "config.json").is_file():
        return False
    # A snapshot directory can exist while the weights themselves are missing.
    return any(snapshot.glob("*.safetensors")) or any(snapshot.glob("*.bin"))


def download() -> None:
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

    print(f"Model: {MODEL_ID}")
    print("Downloading to the Hugging Face cache. This is a one-time download of")
    print("several GB; transcribe.py will reuse it from disk afterwards.\n")

    print("Fetching processor and tokenizer...")
    AutoProcessor.from_pretrained(MODEL_ID)

    print("Fetching model weights...")
    AutoModelForSpeechSeq2Seq.from_pretrained(MODEL_ID)

    print("\nDone. The model is cached and ready to use offline.")


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if is_cached() else 1)
    download()
