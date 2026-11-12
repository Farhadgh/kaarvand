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
    # --- OpenRouter (namespaced ids; per-second STT and per-character TTS prices
    # from https://openrouter.ai/api/v1/models?output_modalities=transcription|speech)
    {
        "slug": "openrouter/whisper-1",
        "external_id": "openai/whisper-1",
        "label_fa": "ویسپر (OpenRouter، گفتار به متن)",
        "kind": "stt",
        "audio_input_price": "0.006",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/whisper-large-v3-turbo",
        "external_id": "openai/whisper-large-v3-turbo",
        "label_fa": "Whisper large-v3 turbo (OpenRouter، سریع و ارزان)",
        "kind": "stt",
        "audio_input_price": "0.0002",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/nova-3",
        "external_id": "deepgram/nova-3",
        "label_fa": "Deepgram Nova-3 (OpenRouter، گفتار به متن)",
        "kind": "stt",
        "audio_input_price": "0.0043",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/scribe-v2",
        "external_id": "elevenlabs/scribe-v2",
        "label_fa": "ElevenLabs Scribe v2 (OpenRouter)",
        "kind": "stt",
        "audio_input_price": "0.00366667",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/qwen3-asr",
        "external_id": "qwen/qwen3-asr-1.7b",
        "label_fa": "Qwen3 ASR 1.7B (OpenRouter، ارزان)",
        "kind": "stt",
        "audio_input_price": "0.00045",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/voxtral-mini-transcribe",
        "external_id": "mistralai/voxtral-mini-transcribe",
        "label_fa": "Voxtral mini Transcribe (OpenRouter)",
        "kind": "stt",
        "audio_input_price": "0.003",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/eleven-v3",
        "external_id": "elevenlabs/eleven-v3",
        "label_fa": "ElevenLabs v3 (OpenRouter، متن به گفتار)",
        "kind": "tts",
        "audio_output_price": "0.08",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/aura-2",
        "external_id": "deepgram/aura-2",
        "label_fa": "Deepgram Aura-2 (OpenRouter)",
        "kind": "tts",
        "audio_output_price": "0.03",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/gemini-flash-tts",
        "external_id": "google/gemini-3.8-flash-tts",
        "label_fa": "Gemini Flash TTS (OpenRouter، ارزان)",
        "kind": "tts",
        "audio_output_price": "0.0005",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/kokoro-82m",
        "external_id": "hexgrad/kokoro-82m",
        "label_fa": "Kokoro 82M (OpenRouter، بسیار ارزان)",
        "kind": "tts",
        "audio_output_price": "0.00062",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/speech-2.8-hd",
        "external_id": "minimax/speech-2.8-hd",
        "label_fa": "MiniMax Speech 2.8 HD (OpenRouter)",
        "kind": "tts",
        "audio_output_price": "0.1",
        "vendor_hint": "openrouter",
    },
    {
        "slug": "openrouter/qwen-audio-3-tts-flash",
        "external_id": "qwen/qwen-audio-3.0-tts-flash",
        "label_fa": "Qwen Audio 3.0 TTS Flash (OpenRouter)",
        "kind": "tts",
        "audio_output_price": "0.015",
        "vendor_hint": "openrouter",
    },
]
