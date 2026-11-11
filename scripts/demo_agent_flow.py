"""Live demo of step 3: editable prompts, versioning and agent binding.

Prereq: API running on :8010 (scripts\\dev.ps1). No AI provider key needed.
"""

from __future__ import annotations

import contextlib
import json
import sys

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
            "/v1/auth/login",
            json={"email": "admin@openbot.local", "password": "admin12345"},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 1) agent bound to the seeded accountant persona
        agent = client.post(
            "/v1/agents",
            headers=headers,
            json={
                "name": "حسابدار ارشد",
                "role": "accountant",
                "system_prompt_key": "agent.system.accountant",
                "max_tokens": 2048,
                "temperature": "0.2",
                "monthly_budget_irr": 5_000_000,
            },
        )
        agent.raise_for_status()
        agent_body = agent.json()
        show("agent created", {"id": agent_body["id"], "name": agent_body["name"]})

        first = client.get(f"/v1/agents/{agent_body['id']}/prompt", headers=headers).json()
        show(
            "effective prompt (seeded persona, v1)",
            {"version": first["version"], "head": first["rendered"][:180] + "…"},
        )

        # 2) tenant override for the same prompt key
        override = client.post(
            "/v1/prompts",
            headers=headers,
            json={
                "key": "agent.system.accountant",
                "title_fa": "حسابدار (نسخه سازمان)",
                "template": (
                    "تو «{{agent.name}}»، حسابدار «{{org.name}}» هستی. امروز {{today_jalali}}.\n"
                    "همیشه ابتدا مانده‌ی حساب‌ها را نشان بده و سپس پیشنهاد سند بده."
                ),
                "kind": "agent.system",
                "publish": True,
            },
        )
        override.raise_for_status()
        prompt = override.json()
        show("org override created", {"version": prompt["current_version"], "status": prompt["status"]})

        after_override = client.get(
            f"/v1/agents/{agent_body['id']}/prompt", headers=headers
        ).json()
        show(
            "effective prompt now uses the override",
            {"version": after_override["version"], "text": after_override["rendered"]},
        )

        # 3) edit the prompt -> the agent follows without any change on the agent
        updated = client.put(
            f"/v1/prompts/{prompt['id']}",
            headers=headers,
            json={
                "template": "ویرایش دوم: تو «{{agent.name}}» حسابدار «{{org.name}}» هستی. {{today_jalali}}",
                "note": "سخت‌گیرتر شدن لحن",
                "publish": True,
            },
        )
        updated.raise_for_status()
        v2 = client.get(f"/v1/agents/{agent_body['id']}/prompt", headers=headers).json()
        show("after edit (v2)", {"version": v2["version"], "rendered": v2["rendered"]})

        # 4) rollback to v1 (append only, new version number)
        rolled = client.post(
            f"/v1/prompts/{prompt['id']}/rollback", headers=headers, json={"version": 1}
        )
        rolled.raise_for_status()
        show("rollback", {"current_version": rolled.json()["current_version"]})

        versions = client.get(f"/v1/prompts/{prompt['id']}/versions", headers=headers).json()
        show(
            "version history",
            [{"version": item["version"], "note": item["note"]} for item in versions],
        )

        # 5) a scheduled task with a prompt key
        task = client.post(
            f"/v1/agents/{agent_body['id']}/tasks",
            headers=headers,
            json={
                "name": "گزارش روزانه فروش",
                "prompt_key": "agent.task.daily_sales_report",
                "trigger_type": "schedule",
                "schedule_cron": "0 8 * * *",
                "requires_approval": True,
            },
        )
        task.raise_for_status()
        show("task created", {"name": task.json()["name"], "cron": task.json()["schedule_cron"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
