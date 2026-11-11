"""Billing port: free mode, no gateway wired."""

from __future__ import annotations

from typing import Any


async def test_status_reports_noop_gateway(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/billing/status", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "gateway": "noop",
        "gateway_enabled": False,
        "free_mode": True,
        "billing_enabled": False,
    }


async def test_checkout_is_disabled_with_stable_code(
    client: Any, auth_headers: dict[str, str]
) -> None:
    response = await client.post("/v1/billing/checkout", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "billing.disabled"


async def test_billing_requires_auth(client: Any) -> None:
    response = await client.get("/v1/billing/status")
    assert response.status_code == 401
