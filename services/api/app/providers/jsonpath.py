"""Minimal JSON path resolver used by the declarative adapter.

Supports the small subset providers actually need:
    $.data[0].id
    $.choices[*].message.content
    $.data[*].pricing.prompt
"""

from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"\.?([A-Za-z0-9_\-]+)|\[(\*|\d+)\]")


def resolve(data: Any, path: str) -> Any:
    if not path:
        return None
    expression = path.strip()
    if expression.startswith("$"):
        expression = expression[1:]

    current: list[Any] = [data]
    for key, index in _TOKEN.findall(expression):
        next_values: list[Any] = []
        for item in current:
            if key and isinstance(item, dict):
                next_values.append(item.get(key))
            elif index == "*" and isinstance(item, list):
                next_values.extend(item)
            elif index.isdigit() and isinstance(item, list) and int(index) < len(item):
                next_values.append(item[int(index)])
        current = next_values
        if not current:
            return None
    return current if len(current) > 1 else current[0]


def resolve_list(data: Any, path: str) -> list[Any]:
    value = resolve(data, path)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def fill(template: Any, variables: dict[str, Any]) -> Any:
    """Recursively substitute ``{{name}}`` placeholders inside JSON structures."""
    if isinstance(template, str):
        whole = re.fullmatch(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}", template.strip())
        if whole:
            return variables.get(whole.group(1), template)
        return re.sub(
            r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}",
            lambda match: str(variables.get(match.group(1), match.group(0))),
            template,
        )
    if isinstance(template, dict):
        return {key: fill(value, variables) for key, value in template.items()}
    if isinstance(template, list):
        return [fill(item, variables) for item in template]
    return template
