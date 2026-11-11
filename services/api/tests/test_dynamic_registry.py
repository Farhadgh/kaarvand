"""Guard: providers / models / prompts must never be hardcoded in logic.

This is the regression test for the "everything dynamic" contract. If somebody
adds a model id or a prompt string to a service module, CI fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models import Prompt, PromptVersion, ProviderAdapter
from app.db.session import session_scope

APP_DIR = Path(__file__).resolve().parent.parent / "app"

# folders where literal model ids / prompt text are allowed
ALLOWED_DIRS = {"seeding", "db", "core"}

FORBIDDEN_PATTERNS = [
    r"gpt-4o",
    r"gpt-3\.5",
    r"claude-3",
    r"gemini-1\.5",
    r"openrouter/anthropic",
    r"text-embedding-ada",
]


def _iter_sources() -> list[Path]:
    sources: list[Path] = []
    for path in APP_DIR.rglob("*.py"):
        relative = path.relative_to(APP_DIR)
        if relative.parts and relative.parts[0] in ALLOWED_DIRS:
            continue
        sources.append(path)
    return sources


@pytest.mark.parametrize("pattern", FORBIDDEN_PATTERNS)
def test_no_hardcoded_model_ids(pattern: str) -> None:
    regex = re.compile(pattern, re.IGNORECASE)
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in _iter_sources()
        if regex.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"hardcoded {pattern!r} found in {offenders}"


async def test_provider_adapters_come_from_the_database() -> None:
    async with session_scope(bypass_rls=True) as db:
        kinds = set((await db.execute(select(ProviderAdapter.kind))).scalars().all())

    assert {
        "openai",
        "openai_compatible",
        "openrouter",
        "anthropic",
        "gemini",
        "azure_openai",
        "declarative",
    }.issubset(kinds)


async def test_prompts_are_rows_and_versioned() -> None:
    async with session_scope(bypass_rls=True) as db:
        prompts = (await db.execute(select(Prompt))).scalars().all()
        versions = (await db.execute(select(PromptVersion))).scalars().all()

    assert len(prompts) >= 9
    assert all(p.locale == "fa" for p in prompts)
    assert all(p.template.strip() for p in prompts)
    assert {v.prompt_id for v in versions} == {p.id for p in prompts}
