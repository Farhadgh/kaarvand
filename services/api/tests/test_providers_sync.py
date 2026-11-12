"""Model/price synchronisation (HTTP mocked with respx)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import httpx
import respx

MODELS_PAYLOAD = {
    "object": "list",
    "data": [
        {"id": "test-vision-vl-1", "owned_by": "test", "context_length": 128000},
        {"id": "test-chat-mini", "owned_by": "test"},
        {"id": "test-embedding-3-small", "owned_by": "test"},
    ],
}

OPENROUTER_PAYLOAD = {
    "data": [{"id": "openai/gpt-x", "pricing": {"prompt": "0.0000015", "completion": "0.000006"}}]
}

# speech models: OpenRouter flags them through architecture.output_modalities
OPENROUTER_AUDIO_PAYLOAD = {
    "data": [
        {
            "id": "openai/whisper-1",
            "pricing": {"prompt": "0.0001", "completion": "0"},
            "architecture": {
                "modality": "audio->transcription",
                "input_modalities": ["audio"],
                "output_modalities": ["transcription"],
            },
        },
        {
            "id": "elevenlabs/eleven-v3",
            "pricing": {"prompt": "0.00008", "completion": "0"},
            "architecture": {
                "modality": "text->speech",
                "input_modalities": ["text"],
                "output_modalities": ["speech"],
            },
        },
        {
            "id": "google/gemini-2.5-flash",
            "pricing": {"prompt": "0.0000003", "completion": "0.0000025"},
            "architecture": {
                "modality": "text+image+audio->text",
                "input_modalities": ["text", "image", "audio"],
                "output_modalities": ["text"],
            },
        },
    ]
}

BASE = "https://api.test.local/v1"


async def _create(client: Any, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": f"provider-{uuid.uuid4().hex[:6]}",
        "kind": "openai_compatible",
        "base_url": BASE,
        "api_key": "sk-test-key-abcd",
    }
    payload.update(overrides)
    response = await client.post("/v1/providers", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@respx.mock
async def test_sync_models_infers_capabilities(client: Any, auth_headers: dict[str, str]) -> None:
    provider = await _create(client, auth_headers)
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))

    response = await client.post(
        f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"created": 3, "updated": 0, "total": 3}

    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=auth_headers)
    ).json()
    by_id = {model["external_id"]: model for model in models}

    assert by_id["test-vision-vl-1"]["supports_vision"] is True
    assert by_id["test-vision-vl-1"]["supports_tools"] is True
    assert by_id["test-vision-vl-1"]["context_window"] == 128000
    assert by_id["test-embedding-3-small"]["supports_tools"] is False
    assert by_id["test-embedding-3-small"]["supports_stream"] is False


@respx.mock
async def test_sync_models_is_idempotent(client: Any, auth_headers: dict[str, str]) -> None:
    provider = await _create(client, auth_headers)
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))

    first = await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers)
    second = await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers)
    assert first.json()["created"] == 3
    assert second.json() == {"created": 0, "updated": 3, "total": 3}


@respx.mock
async def test_sync_prices_from_provider_payload(client: Any, auth_headers: dict[str, str]) -> None:
    provider = await _create(
        client,
        auth_headers,
        kind="openrouter",
        base_url="https://openrouter.ai/api/v1",
        prices_url="https://openrouter.ai/api/v1/models",
    )
    respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(200, json=OPENROUTER_PAYLOAD)
    )

    await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers)
    prices = await client.post(f"/v1/providers/{provider['id']}/sync-prices", headers=auth_headers)
    assert prices.status_code == 200, prices.text
    assert prices.json()["updated"] == 1
    assert prices.json()["source"] == "provider"

    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=auth_headers)
    ).json()
    model = models[0]
    assert Decimal(str(model["input_price"])) == Decimal("0.0000015")
    assert Decimal(str(model["output_price"])) == Decimal("0.000006")
    assert model["price_source"] == "provider"

    history = (await client.get(f"/v1/models/{model['id']}/prices", headers=auth_headers)).json()
    assert len(history) == 1
    assert history[0]["source"] == "provider"


@respx.mock
async def test_sync_reads_speech_models_from_the_filtered_lists(
    client: Any, auth_headers: dict[str, str]
) -> None:
    """The real OpenRouter list returns ``architecture: null`` for speech models;
    only ``?output_modalities=…`` reveals them (with pricing)."""
    provider = await _create(
        client,
        auth_headers,
        kind="openrouter",
        base_url="https://openrouter.ai/api/v1",
        prices_url="https://openrouter.ai/api/v1/models",
    )
    listing = {
        "data": [
            {
                "id": "openai/whisper-1",
                "pricing": {"prompt": "0.0001", "completion": "0"},
                "architecture": None,
            },
            {
                "id": "google/gemini-2.5-flash",
                "pricing": {"prompt": "0.0000003", "completion": "0.0000025"},
                "architecture": {
                    "modality": "text+audio->text",
                    "input_modalities": ["text", "audio"],
                    "output_modalities": ["text"],
                },
            },
        ]
    }
    stt = {
        "data": [
            {
                "id": "openai/whisper-1",
                "pricing": {"prompt": "0.0001", "completion": "0"},
                "architecture": {
                    "modality": "audio->transcription",
                    "output_modalities": ["transcription"],
                },
            },
            {
                "id": "deepgram/nova-3",
                "pricing": {"prompt": "0.0000716666666667", "completion": "0"},
                "architecture": {
                    "modality": "audio->transcription",
                    "output_modalities": ["transcription"],
                },
            },
        ]
    }
    tts = {
        "data": [
            {
                "id": "elevenlabs/eleven-v3",
                "pricing": {"prompt": "0.00008", "completion": "0"},
                "architecture": {"modality": "text->speech", "output_modalities": ["speech"]},
            }
        ]
    }
    respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(200, json=listing)
    )
    respx.get(
        url__regex=r"https://openrouter\.ai/api/v1/models\?output_modalities=transcription"
    ).mock(return_value=httpx.Response(200, json=stt))
    respx.get(url__regex=r"https://openrouter\.ai/api/v1/models\?output_modalities=speech").mock(
        return_value=httpx.Response(200, json=tts)
    )

    synced = await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers)
    assert synced.status_code == 200, synced.text
    # 2 from the plain list + 2 speech models that only the filtered lists expose
    assert synced.json()["created"] == 4

    await client.post(f"/v1/providers/{provider['id']}/sync-prices", headers=auth_headers)

    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=auth_headers)
    ).json()
    by_id = {model["external_id"]: model for model in models}

    assert by_id["openai/whisper-1"]["audio_kind"] == "stt"
    assert Decimal(str(by_id["openai/whisper-1"]["audio_input_price"])) == Decimal("0.0060000000")
    assert by_id["deepgram/nova-3"]["audio_kind"] == "stt"
    assert Decimal(str(by_id["deepgram/nova-3"]["audio_input_price"])) == Decimal("0.0043000000")
    assert by_id["elevenlabs/eleven-v3"]["audio_kind"] == "tts"
    assert Decimal(str(by_id["elevenlabs/eleven-v3"]["audio_output_price"])) == Decimal(
        "0.0800000000"
    )
    assert by_id["google/gemini-2.5-flash"]["audio_chat"] is True


@respx.mock
async def test_sync_discovers_speech_models_and_audio_prices(
    client: Any, auth_headers: dict[str, str]
) -> None:
    """`output_modalities` decides STT/TTS; audio prices land in the audio columns."""
    provider = await _create(
        client,
        auth_headers,
        kind="openrouter",
        base_url="https://openrouter.ai/api/v1",
        prices_url="https://openrouter.ai/api/v1/models",
    )
    respx.get("https://openrouter.ai/api/v1/models").mock(
        return_value=httpx.Response(200, json=OPENROUTER_AUDIO_PAYLOAD)
    )

    synced = await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers)
    assert synced.status_code == 200, synced.text
    assert synced.json()["created"] == 3

    prices = await client.post(f"/v1/providers/{provider['id']}/sync-prices", headers=auth_headers)
    assert prices.status_code == 200, prices.text

    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=auth_headers)
    ).json()
    by_id = {model["external_id"]: model for model in models}

    stt = by_id["openai/whisper-1"]
    assert stt["audio_kind"] == "stt"
    assert stt["audio_chat"] is False
    assert stt["supports_audio"] is True
    assert stt["supports_tools"] is False
    assert stt["supports_stream"] is False
    # per audio second (0.0001) -> per minute
    assert Decimal(str(stt["audio_input_price"])) == Decimal("0.0060000000")
    assert stt["audio_output_price"] is None

    tts = by_id["elevenlabs/eleven-v3"]
    assert tts["audio_kind"] == "tts"
    assert tts["audio_chat"] is False
    # per character (0.00008) -> per 1000 characters
    assert Decimal(str(tts["audio_output_price"])) == Decimal("0.0800000000")
    assert tts["audio_input_price"] is None

    chat = by_id["google/gemini-2.5-flash"]
    assert chat["audio_kind"] is None
    assert chat["audio_chat"] is True
    assert chat["supports_audio"] is True
    assert chat["supports_stream"] is True

    audio_only = (
        await client.get("/v1/models", params={"capability": "audio"}, headers=auth_headers)
    ).json()
    assert {model["external_id"] for model in audio_only} == {
        "openai/whisper-1",
        "elevenlabs/eleven-v3",
        "google/gemini-2.5-flash",
    }
