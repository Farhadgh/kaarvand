"""Generate + apply one migration per logical schema group.

Usage (from repo root):
    python scripts/mkmig.py core     0001 core_tenancy
    python scripts/mkmig.py providers 0003 providers_registry
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "services" / "api"


def run(args: list[str], env: dict[str, str]) -> None:
    print(f"$ alembic {' '.join(args)}")
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if out:
        print(out[-2000:])
    if err:
        # alembic logs to stderr; only surface warnings/errors and detected changes
        interesting = [
            line
            for line in err.splitlines()
            if "Detected" in line or "ERROR" in line or "Error" in line or "WARN" in line
        ]
        for line in interesting[-25:]:
            print("  " + line)
    if result.returncode != 0:
        print(err[-3000:])
        raise SystemExit(f"alembic failed with code {result.returncode}")


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    group, rev_id, message = sys.argv[1:4]
    env = {**os.environ, "ALEMBIC_GROUPS": group, "PYTHONIOENCODING": "utf-8"}

    run(["revision", "--autogenerate", "-m", message, "--rev-id", rev_id], env)
    run(["upgrade", "head"], env)
    run(["current"], env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
