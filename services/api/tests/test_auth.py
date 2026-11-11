"""Auth flow: login, me, refresh rotation, error codes in Persian-neutral form."""

from __future__ import annotations

from typing import Any

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


async def test_login_returns_tokens_and_user(client: Any) -> None:
    response = await client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["user"]["email"] == ADMIN_EMAIL
    assert body["user"]["locale"] == "fa"
    assert body["user"]["digits_pref"] == "fa"


async def test_login_persian_digits_email_is_normalised(client: Any) -> None:
    response = await client.post(
        "/v1/auth/login", json={"email": "ADMIN@openbot.local", "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200


async def test_wrong_password_returns_code(client: Any) -> None:
    response = await client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.invalid_credentials"


async def test_unknown_org_returns_code(client: Any) -> None:
    response = await client.post(
        "/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "org_slug": "no-such-org"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.org_not_found"


async def test_me_requires_token(client: Any) -> None:
    response = await client.get("/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.missing_token"


async def test_me_returns_current_user(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == ADMIN_EMAIL


async def test_refresh_rotates_and_invalidates_old_token(
    client: Any, admin_tokens: dict[str, Any]
) -> None:
    old_refresh = admin_tokens["refresh_token"]

    first = await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200
    new_tokens = first.json()
    assert new_tokens["refresh_token"] != old_refresh

    second = await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "auth.session_expired"

    me = await client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
    )
    assert me.status_code == 200


async def test_logout_revokes_refresh_token(client: Any, admin_tokens: dict[str, Any]) -> None:
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    logout = await client.post(
        "/v1/auth/logout", json={"refresh_token": admin_tokens["refresh_token"]}, headers=headers
    )
    assert logout.status_code == 200

    after = await client.post(
        "/v1/auth/refresh", json={"refresh_token": admin_tokens["refresh_token"]}
    )
    assert after.status_code == 401
