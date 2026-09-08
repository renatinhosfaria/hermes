"""Replay observed tools from Reno state.db read-only. No MCP, writes or notifications."""

import argparse
import importlib.util
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "reno_replay_guard",
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    guard = module.RenoGuard(args.task, args.run)
    calls = {}
    patches = []
    other_blocks = []
    history_evidence = []
    with closing(
        sqlite3.connect("file:/root/.hermes/profiles/reno/state.db?mode=ro", uri=True)
    ) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        for row in conn.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id", (args.session,)
        ):
            if row["role"] == "assistant" and row["tool_calls"]:
                for call in json.loads(row["tool_calls"]):
                    fn = call["function"]
                    payload = fn.get("arguments", {})
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    cid = call["id"]
                    kw = dict(
                        tool_name=fn["name"],
                        args=payload,
                        session_id=args.session,
                        tool_call_id=cid,
                    )
                    verdict = guard.before(**kw)
                    blocked = bool(verdict and verdict.get("action") == "block")
                    calls[cid] = (kw, blocked)
                    actual_name, _ = guard.unwrap(fn["name"], payload)
                    if actual_name == module.PATCH:
                        patches.append(
                            {
                                "message_id": row["id"],
                                "blocked": blocked,
                                "reason": verdict.get("message") if verdict else None,
                            }
                        )
                    elif blocked:
                        other_blocks.append(
                            {"tool": fn["name"], "reason": verdict.get("message")}
                        )
            elif row["role"] == "tool" and row["tool_call_id"] in calls:
                kw, blocked = calls[row["tool_call_id"]]
                if not blocked:
                    guard.after(**kw, result=row["content"], status="ok")
                    actual_name, _ = guard.unwrap(kw["tool_name"], kw["args"])
                    if actual_name == module.HISTORY:
                        history_evidence.append(
                            {
                                "client_messages": sum(
                                    m.get("speaker") == "cliente"
                                    for m in guard.messages
                                ),
                                "later_message_after_initial": module.later_message(
                                    guard.messages,
                                    (guard.doc or {}).get("pedido_exato"),
                                ),
                            }
                        )
    print(
        json.dumps(
            {
                "task": args.task,
                "run": args.run,
                "patches": patches,
                "history_evidence": history_evidence,
                "other_blocks": other_blocks,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
