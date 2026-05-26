#!/usr/bin/env python
"""Standalone CLI: print the data-freshness snapshot and exit 0/1.

Usage:
    python scripts/health_check.py

Exit codes:
    0 — healthy (is_stale=false, recent_errors_24h=0)
    1 — unhealthy (data is stale OR scheduler errors in last 24h)
"""
from __future__ import annotations

import asyncio
import json
import sys

from app.core.deps import AsyncSessionLocal
from app.api.v1.endpoints.health import build_health_snapshot


async def main() -> int:
    async with AsyncSessionLocal() as db:
        snapshot = await build_health_snapshot(db)
    print(json.dumps(snapshot, indent=2))
    return 0 if (not snapshot["is_stale"] and snapshot["recent_errors_24h"] == 0) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
