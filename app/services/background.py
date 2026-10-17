"""Background tasks owned by the app process (evaluation runs, corpus ingestion).

asyncio keeps only weak references to tasks, so they are held here until done
and cancelled at shutdown.
"""
import asyncio
import logging
from typing import Coroutine

logger = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()


def spawn(coro: Coroutine, name: str) -> asyncio.Task:
    """Run a coroutine in the background; failures are logged."""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)

    def _done(t: asyncio.Task) -> None:
        _tasks.discard(t)
        if not t.cancelled() and t.exception():
            logger.error("Background task %s failed", name, exc_info=t.exception())

    task.add_done_callback(_done)
    return task


async def cancel_background_tasks() -> None:
    for task in list(_tasks):
        task.cancel()
    if _tasks:
        await asyncio.gather(*_tasks, return_exceptions=True)
