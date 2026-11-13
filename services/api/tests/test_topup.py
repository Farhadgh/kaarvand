"""Wallet top-up through a payment gateway.

No network here: a fake gateway is patched into ``app.billing.topup`` so the
whole flow (create -> redirect -> callback -> credit) is exercised end to end,
including the "credit only once" rule. A couple of unit tests cover the
Zarinpal adapter's request/verify parsing with a canned HTTP body.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.billing.gateway import PaymentInit, PaymentResult
from app.billing.zarinpal import ZarinpalGateway
from app.core.config import Settings
from app.core.errors import AppError

MIN_TOMAN = 10_000  # APP_MIN_TOPUP_IRR default = 100,000 IRR


class FakeGateway:
    """Stands in for Zarinpal: same port, no HTTP."""

    name = "fake"
    enabled = True

    def __init__(self) -> None:
        self.paid = True
        self.calls: list[tuple[str, Any]] = []

    async def create_payment(
        self, *, amount_irr: int, order_id: str, callback_url: str, description_fa: str
    ) -> PaymentInit:
        token = f"A{uuid.uuid4().hex[:20]}"
        self.calls.append(("create", amount_irr, callback_url, order_id))
        return PaymentInit(
            gateway=self.name, token=token, redirect_url=f"https://sandbox.test/pay/{token}"
        )

    async def verify_payment(self, *, token: str, amount_irr: int) -> PaymentResult:
        self.calls.append(("verify", token, amount_irr))
        return PaymentResult(
            gateway=self.name,
            reference="REF-7788",
            paid=self.paid,
            amount_irr=int(amount_irr),
            raw={"data": {"code": 100 if self.paid else -51}},
        )


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


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> FakeGateway:
    fake = FakeGateway()
    monkeypatch.setattr("app.billing.topup.get_gateway", lambda settings=None: fake)
    return fake


async def _topup(
    client: Any, headers: dict[str, str], toman: int = MIN_TOMAN * 2
) -> dict[str, Any]:
    response = await client.post(
        "/v1/wallet/topup", json={"amount_toman": toman}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _balance(client: Any, headers: dict[str, str]) -> int:
    response = await client.get("/v1/wallet", headers=headers)
    assert response.status_code == 200, response.text
    return int(response.json()["balance_irr"])


async def _callback(client: Any, authority: str, status: str = "OK") -> Any:
    return await client.get(
        "/v1/wallet/topup/callback",
        params={"Authority": authority, "Status": status},
        follow_redirects=False,
    )


# --- flow -------------------------------------------------------------------


async def test_topup_is_disabled_without_a_gateway(client: Any) -> None:
    """Default config is ``noop``: the customer gets a clear 409, not a 500."""
    headers = await _customer(client)
    response = await client.post(
        "/v1/wallet/topup", json={"amount_toman": MIN_TOMAN * 2}, headers=headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "billing.disabled"

    wallet = (await client.get("/v1/wallet", headers=headers)).json()
    assert wallet["topup_enabled"] is False
    assert wallet["min_topup_toman"] == MIN_TOMAN


async def test_topup_below_minimum_is_rejected(
    client: Any, gateway: FakeGateway
) -> None:
    headers = await _customer(client)
    response = await client.post(
        "/v1/wallet/topup", json={"amount_toman": MIN_TOMAN - 1}, headers=headers
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "wallet.amount_below_min"
    assert body["params"]["min_toman"] == MIN_TOMAN
    assert gateway.calls == []


async def test_topup_returns_redirect_and_stays_pending(
    client: Any, gateway: FakeGateway
) -> None:
    headers = await _customer(client)
    body = await _topup(client, headers)

    assert body["status"] == "pending"
    assert body["gateway"] == "fake"
    assert body["amount_irr"] == MIN_TOMAN * 2 * 10
    assert body["amount_toman"] == MIN_TOMAN * 2
    assert body["authority"].startswith("A")
    assert body["redirect_url"].endswith(body["authority"])

    # money has not moved yet
    assert await _balance(client, headers) == 0

    payments = (await client.get("/v1/wallet/payments", headers=headers)).json()
    assert len(payments) == 1
    assert payments[0]["status"] == "pending"
    assert payments[0]["id"] == body["payment_id"]


async def test_callback_credits_the_wallet_once(
    client: Any, gateway: FakeGateway
) -> None:
    headers = await _customer(client)
    body = await _topup(client, headers)

    first = await _callback(client, body["authority"])
    assert first.status_code == 303
    location = first.headers["location"]
    assert location.startswith("kaarvand://wallet?")
    assert "status=paid" in location
    assert "REF-7788" in location

    assert await _balance(client, headers) == MIN_TOMAN * 2 * 10

    # a retried callback (browser refresh) must not credit twice
    again = await _callback(client, body["authority"])
    assert again.status_code == 303
    assert await _balance(client, headers) == MIN_TOMAN * 2 * 10
    assert [call[0] for call in gateway.calls].count("verify") == 1

    statement = (await client.get("/v1/wallet/transactions", headers=headers)).json()
    assert len(statement) == 1
    assert statement[0]["kind"] == "topup"
    assert statement[0]["amount_irr"] == MIN_TOMAN * 2 * 10
    assert statement[0]["ref"] == "REF-7788"

    payment = (await client.get("/v1/wallet/payments", headers=headers)).json()[0]
    assert payment["status"] == "paid"
    assert payment["reference"] == "REF-7788"
    assert payment["paid_at"] is not None


async def test_canceled_callback_does_not_credit(
    client: Any, gateway: FakeGateway
) -> None:
    headers = await _customer(client)
    body = await _topup(client, headers)

    response = await _callback(client, body["authority"], status="NOK")
    assert response.status_code == 303
    assert "status=canceled" in response.headers["location"]

    assert await _balance(client, headers) == 0
    assert [call[0] for call in gateway.calls] == ["create"]
    payment = (await client.get("/v1/wallet/payments", headers=headers)).json()[0]
    assert payment["status"] == "canceled"


async def test_failed_verification_does_not_credit(
    client: Any, gateway: FakeGateway
) -> None:
    gateway.paid = False
    headers = await _customer(client)
    body = await _topup(client, headers)

    response = await _callback(client, body["authority"])
    assert response.status_code == 303
    assert "status=failed" in response.headers["location"]

    assert await _balance(client, headers) == 0
    payment = (await client.get("/v1/wallet/payments", headers=headers)).json()[0]
    assert payment["status"] == "failed"


async def test_unknown_authority_is_404(client: Any, gateway: FakeGateway) -> None:
    response = await _callback(client, "A-does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "payment.not_found"


async def test_customers_only_see_their_own_payments(
    client: Any, gateway: FakeGateway
) -> None:
    first = await _customer(client)
    second = await _customer(client)
    await _topup(client, first)

    assert len((await client.get("/v1/wallet/payments", headers=first)).json()) == 1
    assert (await client.get("/v1/wallet/payments", headers=second)).json() == []


# --- admin accounting -------------------------------------------------------


async def test_admin_sees_payments_and_totals(
    client: Any, gateway: FakeGateway, auth_headers: dict[str, str]
) -> None:
    headers = await _customer(client)
    body = await _topup(client, headers, toman=MIN_TOMAN * 5)
    await _callback(client, body["authority"])

    me = (await client.get("/v1/auth/me", headers=headers)).json()
    listing = await client.get("/v1/payments", headers=auth_headers, params={"user_id": me["id"]})
    assert listing.status_code == 200, listing.text
    rows = listing.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "paid"
    assert rows[0]["user_phone"] == me["phone"]
    assert rows[0]["amount_toman"] == MIN_TOMAN * 5

    filtered = await client.get("/v1/payments", headers=auth_headers, params={"status": "pending"})
    assert all(row["status"] == "pending" for row in filtered.json())

    summary = await client.get("/v1/payments/summary", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert data["paid_count"] >= 1
    assert data["paid_irr"] >= MIN_TOMAN * 5 * 10
    assert data["paid_toman"] >= MIN_TOMAN * 5
    assert data["today_paid_irr"] >= MIN_TOMAN * 5 * 10


async def test_customer_cannot_read_the_accounting(
    client: Any, gateway: FakeGateway
) -> None:
    headers = await _customer(client)
    assert (await client.get("/v1/payments", headers=headers)).status_code == 403
    assert (await client.get("/v1/payments/summary", headers=headers)).status_code == 403


async def test_admin_settles_a_lost_callback(
    client: Any, gateway: FakeGateway, auth_headers: dict[str, str]
) -> None:
    """The customer paid but the browser never came back: admin re-verifies."""
    headers = await _customer(client)
    body = await _topup(client, headers)
    assert await _balance(client, headers) == 0  # still pending

    settled = await client.post(
        f"/v1/payments/{body['payment_id']}/verify", headers=auth_headers
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["status"] == "paid"
    assert settled.json()["reference"] == "REF-7788"
    assert await _balance(client, headers) == MIN_TOMAN * 2 * 10

    again = await client.post(
        f"/v1/payments/{body['payment_id']}/verify", headers=auth_headers
    )
    assert again.status_code == 200
    assert await _balance(client, headers) == MIN_TOMAN * 2 * 10

    denied = await client.post(f"/v1/payments/{body['payment_id']}/verify", headers=headers)
    assert denied.status_code == 403


# --- Zarinpal adapter (no HTTP) ---------------------------------------------


def _zarinpal(**overrides: Any) -> ZarinpalGateway:
    base: dict[str, Any] = {"zarinpal_merchant_id": "m" * 36}
    base.update(overrides)
    return ZarinpalGateway(Settings(**base))


async def test_zarinpal_create_maps_authority_and_rial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def fake_post(
        self: ZarinpalGateway, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        seen["path"] = path
        seen["payload"] = payload
        return {
            "data": {"code": 100, "authority": "A000000000000000000000000000000001"},
            "errors": [],
        }

    monkeypatch.setattr(ZarinpalGateway, "_post", fake_post)
    gateway = _zarinpal()
    init = await gateway.create_payment(
        amount_irr=250_000,
        order_id="order-1",
        callback_url="https://api.test/v1/wallet/topup/callback",
        description_fa="شارژ کیف پول",
    )

    assert seen["path"] == "/pg/v4/payment/request.json"
    assert seen["payload"]["amount"] == 250_000  # Rial, never Toman
    assert seen["payload"]["merchant_id"] == "m" * 36
    assert seen["payload"]["metadata"]["order_id"] == "order-1"
    assert init.gateway == "zarinpal"
    assert init.token == "A000000000000000000000000000000001"
    assert init.redirect_url == (
        "https://payment.zarinpal.com/pg/StartPay/A000000000000000000000000000000001"
    )


async def test_zarinpal_verify_accepts_100_and_101(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bodies = iter(
        [
            {"data": {"code": 100, "ref_id": 201}, "errors": []},
            {"data": {"code": 101, "ref_id": 201}, "errors": []},
            {"data": {"code": -51}, "errors": [{"code": -51, "message": "failed"}]},
        ]
    )

    async def fake_post(
        self: ZarinpalGateway, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        assert path == "/pg/v4/payment/verify.json"
        assert payload["authority"] == "A1"
        return next(bodies)

    monkeypatch.setattr(ZarinpalGateway, "_post", fake_post)
    gateway = _zarinpal()

    fresh = await gateway.verify_payment(token="A1", amount_irr=100_000)
    assert fresh.paid is True and fresh.reference == "201"

    repeated = await gateway.verify_payment(token="A1", amount_irr=100_000)
    assert repeated.paid is True and repeated.reference == "201"

    refused = await gateway.verify_payment(token="A1", amount_irr=100_000)
    assert refused.paid is False and refused.reference == ""


async def test_zarinpal_without_merchant_id_is_disabled() -> None:
    gateway = _zarinpal(zarinpal_merchant_id="")
    assert gateway.enabled is False
    with pytest.raises(AppError) as excinfo:
        await gateway.create_payment(
            amount_irr=100_000,
            order_id="o",
            callback_url="https://api.test/cb",
            description_fa="x",
        )
    assert excinfo.value.code == "billing.gateway_not_configured"
    assert excinfo.value.status_code == 409
