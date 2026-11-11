"""Kaarvand API application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.deps import get_db
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging, get_logger
from app.db.session import dispose_engine, set_bypass_rls
from app.schemas.meta import HealthOut

log = get_logger("openbot.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(debug=settings.debug)
    log.info(
        "api.startup",
        env=settings.app_env,
        version=settings.app_version,
        locale=settings.default_locale,
        free_mode=settings.free_mode,
        billing_enabled=settings.billing_enabled,
    )
    yield
    await dispose_engine()
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings: Settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    health = APIRouter(tags=["meta"])

    @health.get("/healthz", response_model=HealthOut)
    async def healthz(db: AsyncSession = Depends(get_db)) -> HealthOut | JSONResponse:
        try:
            await set_bypass_rls(db, True)
            await db.execute(text("select 1"))
        except SQLAlchemyError as exc:  # pragma: no cover - infra failure path
            log.error("healthz.db_error", error=str(exc))
            return JSONResponse(
                status_code=503,
                content={"error": {"code": "system.db_unavailable", "params": {}}},
            )
        return HealthOut(status="ok", db="ok", version=settings.app_version)

    app.include_router(health)
    return app


app = create_app()
