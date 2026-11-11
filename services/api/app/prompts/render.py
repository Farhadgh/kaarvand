"""Prompt rendering: ``{{variable}}`` substitution with strict validation."""

from __future__ import annotations

import re
from typing import Any

from app.core.errors import AppError
from app.core.jalali import format_jalali, today_jalali

VARIABLE = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")


def extract_variables(template: str) -> list[str]:
    seen: list[str] = []
    for match in VARIABLE.finditer(template or ""):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def render(template: str, values: dict[str, Any], *, strict: bool = True) -> str:
    """Replace placeholders; in strict mode unknown variables raise a stable code."""
    missing = [name for name in extract_variables(template) if name not in values]
    if missing and strict:
        raise AppError(
            code="prompt.missing_variables",
            status_code=422,
            params={"missing": missing},
        )

    def _replace(match: re.Match[str]) -> str:
        value = values.get(match.group(1))
        return "" if value is None else str(value)

    return VARIABLE.sub(_replace, template or "")


def base_values(
    *,
    org_name: str = "",
    org_timezone: str = "Asia/Tehran",
    agent_name: str | None = None,
    agent_role: str | None = None,
    extra: dict[str, Any] | None = None,
    digits: str = "fa",
) -> dict[str, Any]:
    """Values every prompt may rely on (Persian date included)."""
    values: dict[str, Any] = {
        "org.name": org_name,
        "org.timezone": org_timezone,
        "today_jalali": today_jalali(org_timezone, digits=digits),
        "today": format_jalali(__import__("datetime").datetime.now(), digits=digits),
    }
    if agent_name is not None:
        values["agent.name"] = agent_name
    if agent_role is not None:
        values["agent.role"] = agent_role
    if extra:
        values.update(extra)
    return values


def preview(template: str, values: dict[str, Any]) -> dict[str, Any]:
    rendered = render(template, values, strict=False)
    return {
        "rendered": rendered,
        "variables": extract_variables(template),
        "missing": [name for name in extract_variables(template) if name not in values],
    }
