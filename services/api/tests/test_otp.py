"""Phone OTP sign-in: request, verify, limits and the wallet bootstrap.

SMS is disabled in the test environment, so the API echoes the code back as
``debug_code``; that is exactly the dev behaviour we want to cover.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import update

from app.db.models import OtpCode
from app.db.session import session_scope


def _phone() -> str:
    """Unique number per test so the per-phone daily quota never interferes."""
    return "09" + f"{uuid.uuid4().int % 10**9:09d}"


async def _request(client: Any, phone: str) -> dict[str, Any]:
    response = await client.post("/v1/auth/otp/request", json={"phone": phone})
    assert response.status_code == 200, response.text
    return response.json()


async def _age_codes(phone: str) -> None:
    """Move the previous code out of the resend cooldown window."""
    async with session_scope(bypass_rls=True) as db:
        await db.execute(
            update(OtpCode)
            .where(OtpCode.phone == phone)
            .values(created_at=datetime.now(UTC) - timedelta(minutes=5))
        )


async def test_request_returns_debug_code_in_dev(client: Any) -> None:
    body = await _request(client, _phone())
    assert body["sent"] is True
    assert body["expires_in"] == 120
    assert body["resend_in"] == 60
    assert body["sms_delivered"] is False
    assert body["debug_code"] and len(body["debug_code"]) == 5


async def test_verify_creates_customer_and_wallet(client: Any) -> None:
    phone = _phone()
    code = (await _request(client, phone))["debug_code"]

    verified = await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["is_new_user"] is True
    assert body["token_type"] == "bearer"
    assert body["user"]["phone"] == phone
    assert body["user"]["role"] == "user"
    assert body["user"]["is_phone_verified"] is True
    assert body["user"]["has_password"] is False
    assert body["user"]["email"] is None

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = await client.get("/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["phone"] == phone

    wallet = await client.get("/v1/wallet", headers=headers)
    assert wallet.status_code == 200, wallet.text
    assert wallet.json()["balance_irr"] == 0
    assert wallet.json()["balance_toman"] == 0

    statement = await client.get("/v1/wallet/transactions", headers=headers)
    assert statement.status_code == 200
    assert statement.json() == []


async def test_second_login_reuses_the_same_account(client: Any) -> None:
    phone = _phone()
    first_code = (await _request(client, phone))["debug_code"]
    first = await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": first_code})
    assert first.status_code == 200

    await _age_codes(phone)
    second_code = (await _request(client, phone))["debug_code"]
    second = await client.post(
        "/v1/auth/otp/verify", json={"phone": phone, "code": second_code}
    )
    assert second.status_code == 200
    assert second.json()["is_new_user"] is False
    assert second.json()["user"]["id"] == first.json()["user"]["id"]


async def test_persian_digits_and_plus98_are_normalised(client: Any) -> None:
    digits = f"{uuid.uuid4().int % 10**9:09d}"
    national = "9" + digits  # 09xxxxxxxxx without the trunk zero
    persian = "۰۹" + "".join("۰۱۲۳۴۵۶۷۸۹"[int(d)] for d in digits)
    body = await _request(client, persian)
    code = body["debug_code"]
    assert code

    verified = await client.post(
        "/v1/auth/otp/verify", json={"phone": f"+98{national}", "code": code}
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["user"]["phone"] == "09" + digits


async def test_invalid_phone_is_rejected(client: Any) -> None:
    response = await client.post("/v1/auth/otp/request", json={"phone": "12345678901"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "auth.invalid_phone"


async def test_resend_cooldown(client: Any) -> None:
    phone = _phone()
    await _request(client, phone)
    again = await client.post("/v1/auth/otp/request", json={"phone": phone})
    assert again.status_code == 429
    assert again.json()["error"]["code"] == "otp.too_many_requests"
    assert again.json()["error"]["params"]["retry_after"] >= 1


async def test_wrong_code_and_attempt_limit(client: Any) -> None:
    phone = _phone()
    code = (await _request(client, phone))["debug_code"]
    wrong = "00000" if code != "00000" else "11111"

    first = await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": wrong})
    assert first.status_code == 401
    assert first.json()["error"]["code"] == "otp.code_invalid"

    for _ in range(4):
        await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": wrong})

    blocked = await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": wrong})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "otp.too_many_attempts"

    # the right code is refused too once the counter is exhausted
    locked = await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert locked.status_code == 429


async def test_code_is_single_use(client: Any) -> None:
    phone = _phone()
    code = (await _request(client, phone))["debug_code"]
    ok = await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert ok.status_code == 200

    replay = await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "otp.code_not_found"


async def test_expired_code(client: Any) -> None:
    phone = _phone()
    code = (await _request(client, phone))["debug_code"]

    async with session_scope(bypass_rls=True) as db:
        await db.execute(
            update(OtpCode)
            .where(OtpCode.phone == phone)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )

    response = await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "otp.code_expired"


async def test_customer_cannot_reach_admin_panel(client: Any) -> None:
    phone = _phone()
    code = (await _request(client, phone))["debug_code"]
    body = (
        await client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code})
    ).json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    providers = await client.get("/v1/providers", headers=headers)
    assert providers.status_code == 403
    assert providers.json()["error"]["code"] == "auth.insufficient_role"

    # ... but customers do get their own wallet and profile
    assert (await client.get("/v1/wallet", headers=headers)).status_code == 200
