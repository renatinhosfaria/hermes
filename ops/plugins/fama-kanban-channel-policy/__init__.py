"""Fama policy for isolating external WhatsApp Kanban notifications."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from hermes_cli import kanban_db as kb


logger = logging.getLogger(__name__)


def enforce_whatsapp_wake_only(
    *,
    task_id: str,
    board: Optional[str] = None,
    db_path: Optional[Path] = None,
    **_: object,
) -> bool:
    """Change existing WhatsApp subscriptions to wake-only delivery."""
    conn = None
    try:
        conn = kb.connect(db_path=db_path, board=board)
        subscriptions = kb.list_notify_subs(conn, task_id)
        if not subscriptions:
            logger.error(
                "fama-kanban-channel-policy: policy enforcement failed; "
                "no subscription found for task"
            )
            return False

        changed = False
        for subscription in subscriptions:
            if str(subscription.get("platform") or "").lower() != "whatsapp":
                continue
            if subscription.get("delivery_mode") == "wake":
                continue
            kb.add_notify_sub(
                conn,
                task_id=subscription["task_id"],
                platform=subscription["platform"],
                chat_id=subscription["chat_id"],
                thread_id=subscription.get("thread_id"),
                user_id=subscription.get("user_id"),
                user_id_alt=subscription.get("user_id_alt"),
                chat_type=subscription.get("chat_type"),
                notifier_profile=subscription.get("notifier_profile"),
                delivery_mode="wake",
                delivery_metadata=subscription.get("delivery_metadata"),
            )
            changed = True

        if changed:
            logger.info(
                "fama-kanban-channel-policy: enforced wake-only for task"
            )
        return True
    except Exception as exc:
        logger.error(
            "fama-kanban-channel-policy: policy enforcement failed for task (%s)",
            type(exc).__name__,
        )
        return False
    finally:
        if conn is not None:
            conn.close()


def register(ctx) -> None:
    """Register the pre-worker-spawn enforcement hook."""
    ctx.register_hook("kanban_task_claimed", enforce_whatsapp_wake_only)
