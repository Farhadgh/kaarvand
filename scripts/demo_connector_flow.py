"""Live demo of step 6: pair a desktop connector and let a tool touch the disk.

Prereq: API on :8010 (scripts\\dev.ps1 or uvicorn).
The demo starts the reference connector itself, so no manual step is needed.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx

API = "http://127.0.0.1:8010"
ROOT = Path(__file__).resolve().parent.parent


def show(title: str, payload: object) -> None:
    print(f"\n== {title}")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def main() -> int:
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8")

    workdir = tempfile.mkdtemp(prefix="openbot-connector-")
    connector: subprocess.Popen[bytes] | None = None

    with httpx.Client(base_url=API, timeout=90, trust_env=False) as client:
        login = client.post(
            "/v1/auth/login", json={"email": "admin@openbot.local", "password": "admin12345"}
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        device = client.post(
            "/v1/devices", headers=headers, json={"name": "کیف پول مدیر"}
        ).json()
        show("device created", {"id": device["id"], "code": device["pairing_code"]})

        connector = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                str(ROOT / "scripts" / "connector_client.py"),
                "--server",
                API,
                "--code",
                device["pairing_code"],
                "--allow-dir",
                workdir,
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        ops: dict = {}
        for _ in range(20):
            time.sleep(0.5)
            ops = client.get(f"/v1/devices/{device['id']}/ops", headers=headers).json()
            if ops.get("online"):
                break
        show("device online", {"online": ops.get("online"), "ops": ops.get("ops")})

        tool = client.post(
            "/v1/tools",
            headers=headers,
            json={
                "slug": f"demo.fs.{uuid.uuid4().hex[:5]}",
                "name_fa": "نوشتن و فهرست فایل",
                "kind": "connector",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "text": {"type": "string"},
                        "folder": {"type": "string"},
                    },
                    "required": ["file", "text", "folder"],
                },
                "actions": [
                    {"op": "fs.write", "path": "{{input.file}}", "content": "{{input.text}}"},
                    {"op": "fs.list", "path": "{{input.folder}}"},
                ],
                "risk_level": "low",
                "approval_policy": "auto",
                "config": {"device_id": device["id"]},
            },
        ).json()

        target = os.path.join(workdir, "report.txt")
        result = client.post(
            f"/v1/tools/{tool['id']}/test",
            headers=headers,
            json={
                "arguments": {
                    "file": target,
                    "text": "گزارش فروش آبان ۱۴۰۵",
                    "folder": workdir,
                }
            },
        )
        result.raise_for_status()
        show("tool executed on the device", result.json()["result"])

        written = Path(target)
        show(
            "file really written on this machine",
            {"path": str(written), "exists": written.exists(), "text": written.read_text("utf-8") if written.exists() else None},
        )

        blocked = client.post(
            f"/v1/tools/{tool['id']}/test",
            headers=headers,
            json={
                "arguments": {
                    "file": "C:/Windows/System32/evil.txt",
                    "text": "x",
                    "folder": workdir,
                }
            },
        )
        show(
            "write outside allow-dir is blocked",
            {"status": blocked.status_code, "error": blocked.json().get("error")},
        )

    if connector is not None:
        connector.terminate()
        with contextlib.suppress(Exception):
            connector.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
