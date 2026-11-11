"""Tool primitives: names, schema validation, policy, actions, request building."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.errors import AppError
from app.tools.actions import validate_actions
from app.tools.http_exec import build_request
from app.tools.names import llm_index, llm_name
from app.tools.policy import decide
from app.tools.schema import to_llm_tool, validate_arguments

SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"}, "count": {"type": "integer"}},
    "required": ["text"],
}


class FakeTool:
    slug = "demo.http.send"
    name_fa = "ارسال دمو"
    description_fa = "یک ابزار آزمایشی"
    input_schema = SCHEMA
    secret_enc = None

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}


def test_llm_name_sanitizes_dots() -> None:
    assert llm_name("office.excel.append_row") == "office_excel_append_row"
    assert llm_name("--weird--slug--") == "weird_slug"
    assert len(llm_name("a" * 200)) == 64


def test_llm_index_dedupes_collisions() -> None:
    class T:
        def __init__(self, slug: str) -> None:
            self.slug = slug

    index = llm_index([T("a.b"), T("a_b"), T("a-b")])
    assert len(index) == 3
    assert index["a_b"] == "a.b"
    assert "a_b_2" in index


def test_validate_arguments_accepts_valid() -> None:
    validate_arguments(SCHEMA, {"text": "سلام"})


def test_validate_arguments_rejects_missing_required() -> None:
    with pytest.raises(AppError) as exc:
        validate_arguments(SCHEMA, {})
    assert exc.value.code == "tool.invalid_arguments"


def test_validate_arguments_rejects_wrong_type() -> None:
    with pytest.raises(AppError) as exc:
        validate_arguments(SCHEMA, {"text": "x", "count": "not-an-int"})
    assert exc.value.code == "tool.invalid_arguments"
    assert exc.value.params["path"] == "count"


@pytest.mark.parametrize(
    ("risk", "permission", "policy", "allowed", "approval"),
    [
        ("low", "auto", "auto", True, False),
        ("low", "confirm", "auto", True, True),
        ("low", "auto", "confirm", True, True),
        ("medium", "auto", "auto", True, False),
        ("medium", "confirm", "auto", True, True),
        ("high", "auto", "auto", True, True),
        ("high", "confirm", "auto", True, True),
        ("low", "deny", "auto", False, False),
        ("low", "auto", "deny", False, False),
    ],
)
def test_policy_matrix(
    risk: str, permission: str, policy: str, allowed: bool, approval: bool
) -> None:
    decision = decide(risk_level=risk, permission_level=permission, approval_policy=policy)
    assert decision.allowed is allowed
    assert decision.needs_approval is approval


def test_policy_disabled_tool() -> None:
    decision = decide(risk_level="low", permission_level="auto", is_enabled=False)
    assert decision.allowed is False
    assert decision.code == "tool.disabled"


def test_validate_actions_accepts_action_script() -> None:
    script = [
        {"op": "office.open", "app": "excel", "path": "D:/a.xlsx"},
        {"op": "office.cells", "sheet": "Sheet1", "append": [1, 2]},
        {"op": "office.save"},
    ]
    assert validate_actions(script) == script


def test_validate_actions_rejects_unknown_op() -> None:
    with pytest.raises(AppError) as exc:
        validate_actions([{"op": "teleport"}])
    assert exc.value.code == "tool.invalid_actions"
    assert exc.value.params["reason"] == "unknown_op"


def test_validate_actions_rejects_missing_field() -> None:
    with pytest.raises(AppError) as exc:
        validate_actions([{"op": "office.open", "app": "excel"}])
    assert exc.value.params["field"] == "path"


def test_build_request_fills_templates() -> None:
    tool = FakeTool(
        {
            "method": "POST",
            "url": "{{base_url}}/send",
            "base_url": "https://api.demo.test",
            "allowed_domains": ["demo.test"],
            "headers": {"X-Custom": "{{tag}}"},
            "body": {"text": "{{text}}", "fixed": 1},
            "response_map": {"id": "$.id"},
        }
    )
    request = build_request(tool, {"text": "سلام", "tag": "abc"})
    assert request["url"] == "https://api.demo.test/send"
    assert request["headers"]["X-Custom"] == "abc"
    assert request["json"] == {"text": "سلام", "fixed": 1}
    assert request["method"] == "POST"


def test_build_request_blocks_foreign_domain() -> None:
    tool = FakeTool({"url": "https://evil.test/x", "allowed_domains": ["demo.test"]})
    with pytest.raises(AppError) as exc:
        build_request(tool, {})
    assert exc.value.code == "tool.domain_not_allowed"


def test_build_request_rejects_non_ascii_header() -> None:
    tool = FakeTool(
        {
            "url": "https://api.demo.test/x",
            "allowed_domains": ["demo.test"],
            "headers": {"X-Trace": "{{text}}"},
        }
    )
    with pytest.raises(AppError) as exc:
        build_request(tool, {"text": "سلام"})
    assert exc.value.code == "tool.invalid_header"


def test_build_request_requires_url() -> None:
    with pytest.raises(AppError) as exc:
        build_request(FakeTool({}), {})
    assert exc.value.code == "tool.missing_url"


def test_to_llm_tool_shape() -> None:
    payload = to_llm_tool(FakeTool())
    assert payload["type"] == "function"
    assert payload["function"]["name"] == "demo_http_send"
    assert payload["function"]["parameters"] == SCHEMA
