"""Prompt API: versioning, publish, rollback, org scope."""

from __future__ import annotations

import uuid
from typing import Any


async def test_list_includes_seeded_persian_prompts(
    client: Any, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/v1/prompts", headers=auth_headers)
    assert response.status_code == 200
    rows = response.json()
    globals_only = {row["key"] for row in rows if row["org_id"] is None}
    assert {
        "agent.system.default",
        "agent.system.accountant",
        "agent.system.sales",
        "agent.system.receptionist",
        "agent.task.daily_sales_report",
        "voice.persona.default",
        "guard_input.default",
    }.issubset(globals_only)
    assert all(row["locale"] == "fa" for row in rows)


async def test_global_prompt_is_read_only(client: Any, auth_headers: dict[str, str]) -> None:
    rows = (await client.get("/v1/prompts", headers=auth_headers)).json()
    target = next(row for row in rows if row["key"] == "agent.system.default")

    response = await client.put(
        f"/v1/prompts/{target['id']}", json={"template": "x"}, headers=auth_headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "prompt.global_readonly"


async def test_create_update_rollback_flow(client: Any, auth_headers: dict[str, str]) -> None:
    key = f"org.custom.{uuid.uuid4().hex[:6]}"
    created = await client.post(
        "/v1/prompts",
        headers=auth_headers,
        json={
            "key": key,
            "title_fa": "پرامپت سازمانی",
            "template": "نسخه یک برای {{org.name}}",
            "kind": "agent.system",
            "publish": True,
        },
    )
    assert created.status_code == 201, created.text
    prompt = created.json()
    assert prompt["current_version"] == 1
    assert prompt["status"] == "published"
    assert prompt["variables"] == ["org.name"]
    assert prompt["org_id"] is not None

    updated = await client.put(
        f"/v1/prompts/{prompt['id']}",
        headers=auth_headers,
        json={"template": "نسخه دو برای {{org.name}}", "note": "ویرایش", "publish": True},
    )
    assert updated.status_code == 200
    assert updated.json()["current_version"] == 2

    versions = (
        await client.get(f"/v1/prompts/{prompt['id']}/versions", headers=auth_headers)
    ).json()
    assert [item["version"] for item in versions] == [2, 1]

    rolled = await client.post(
        f"/v1/prompts/{prompt['id']}/rollback", json={"version": 1}, headers=auth_headers
    )
    body = rolled.json()
    assert body["current_version"] == 3
    assert body["template"] == "نسخه یک برای {{org.name}}"
    assert body["status"] == "published"

    versions = (
        await client.get(f"/v1/prompts/{prompt['id']}/versions", headers=auth_headers)
    ).json()
    assert [item["version"] for item in versions] == [3, 2, 1]
    assert versions[0]["note"] == "بازگشت به نسخه 1"


async def test_duplicate_key_is_conflict(client: Any, auth_headers: dict[str, str]) -> None:
    key = f"org.dup.{uuid.uuid4().hex[:6]}"
    payload = {"key": key, "title_fa": "تکراری", "template": "متن"}
    first = await client.post("/v1/prompts", json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post("/v1/prompts", json=payload, headers=auth_headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "prompt.duplicate_key"


async def test_invalid_key_is_rejected(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/v1/prompts",
        headers=auth_headers,
        json={"key": "Bad Key!", "title_fa": "بد", "template": "x"},
    )
    assert response.status_code == 422


async def test_resolve_renders_org_and_jalali_date(
    client: Any, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/v1/prompts/resolve/agent.system.default", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "سازمان نمونه" in body["rendered"]
    assert any(character in "۰۱۲۳۴۵۶۷۸۹" for character in body["rendered"])
    assert "{{" not in body["rendered"]
    # no agent was passed, so agent.* variables are legitimately unresolved
    assert "org.name" not in body["missing"]
    assert "agent.name" in body["missing"]


async def test_unknown_prompt_returns_404(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/prompts/resolve/agent.system.nope", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "prompt.not_found"


async def test_preview_with_custom_values(client: Any, auth_headers: dict[str, str]) -> None:
    rows = (await client.get("/v1/prompts", headers=auth_headers)).json()
    target = next(row for row in rows if row["key"] == "rag.answer.default")

    response = await client.post(
        f"/v1/prompts/{target['id']}/preview",
        headers=auth_headers,
        json={"values": {"question": "ساعت کاری؟", "context": "۸ تا ۱۷"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert "ساعت کاری؟" in body["rendered"]
    assert "۸ تا ۱۷" in body["rendered"]
    assert body["missing"] == []
