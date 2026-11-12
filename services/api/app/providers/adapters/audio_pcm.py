"""Wrap raw PCM audio from a TTS provider into a playable WAV container.

Some speech models (``google/gemini-*-tts``, ``heygen/*`` …) only emit
``response_format="pcm"``: header-less 16-bit samples plus a content type such as
``audio/pcm;rate=24000;channels=1``. Browsers cannot play that, so the adapter
wraps it in a WAV header before returning it to the caller.
"""

from __future__ import annotations

import io
import re
import wave

#: Used when the provider does not advertise its PCM layout.
DEFAULT_RATE = 24000
DEFAULT_CHANNELS = 1

#: 16-bit signed little-endian samples (what every probed provider returned).
SAMPLE_WIDTH = 2

_RATE_RE = re.compile(r"rate=(\d+)", re.IGNORECASE)
_CHANNELS_RE = re.compile(r"channels=(\d+)", re.IGNORECASE)


def pcm_layout(content_type: str | None) -> tuple[int, int]:
    """``(sample_rate, channels)`` parsed from ``audio/pcm;rate=24000;channels=1``."""
    rate, channels = DEFAULT_RATE, DEFAULT_CHANNELS
    if content_type:
        found_rate = _RATE_RE.search(content_type)
        if found_rate:
            rate = int(found_rate.group(1))
        found_channels = _CHANNELS_RE.search(content_type)
        if found_channels:
            channels = int(found_channels.group(1))
    return rate, max(1, channels)


def to_wav(data: bytes, content_type: str | None = None) -> bytes:
    """Return ``data`` as a WAV file (already-WAV input is passed through)."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return data
    rate, channels = pcm_layout(content_type)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(SAMPLE_WIDTH)
        handle.setframerate(rate)
        handle.writeframes(data)
    return buffer.getvalue()
