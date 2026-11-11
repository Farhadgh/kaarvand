"""Risk policy: can this agent run this tool, and does a human have to approve?"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolDecision:
    allowed: bool
    needs_approval: bool
    code: str | None = None


def decide(
    *,
    risk_level: str,
    permission_level: str,
    approval_policy: str = "auto",
    is_enabled: bool = True,
) -> ToolDecision:
    """Matrix: tool risk x agent permission x tool approval policy.

    * a disabled tool is never callable
    * ``high`` risk always requires a human, even with ``auto`` permission
    * ``deny`` in either place wins
    """
    if not is_enabled:
        return ToolDecision(allowed=False, needs_approval=False, code="tool.disabled")
    if approval_policy == "deny" or permission_level == "deny":
        return ToolDecision(allowed=False, needs_approval=False, code="tool.denied")
    if risk_level == "high":
        return ToolDecision(allowed=True, needs_approval=True)
    if approval_policy == "confirm" or permission_level == "confirm":
        return ToolDecision(allowed=True, needs_approval=True)
    return ToolDecision(allowed=True, needs_approval=False)
