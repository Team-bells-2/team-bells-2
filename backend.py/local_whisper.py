from __future__ import annotations

import os
import importlib
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any


AUDIO_SUFFIXES = {
    "audio/flac": ".flac",
    "audio/m4a": ".m4a",
	"audio/mp4": ".m4a",
    "audio/mp3": ".mp3",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/x-m4a": ".m4a",
    "audio/x-wav": ".wav",
    "application/octet-stream": ".wav",
}


@lru_cache(maxsize=2)
def _load_model(model_name: str) -> Any:
    try:
        whisper = importlib.import_module("whisper")
    except ImportError as error:
        raise RuntimeError(
            "Local Whisper is not installed. Install the optional requirements-whisper.txt and ffmpeg."
        ) from error
    download_root = os.getenv("WHISPER_CACHE_DIR")
    return whisper.load_model(model_name, device="cpu", download_root=download_root)


def transcribe_audio(
    audio_bytes: bytes,
    content_type: str,
    language: str | None = None,
) -> dict[str, str | None]:
    """Transcribe a bounded audio upload using the local open-source Whisper model."""
    suffix = AUDIO_SUFFIXES.get(content_type.casefold().split(";", maxsplit=1)[0].strip())
    if suffix is None:
        raise ValueError("Unsupported audio type. Use WAV, MP3, M4A, WebM, OGG, or FLAC.")
    if not audio_bytes:
        raise ValueError("Audio upload is empty.")

    model_name = os.getenv("WHISPER_MODEL", "base")
    model = _load_model(model_name)
    with tempfile.NamedTemporaryFile(suffix=suffix) as audio_file:
        audio_file.write(audio_bytes)
        audio_file.flush()
        result = model.transcribe(
            str(Path(audio_file.name)),
            language=language,
            task="transcribe",
            fp16=False,
            initial_prompt=(
                "Nigerian market business conversation. Product names include rice, beans, garri, "
                "tomatoes, palm oil. Money may be in naira or k shorthand. Preserve names and quantities."
            ),
        )
    return {
        "text": str(result.get("text", "")).strip(),
        "language": result.get("language"),
        "model": model_name,
    }
