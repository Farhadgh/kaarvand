"""Audio (STT/TTS): model discovery, pricing, ledger and error paths."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select

from app.billing.cost import compute_audio_cost, price_audio_usage
from app.db.models import UsageLedger
from app.db.session import session_scope

BASE = "https://api.audio.test/v1"


async def make_provider(client: Any, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.post(
        "/v1/providers",
        headers=headers,
        json={
            "name": f"audio-{uuid.uuid4().hex[:6]}",
            "kind": "openai_compatible",
            "base_url": BASE,
            "api_key": "sk-audio",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_model(
    client: Any,
    headers: dict[str, str],
    provider_id: str,
    *,
    external_id: str = "whisper-1",
    audio_kind: str = "stt",
    audio_input_price: str | None = "0.006",
    audio_output_price: str | None = None,
) -> dict[str, Any]:
    response = await client.post(
        "/v1/models",
        headers=headers,
        json={
            "provider_id": provider_id,
            "external_id": external_id,
            "display_name_fa": "مدل صوتی",
            "audio_kind": audio_kind,
            "audio_input_price": audio_input_price,
            "audio_output_price": audio_output_price,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_audio_cost_units() -> None:
    # STT: 90 seconds at USD 0.006/min -> 0.009
    assert compute_audio_cost(audio_seconds=90, per_minute_price="0.006") == Decimal("0.009")
    # TTS: 2000 chars at USD 0.015/1K -> 0.03
    assert compute_audio_cost(audio_chars=2000, per_1k_chars_price="0.015") == Decimal("0.030")

    class Row:
        audio_input_price = Decimal("0.006")
        audio_output_price = Decimal("0.015")
        markup_percent = Decimal("10")

    usd, irr = price_audio_usage(Row(), audio_seconds=60, fx_rate=1_000_000)
    assert usd == Decimal("0.006")
    assert irr == 6600  # 0.006 * 1.1 * 1_000_000


async def test_presets_are_available(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/audio/presets", headers=auth_headers)
    assert response.status_code == 200
    presets = {row["slug"]: row for row in response.json()}
    assert presets["whisper-1"]["kind"] == "stt"
    assert presets["tts-1"]["kind"] == "tts"
    assert all(row["label_fa"] for row in presets.values())


async def test_audio_meta_exposes_limits(client: Any, auth_headers: dict[str, str]) -> None:
    meta = (await client.get("/v1/audio/meta", headers=auth_headers)).json()
    assert meta["max_upload_mb"] >= 1
    assert meta["max_tts_chars"] >= 100
    assert "mp3" in meta["formats"]
    assert "alloy" in meta["voices"]


async def test_create_audio_model_sets_flags_and_kind(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    model = await add_model(client, auth_headers, provider["id"])

    assert model["supports_audio"] is True
    assert model["supports_tools"] is False
    assert model["supports_stream"] is False
    assert model["audio_input_price"] == "0.0060000000" or Decimal(
        model["audio_input_price"]
    ) == Decimal("0.006")

    listing = (await client.get("/v1/audio/models", headers=auth_headers)).json()
    row = next(item for item in listing if item["id"] == model["id"])
    assert row["kind"] == "stt"
    assert row["provider_name"] == provider["name"]


async def test_duplicate_audio_model_is_rejected(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    await add_model(client, auth_headers, provider["id"])
    again = await client.post(
        "/v1/models",
        headers=auth_headers,
        json={
            "provider_id": provider["id"],
            "external_id": "whisper-1",
            "audio_kind": "stt",
        },
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "model.exists"


@respx.mock
async def test_transcription_bills_per_minute_and_writes_ledger(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    model = await add_model(client, auth_headers, provider["id"])

    respx.post(f"{BASE}/audio/transcriptions").mock(
        return_value=httpx.Response(
            200, json={"text": "سلام دنیا", "language": "fa", "duration": 90.0}
        )
    )

    response = await client.post(
        "/v1/audio/transcriptions",
        headers=auth_headers,
        files={"file": ("voice.webm", b"RIFFxxxx", "audio/webm")},
        data={"model_id": model["id"], "language": "fa"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "سلام دنیا"
    assert body["seconds"] == 90.0
    assert Decimal(body["cost_usd"]) == Decimal("0.009")  # 1.5 min * 0.006

    async with session_scope(bypass_rls=True) as db:
        ledger = (
            (
                await db.execute(
                    select(UsageLedger).where(UsageLedger.model_id == uuid.UUID(model["id"]))
                )
            )
            .scalars()
            .all()
        )
    assert len(ledger) == 1
    assert ledger[0].audio_seconds == 90
    assert ledger[0].audio_chars == 0
    assert ledger[0].cost_usd == Decimal("0.00900000")


@respx.mock
async def test_speech_returns_audio_and_bills_per_characters(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    model = await add_model(
        client,
        auth_headers,
        provider["id"],
        external_id="tts-1",
        audio_kind="tts",
        audio_input_price=None,
        audio_output_price="0.015",
    )

    respx.post(f"{BASE}/audio/speech").mock(
        return_value=httpx.Response(
            200, content=b"ID3fake", headers={"content-type": "audio/mpeg"}
        )
    )

    text = "ا" * 2000
    response = await client.post(
        "/v1/audio/speech",
        headers=auth_headers,
        json={"model_id": model["id"], "text": text, "voice": "alloy", "format": "mp3"},
    )
    assert response.status_code == 200, response.text
    assert response.content == b"ID3fake"
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert Decimal(response.headers["x-cost-usd"]) == Decimal("0.03")
    assert response.headers["x-chars"] == "2000"


async def test_transcription_rejects_non_audio_model(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    chat = (
        await client.post(
            "/v1/models",
            headers=auth_headers,
            json={"provider_id": provider["id"], "external_id": "plain-chat"},
        )
    ).json()

    response = await client.post(
        "/v1/audio/transcriptions",
        headers=auth_headers,
        files={"file": ("a.webm", b"x", "audio/webm")},
        data={"model_id": chat["id"]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "audio.not_audio_model"


async def test_wrong_kind_is_rejected(client: Any, auth_headers: dict[str, str]) -> None:
    provider = await make_provider(client, auth_headers)
    stt = await add_model(client, auth_headers, provider["id"])

    response = await client.post(
        "/v1/audio/speech",
        headers=auth_headers,
        json={"model_id": stt["id"], "text": "سلام"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "audio.wrong_kind"


async def test_empty_file_and_long_text_are_errors(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    stt = await add_model(client, auth_headers, provider["id"])
    tts = await add_model(
        client,
        auth_headers,
        provider["id"],
        external_id="tts-1",
        audio_kind="tts",
        audio_input_price=None,
        audio_output_price="0.015",
    )

    empty = await client.post(
        "/v1/audio/transcriptions",
        headers=auth_headers,
        files={"file": ("a.webm", b"", "audio/webm")},
        data={"model_id": stt["id"]},
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "audio.empty_file"

    too_long = await client.post(
        "/v1/audio/speech",
        headers=auth_headers,
        json={"model_id": tts["id"], "text": "ا" * 4001},
    )
    assert too_long.status_code in (413, 422)


async def test_speech_estimate_does_not_call_provider(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    tts = await add_model(
        client,
        auth_headers,
        provider["id"],
        external_id="tts-1",
        audio_kind="tts",
        audio_input_price=None,
        audio_output_price="0.015",
    )
    response = await client.get(
        "/v1/audio/speech/estimate",
        headers=auth_headers,
        params={"model_id": tts["id"], "text": "ا" * 1000},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["chars"] == 1000
    assert Decimal(body["cost_usd"]) == Decimal("0.015")


@respx.mock
async def test_provider_error_is_mapped_not_swallowed(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    model = await add_model(client, auth_headers, provider["id"])

    respx.post(f"{BASE}/audio/transcriptions").mock(
        return_value=httpx.Response(401, json={"error": "bad key"})
    )

    response = await client.post(
        "/v1/audio/transcriptions",
        headers=auth_headers,
        files={"file": ("a.webm", b"x", "audio/webm")},
        data={"model_id": model["id"]},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider.auth_failed"


async def test_deleted_model_disappears_from_audio_list(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await make_provider(client, auth_headers)
    model = await add_model(client, auth_headers, provider["id"])
    deleted = await client.delete(f"/v1/models/{model['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    listing = (await client.get("/v1/audio/models", headers=auth_headers)).json()
    assert all(row["id"] != model["id"] for row in listing)


@pytest.mark.parametrize("kind_filter", ["stt", "tts"])
async def test_audio_models_filter(
    client: Any, auth_headers: dict[str, str], kind_filter: str
) -> None:
    provider = await make_provider(client, auth_headers)
    await add_model(client, auth_headers, provider["id"], external_id="whisper-1")
    await add_model(
        client,
        auth_headers,
        provider["id"],
        external_id="tts-1",
        audio_kind="tts",
        audio_input_price=None,
        audio_output_price="0.015",
    )
    rows = (
        await client.get(
            "/v1/audio/models", headers=auth_headers, params={"kind": kind_filter}
        )
    ).json()
    assert rows and all(row["kind"] == kind_filter for row in rows)



