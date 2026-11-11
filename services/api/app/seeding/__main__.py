"""python -m app.seeding"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys

from app.seeding.runner import run_seed


def main() -> int:
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf-8")  # Persian output on Windows consoles
    result = asyncio.run(run_seed())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
