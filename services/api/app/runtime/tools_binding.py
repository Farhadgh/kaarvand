"""Bind the tools an agent may use: schemas for the model + policy metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Agent, AgentTool, Tool
from app.tools.names import llm_index
from app.tools.schema import to_llm_tools


@dataclass(slots=True)
class BoundTool:
    tool: Tool
    permission_level: str


async def load_bound_tools(
    db: AsyncSession, agent: Agent
) -> tuple[dict[str, BoundTool], list[dict[str, Any]], dict[str, str]]:
    rows = (
        await db.execute(
            select(Tool, AgentTool)
            .join(AgentTool, AgentTool.tool_id == Tool.id)
            .where(
                AgentTool.agent_id == agent.id,
                AgentTool.is_enabled.is_(True),
                Tool.is_enabled.is_(True),
            )
            .order_by(Tool.slug)
        )
    ).all()

    bound: dict[str, BoundTool] = {}
    tools: list[Tool] = []
    for tool, binding in rows:
        bound[tool.slug] = BoundTool(tool=tool, permission_level=binding.permission_level)
        tools.append(tool)

    return bound, to_llm_tools(tools), llm_index(tools)
