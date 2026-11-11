"""Live end-to-end demo of the dynamic provider flow.

Requires:
    python scripts/fake_provider.py                # :8020 (fake OpenAI-compatible)
    scripts\\dev.ps1 (or uvicorn) on :8010 with APP_FX_USD_IRR set

Then:
    python scripts/demo_provider_flow.py
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
        sys.stdout.reconfigure(encoding="utf-8")  # Persian output on Windows consoles

    with httpx.Client(base_url=API, timeout=90, trust_env=False) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@openbot.local", "password": "admin12345"},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        show("login", {"user": login.json()["user"]["full_name"], "role": login.json()["user"]["role"]})

        created = client.post(
            "/v1/providers",
            headers=headers,
            json={
                "name": "پروایدر آزمایشی محلی",
                "kind": "openai_compatible",
                "base_url": "http://127.0.0.1:8020/v1",
                "api_key": "sk-fake-local-key-123456",
                "priority": 10,
            },
        )
        created.raise_for_status()
        provider = created.json()
        show("provider created", provider)
        provider_id = provider["id"]

        show("connection test", client.post(f"/v1/providers/{provider_id}/test", headers=headers).json())
        show("sync models", client.post(f"/v1/providers/{provider_id}/sync-models", headers=headers).json())
        show("sync prices", client.post(f"/v1/providers/{provider_id}/sync-prices", headers=headers).json())

        models = client.get(
            "/v1/models", params={"provider_id": provider_id}, headers=headers
        ).json()
        show(
            "models (capability inference)",
            [
                {
                    "id": model["external_id"],
                    "tools": model["supports_tools"],
                    "vision": model["supports_vision"],
                    "tools_price_in": model["input_price"],
                    "tools_price_out": model["output_price"],
                }
                for model in models
            ],
        )

        target = next(model for model in models if model["external_id"] == "fake-chat")
        probe = client.post(
            f"/v1/models/{target['id']}/probe",
            headers=headers,
            json={"prompt": "سلام، خودت را معرفی کن", "max_tokens": 64},
        )
        print("\n== probe status:", probe.status_code)
        show("probe (stream + cost)", probe.json())

        history = client.get(f"/v1/models/{target['id']}/prices", headers=headers).json()
        show("price history", history)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
