"""Measure which speech models actually handle Persian (``fa``).

The verdict in ``app/audio/languages.py`` is not a guess: this script produces it.
For every text-to-speech model it

1. synthesises a Persian sentence,
2. transcribes the produced audio with a Persian-capable STT model (the judge),
3. scores the similarity between transcript and the original sentence.

A model that answers in English/Arabic or gibberish scores near zero, a model
with a real Persian voice scores near one. ``--kind stt`` runs the reverse test
(Persian audio -> transcript) for speech-to-text models.

Usage (from ``services/api``)::

    OPENROUTER_API_KEY=sk-or-... python ../../scripts/fa_audio_probe.py
    OPENROUTER_API_KEY=... python ../../scripts/fa_audio_probe.py --kind stt
    OPENROUTER_API_KEY=... python ../../scripts/fa_audio_probe.py --write-meta

``--write-meta`` stores the fresh verdict in ``models.meta.persian_probe`` so the
panel picks it up without a redeploy (it needs database access, i.e. run it on the
server next to ``.env``).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import difflib
import io
import json
import os
import re
import sys
import wave
from typing import Any

import httpx

API = "https://openrouter.ai/api/v1"
SAMPLE_TEXT = "سلام، این یک آزمایش تبدیل متن فارسی به گفتار است."
JUDGE = "openai/whisper-1"


def wrap_pcm(data: bytes, content_type: str) -> bytes:
    """Raw samples -> WAV (providers that only emit ``response_format=pcm``)."""
    rate = re.search(r"rate=(\d+)", content_type)
    channels = re.search(r"channels=(\d+)", content_type)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(int(channels.group(1)) if channels else 1)
        handle.setsampwidth(2)
        handle.setframerate(int(rate.group(1)) if rate else 24000)
        handle.writeframes(data)
    return buffer.getvalue()


def normalise(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").replace("\u200c", " ")).split())


def similarity(expected: str, heard: str) -> float:
    return difflib.SequenceMatcher(None, normalise(expected), normalise(heard)).ratio()


def level_of(score: float) -> str:
    if score >= 0.95:
        return "verified"
    if score >= 0.80:
        return "good"
    if score >= 0.50:
        return "weak"
    return "none"


async def speech_catalog(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    """TTS + STT models with their supported voices (OpenRouter only lists them this way)."""
    catalog: dict[str, Any] = {"tts": [], "stt": []}
    for modality, kind in (("speech", "tts"), ("transcription", "stt")):
        response = await client.get(
            f"{API}/models", params={"output_modalities": modality}, headers=headers
        )
        response.raise_for_status()
        catalog[kind] = response.json().get("data") or []
    return catalog


async def synthesise(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    model: dict[str, Any],
    text: str,
) -> tuple[bytes, str]:
    """Return (audio bytes, format) for one TTS model, retrying the format it demands."""
    voices = model.get("supported_voices") or []
    body: dict[str, Any] = {"model": model["id"], "input": text, "response_format": "mp3"}
    if voices:
        body["voice"] = voices[0]
    response = await client.post(f"{API}/audio/speech", json=body, headers=headers)
    fmt = "mp3"
    if response.status_code >= 400 and "response_format" in response.text:
        wanted = re.search(r'response_format\s*=?\s*\\?"?([a-z0-9]{3,5})', response.text)
        if wanted:
            fmt = wanted.group(1).lower()
            body["response_format"] = fmt
            response = await client.post(f"{API}/audio/speech", json=body, headers=headers)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    data = response.content
    if content_type.startswith("audio/pcm"):
        return wrap_pcm(data, content_type), "wav"
    if content_type.startswith("audio/wav"):
        return data, "wav"
    if content_type.startswith("audio/ogg"):
        return data, "ogg"
    return data, fmt


async def transcribe(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    model: str,
    data: bytes,
    fmt: str,
) -> str:
    response = await client.post(
        f"{API}/audio/transcriptions",
        json={
            "model": model,
            "input_audio": {"data": base64.b64encode(data).decode(), "format": fmt},
        },
        headers=headers,
    )
    if response.status_code >= 400:
        return f"<error {response.status_code}: {response.text[:60]}>"
    return str(response.json().get("text") or "")

async def probe_tts(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    models: list[dict[str, Any]],
    text: str,
    judge: str,
) -> tuple[list[dict[str, Any]], tuple[bytes, str] | None]:
    results: list[dict[str, Any]] = []
    reference: tuple[bytes, str] | None = None
    for model in models:
        model_id = model["id"]
        try:
            data, fmt = await synthesise(client, headers, model, text)
            if reference is None:
                reference = (data, fmt)
            heard = await transcribe(client, headers, judge, data, fmt)
            results.append(
                {"id": model_id, "score": round(similarity(text, heard), 2), "heard": heard[:70]}
            )
        except Exception as exc:  # noqa: BLE001 - a probe failure is data too
            results.append({"id": model_id, "score": None, "heard": f"<{exc}>"[:70]})
    return results, reference


async def probe_stt(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    models: list[dict[str, Any]],
    reference: tuple[bytes, str],
    text: str,
) -> list[dict[str, Any]]:
    data, fmt = reference
    results: list[dict[str, Any]] = []
    for model in models:
        model_id = model["id"]
        try:
            heard = await transcribe(client, headers, model_id, data, fmt)
            results.append(
                {"id": model_id, "score": round(similarity(text, heard), 2), "heard": heard[:70]}
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"id": model_id, "score": None, "heard": f"<{exc}>"[:70]})
    return results


async def persist(results: list[dict[str, Any]]) -> int:
    """Write ``models.meta.persian_probe`` (needs the API's .env and database)."""
    from sqlalchemy import select

    from app.audio.languages import PROBE_METHOD
    from app.db.models import Model
    from app.db.session import session_scope

    written = 0
    async with session_scope(bypass_rls=True) as db:
        for row in results:
            if row["score"] is None:
                continue
            model = (
                (await db.execute(select(Model).where(Model.external_id == row["id"])))
                .scalars()
                .first()
            )
            if model is None:
                continue
            model.meta = {
                **(model.meta or {}),
                "persian_probe": {
                    "level": level_of(row["score"]),
                    "score": row["score"],
                    "method": PROBE_METHOD,
                },
            }
            written += 1
        await db.flush()
    return written


def write_json(path: str, payload: dict[str, Any]) -> None:
    """Blocking write, kept out of the event loop (and out of ``async def``)."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def print_table(title: str, results: list[dict[str, Any]]) -> None:
    print(f"\n== {title} ==")
    for row in sorted(results, key=lambda item: -(item["score"] or 0)):
        score = "err " if row["score"] is None else f"{row['score']:.2f}"
        level = "?" if row["score"] is None else level_of(row["score"])
        print(f"{score}  {level:8s}  {row['id']:44s}  {row['heard']}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("tts", "stt", "both"), default="both")
    parser.add_argument("--models", nargs="*", help="only probe these external ids")
    parser.add_argument("--text", default=SAMPLE_TEXT)
    parser.add_argument("--judge", default=JUDGE)
    parser.add_argument("--json", dest="json_path", help="write raw results here")
    parser.add_argument("--write-meta", action="store_true", help="store verdicts in the database")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("OPENROUTER_API_KEY is required", file=sys.stderr)
        return 2
    headers = {"Authorization": f"Bearer {api_key}"}
    payload: dict[str, Any] = {"text": args.text}

    async with httpx.AsyncClient(timeout=180.0) as client:
        catalog = await speech_catalog(client, headers)
        tts_models = catalog["tts"]
        stt_models = catalog["stt"]
        if args.models:
            wanted = set(args.models)
            tts_models = [row for row in tts_models if row["id"] in wanted]
            stt_models = [row for row in stt_models if row["id"] in wanted]

        reference: tuple[bytes, str] | None = None
        if args.kind in ("tts", "both"):
            tts_results, reference = await probe_tts(
                client, headers, tts_models, args.text, args.judge
            )
            payload["tts"] = tts_results
            print_table("text -> speech (Persian)", tts_results)
        if args.kind in ("stt", "both"):
            if reference is None:
                # STT needs Persian audio: synthesise one with a known-good model
                source = next(
                    row for row in catalog["tts"] if row["id"] == "elevenlabs/eleven-v3"
                )
                reference = await synthesise(client, headers, source, args.text)
            stt_results = await probe_stt(client, headers, stt_models, reference, args.text)
            payload["stt"] = stt_results
            print_table("speech -> text (Persian)", stt_results)

    if args.json_path:
        write_json(args.json_path, payload)
        print(f"\nwrote {args.json_path}")
    if args.write_meta:
        flat = [row for key in ("tts", "stt") for row in payload.get(key, [])]
        print(f"updated {await persist(flat)} models")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

