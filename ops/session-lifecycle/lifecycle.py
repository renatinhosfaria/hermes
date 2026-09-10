"""Read-only eligibility and durable delivery timestamps. No Hermes SQL writes."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

DAYS = 90
RUNTIME = "session-lifecycle"


def ro(path):
    db = sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=1
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


@dataclass(frozen=True)
class Candidate:
    session_id: str
    last_activity: float
    conservative_outbound: bool


def capture_deliveries(home: Path):
    """Retain timestamps before Hermes prunes the delivery ledger. No message copies."""
    root = home / RUNTIME
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    path = root / "activity.sqlite3"
    # Create private before SQLite opens it.
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    with (
        closing(ro(home / "state.db")) as state,
        closing(sqlite3.connect(path)) as own,
        own,
    ):
        own.execute(
            "CREATE TABLE IF NOT EXISTS activity(session_id TEXT PRIMARY KEY, delivered_at REAL NOT NULL)"
        )
        for (
            row
        ) in state.execute("""SELECT s.id,MAX(d.updated_at) AS stamp FROM sessions s
            JOIN delivery_obligations d ON d.chat_id=s.chat_id AND d.platform=s.source
            WHERE s.source='whatsapp' AND s.chat_type='dm'
            AND (s.profile_name IS NULL OR s.profile_name='default') AND d.state='delivered'
            GROUP BY s.id"""):
            own.execute(
                "INSERT INTO activity VALUES(?,?) ON CONFLICT(session_id) DO UPDATE SET delivered_at=MAX(delivered_at,excluded.delivered_at)",
                (row["id"], row["stamp"]),
            )


def identity_aliases(value):
    # Use the same trusted LID mapping and Brazilian phone variants as handover.
    from gateway.whatsapp_identity import expand_whatsapp_aliases

    result = set()
    for alias in expand_whatsapp_aliases(value) or {value}:
        digits = re.sub(r"\D+", "", alias)
        if not digits:
            continue
        result.add(digits)
        if digits.startswith("55") and len(digits) == 13 and digits[4] == "9":
            result.add(digits[:4] + digits[5:])
        elif digits.startswith("55") and len(digits) == 12:
            result.add(digits[:4] + "9" + digits[4:])
    return result


class Busy(Exception):
    """Transient work in progress; retry soon instead of treating as zero candidates."""


def scan(
    home: Path,
    now: float | None = None,
    *,
    ignore_holder=None,
    only_session_id=None,
    budget_seconds=None,
):
    now = time.time() if now is None else now
    deadline = time.monotonic() + budget_seconds if budget_seconds else None
    cutoff = now - DAYS * 86400
    output = []
    with (
        closing(ro(home / "state.db")) as state,
        closing(ro(home / "kanban.db")) as board,
    ):
        if deadline:
            for connection in (state, board):
                connection.execute("PRAGMA busy_timeout=20")
                connection.set_progress_handler(
                    lambda: int(time.monotonic() > deadline), 1000
                )
        # Conservatively skip if any cross-process turn or compression is active.
        for row in state.execute("SELECT holder,expires_at FROM session_turn_leases"):
            if row["holder"] != ignore_holder and row["expires_at"] > now:
                raise Busy()
        if state.execute(
            "SELECT 1 FROM compression_locks WHERE expires_at>? LIMIT 1", (now,)
        ).fetchone():
            raise Busy()
        candidates = state.execute(
            """SELECT id,chat_id,session_key FROM sessions
            WHERE source='whatsapp' AND chat_type='dm' AND ended_at IS NULL
            AND (profile_name IS NULL OR profile_name='default') AND COALESCE(pinned,0)=0
            AND COALESCE(handoff_state,'')='' AND (? IS NULL OR id=?)""",
            (only_session_id, only_session_id),
        ).fetchall()
        stored = {}
        if (home / RUNTIME / "activity.sqlite3").exists():
            with closing(ro(home / RUNTIME / "activity.sqlite3")) as own:
                stored = dict(
                    own.execute(
                        "SELECT session_id,delivered_at FROM activity WHERE (? IS NULL OR session_id=?)",
                        (only_session_id, only_session_id),
                    )
                )
        pause_path = Path(
            os.getenv("FAMA_WHATSAPP_HANDOVER_DB")
            or str(home / "plugin-data/fama-whatsapp-human-handover/handover.db")
        )
        paused = []
        if pause_path.exists():
            with closing(ro(pause_path)) as handover:
                paused = handover.execute(
                    "SELECT contact_id,session_key FROM paused_contacts"
                ).fetchall()
        if not pause_path.exists() and (home / "config.yaml").exists():
            import yaml

            config = yaml.safe_load((home / "config.yaml").read_text()) or {}
            if "fama-whatsapp-human-handover" in (config.get("plugins") or {}).get(
                "enabled", []
            ):
                raise FileNotFoundError("Required human pause store is unavailable")
        paused_aliases = set()
        if paused:
            for pause in paused:
                paused_aliases.update(identity_aliases(pause["contact_id"]))
        for row in candidates:
            if deadline and time.monotonic() > deadline:
                raise Busy()
            if any(
                p["session_key"] == row["session_key"]
                or p["contact_id"] == row["chat_id"]
                for p in paused
            ):
                continue
            if paused and identity_aliases(row["chat_id"]) & paused_aliases:
                continue
            chat = row["chat_id"]
            # Multiple live roots for a peer: do not guess which route to close.
            if (
                state.execute(
                    "SELECT COUNT(*) FROM sessions WHERE source='whatsapp' AND chat_id=? AND ended_at IS NULL",
                    (chat,),
                ).fetchone()[0]
                != 1
            ):
                continue
            if board.execute(
                """SELECT 1 FROM tasks t LEFT JOIN kanban_notify_subs n ON n.task_id=t.id
                WHERE t.status NOT IN ('done','cancelled','canceled')
                AND (t.session_id=? OR (n.platform='whatsapp' AND n.chat_id=?)) LIMIT 1""",
                (row["id"], chat),
            ).fetchone():
                continue
            deliveries = state.execute(
                "SELECT state,updated_at FROM delivery_obligations WHERE platform='whatsapp' AND chat_id=?",
                (chat,),
            ).fetchall()
            if any(d["state"] not in ("delivered", "abandoned") for d in deliveries):
                continue
            activity = state.execute(
                """SELECT
                MAX(CASE WHEN m.role='user' AND m.platform_message_id IS NOT NULL
                    AND m.platform_message_id!='' THEN m.timestamp END) inbound,
                MAX(CASE WHEN (m.tool_calls IS NULL OR m.tool_calls='')
                    AND TRIM(COALESCE(m.content,'')) NOT IN ('','[SILENT]')
                    THEN m.timestamp END) uncertain
                FROM messages m JOIN sessions s ON s.id=m.session_id
                WHERE s.source='whatsapp' AND s.chat_id=? AND s.chat_type='dm'
                AND (s.profile_name IS NULL OR s.profile_name='default')
                AND m.role IN ('user','assistant') AND m.tool_name IS NULL AND m.display_kind IS NULL""",
                (chat,),
            ).fetchone()
            if activity["inbound"] is None:
                continue
            inbound = [activity["inbound"]]
            uncertain = (
                [activity["uncertain"]] if activity["uncertain"] is not None else []
            )
            confirmed = [
                d["updated_at"] for d in deliveries if d["state"] == "delivered"
            ]
            known = max([*inbound, *confirmed, stored.get(row["id"], 0)])
            last = max([known, *uncertain])
            if last <= cutoff:
                output.append(Candidate(row["id"], last, last > known))
    return output


if __name__ == "__main__":
    sys.path.insert(0, "/usr/local/lib/hermes-agent")
    parser = argparse.ArgumentParser(
        description="Read-only CEO WhatsApp session expiry preview"
    )
    parser.add_argument("--home", type=Path, default=Path("/root/.hermes"))
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "mode": "dry-run",
                "idle_days": DAYS,
                "candidates": [asdict(c) for c in scan(args.home)],
            }
        )
    )
