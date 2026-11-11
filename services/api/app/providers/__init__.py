"""Provider registry package."""

from app.providers.registry import get_adapter, known_kinds

__all__ = ["get_adapter", "known_kinds"]
