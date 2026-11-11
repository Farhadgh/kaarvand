"""Ready-made audio model presets.

A provider's ``/models`` list sometimes omits speech models (or lists them
without prices). These presets let an operator add a working audio model in one
click; prices are USD list prices and can be edited per org afterwards.
"""

from __future__ import annotations

from typing import Any

AUDIO_PRESETS: list[dict[str, Any]] = [
    {
        "slug": "whisper-1",
        "external_id": "whisper-1",
        "label_fa": "ویسپر (گفتار به متن، همه‌کاره)",
        "kind": "stt",
        "audio_input_price": "0.006",  # USD per minute
        "vendor_hint": "openai",
    },
    {
        "slug": "gpt-4o-transcribe",
        "external_id": "gpt-4o-transcribe",
        "label_fa": "GPT-4o Transcribe (دقت بالا، فارسی خوب)",
        "kind": "stt",
        "audio_input_price": "0.006",
        "vendor_hint": "openai",
    },
    {
        "slug": "gpt-4o-mini-transcribe",
        "external_id": "gpt-4o-mini-transcribe",
        "label_fa": "GPT-4o mini Transcribe (ارزان‌تر)",
        "kind": "stt",
        "audio_input_price": "0.003",
        "vendor_hint": "openai",
    },
    {
        "slug": "tts-1",
        "external_id": "tts-1",
        "label_fa": "TTS-1 (متن به گفتار، سریع)",
        "kind": "tts",
        "audio_output_price": "0.015",  # USD per 1K characters
        "vendor_hint": "openai",
    },
    {
        "slug": "tts-1-hd",
        "external_id": "tts-1-hd",
        "label_fa": "TTS-1 HD (کیفیت بالاتر)",
        "kind": "tts",
        "audio_output_price": "0.03",
        "vendor_hint": "openai",
    },
    {
        "slug": "gpt-4o-mini-tts",
        "external_id": "gpt-4o-mini-tts",
        "label_fa": "GPT-4o mini TTS (قابل هدایت با پرامپت)",
        "kind": "tts",
        "audio_output_price": "0.015",
        "vendor_hint": "openai",
    },
]
