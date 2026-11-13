"""Settings: organization, personal preferences, exchange rate."""

from __future__ import annotations

from typing import Any


async def test_read_settings(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/settings", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["org"]["timezone"] == "Asia/Tehran"
    assert body["org"]["calendar"] == "jalali"
    assert body["org"]["digits"] == "fa"
    assert body["me"]["role"] == "admin"
    assert body["fx"]["usd_irr"] == 1000000
    assert body["free_mode"] is True
    assert body["billing_enabled"] is False
    assert body["payment_gateway"] == "noop"


async def test_update_org_settings(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.patch(
        "/v1/settings/org",
        headers=auth_headers,
        json={"name": "شرکت نمونه", "digits": "fa", "tax_rate": "9.00", "invoice_prefix": "FAC"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "شرکت نمونه"
    assert body["invoice_prefix"] == "FAC"
    assert body["tax_rate"] in ("9.00", 9.0)


async def test_update_fx_rate_changes_future_costs(
    client: Any, auth_headers: dict[str, str]
) -> None:
    response = await client.patch(
        "/v1/settings/fx", headers=auth_headers, json={"usd_irr": 1_250_000}
    )
    assert response.status_code == 200
    assert response.json()["usd_irr"] == 1_250_000

    again = (await client.get("/v1/settings", headers=auth_headers)).json()
    assert again["fx"]["usd_irr"] == 1_250_000


async def test_update_my_preferences(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.patch(
        "/v1/settings/me", headers=auth_headers, json={"digits_pref": "en", "full_name": "مدیر"}
    )
    assert response.status_code == 200
    assert response.json()["digits_pref"] == "en"

    me = (await client.get("/v1/auth/me", headers=auth_headers)).json()
    assert me["digits_pref"] == "en"


async def test_viewer_cannot_change_settings(
    client: Any, viewer_headers: dict[str, str]
) -> None:
    org = await client.patch(
        "/v1/settings/org", headers=viewer_headers, json={"name": "x"}
    )
    assert org.status_code == 403
    fx = await client.patch("/v1/settings/fx", headers=viewer_headers, json={"usd_irr": 1})
    assert fx.status_code == 403

    # but a viewer can read settings
    read = await client.get("/v1/settings", headers=viewer_headers)
    assert read.status_code == 200
