"""Argument validation and conversion to the LLM tool schema."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from app.core.errors import AppError
from app.tools.names import llm_name

EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


def validate_arguments(schema: dict[str, Any] | None, arguments: dict[str, Any]) -> None:
    if not schema or not schema.get("properties") and not schema.get("required"):
        return
    try:
        Draft202012Validator(schema).validate(arguments)
    except ValidationError as exc:
        path = "/".join(str(part) for part in exc.absolute_path)
        raise AppError(
            code="tool.invalid_arguments",
            status_code=422,
            params={"path": path, "message": str(exc.message)[:300]},
        ) from exc


def validate_schema_definition(schema: dict[str, Any]) -> None:
    """Reject a broken input schema at creation time, not at call time."""
    if not schema:
        return
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001 - jsonschema raises its own types
        raise AppError(
            code="tool.invalid_schema",
            status_code=422,
            params={"message": str(exc)[:300]},
        ) from exc


def to_llm_tool(tool: Any) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": llm_name(tool.slug),
            "description": tool.description_fa or tool.name_fa,
            "parameters": tool.input_schema or EMPTY_SCHEMA,
        },
    }


def to_llm_tools(tools: list[Any]) -> list[dict[str, Any]]:
    return [to_llm_tool(tool) for tool in tools]
