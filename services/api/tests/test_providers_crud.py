"""Provider CRUD, key handling and RBAC."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, text

from app.core.security import hash_password
from app.db.models import Provider, User
from app.db.session import session_scope


def _payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": f"پروایدر تست {uuid.uuid4().hex[:6]}",
        "kind": "openai_compatible",
        "base_url": "https://api.test.local/v1",
        "api_key": "sk-secret-value-1234567890",
    }
    data.update(overrides)
    return data


async def test_create_provider_encrypts_and_masks_key(
    client: Any, auth_headers: dict[str, str]
) -> None:
    response = await client.post("/v1/providers", json=_payload(), headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["has_credentials"] is True
    assert body["auth_type"] == "bearer"
    assert body["health"] == "unknown"
    assert body["api_key_masked"] is not None
    assert "secret-value" not in body["api_key_masked"]
    assert "api_key" not in body

    async with session_scope(bypass_rls=True) as db:
        row = (
            await db.execute(select(Provider).where(Provider.id == uuid.UUID(body["id"])))
        ).scalar_one()
        blob = row.credentials_enc
        assert isinstance(blob, bytes)
        assert b"secret-value" not in blob


async def test_update_rotates_key(client: Any, auth_headers: dict[str, str]) -> None:
    created = (await client.post("/v1/providers", json=_payload(), headers=auth_headers)).json()
    response = await client.patch(
        f"/v1/providers/{created['id']}",
        json={"api_key": "sk-rotated-0987654321", "priority": 5, "is_enabled": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == 5
    assert body["is_enabled"] is False
    assert body["api_key_masked"] != created["api_key_masked"]


async def test_unknown_kind_is_rejected(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/v1/providers", json=_payload(kind="not-a-real-kind"), headers=auth_headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "provider.unknown_kind"


async def test_adapters_catalog_is_persian(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/provider-adapters", headers=auth_headers)
    assert response.status_code == 200
    kinds = {row["kind"]: row for row in response.json()}
    assert "openai_compatible" in kinds
    assert kinds["openai_compatible"]["title_fa"]
    assert "declarative" in kinds
    assert kinds["declarative"]["spec_schema"]["chat"]["url"]


async def test_delete_provider(client: Any, auth_headers: dict[str, str]) -> None:
    created = (await client.post("/v1/providers", json=_payload(), headers=auth_headers)).json()
    deleted = await client.delete(f"/v1/providers/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/v1/providers/{created['id']}", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "provider.not_found"


async def test_viewer_cannot_create_provider(client: Any, admin_tokens: dict[str, Any]) -> None:
    org_id = admin_tokens["user"]["org_id"]
    email = f"viewer-{uuid.uuid4().hex[:6]}@openbot.local"
    password = "viewer-pass-123"

    async with session_scope(bypass_rls=True) as db:
        await db.execute(text("select set_config('app.org_id', :o, true)"), {"o": org_id})
        db.add(
            User(
                org_id=uuid.UUID(org_id),
                email=email,
                full_name="کاربر بیننده",
                password_hash=hash_password(password),
                role="viewer",
            )
        )

    login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.post("/v1/providers", json=_payload(), headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth.insufficient_role"
