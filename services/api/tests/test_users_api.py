"""User management: create, roles, password reset, deactivation.

Two roles only: ``admin`` (platform staff, can manage accounts) and ``user``
(customer, OTP account). Platform admins may create other admins.
"""

from __future__ import annotations

import uuid
from typing import Any


def _payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "email": f"user-{uuid.uuid4().hex[:6]}@openbot.local",
        "full_name": "کارشناس فروش",
        "password": "strong-pass-123",
        "role": "user",
    }
    data.update(overrides)
    return data


async def test_create_and_list_users(client: Any, auth_headers: dict[str, str]) -> None:
    created = await client.post("/v1/users", json=_payload(), headers=auth_headers)
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["role"] == "user"
    assert user["is_active"] is True
    assert user["digits_pref"] == "fa"
    assert user["has_password"] is True

    listed = (await client.get("/v1/users", headers=auth_headers)).json()
    assert any(row["id"] == user["id"] for row in listed)

    found = (
        await client.get("/v1/users", params={"q": "کارشناس"}, headers=auth_headers)
    ).json()
    assert any(row["id"] == user["id"] for row in found)


async def test_new_user_gets_a_wallet(client: Any, auth_headers: dict[str, str]) -> None:
    payload = _payload()
    created = await client.post("/v1/users", json=payload, headers=auth_headers)
    assert created.status_code == 201

    login = await client.post(
        "/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    wallet = await client.get("/v1/wallet", headers=headers)
    assert wallet.status_code == 200, wallet.text
    body = wallet.json()
    assert body["balance_irr"] == 0
    assert body["is_enabled"] is True
    assert body["markup_percent"] == 30


async def test_duplicate_email_is_conflict(client: Any, auth_headers: dict[str, str]) -> None:
    payload = _payload()
    first = await client.post("/v1/users", json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post("/v1/users", json=payload, headers=auth_headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "user.duplicate_email"


async def test_invalid_payloads_are_rejected(
    client: Any, auth_headers: dict[str, str]
) -> None:
    bad_email = await client.post(
        "/v1/users", json=_payload(email="not-an-email"), headers=auth_headers
    )
    assert bad_email.status_code == 422

    bad_phone = await client.post(
        "/v1/users", json=_payload(phone="12345"), headers=auth_headers
    )
    assert bad_phone.status_code == 422

    short_password = await client.post(
        "/v1/users", json=_payload(password="123"), headers=auth_headers
    )
    assert short_password.status_code == 422

    unknown_role = await client.post(
        "/v1/users", json=_payload(role="owner"), headers=auth_headers
    )
    assert unknown_role.status_code == 422


async def test_admin_can_create_another_admin(
    client: Any, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/v1/users",
        json=_payload(role="admin", email=f"admin-{uuid.uuid4().hex[:6]}@openbot.local"),
        headers=auth_headers,
    )
    assert created.status_code == 201
    login = await client.post(
        "/v1/auth/login",
        json={"email": created.json()["email"], "password": "strong-pass-123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "admin"


async def test_role_update_and_self_protection(
    client: Any, auth_headers: dict[str, str]
) -> None:
    user = (await client.post("/v1/users", json=_payload(), headers=auth_headers)).json()

    promoted = await client.patch(
        f"/v1/users/{user['id']}", json={"role": "admin"}, headers=auth_headers
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    me = (await client.get("/v1/auth/me", headers=auth_headers)).json()
    self_role = await client.patch(
        f"/v1/users/{me['id']}", json={"role": "admin"}, headers=auth_headers
    )
    assert self_role.status_code == 409
    assert self_role.json()["error"]["code"] == "user.cannot_modify_self"


async def test_password_reset_revokes_sessions(
    client: Any, auth_headers: dict[str, str]
) -> None:
    payload = _payload()
    user = (await client.post("/v1/users", json=payload, headers=auth_headers)).json()

    login = await client.post(
        "/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert login.status_code == 200

    reset = await client.post(
        f"/v1/users/{user['id']}/reset-password",
        json={"password": "brand-new-pass-9"},
        headers=auth_headers,
    )
    assert reset.status_code == 200

    old = await client.post(
        "/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert old.status_code == 401

    new = await client.post(
        "/v1/auth/login", json={"email": payload["email"], "password": "brand-new-pass-9"}
    )
    assert new.status_code == 200


async def test_deactivate_user_blocks_login(
    client: Any, auth_headers: dict[str, str]
) -> None:
    payload = _payload()
    user = (await client.post("/v1/users", json=payload, headers=auth_headers)).json()

    removed = await client.delete(f"/v1/users/{user['id']}", headers=auth_headers)
    assert removed.status_code == 204

    blocked = await client.post(
        "/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert blocked.status_code == 401
    assert blocked.json()["error"]["code"] == "auth.user_inactive"

    listed = (
        await client.get("/v1/users", params={"is_active": "false"}, headers=auth_headers)
    ).json()
    assert any(row["id"] == user["id"] for row in listed)


async def test_customer_cannot_manage_users(
    client: Any, viewer_headers: dict[str, str]
) -> None:
    listed = await client.get("/v1/users", headers=viewer_headers)
    assert listed.status_code == 403
    created = await client.post("/v1/users", json=_payload(), headers=viewer_headers)
    assert created.status_code == 403
