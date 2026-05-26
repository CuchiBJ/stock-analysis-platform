"""Decorator that captures unhandled exceptions from async scheduler tasks
and persists them to `scheduler_errors` so they surface in the health
endpoint instead of disappearing into `Task exception was never retrieved`.
"""
from __future__ import annotations

import functools
import logging
import sys
import traceback as tb_module
from datetime import datetime
from typing import Callable, Awaitable, Any

from app.core.deps import AsyncSessionLocal
from app.models.stock import SchedulerError

logger = logging.getLogger(__name__)


def track_task_errors(task_name: str) -> Callable:
    """Wrap an async function so any raised Exception is logged AND persisted
    to `scheduler_errors`. The original exception is swallowed (task fails
    quietly) — the same behavior as before, but now visible.

    Usage:
        @track_task_errors(task_name="evaluate_outcomes")
        async def _evaluate_pending_outcomes(self):
            ...
    """

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                tb_str = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))
                logger.error(
                    f"[task_error_tracker] {task_name} raised {type(exc).__name__}: {exc}\n{tb_str}"
                )
                try:
                    async with AsyncSessionLocal() as session:
                        session.add(
                            SchedulerError(
                                task_name=task_name,
                                exception_type=type(exc).__name__,
                                exception_message=str(exc)[:5000],
                                traceback=tb_str[:20000],
                                occurred_at=datetime.utcnow(),
                                resolved=False,
                            )
                        )
                        await session.commit()
                except Exception as persist_exc:
                    print(
                        f"[task_error_tracker] FAILED to persist error for {task_name}: {persist_exc}",
                        file=sys.stderr,
                    )
                return None

        return wrapper

    return decorator
