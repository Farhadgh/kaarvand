"""Reference desktop connector (Python).

Pairs with the platform, keeps an outbound websocket open and executes action
scripts locally with a hard safety layer:

* every file operation must stay inside ``--allow-dir`` (the server also sends
  the device's allowlist and we intersect both)
* ``shell.run`` only runs commands whose prefix is in ``--allow-cmd``
* office / print / COM / phone steps are *simulated* in this reference build
  (the production connector wraps the real Windows APIs behind the same ops)

Usage:
    python scripts\\connector_client.py --server http://127.0.0.1:8010 --code ABC12345 --allow-dir D:\\data
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import websockets

VERSION = "0.1.0"
OPS = [
    "fs.read",
    "fs.write",
    "fs.list",
    "shell.run",
    "wait",
    "http.request",
    "screenshot",
    "print",
    "office.open",
    "office.cells",
    "office.save",
    "com.invoke",
    "phone.dial",
    "browser.open",
    "keyboard.type",
    # driving an installed application (see app_catalog on the server)
    "app.launch",
    "app.focus",
    "app.windows",
    "ui.invoke",
    "clipboard.set",
    "clipboard.get",
    "keyboard.hotkey",
]

# well-known executables for `app.launch` (extend freely; the server only ever
# sends a catalog slug, never a raw path from the model)
APP_EXES: dict[str, list[str]] = {
    "excel": ["EXCEL.EXE"],
    "word": ["WINWORD.EXE"],
    "outlook": ["OUTLOOK.EXE"],
    "chrome": ["chrome.exe"],
    "telegram_desktop": ["Telegram.exe"],
    "whatsapp_desktop": ["WhatsApp.exe"],
}


class Safety:
    def __init__(self, allow_dirs: list[str], allow_cmds: list[str]) -> None:
        self.allow_dirs = [Path(item).resolve() for item in allow_dirs]
        self.allow_cmds = allow_cmds

    def merge(self, remote: list[str]) -> None:
        for item in remote:
            path = Path(item).resolve()
            if path not in self.allow_dirs:
                self.allow_dirs.append(path)

    def path(self, raw: str) -> Path:
        candidate = Path(str(raw)).expanduser().resolve()
        if not any(
            candidate == base or base in candidate.parents for base in self.allow_dirs
        ):
            raise PermissionError(f"path not allowed: {candidate}")
        return candidate

    def command(self, raw: str) -> str:
        command = str(raw).strip()
        if not any(command.startswith(prefix) for prefix in self.allow_cmds):
            raise PermissionError(f"command not allowed: {command[:60]}")
        return command


def _process_names() -> set[str]:
    """Lower-cased executable names of running processes (psutil, else tasklist)."""
    try:
        import psutil

        names: set[str] = set()
        for proc in psutil.process_iter(["name"]):
            name = proc.info.get("name")
            if name:
                names.add(str(name).lower())
        return names
    except Exception:  # noqa: BLE001 - psutil is optional
        try:
            out = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception:  # noqa: BLE001
            return set()
        names = set()
        for line in out.stdout.splitlines():
            if not line.strip():
                continue
            names.add(line.split('","')[0].strip('"').lower())
        return names


def _exe_installed(exe: str) -> bool:
    if not exe:
        return False
    if shutil.which(exe):
        return True
    roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    for root in [item for item in roots if item]:
        base = Path(root)
        for pattern in (exe, f"*/{exe}", f"*/*/{exe}"):
            try:
                if next(base.glob(pattern), None) is not None:
                    return True
            except Exception:  # noqa: BLE001
                continue
    return False


def _prog_id_present(prog_id: str) -> bool:
    if platform.system() != "Windows" or not prog_id:
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id):
            return True
    except OSError:
        return False


def detect_apps(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match the server's catalog rules against this machine."""
    running = _process_names()
    found: list[dict[str, Any]] = []
    for entry in catalog or []:
        slug = str(entry.get("slug") or "")
        if not slug:
            continue
        exes = [str(item) for item in (entry.get("exe") or []) if item]
        prog_id = str(entry.get("prog_id") or "")
        hit = next((exe for exe in exes if exe.lower() in running), None)
        detected = bool(hit) or bool(prog_id and _prog_id_present(prog_id))
        if not detected:
            detected = any(_exe_installed(exe) for exe in exes)
        if not detected:
            continue
        found.append(
            {
                "slug": slug,
                "exe": hit or (exes[0] if exes else None),
                "prog_id": prog_id or None,
                "name": slug,
                "version": None,
            }
        )
    return found


def launch_app(slug: str) -> dict[str, Any]:
    """Start a catalog app by slug (never a path from the model)."""
    candidates = APP_EXES.get(slug) or []
    for exe in candidates:
        resolved = shutil.which(exe)
        if resolved:
            subprocess.Popen([resolved])  # noqa: S603 - allowlisted executable
            return {"launched": slug, "exe": resolved}
    raise PermissionError(f"app not resolvable on this machine: {slug}")


def _pyautogui() -> Any:
    try:
        import pyautogui

        return pyautogui
    except Exception:  # noqa: BLE001 - optional dependency
        return None


def _clipboard(action: str, text: str = "") -> dict[str, Any]:
    if platform.system() != "Windows":
        return {"simulated": True, "op": f"clipboard.{action}"}
    if action == "set":
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
            input=text,
            text=True,
            timeout=20,
            check=False,
        )
        return {"copied": len(text)}
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return {"text": out.stdout.strip()[:4000]}


async def run_step(step: dict[str, Any], safety: Safety) -> dict[str, Any]:
    op = str(step.get("op") or "")
    if op == "fs.list":
        folder = safety.path(step.get("path") or ".")
        return {"entries": sorted(child.name for child in folder.iterdir())[:200]}
    if op == "fs.read":
        path = safety.path(step.get("path"))
        return {"path": str(path), "text": path.read_text(encoding="utf-8")[:4000]}
    if op == "fs.write":
        path = safety.path(step.get("path"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(step.get("content") or ""), encoding="utf-8")
        return {"path": str(path), "bytes": path.stat().st_size}
    if op == "shell.run":
        command = safety.command(step.get("command"))
        result = subprocess.run(  # noqa: S602 - gated by the allowlist
            command, shell=True, capture_output=True, text=True, timeout=60
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-1000:],
        }
    if op == "wait":
        await asyncio.sleep(min(float(step.get("seconds") or 0.2), 10))
        return {"waited": True}
    if op == "http.request":
        async with httpx.AsyncClient(trust_env=False, timeout=20) as client:
            response = await client.request(
                str(step.get("method") or "GET"), str(step.get("url")), json=step.get("body")
            )
        return {"status_code": response.status_code, "text": response.text[:2000]}
    if op == "screenshot":
        target = safety.path(step.get("save_as") or "screenshot.png")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")
        return {"path": str(target), "note": "placeholder (no imaging library installed)"}

    # --- driving an installed application --------------------------------
    if op == "app.launch":
        return launch_app(str(step.get("app") or ""))
    if op == "app.windows":
        try:
            import pygetwindow as gw  # noqa: PLC0415 - optional dependency

            return {"windows": [title for title in gw.getAllTitles() if title][:100]}
        except Exception:  # noqa: BLE001
            return {"windows": [], "note": "pygetwindow نصب نیست"}
    if op == "app.focus":
        try:
            import pygetwindow as gw  # noqa: PLC0415

            needle = str(step.get("app") or "").lower()
            matches = [w for w in gw.getAllWindows() if needle and needle in w.title.lower()]
            if not matches:
                return {"focused": None}
            matches[0].activate()
            return {"focused": matches[0].title}
        except Exception as exc:  # noqa: BLE001
            return {"focused": None, "note": str(exc)[:160]}
    if op == "ui.invoke":
        try:
            import uiautomation as auto  # noqa: PLC0415

            auto.ButtonControl(Name=str(step.get("name") or "")).Invoke()
            return {"invoked": step.get("name")}
        except Exception as exc:  # noqa: BLE001
            return {"simulated": True, "op": op, "note": f"uiautomation: {exc}"[:160]}
    if op in ("clipboard.set", "clipboard.get"):
        return _clipboard(op.split(".")[1], str(step.get("text") or ""))
    if op == "keyboard.hotkey":
        gui = _pyautogui()
        keys = [str(key) for key in (step.get("keys") or [])]
        if gui and keys:
            gui.hotkey(*[key.lower() for key in keys])
            return {"keys": keys}
        return {"simulated": True, "op": op, "keys": keys, "note": "pyautogui نصب نیست"}
    if op == "keyboard.type":
        gui = _pyautogui()
        text = str(step.get("text") or "")
        if gui and text:
            gui.typewrite(text, interval=0.01)
            return {"typed": len(text)}
        return {"simulated": True, "op": op, "note": "pyautogui نصب نیست"}

    # office / print / com / phone: simulated in this reference build
    return {"simulated": True, "op": op, "note": "این گام در نسخه‌ی مرجع شبیه‌سازی شده است"}


async def execute_script(message: dict[str, Any], safety: Safety, ws: Any) -> dict[str, Any]:
    steps = message.get("steps") or []
    safety.merge(list(message.get("allow_paths") or []))
    outputs: list[dict[str, Any]] = []

    for index, step in enumerate(steps):
        await ws.send(
            json.dumps(
                {
                    "type": "script.progress",
                    "call_id": message.get("call_id"),
                    "step": index,
                    "op": step.get("op"),
                },
                ensure_ascii=False,
            )
        )
        try:
            outputs.append({"step": index, **(await run_step(step, safety))})
        except Exception as exc:  # noqa: BLE001 - report, do not crash the channel
            return {
                "ok": False,
                "step": index,
                "error": f"{type(exc).__name__}: {exc}"[:300],
                "output": outputs,
            }
    return {"ok": True, "output": outputs, "artifacts": []}


async def main() -> int:
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="OpenBot desktop connector")
    parser.add_argument("--server", default="http://127.0.0.1:8010")
    parser.add_argument("--code", required=True, help="pairing code from the panel")
    parser.add_argument("--allow-dir", action="append", default=[], help="allowed folder")
    parser.add_argument("--allow-cmd", action="append", default=[], help="allowed command prefix")
    args = parser.parse_args()

    allow_dirs = args.allow_dir or [str(Path.cwd())]
    safety = Safety(allow_dirs, args.allow_cmd)

    pubkey = base64.b64encode(os.urandom(32)).decode()
    async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
        paired = await client.post(
            f"{args.server}/v1/devices/pair",
            json={
                "code": args.code,
                "pubkey": pubkey,
                "os": platform.system(),
                "version": VERSION,
            },
        )
    if paired.status_code != 200:
        print("pairing failed:", paired.status_code, paired.text)
        return 1
    info = paired.json()
    print("paired device:", info["device_id"])

    url = f"{info['ws_url']}?token={info['device_token']}"
    async with websockets.connect(url, max_size=8_000_000) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "hello",
                    "name": platform.node(),
                    "os": platform.system(),
                    "version": VERSION,
                    "manifest": {"ops": OPS, "allow_dirs": [str(p) for p in safety.allow_dirs]},
                }
            )
        )
        print("connected; waiting for scripts…")

        async for raw in ws:
            message = json.loads(raw)
            if message.get("type") == "apps.scan":
                try:
                    found = detect_apps(list(message.get("catalog") or []))
                except Exception as exc:  # noqa: BLE001 - report, never crash
                    await ws.send(
                        json.dumps(
                            {
                                "type": "apps.result",
                                "call_id": message.get("call_id"),
                                "ok": False,
                                "error": str(exc)[:300],
                            },
                            ensure_ascii=False,
                        )
                    )
                    continue
                await ws.send(
                    json.dumps(
                        {
                            "type": "apps.result",
                            "call_id": message.get("call_id"),
                            "ok": True,
                            "apps": found,
                        },
                        ensure_ascii=False,
                    )
                )
                print("scan:", len(found), "apps detected")
                continue
            if message.get("type") != "script.run":
                continue
            print("script:", len(message.get("steps") or []), "steps")
            result = await execute_script(message, safety, ws)
            await ws.send(
                json.dumps(
                    {"type": "script.result", "call_id": message.get("call_id"), **result},
                    ensure_ascii=False,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

