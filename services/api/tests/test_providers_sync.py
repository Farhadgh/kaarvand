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
