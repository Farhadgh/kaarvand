"""Machine readable error codes.

The API never returns Persian text. It returns a stable ``code`` plus optional
``params``; the web client renders the Persian message from its own catalog.
That keeps every user facing string translatable without touching the backend.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Domain error carrying a stable code."""

    def __init__(
        self,
        code: str,
        *,
        status_code: int = 400,
        params: dict[str, Any] | None = None,
        log_message: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.params = params or {}
        self.log_message = log_message or code

    def as_payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "params": self.params}}


class AuthError(AppError):
    def __init__(self, code: str = "auth.unauthorized", **kw: Any) -> None:
        super().__init__(code, status_code=401, **kw)


class ForbiddenError(AppError):
    def __init__(self, code: str = "auth.forbidden", **kw: Any) -> None:
        super().__init__(code, status_code=403, **kw)


class NotFoundError(AppError):
    def __init__(self, code: str = "common.not_found", **kw: Any) -> None:
        super().__init__(code, status_code=404, **kw)


class ConflictError(AppError):
    def __init__(self, code: str = "common.conflict", **kw: Any) -> None:
        super().__init__(code, status_code=409, **kw)


class ConfigError(AppError):
    def __init__(self, code: str = "config.invalid", **kw: Any) -> None:
        super().__init__(code, status_code=500, **kw)


class BillingDisabledError(AppError):
    def __init__(self, code: str = "billing.disabled", **kw: Any) -> None:
        super().__init__(code, status_code=409, **kw)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.as_payload())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "common.validation_error",
                    "params": {"fields": [err.get("loc") for err in exc.errors()]},
                }
            },
        )
