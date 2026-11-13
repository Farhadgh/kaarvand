"""Test setup.

Tests run against a real PostgreSQL database (``openbot_test``): RLS, JSONB and
pgvector behaviour cannot be faked on SQLite.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import asyncpg
import pytest

API_DIR = Path(__file__).resolve().parent.parent
ENV_LOCAL = API_DIR / ".env.local"


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def swap_db(url: str, dbname: str) -> str:
    head, _, tail = url.rpartition("/")
    _, _, query = tail.partition("?")
    return f"{head}/{dbname}" + (f"?{query}" if query else "")


_ENV = read_env(ENV_LOCAL)
_APP_URL = _ENV.get(
    "APP_DATABASE_URL", "postgresql+asyncpg://openbot_app:openbot@127.0.0.1:5432/openbot"
)
_MIG_URL = _ENV.get("APP_MIGRATION_DATABASE_URL", _APP_URL)

APP_TEST_URL = swap_db(_APP_URL, "openbot_test")
MIG_TEST_URL = swap_db(_MIG_URL, "openbot_test")

os.environ["APP_APP_ENV"] = "test"
os.environ["APP_DATABASE_URL"] = APP_TEST_URL
os.environ["APP_MIGRATION_DATABASE_URL"] = MIG_TEST_URL
os.environ.setdefault("APP_JWT_SECRET", _ENV.get("APP_JWT_SECRET", "test-secret"))
os.environ.setdefault("APP_MASTER_KEY", _ENV.get("APP_MASTER_KEY", ""))
os.environ["APP_FREE_MODE"] = "true"
os.environ["APP_BILLING_ENABLED"] = "false"
os.environ["APP_PAYMENT_GATEWAY"] = "noop"
os.environ["APP_FX_USD_IRR"] = "1000000"  # so runs show a real Toman cost

ADMIN_EMAIL = os.getenv("OPENBOT_ADMIN_EMAIL", "admin@openbot.local")
ADMIN_PASSWORD = os.getenv("OPENBOT_ADMIN_PASSWORD", "admin12345")


def libpq(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _truncate() -> None:
    conn = await asyncpg.connect(libpq(MIG_TEST_URL))
    try:
        rows = await conn.fetch(
            "select tablename from pg_tables "
            "where schemaname = 'public' and tablename <> 'alembic_version'"
        )
        tables = ", ".join(f'"{row["tablename"]}"' for row in rows)
        if tables:
            await conn.execute(f"truncate {tables} cascade")
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def prepared_database() -> None:
    if not ENV_LOCAL.exists():
        pytest.skip("run `python scripts/devdb.py` first to create the local database")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert migration.returncode == 0, migration.stderr

    asyncio.run(_truncate())

    seed = subprocess.run(
        [sys.executable, "-m", "app.seeding"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert seed.returncode == 0, seed.stderr


@pytest.fixture(autouse=True)
async def _engine_guard() -> Any:
    """Each test gets its own event loop; never leak a pooled connection."""
    yield
    from app.db.session import dispose_engine

    await dispose_engine()


@pytest.fixture
async def client() -> Any:
    from httpx import ASGITransport, AsyncClient

    from app.db.session import dispose_engine
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await dispose_engine()


@pytest.fixture
async def admin_tokens(client: Any) -> dict[str, Any]:
    response = await client.post(
        "/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
async def auth_headers(admin_tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_tokens['access_token']}"}


@pytest.fixture
async def viewer_headers(client: Any, admin_tokens: dict[str, Any]) -> dict[str, str]:
    """A read-only user of the same organization (RBAC tests)."""
    import uuid as _uuid

    from app.core.security import hash_password
    from app.db.models import User
    from app.db.session import session_scope

    org_id = admin_tokens["user"]["org_id"]
    email = f"viewer-{_uuid.uuid4().hex[:6]}@openbot.local"
    password = "viewer-pass-123"

    async with session_scope(bypass_rls=True) as db:
        db.add(
            User(
                org_id=_uuid.UUID(org_id),
                email=email,
                full_name="کاربر عادی",
                password_hash=hash_password(password),
                role="user",
            )
        )

    login = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
