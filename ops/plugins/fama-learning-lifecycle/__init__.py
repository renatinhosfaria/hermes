"""Let native learning reviews finish before a short CLI worker exits."""
from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


def drain_cli_reviews(*, platform: str, timeout_seconds: float = 300, **_: object):
    """Bounded last-chance drain; gateway sessions keep asynchronous delivery.

    One CLI process owns its native bg-review threads. The finalization hook is
    synchronous and runs before one-shot client cleanup. No tools, permissions,
    model settings or review decisions are changed here.
    """
    if platform != "cli":
        return None
    current = threading.current_thread()
    reviews = [
        thread for thread in threading.enumerate()
        if thread.name == "bg-review" and thread is not current and thread.is_alive()
    ]
    deadline = time.monotonic() + max(0, timeout_seconds)
    for thread in reviews:
        thread.join(max(0, deadline - time.monotonic()))
    pending = sum(thread.is_alive() for thread in reviews)
    if reviews:
        logger.log(
            logging.WARNING if pending else logging.INFO,
            "Learning CLI drain: waited=%d pending=%d", len(reviews), pending,
        )
    return {"waited": len(reviews), "pending": pending}


def register(ctx) -> None:
    ctx.register_hook("on_session_finalize", drain_cli_reviews)
