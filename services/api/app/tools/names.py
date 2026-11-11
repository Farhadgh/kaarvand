"""Tool naming: DB slugs use dots, LLM function names must be [a-zA-Z0-9_-]{1,64}."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

_UNSAFE = re.compile(r"[^a-zA-Z0-9_-]+")
MAX_LEN = 64


def llm_name(slug: str) -> str:
    """``office.excel.append_row`` -> ``office_excel_append_row``."""
    cleaned = _UNSAFE.sub("_", slug or "")
    cleaned = re.sub(r"[_-]{2,}", "_", cleaned).strip("_-")
    return (cleaned or "tool")[:MAX_LEN]


def llm_index(tools: Iterable[Any]) -> dict[str, str]:
    """Map LLM function name -> database slug (collisions get a numeric suffix)."""
    index: dict[str, str] = {}
    for tool in tools:
        slug = tool.slug
        candidate = llm_name(slug)
        if candidate not in index:
            index[candidate] = slug
            continue
        counter = 2
        while f"{candidate[: MAX_LEN - 3]}_{counter}" in index:
            counter += 1
        index[f"{candidate[: MAX_LEN - 3]}_{counter}"] = slug
    return index


def slug_for(name: str, index: dict[str, str]) -> str | None:
    """Reverse lookup: assistant tool call name -> slug."""
    return index.get(name) or (name if name in index.values() else None)
