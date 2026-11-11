"""Health and meta endpoints."""

from __future__ import annotations

from typing import Any


async def test_healthz(client: Any) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "db": "ok", "version": "0.1.0"}
    assert response.headers.get("x-request-id")


async def test_meta_is_persian_first(client: Any) -> None:
    response = await client.get("/v1/meta")
    assert response.status_code == 200
    body = response.json()

    assert body["locale"] == "fa"
    assert body["timezone"] == "Asia/Tehran"
    assert body["calendar"] == "jalali"
    assert body["currency"] == "IRR"
    assert body["digits"] == "fa"
    assert body["api_prefix"] == "/v1"


async def test_meta_free_mode_no_gateway(client: Any) -> None:
    body = (await client.get("/v1/meta")).json()
    assert body["free_mode"] is True
    assert body["billing_enabled"] is False
    assert body["payment_gateway"] == "noop"
    assert body["payment_gateway_enabled"] is False
