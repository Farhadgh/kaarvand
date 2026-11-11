"""Shared pydantic schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    params: dict[str, Any] = {}


class ErrorEnvelope(BaseModel):
    """Every error response looks like {"error": {"code": ..., "params": ...}}."""

    error: ErrorBody


class OkOut(BaseModel):
    ok: bool = True
    code: str | None = None
