"""Metadata registry + logical table groups (used to split migrations)."""

from __future__ import annotations

from app.db import models as _models  # noqa: F401  (registers all mappers)
from app.db.base_class import Base

# Logical groups: `ALEMBIC_GROUPS=core alembic revision --autogenerate` only
# compares the tables of that group, which keeps migrations small and readable.
GROUPS: dict[str, tuple[str, ...]] = {
    "core": (
        "organizations",
        "users",
        "memberships",
        "api_keys",
        "sessions",
        "user_mfa",
        "login_attempts",
        "app_settings",
    ),
    "locale": ("translations",),
    "providers": (
        "provider_adapters",
        "providers",
        "models",
        "price_history",
        "capability_rules",
    ),
    "prompts": ("prompts", "prompt_versions", "prompt_examples"),
    "agents": ("agents", "agent_workflows", "agent_tasks"),
    "tools": ("tools", "mcp_servers", "devices", "device_tools", "agent_tools"),
    "runtime": (
        "conversations",
        "messages",
        "runs",
        "trace_spans",
        "tool_invocations",
        "usage_ledger",
        "audit_logs",
        "knowledge_bases",
        "documents",
        "chunks",
        "plans",
        "wallets",
        "wallet_transactions",
        "feature_flags",
    ),
}

__all__ = ["Base", "GROUPS"]
