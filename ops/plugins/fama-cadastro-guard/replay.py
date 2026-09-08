#!/usr/bin/env python3
"""Replay recorded tool responses locally through the guard; never execute tools."""
import argparse
import importlib.util
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-db", required=True, type=Path)
    parser.add_argument("--session", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("cadastro_guard", Path(__file__).with_name("__init__.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with sqlite3.connect(args.state_db.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT role, tool_calls, tool_call_id, tool_name, content FROM messages WHERE session_id=? ORDER BY id", (args.session,)).fetchall()
    task = next(module.decode_result(content)["task"] for role, _calls, _cid, name, content in rows if role == "tool" and name == "kanban_show")
    validator = module.CadastroGuard(task["id"], task["current_run_id"])
    calls, blocked, completion = {}, [], None
    for role, raw_calls, call_id, tool_name, content in rows:
        if role == "assistant" and raw_calls:
            for call in json.loads(raw_calls):
                fn = call["function"]
                payload = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                name, payload = validator.unwrap(fn["name"], payload)
                calls[call["id"]] = (name, payload)
        if role != "tool" or call_id not in calls:
            continue
        name, payload = calls[call_id]
        if name not in module.WATCHED:
            continue
        context = dict(tool_name=name, args=payload, session_id=args.session, tool_call_id=call_id)
        directive = validator.before(**context)
        if directive and directive.get("action") == "block":
            blocked.append({"tool": name, "reason": directive["message"]})
            continue
        if name == "kanban_complete":
            completion = directive["args"]["metadata"]
            continue
        transformed = validator.transform(**context, result=content) or content
        validator.after(**context, result=transformed)
    report = {"task_id": task["id"], "run_id": task["current_run_id"], "blocked": blocked, "handoff": completion}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if completion and not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
