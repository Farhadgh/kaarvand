"""Customer catalog: Toman prices and no provider leakage.

The admin endpoint (`/v1/models`) is deliberately different: it shows USD
prices, provider ids and sync state. These tests pin the customer contract:
only enabled models, Persian names, Toman prices, and none of the provider
internals.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

FORBIDDEN_KEYS = {
    "provider_id",
    "provider",
    "provider_name",
    "base_url",
    "input_price",
    "output_price",
    "cached_input_price",
    "price_currency",
    "price_source",
    "price_synced_at",
    "markup_percent",
    "external_id",
}


def _phone() -> str:
    return "09" + f"{uuid.uuid4().int % 10**9:09d}"


async def _customer(client: Any) -> dict[str, str]:
    phone = _phone()
    asked = await client.post("/v1/auth/otp/request", json={"phone": phone})
    assert asked.status_code == 200, asked.text
    verified = await client.post(
        "/v1/auth/otp/verify", json={"phone": phone, "code": asked.json()["debug_code"]}
    )
    assert verified.status_code == 200, verified.text
    return {"Authorization": f"Bearer {verified.json()['access_token']}"}


async def _provider(client: Any, auth_headers: dict[str, str]) -> str:
    response = await client.post(
        "/v1/providers",
        json={
            "name": f"پروایدر کاتالوگ {uuid.uuid4().hex[:6]}",
            "kind": "openai_compatible",
            "base_url": "https://api.secret-host.local/v1",
            "api_key": "sk-catalog-secret-1234567890",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _model(
    client: Any,
    auth_headers: dict[str, str],
    provider_id: str,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider_id": provider_id,
        "external_id": f"catalog/model-{uuid.uuid4().hex[:8]}",
        "display_name_fa": "مدل آزمایشی کاتالوگ",
        "input_price": "0.0000025",
        "output_price": "0.00001",
    }
    payload.update(overrides)
    response = await client.post("/v1/models", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _fx(client: Any, headers: dict[str, str]) -> int:
    wallet = await client.get("/v1/wallet", headers=headers)
    assert wallet.status_code == 200, wallet.text
    return int(wallet.json()["usd_irr"])


def _toman(usd_per_token: str, fx: int, markup: str, units: int = 1_000_000) -> int:
    amount = (
        Decimal(usd_per_token)
        * Decimal(units)
        * (Decimal(1) + Decimal(markup) / Decimal(100))
        * Decimal(fx)
    )
    return int((amount / Decimal(10)).to_integral_value(rounding="ROUND_HALF_UP"))


async def test_catalog_hides_every_provider_detail(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider_id = await _provider(client, auth_headers)
    created = await _model(client, auth_headers, provider_id)

    headers = await _customer(client)
    response = await client.get("/v1/catalog/models", headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    row = next(item for item in rows if item["id"] == created["id"])

    assert FORBIDDEN_KEYS.isdisjoint(row.keys())
    assert row["name"] == "مدل آزمایشی کاتالوگ"
    assert row["price_known"] is True
    assert row["billing_unit"] == "per_1m_tokens"
    # nothing about the hosting provider may appear in the raw payload
    assert "secret-host" not in response.text
    assert "openai_compatible" not in response.text


async def test_catalog_prices_are_toman_per_million_tokens(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider_id = await _provider(client, auth_headers)
    created = await _model(client, auth_headers, provider_id)

    headers = await _customer(client)
    fx = await _fx(client, headers)
    rows = (await client.get("/v1/catalog/models", headers=headers)).json()
    row = next(item for item in rows if item["id"] == created["id"])

    # default platform markup is 30%
    assert row["price_input_toman"] == _toman("0.0000025", fx, "30")
    assert row["price_output_toman"] == _toman("0.00001", fx, "30")


async def test_model_markup_overrides_the_platform_default(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider_id = await _provider(client, auth_headers)
    created = await _model(client, auth_headers, provider_id)
    patched = await client.patch(
        f"/v1/models/{created['id']}", json={"markup_percent": "50"}, headers=auth_headers
    )
    assert patched.status_code == 200, patched.text

    headers = await _customer(client)
    fx = await _fx(client, headers)
    rows = (await client.get("/v1/catalog/models", headers=headers)).json()
    row = next(item for item in rows if item["id"] == created["id"])
    assert row["price_input_toman"] == _toman("0.0000025", fx, "50")


async def test_disabled_models_and_providers_are_invisible(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider_id = await _provider(client, auth_headers)
    created = await _model(client, auth_headers, provider_id)

    headers = await _customer(client)
    await client.patch(
        f"/v1/models/{created['id']}", json={"is_enabled": False}, headers=auth_headers
    )

    rows = (await client.get("/v1/catalog/models", headers=headers)).json()
    assert all(item["id"] != created["id"] for item in rows)
    detail = await client.get(f"/v1/catalog/models/{created['id']}", headers=headers)
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "model.not_found"

    # re-enable the model but disable the whole provider
    await client.patch(
        f"/v1/models/{created['id']}", json={"is_enabled": True}, headers=auth_headers
    )
    await client.patch(
        f"/v1/providers/{provider_id}", json={"is_enabled": False}, headers=auth_headers
    )
    rows = (await client.get("/v1/catalog/models", headers=headers)).json()
    assert all(item["id"] != created["id"] for item in rows)


async def test_capability_and_modality_filters(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider_id = await _provider(client, auth_headers)
    vision = await _model(client, auth_headers, provider_id)
    await client.patch(
        f"/v1/models/{vision['id']}", json={"supports_vision": True}, headers=auth_headers
    )

    speech = await _model(
        client,
        auth_headers,
        provider_id,
        external_id=f"catalog/whisper-{uuid.uuid4().hex[:6]}",
        display_name_fa="تبدیل گفتار به متن",
        audio_kind="stt",
        audio_input_price="0.006",
        input_price=None,
        output_price=None,
    )

    headers = await _customer(client)
    fx = await _fx(client, headers)

    vision_rows = (
        await client.get("/v1/catalog/models", headers=headers, params={"capability": "vision"})
    ).json()
    # the shared test database may already hold seeded models, so assert membership
    # (and that the filter really excludes the non-vision one) instead of equality.
    vision_ids = [item["id"] for item in vision_rows]
    assert vision["id"] in vision_ids
    assert speech["id"] not in vision_ids
    assert all("vision" in item["capabilities"] for item in vision_rows)

    audio_rows = (
        await client.get("/v1/catalog/models", headers=headers, params={"capability": "audio"})
    ).json()
    row = next(item for item in audio_rows if item["id"] == speech["id"])
    assert row["audio_kind"] == "stt"
    assert row["billing_unit"] == "per_minute"
    assert row["price_audio_minute_toman"] == _toman("0.006", fx, "30", units=1)
    assert row["price_input_toman"] is None

    modality_rows = (
        await client.get("/v1/catalog/models", headers=headers, params={"modality": "audio"})
    ).json()
    modality_ids = [item["id"] for item in modality_rows]
    assert speech["id"] in modality_ids
    assert vision["id"] not in modality_ids


async def test_detail_matches_the_list(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider_id = await _provider(client, auth_headers)
    created = await _model(client, auth_headers, provider_id)

    headers = await _customer(client)
    listed = next(
        item
        for item in (await client.get("/v1/catalog/models", headers=headers)).json()
        if item["id"] == created["id"]
    )
    detail = await client.get(f"/v1/catalog/models/{created['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json() == listed


async def test_catalog_requires_a_signed_in_customer(client: Any) -> None:
    assert (await client.get("/v1/catalog/models")).status_code == 401


async def test_customer_cannot_open_the_admin_model_list(
    client: Any, auth_headers: dict[str, str]
) -> None:
    provider_id = await _provider(client, auth_headers)
    await _model(client, auth_headers, provider_id)

    headers = await _customer(client)
    response = await client.get("/v1/models", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth.insufficient_role"
