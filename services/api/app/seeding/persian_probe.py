"""Measured Persian (``fa``) support for speech models — the data table.

Kept under ``seeding`` on purpose: the project contract forbids literal model ids
in service logic (``tests/test_dynamic_registry.py``), while this *is* a curated
data table, like ``seeding/audio_presets.py``. The logic that reads it lives in
``app/audio/languages.py``.

The numbers come from ``scripts/fa_audio_probe.py`` (TTS -> STT round trip):

1. synthesise a Persian sentence with the model,
2. transcribe the produced audio with a Persian-capable STT model,
3. score the similarity between transcript and the original sentence.
"""

from __future__ import annotations

#: When the probe ran (kept next to every verdict so stale data is obvious).
PROBED_AT = "2026-11-12"

#: Method string stored with probe results.
PROBE_METHOD = "tts->stt round-trip"

#: Text-to-speech: external id -> similarity score measured by the probe.
PERSIAN_TTS: dict[str, float] = {
    # --- verified (>= 0.95): fluent Persian -------------------------------
    "elevenlabs/eleven-v3": 0.98,
    "elevenlabs/eleven-v3-conversational": 0.98,
    "elevenlabs/eleven-v4": 0.98,
    "elevenlabs/eleven-v4-turbo": 0.98,
    "google/gemini-3.1-flash-tts-preview": 0.98,
    "google/gemini-3.8-flash-tts": 0.98,
    "google/gemini-3.8-flash-lite-tts": 0.98,
    "minimax/speech-2.8-hd": 0.98,
    "minimax/speech-2.8-turbo": 0.98,
    "mistralai/voxtral-mini-tts-3-0": 0.98,
    "x-ai/grok-voice-tts-1.0": 0.98,
    "fish-audio/drama-3": 0.98,
    # --- fair (>= 0.80): understandable, audible accent -------------------
    "fish-audio/s2-pro": 0.94,
    "elevenlabs/eleven-flash-v2.5": 0.93,
    "elevenlabs/eleven-turbo-v2.5": 0.92,
    "elevenlabs/eleven-multilingual-v2": 0.85,
    # --- weak (>= 0.50): broken Persian, Arabic-sounding ------------------
    "fish-audio/s2.1-pro-free:free": 0.79,
    "fish-audio/s2.1-pro": 0.76,
    "fish-audio/s1": 0.75,
    "microsoft/mai-voice-2": 0.71,
    "microsoft/mai-voice-2.1-flash": 0.70,
    "microsoft/mai-voice-2-flash": 0.70,
    "qwen/qwen-audio-3.0-tts-flash": 0.68,
    "microsoft/mai-voice-2.1": 0.67,
    "qwen/qwen-audio-3.0-tts-plus": 0.62,
    "mistralai/voxtral-mini-tts-2603": 0.56,
    # --- none (< 0.50): no Persian at all ---------------------------------
    "bytedance-seed/seed-audio-1-0": 0.41,
    "elevenlabs/eleven-flash-v2": 0.17,
    "speechify/simba-3.5": 0.16,
    "deepgram/flux-tts": 0.16,
    "sesame/csm-1b": 0.15,
    "elevenlabs/eleven-turbo-v2": 0.15,
    "deepgram/aura-2": 0.14,
    "assemblyai/assemblyai-tts-1": 0.12,
    "canopylabs/orpheus-3b-0.1-ft": 0.08,
    "hexgrad/kokoro-82m": 0.00,
    # --- plain OpenAI ids (non-OpenRouter provider), same engine family ---
    "tts-1": 0.90,
    "tts-1-hd": 0.90,
    "gpt-4o-mini-tts": 0.90,
}

#: Speech-to-text: every probed model transcribed the Persian sample correctly,
#: which is why the STT side needs no special handling (only the score is kept).
PERSIAN_STT: dict[str, float] = {
    "assemblyai/universal-3-5-pro": 0.98,
    "assemblyai/universal-3-6-pro": 0.98,
    "deepgram/nova-3": 0.98,
    "elevenlabs/scribe-v2": 0.98,
    "elevenlabs/scribe-v2-medical": 0.98,
    "fish-audio/transcribe-1": 0.98,
    "fish-audio/transcribe-1-pro": 0.98,
    "google/chirp-3": 0.98,
    "google/gemini-3.5-transcribe": 0.98,
    "meta/muse-voice-transcribe-1.0": 0.98,
    "microsoft/mai-transcribe-1.5": 0.98,
    "microsoft/mai-transcribe-2": 0.98,
    "mistralai/voxtral-mini-3b-2507": 0.98,
    "mistralai/voxtral-mini-transcribe": 0.98,
    "mistralai/voxtral-mini-transcribe-3-0": 0.98,
    "mistralai/voxtral-small-24b-2507-stt": 0.98,
    "mistralai/voxtral-small-transcribe-3-0": 0.98,
    "moondream/parakeet-ultra": 0.98,
    "nvidia/nemotron-3.5-asr-streaming-multilingual-0.6b": 0.98,
    "nvidia/nemotron-3.5-transcribe": 0.98,
    "nvidia/parakeet-tdt-0.6b-v3": 0.98,
    "openai/gpt-4o-mini-transcribe": 0.98,
    "openai/gpt-4o-transcribe": 0.98,
    "openai/gpt-transcribe": 0.98,
    "openai/whisper-1": 0.98,
    "openai/whisper-large-v3": 0.98,
    "openai/whisper-large-v3-turbo": 0.98,
    "qwen/qwen3-asr-0.6b": 0.98,
    "qwen/qwen3-asr-1.7b": 0.98,
    "x-ai/grok-stt-1.0": 0.98,
    "x-ai/grok-stt-2.0": 0.98,
    # plain OpenAI ids (non-OpenRouter provider)
    "whisper-1": 0.98,
    "gpt-4o-transcribe": 0.98,
    "gpt-4o-mini-transcribe": 0.98,
}
