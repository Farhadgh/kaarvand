"""Prompt rendering primitives."""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.prompts.render import base_values, extract_variables, preview, render


def test_extract_variables_keeps_order_and_unique() -> None:
    template = "{{a}} {{ b }} {{a}} {{c.d}}"
    assert extract_variables(template) == ["a", "b", "c.d"]


def test_render_substitutes_values() -> None:
    assert render("سلام {{name}}", {"name": "علی"}) == "سلام علی"


def test_render_none_becomes_empty() -> None:
    assert render("x{{value}}y", {"value": None}) == "xy"


def test_render_strict_raises_stable_code() -> None:
    with pytest.raises(AppError) as exc:
        render("{{missing}}", {})
    assert exc.value.code == "prompt.missing_variables"
    assert exc.value.params["missing"] == ["missing"]


def test_preview_reports_missing_without_raising() -> None:
    result = preview("{{a}} {{b}}", {"a": 1})
    assert result["rendered"] == "1 "
    assert result["missing"] == ["b"]


def test_base_values_include_persian_date() -> None:
    values = base_values(org_name="سازمان نمونه", org_timezone="Asia/Tehran")
    assert values["org.name"] == "سازمان نمونه"
    assert values["org.timezone"] == "Asia/Tehran"
    assert values["today_jalali"]
    assert any(character in "۰۱۲۳۴۵۶۷۸۹" for character in values["today"])


def test_base_values_agent_and_extra() -> None:
    values = base_values(agent_name="حسابدار", agent_role="accountant", extra={"x": 1})
    assert values["agent.name"] == "حسابدار"
    assert values["agent.role"] == "accountant"
    assert values["x"] == 1
