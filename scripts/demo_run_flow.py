"""Live demo of step 5: a real agent run with streaming, a tool call and cost.

Prereq:
    python scripts\\fake_provider.py      # :8020 (answers + calls the first tool)
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
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8")

    with httpx.Client(base_url=API, timeout=120, trust_env=False) as client:
        login = client.post(
            "/v1/auth/login", json={"email": "admin@openbot.local", "password": "admin12345"}
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 1) provider + model
        provider = client.post(
            "/v1/providers",
            headers=headers,
            json={
                "name": f"دمو اجرا {uuid.uuid4().hex[:5]}",
                "kind": "openai_compatible",
                "base_url": "http://127.0.0.1:8020/v1",
                "api_key": "sk-demo-run",
            },
        ).json()
        client.post(f"/v1/providers/{provider['id']}/sync-models", headers=headers).raise_for_status()
        client.post(f"/v1/providers/{provider['id']}/sync-prices", headers=headers).raise_for_status()
        models = client.get(
            "/v1/models", params={"provider_id": provider["id"]}, headers=headers
        ).json()
        model = next(m for m in models if m["external_id"] == "fake-chat")

        # 2) agent + bound builtin tool
        agent = client.post(
            "/v1/agents",
            headers=headers,
            json={
                "name": "دستیار عملیاتی",
                "role": "assistant",
                "system_prompt_key": "agent.system.default",
                "model_id": model["id"],
                "max_tokens": 512,
                "temperature": "0.2",
            },
        ).json()
        tools = client.get("/v1/tools", headers=headers).json()
        calendar = next(t for t in tools if t["slug"] == "system.now_jalali")
        client.put(
            f"/v1/agents/{agent['id']}/tools",
            headers=headers,
            json=[{"tool_id": calendar["id"], "permission_level": "auto"}],
        ).raise_for_status()

        # 3) run with SSE streaming
        tokens: list[str] = []
        events: list[str] = []
        with client.stream(
            "POST",
            f"/v1/agents/{agent['id']}/runs",
            headers=headers,
            json={"input": "امروز چندم است؟", "stream": True},
        ) as response:
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                item = json.loads(line[6:])
                events.append(item["event"])
                if item["event"] == "token":
                    tokens.append(item["data"]["text"])

        show("streamed tokens", "".join(tokens))
        show("event order", events)

        runs = client.get("/v1/runs", params={"agent_id": agent["id"]}, headers=headers).json()
        run = runs[0]
        show(
            "run record",
            {
                "status": run["status"],
                "steps": run["steps_taken"],
                "tokens_in": run["tokens_in"],
                "tokens_out": run["tokens_out"],
                "cost_usd": run["cost_usd"],
                "cost_irr": run["cost_irr"],
            },
        )
        show(
            "tool invocations",
            [
                {"slug": i["tool_slug"], "status": i["status"]}
                for i in client.get(
                    f"/v1/runs/{run['id']}/invocations", headers=headers
                ).json()
            ],
        )

        # 4) a high risk tool -> human approval
        device_tool = client.post(
            "/v1/tools",
            headers=headers,
            json={
                "slug": f"demo.print.{uuid.uuid4().hex[:5]}",
                "name_fa": "چاپ سند",
                "kind": "connector",
                "input_schema": {"type": "object", "properties": {}},
                "actions": [{"op": "print"}],
                "risk_level": "high",
                "approval_policy": "confirm",
            },
        ).json()
        client.put(
            f"/v1/agents/{agent['id']}/tools",
            headers=headers,
            json=[{"tool_id": device_tool["id"], "permission_level": "auto"}],
        ).raise_for_status()

        blocked = client.post(
            f"/v1/agents/{agent['id']}/runs",
            headers=headers,
            json={"input": "سند را چاپ کن", "stream": False},
        ).json()
        show(
            "high risk run",
            {"status": blocked["run"]["status"], "events": [e["event"] for e in blocked["events"]]},
        )

        approved = client.post(
            f"/v1/runs/{blocked['run']['id']}/approve",
            headers=headers,
            json={"stream": False},
        ).json()
        show(
            "after approval",
            {
                "status": approved["run"]["status"],
                "events": [e["event"] for e in approved["events"]],
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
