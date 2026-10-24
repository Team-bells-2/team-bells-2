from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.shared.env import settings

# Explicit allow-list: an unknown or generic type (e.g. application/octet-stream) is rejected,
# never guessed, so a mislabelled upload cannot be decoded as the wrong format.
SUPPORTED_AUDIO_TYPES: dict[str, str] = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/flac": "flac",
}


class TranscriptionError(Exception):
    """The speech-to-text provider failed or returned no text."""


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, content_type: str) -> str: ...


class OpenAICompatibleTranscriber:
    """Calls any OpenAI-compatible /audio/transcriptions endpoint: the local whisper.cpp
    server today, an online provider later, chosen by .env alone."""

    def __init__(self, base_url: str, inference_path: str, api_key: str, model: str, timeout_seconds: float):
        self.url = f"{base_url.rstrip('/')}/{inference_path.lstrip('/')}"
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def transcribe(self, audio: bytes, content_type: str) -> str:
        extension = SUPPORTED_AUDIO_TYPES[content_type]
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = httpx.post(
                self.url,
                headers=headers,
                files={"file": (f"voice.{extension}", audio, content_type)},
                data={"model": self.model, "response_format": "json"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body: dict[str, Any] = response.json()
        except httpx.HTTPError as error:
            raise TranscriptionError(f"Transcription request failed: {type(error).__name__}") from error
        except ValueError as error:
            raise TranscriptionError("Transcription provider returned a malformed response.") from error

        text = str(body.get("text", "")).strip()
        if not text:
            raise TranscriptionError("No speech was recognised in the voice note.")
        return text


@lru_cache(maxsize=1)
def get_transcriber() -> Transcriber:
    return OpenAICompatibleTranscriber(
        base_url=settings.STT_BASE_URL,
        inference_path=settings.STT_INFERENCE_PATH,
        api_key=settings.STT_API_KEY,
        model=settings.STT_MODEL,
        timeout_seconds=settings.STT_TIMEOUT_SECONDS,
    )
