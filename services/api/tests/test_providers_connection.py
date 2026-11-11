"""Manual pricing and connection tests (HTTP mocked with respx)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import httpx
import respx

from tests.test_providers_sync import BASE, MODELS_PAYLOAD, _create


@respx.mock
async def test_manual_price_override_wins(client: Any, auth_headers: dict[str, str]) -> None:
    provider = await _create(client, auth_headers)
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))
    await client.post(f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers)

    models = (
        await client.get("/v1/models", params={"provider_id": provider["id"]}, headers=auth_headers)
    ).json()
    model_id = models[0]["id"]

    response = await client.post(
        f"/v1/models/{model_id}/price",
        json={
            "input_price": "0.000002",
            "output_price": "0.000008",
            "currency": "USD",
            "note": "قیمت توافقی",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["source"].startswith("manual")

    updated = (await client.get(f"/v1/models/{model_id}", headers=auth_headers)).json()
    assert updated["price_source"] == "manual"
    assert Decimal(str(updated["output_price"])) == Decimal("0.000008")


@respx.mock
async def test_connection_ok(client: Any, auth_headers: dict[str, str]) -> None:
    provider = await _create(client, auth_headers)
    respx.get(f"{BASE}/models").mock(return_value=httpx.Response(200, json=MODELS_PAYLOAD))

    response = await client.post(f"/v1/providers/{provider['id']}/test", headers=auth_headers)
    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["models_seen"] == 3
    assert body["latency_ms"] >= 0

    refreshed = (await client.get(f"/v1/providers/{provider['id']}", headers=auth_headers)).json()
    assert refreshed["health"] == "ok"


@respx.mock
async def test_connection_error_never_leaks_the_key(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider = await _create(client, auth_headers)
    respx.get(f"{BASE}/models").mock(
        return_value=httpx.Response(401, json={"error": "invalid api key sk-test-key-abcd"})
    )

    response = await client.post(f"/v1/providers/{provider['id']}/test", headers=auth_headers)
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "provider.connection_failed"
    assert "sk-test-key-abcd" not in (body["detail"] or "")

    refreshed = (await client.get(f"/v1/providers/{provider['id']}", headers=auth_headers)).json()
    assert refreshed["health"] == "error"


async def test_sync_failure_returns_stable_code(client: Any, auth_headers: dict[str, str]) -> None:
    provider = await _create(
        client,
        auth_headers,
        base_url=f"https://no-such-host-{uuid.uuid4().hex[:6]}.invalid/v1",
    )
    response = await client.post(
        f"/v1/providers/{provider['id']}/sync-models", headers=auth_headers
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider.sync_failed"
