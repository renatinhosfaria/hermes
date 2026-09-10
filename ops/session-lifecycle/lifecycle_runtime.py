"""Version-fenced adapter: only the gateway event loop may expire a session."""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Mapping
from pathlib import Path

import yaml
from lifecycle import RUNTIME, Busy, capture_deliveries, scan

LOG = logging.getLogger("fama.session_lifecycle")
ROOT = Path(__file__).resolve().parent
CORE = Path("/usr/local/lib/hermes-agent")
ADAPTER_GUARDS = (
    "_active_sessions",
    "_session_tasks",
    "_pending_messages",
    "_text_debounce",
    "_post_delivery_callbacks",
)
WHATSAPP_GUARDS = ("_pending_text_batches", "_pending_text_batch_tasks")


def compatible():
    expected = json.loads((ROOT / "compatibility.json").read_text())
    return bool(expected) and all(
        hashlib.sha256((CORE / name).read_bytes()).hexdigest() == digest
        for name, digest in expected.items()
    )


def retention_safe(home):
    config = yaml.safe_load((home / "config.yaml").read_text()) or {}
    return (config.get("sessions") or {}).get("auto_prune") is False


def quiet(runner):
    """Called synchronously on the gateway loop; missing internals fail closed."""
    try:
        if any(
            getattr(runner, key)
            for key in (
                "_draining",
                "_external_drain_active",
                "_startup_restore_in_progress",
                "_startup_restore_queue",
                "_running_agents",
            )
        ):
            return False
        if not isinstance(runner._sessions, Mapping) or not isinstance(
            runner.adapters, Mapping
        ):
            return False
        if any(s.conversation.queued_events for s in runner._sessions.values()):
            return False
        found = False
        for platform, adapter in runner.adapters.items():
            for name in ADAPTER_GUARDS:
                value = getattr(adapter, name)
                if not isinstance(value, Mapping) or value:
                    return False
            if getattr(platform, "value", platform) != "whatsapp":
                continue
            found = True
            if adapter.is_connected is not True:
                return False
            for name in WHATSAPP_GUARDS:
                value = getattr(adapter, name)
                if not isinstance(value, Mapping) or value:
                    return False
            task = adapter._poll_task
            if task is None or task.done():
                return False
            # The WhatsApp poller can be downloading media before it admits an
            # event into adapter queues. This private dependency is hash-fenced.
            coro = task.get_coro()
            if coro is None or not hasattr(coro, "cr_code"):
                return False
            seen = set()
            while coro is not None:
                if id(coro) in seen:
                    return False
                seen.add(id(coro))
                code = getattr(coro, "cr_code", None)
                if code and code.co_name in (
                    "_build_message_event",
                    "_collect_bridge_media",
                ):
                    return False
                coro = getattr(coro, "cr_await", None)
        return found
    except (AttributeError, TypeError):
        return False


def close_one(runner, home, candidate):
    # No await/thread switch between checking in-memory admission and closing.
    if not quiet(runner) or not retention_safe(home):
        return "gateway_busy_or_retention_unsafe"
    db = runner._session_db._db
    holder = f"{os.getpid()}:{uuid.uuid4().hex}"
    if not db.try_acquire_session_turn_lease(
        candidate.session_id, holder, ttl_seconds=30, patience_s=0.1
    ):
        return "lease_busy"
    try:
        current = {
            c.session_id: c
            for c in scan(
                home,
                ignore_holder=holder,
                only_session_id=candidate.session_id,
                budget_seconds=0.2,
            )
        }
        if candidate.session_id not in current:
            return "changed_or_busy"
        if not quiet(runner):
            return "gateway_busy"
        return (
            "closed"
            if db.promote_to_session_reset(candidate.session_id, reason="idle")
            else "already_closed_or_rejected"
        )
    finally:
        db.release_session_turn_lease(candidate.session_id, holder)


def status(home, **fields):
    root = home / RUNTIME
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    target = root / "status.json"
    temp = root / f".status-{os.getpid()}.tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump({"timestamp": time.time(), "idle_days": 90, **fields}, stream)
    os.replace(temp, target)


def acquire_worker_lock(home):
    (home / RUNTIME).mkdir(mode=0o700, exist_ok=True)
    fd = os.open(home / RUNTIME / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    handle = os.fdopen(fd, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def supervise(home, stop):
    """Minute delivery harvesting, daily expiry, retry while busy. No LLM calls."""
    from gateway import run

    next_scan = 0.0
    last_scan = None
    lock = None
    try:
        while not stop.wait(60):
            try:
                runner = run._gateway_runner_ref()
                loop = getattr(runner, "_gateway_loop", None)
                if loop is None or not loop.is_running():
                    continue  # CLI/plugin discovery is not a running gateway.
                if lock is None:
                    lock = acquire_worker_lock(home)
                    if lock is None:
                        return
                if not compatible() or not retention_safe(home):
                    status(home, state="disabled_incompatible_or_retention_unsafe")
                    continue
                capture_deliveries(home)
                if time.monotonic() < next_scan:
                    status(
                        home,
                        state="ready",
                        last_scan=last_scan,
                        next_scan_in_seconds=round(next_scan - time.monotonic()),
                    )
                    continue
                candidates = scan(home)
                counts = {}
                for candidate in candidates:
                    if stop.is_set():
                        break
                    completed = threading.Event()
                    result = []

                    def apply(
                        c=candidate, done=completed, box=result, active_runner=runner
                    ):
                        try:
                            if stop.is_set() or not compatible():
                                box.append("cancelled_or_incompatible")
                            else:
                                box.append(close_one(active_runner, home, c))
                        except Exception as exc:  # noqa: BLE001 — plugin boundary must fail closed
                            box.append("error_" + type(exc).__name__)
                        finally:
                            done.set()

                    loop.call_soon_threadsafe(apply)
                    # Do not queue overlapping applies if the loop is delayed.
                    while not completed.wait(1):
                        if stop.is_set() or not loop.is_running():
                            break
                    outcome = result[0] if result else "cancelled"
                    counts[outcome] = counts.get(outcome, 0) + 1
                    if outcome == "closed":
                        LOG.info(
                            "session_idle_closed session_id=%s idle_days=90",
                            candidate.session_id,
                        )
                retry = any(k != "closed" for k in counts)
                next_scan = time.monotonic() + (60 if retry else 86400)
                last_scan = {
                    "timestamp": time.time(),
                    "candidates": len(candidates),
                    "outcomes": counts,
                }
                status(
                    home,
                    state="scan_complete",
                    candidates=len(candidates),
                    outcomes=counts,
                )
            except Busy:
                status(home, state="waiting_for_idle_gateway")
            except Exception as exc:  # noqa: BLE001 — plugin boundary must fail closed
                # Never log exception text: DB errors may contain customer content.
                LOG.warning("session_lifecycle_failure kind=%s", type(exc).__name__)
                status(home, state="error", error_type=type(exc).__name__)
    finally:
        if lock is not None:
            lock.close()


def start(ctx, home):
    if ctx.profile_name != "default" or home.resolve() != Path("/root/.hermes"):
        return
    stop = threading.Event()
    worker = threading.Thread(
        target=supervise, args=(home, stop), name="fama-session-lifecycle", daemon=True
    )
    ctx.on_unload(stop.set)
    worker.start()
