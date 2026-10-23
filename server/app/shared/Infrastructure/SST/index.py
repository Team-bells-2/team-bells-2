from __future__ import annotations

import logging

import httpx

from app.shared.env import settings

logger = logging.getLogger(__name__)


def transcribe(audio: bytes, filename: str) -> str | None:
    """Speech-to-text for voice notes. Returns None when transcription is unavailable or fails."""
    if settings.DEMO_MODE or not settings.OPENAI_API_KEY or not audio:
        return None
    try:
        response = httpx.post(
            f"{settings.OPENAI_BASE_URL.rstrip('/')}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            data={"model": settings.OJA_STT_MODEL},
            files={"file": (filename, audio)},
            timeout=settings.LLM_TIMEOUT_SECONDS * 2,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        logger.warning("Transcription failed: %s", error)
        return None
    text = response.json().get("text", "")
    return text.strip() or None
