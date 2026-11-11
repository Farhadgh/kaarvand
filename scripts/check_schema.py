"""Schema self-check: downgrade -> upgrade round trip + RLS inventory.

Usage (repo root):
    python scripts/check_schema.py            # checks the test database
    python scripts/check_schema.py --db openbot
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "services" / "api"
ENV_LOCAL = API_DIR / ".env.local"


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip()
    return data


def swap_db(url: str, dbname: str) -> str:
    head, _, tail = url.rpartition("/")
    _, _, query = tail.partition("?")
    return f"{head}/{dbname}" + (f"?{query}" if query else "")


async def inventory(url: str) -> dict[str, object]:
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        tables = await conn.fetch(
            "select tablename from pg_tables where schemaname='public' "
            "and tablename <> 'alembic_version' order by tablename"
        )
        rls = await conn.fetch(
            "select relname, relrowsecurity, relforcerowsecurity from pg_class "
            "where relkind='r' and relnamespace='public'::regnamespace and relrowsecurity"
        )
        policies = await conn.fetch("select count(*) as n from pg_policies")
        ext = await conn.fetch("select extname from pg_extension order by extname")
        return {
            "tables": [r["tablename"] for r in tables],
            "rls_tables": sorted(r["relname"] for r in rls),
            "forced": all(r["relforcerowsecurity"] for r in rls),
            "policies": policies[0]["n"],
            "extensions": [r["extname"] for r in ext],
        }
    finally:
        await conn.close()


def alembic(args: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(f"alembic {' '.join(args)} failed")
    for line in (result.stderr or "").splitlines():
        if re.search(r"Running (upgrade|downgrade)", line):
            print("  " + line.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="openbot_test")
    args = parser.parse_args()

    env_local = read_env(ENV_LOCAL)
    app_url = swap_db(env_local["APP_DATABASE_URL"], args.db)
    mig_url = swap_db(env_local["APP_MIGRATION_DATABASE_URL"], args.db)
    env = {**os.environ, "APP_DATABASE_URL": app_url, "APP_MIGRATION_DATABASE_URL": mig_url}

    print(f"== downgrade base ({args.db})")
    alembic(["downgrade", "base"], env)
    print(f"== upgrade head ({args.db})")
    alembic(["upgrade", "head"], env)
    print(f"== alembic current ({args.db})")
    alembic(["current"], env)

    info = asyncio.run(inventory(mig_url))
    print(f"\ntables          : {len(info['tables'])}")
    print(f"rls tables      : {len(info['rls_tables'])} (force={info['forced']})")
    print(f"rls policies    : {info['policies']}")
    print(f"extensions      : {', '.join(info['extensions'])}")
    print(f"table names     : {', '.join(info['tables'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
