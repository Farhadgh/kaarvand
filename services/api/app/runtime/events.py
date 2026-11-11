"""SSE event helpers for run streaming."""

from __future__ import annotations

import json
from typing import Any


def event(name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"event": name, "data": payload or {}}


def encode(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


SSE_HEADERS = {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
