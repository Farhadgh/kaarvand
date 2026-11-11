"""Live demo of step 4: build an HTTP tool, call it, bind it to an agent.

Prereq:
    python scripts\\fake_provider.py            # :8020 (serves /echo)
    uvicorn app.main:app --port 8010 (scripts\\dev.ps1)
"""

from __future__ import annotations

import contextlib
import json
import sys
import uuid

import httpx

API = "http://127.0.0.1:8010"


def show(title: str, payload: object) -> None:
    print(f"\n== {title}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8")

    with httpx.Client(base_url=API, timeout=60, trust_env=False) as client:
        login = client.post(
            "/v1/auth/login", json={"email": "admin@openbot.local", "password": "admin12345"}
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        show("action ops (connector DSL)", {"count": len(client.get("/v1/tools/ops", headers=headers).json())})

        tools_all = client.get("/v1/tools", headers=headers).json()
        calendar_tool = next(row for row in tools_all if row["slug"] == "system.now_jalali")

        tool = client.post(
            "/v1/tools",
            headers=headers,
            json={
                "slug": f"demo.local.echo.{uuid.uuid4().hex[:6]}",
                "name_fa": "اکوی محلی",
                "description_fa": "متن را به سرویس محلی می‌فرستد و شناسه را برمی‌گرداند",
                "kind": "http",
                "input_schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "متن ورودی"}},
                    "required": ["text"],
                },
                "config": {
                    "method": "POST",
                    "url": "{{base_url}}/echo",
                    "base_url": "http://127.0.0.1:8020",
                    "allowed_domains": ["127.0.0.1"],
                    "body": {"text": "{{text}}"},
                    "response_map": {"message_id": "$.result.id", "echo": "$.result.echo"},
                    "timeout": 10,
                },
                "risk_level": "medium",
                "approval_policy": "confirm",
                "category": "web",
            },
        )
        tool.raise_for_status()
        created = tool.json()
        show("tool created", {"slug": created["slug"], "kind": created["kind"], "risk": created["risk_level"]})

        test = client.post(
            f"/v1/tools/{created['id']}/test",
            headers=headers,
            json={"arguments": {"text": "سلام از پنل"}},
        )
        test.raise_for_status()
        show("tool test call", test.json()["result"])

        agent = client.post(
            "/v1/agents", headers=headers, json={"name": "ایجنت فروش", "role": "sales"}
        )
        agent.raise_for_status()
        agent_id = agent.json()["id"]

        bind = client.put(
            f"/v1/agents/{agent_id}/tools",
            headers=headers,
            json=[
                {"tool_id": created["id"], "permission_level": "confirm"},
                {"tool_id": calendar_tool["id"], "permission_level": "auto"},
            ],
        )
        bind.raise_for_status()
        show("bound tools", [row["permission_level"] for row in bind.json()])

        schemas = client.get(
            "/v1/tools/llm-schemas", params={"agent_id": agent_id}, headers=headers
        ).json()
        show("what the model sees", [{"name": row["name"], "slug": row["slug"]} for row in schemas])

        mcp = client.post(
            "/v1/mcp-servers",
            headers=headers,
            json={"name": "سرور MCP نمونه", "url": "http://127.0.0.1:8020/mcp", "transport": "http"},
        )
        mcp.raise_for_status()
        show("mcp server registered", {"id": mcp.json()["id"], "transport": mcp.json()["transport"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
