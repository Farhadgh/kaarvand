"""Capability inference from DB rules (no model names hardcoded in logic)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

FLAG_KEYS = (
    "supports_tools",
    "supports_stream",
    "supports_vision",
    "supports_audio",
    "supports_reasoning",
)


def infer_flags(external_id: str, rules: Iterable[Any]) -> dict[str, bool]:
    """Apply ``capability_rules`` ordered by priority; first match wins per flag."""
    flags: dict[str, bool] = {}
    ordered = sorted(rules, key=lambda rule: getattr(rule, "priority", 100))
    for rule in ordered:
        pattern = getattr(rule, "pattern", "")
        try:
            matched = re.search(pattern, external_id, re.IGNORECASE)
        except re.error:
            continue
        if not matched:
            continue
        for key, value in (getattr(rule, "flags", None) or {}).items():
            if key in FLAG_KEYS and key not in flags:
                flags[key] = bool(value)
    flags.setdefault("supports_stream", True)
    return flags
