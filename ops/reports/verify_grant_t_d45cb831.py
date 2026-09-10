"""Read-only grant metadata evidence; no credentials, history or grant claim."""
import json
import sqlite3
import time


def connect(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def main():
    task_id = "t_e857fdfb"
    parent_id = "t_f22fff28"
    authorization_id = "f922bc7e-4d07-4053-937c-4179f2ae649c"
    with connect("/var/lib/brain/runtime/brain-runtime.db") as runtime, connect(
        "/root/.hermes/kanban.db"
    ) as board, connect("/root/.hermes/state.db") as state:
        row = runtime.execute(
            "SELECT * FROM conversation_resumptions WHERE task_id=?", (task_id,)
        ).fetchone()
        assert row is not None, "grant absent"
        binding = json.loads(row["binding"])
        task = board.execute(
            "SELECT session_id,assignee,status,current_run_id FROM tasks WHERE id=?",
            (task_id,),
        ).fetchone()
        parent = board.execute(
            "SELECT session_id,status FROM tasks WHERE id=?", (parent_id,)
        ).fetchone()
        control = state.execute(
            "SELECT id,session_key,source,chat_id,chat_type FROM sessions WHERE id=?", (task["session_id"],)
        ).fetchone()
        origin = state.execute(
            "SELECT id,session_key,source,chat_id,chat_type FROM sessions WHERE id=?", (parent["session_id"],)
        ).fetchone()
        expected = {
            "task_id": task_id,
            "parent_id": parent_id,
            "principal": task["assignee"],
            "control_session_id": control["id"],
            "control_session_key": control["session_key"],
            "control_chat_id": control["chat_id"],
            "control_chat_type": control["chat_type"],
            "context_session_id": origin["id"],
            "context_session_key": origin["session_key"],
            "context_chat_id": origin["chat_id"],
        }
        subs = [board.execute(
            "SELECT chat_id,chat_type,notifier_profile FROM kanban_notify_subs WHERE task_id=? AND platform='whatsapp'",
            (tid,),
        ).fetchall() for tid in (task_id, parent_id)]
        checks = {
            "authorization_reference_matches": row["authorization_id"] == authorization_id,
            "binding_matches_canonical_metadata": binding == expected,
            "control_telegram_context_whatsapp_dm": control["source"] == "telegram"
                and origin["source"] == "whatsapp" and origin["chat_type"] == "dm",
            "separate_sessions": control["id"] != origin["id"],
            "parent_done": parent["status"] == "done",
            "direct_parent_edge": board.execute(
                "SELECT 1 FROM task_links WHERE parent_id=? AND child_id=?", (parent_id, task_id)
            ).fetchone() is not None,
            "destinations_match_canonical_parent": all(rows and all(
                s["chat_id"] == origin["chat_id"] and s["chat_type"] == "dm"
                and s["notifier_profile"] == "default" for s in rows
            ) for rows in subs),
            "task_blocked_without_current_run": task["status"] == "blocked" and task["current_run_id"] is None,
            "no_run_after_watermark": board.execute(
                "SELECT COUNT(*) FROM task_runs WHERE task_id=? AND id>?", (task_id, row["run_watermark"])
            ).fetchone()[0] == 0,
            "grant_unclaimed": row["bound_run_id"] is None,
            "grant_not_revoked": row["revoked_at"] is None,
            "grant_not_expired": time.time() < row["expires_at"],
        }
        print(json.dumps({
            "task_id": task_id, "parent_id": parent_id,
            "authorization_id": row["authorization_id"],
            "issued_at": row["issued_at"], "expires_at": row["expires_at"],
            "run_watermark": row["run_watermark"], "bound_run_id": row["bound_run_id"],
            "checks": checks, "all_checks_passed": all(checks.values()),
            "scope": "persisted_grant_and_canonical_metadata_only_not_live_worker_authorization",
        }, sort_keys=True))
        assert all(checks.values()), "grant metadata verification failed"


if __name__ == "__main__":
    main()
