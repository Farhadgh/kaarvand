"""Tool registry API: CRUD, secrets, validation."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import respx

HTTP_TOOL = {
    "slug": "demo.echo",
    "name_fa": "اکو دمو",
    "description_fa": "پیام را به سرویس دمو می‌فرستد",
    "kind": "http",
    "input_schema": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    "config": {
        "method": "POST",
        "url": "https://api.demo.test/echo",
        "allowed_domains": ["demo.test"],
        "headers": {"X-Static": "demo"},
        "body": {"text": "{{text}}"},
        "response_map": {"message_id": "$.result.id"},
    },
    "risk_level": "medium",
    "approval_policy": "confirm",
    "category": "web",
    "secret": "tok-secret-123456",
    "secret_label": "کلید دمو",
}


def _payload(**overrides: Any) -> dict[str, Any]:
    data = {**HTTP_TOOL, "slug": f"{HTTP_TOOL['slug']}.{uuid.uuid4().hex[:6]}"}
    data.update(overrides)
    return data


async def test_seeded_global_tools_are_listed(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.get("/v1/tools", params={"enabled_only": "false"}, headers=auth_headers)
    assert response.status_code == 200
    slugs = {row["slug"] for row in response.json()}
    assert {"system.now_jalali", "telegram.send_message", "office.excel.append_row"} <= slugs

    enabled = (
        await client.get("/v1/tools", params={"enabled_only": "true"}, headers=auth_headers)
    ).json()
    enabled_slugs = {row["slug"] for row in enabled}
    assert "system.now_jalali" in enabled_slugs
    assert "telegram.send_message" not in enabled_slugs


async def test_global_tool_is_read_only(client: Any, auth_headers: dict[str, str]) -> None:
    rows = (await client.get("/v1/tools", headers=auth_headers)).json()
    target = next(row for row in rows if row["slug"] == "system.now_jalali")

    response = await client.patch(
        f"/v1/tools/{target['id']}", json={"name_fa": "تغییر"}, headers=auth_headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "tool.global_readonly"


async def test_create_http_tool_encrypts_secret(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.post("/v1/tools", json=_payload(), headers=auth_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "http"
    assert body["has_secret"] is True
    assert body["secret_masked"] and "secret-123456" not in body["secret_masked"]
    assert body["secret_label"] == "کلید دمو"


async def test_http_tool_requires_allowed_domains(
    client: Any, auth_headers: dict[str, str]
) -> None:
    payload = _payload()
    payload["config"] = {**payload["config"]}
    payload["config"].pop("allowed_domains")
    response = await client.post("/v1/tools", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tool.domain_not_configured"


async def test_http_tool_requires_url(client: Any, auth_headers: dict[str, str]) -> None:
    payload = _payload()
    payload["config"] = {"allowed_domains": ["demo.test"]}
    response = await client.post("/v1/tools", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tool.missing_url"


async def test_connector_tool_requires_actions(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/v1/tools",
        headers=auth_headers,
        json={
            "slug": f"demo.connector.{uuid.uuid4().hex[:6]}",
            "name_fa": "کانکتور بدون اقدام",
            "kind": "connector",
            "actions": [],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tool.invalid_actions"


async def test_unknown_builtin_is_rejected(client: Any, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/v1/tools",
        headers=auth_headers,
        json={
            "slug": f"demo.builtin.{uuid.uuid4().hex[:6]}",
            "name_fa": "بیلتین ناشناس",
            "kind": "builtin",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tool.unknown_builtin"


async def test_duplicate_slug_is_conflict(client: Any, auth_headers: dict[str, str]) -> None:
    payload = _payload()
    first = await client.post("/v1/tools", json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post("/v1/tools", json=payload, headers=auth_headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "tool.duplicate_slug"


async def test_customer_can_create_tool(client: Any, viewer_headers: dict[str, str]) -> None:
    response = await client.post("/v1/tools", json=_payload(), headers=viewer_headers)
    assert response.status_code == 201, response.text


@respx.mock
async def test_test_endpoint_executes_http_tool(client: Any, auth_headers: dict[str, str]) -> None:
    created = (await client.post("/v1/tools", json=_payload(), headers=auth_headers)).json()
    respx.post("https://api.demo.test/echo").mock(
        return_value=httpx.Response(200, json={"result": {"id": "m-1", "echo": "سلام"}})
    )

    response = await client.post(
        f"/v1/tools/{created['id']}/test",
        headers=auth_headers,
        json={"arguments": {"text": "سلام"}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["result"]["mapped"]["message_id"] == "m-1"
    assert body["result"]["status_code"] == 200
    assert body["invocation_id"]


async def test_test_endpoint_rejects_bad_arguments(
    client: Any, auth_headers: dict[str, str]
) -> None:
    created = (await client.post("/v1/tools", json=_payload(), headers=auth_headers)).json()
    response = await client.post(
        f"/v1/tools/{created['id']}/test", headers=auth_headers, json={"arguments": {}}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tool.invalid_arguments"


@respx.mock
async def test_llm_schemas_for_bound_agent(client: Any, auth_headers: dict[str, str]) -> None:
    global_tools = (await client.get("/v1/tools", headers=auth_headers)).json()
    builtin = next(row for row in global_tools if row["slug"] == "system.now_jalali")

    agent = (
        await client.post("/v1/agents", headers=auth_headers, json={"name": "ایجنت ابزاردار"})
    ).json()
    bind = await client.put(
        f"/v1/agents/{agent['id']}/tools",
        headers=auth_headers,
        json=[{"tool_id": builtin["id"], "permission_level": "auto"}],
    )
    assert bind.status_code == 200, bind.text

    schemas = (
        await client.get(
            "/v1/tools/llm-schemas", params={"agent_id": agent["id"]}, headers=auth_headers
        )
    ).json()
    assert len(schemas) == 1
    assert schemas[0]["slug"] == "system.now_jalali"
    assert schemas[0]["name"] == "system_now_jalali"
    assert schemas[0]["parameters"]["type"] == "object"


@respx.mock
async def test_mcp_server_sync_lists_tools(client: Any, auth_headers: dict[str, str]) -> None:
    server = await client.post(
        "/v1/mcp-servers",
        headers=auth_headers,
        json={"name": "سرور دمو", "transport": "http", "url": "https://mcp.demo.test/rpc"},
    )
    assert server.status_code == 201, server.text

    respx.post("https://mcp.demo.test/rpc").mock(
        return_value=httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {"name": "search", "description": "جست‌وجو"},
                        {"name": "fetch", "description": "واکشی"},
                    ]
                },
            },
        )
    )
    sync = await client.post(f"/v1/mcp-servers/{server.json()['id']}/sync", headers=auth_headers)
    assert sync.status_code == 200, sync.text
    assert sync.json()["count"] == 2
    assert sync.json()["tools"][0]["name"] == "search"


async def test_mcp_sync_reports_rpc_error(client: Any, auth_headers: dict[str, str]) -> None:
    server = (
        await client.post(
            "/v1/mcp-servers",
            headers=auth_headers,
            json={"name": "سرور خطادار", "url": "https://mcp.bad.test/rpc"},
        )
    ).json()

    with respx.mock:
        respx.post("https://mcp.bad.test/rpc").mock(
            return_value=httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "no"}}
            )
        )
        response = await client.post(f"/v1/mcp-servers/{server['id']}/sync", headers=auth_headers)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "mcp.rpc_error"
