"""Refresh stale gateway instruction snapshots at startup, preserving conversations.

Run without --apply for a read-only count. Mutation uses the native SessionDB
API and refuses a running gateway; intended for a temporary ExecStartPre hook.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

POLICY_MARKER = 'fama-agendamento-v1'
ROOT = Path('/root/.hermes')


def candidates(path: Path) -> list[str]:
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        return [row[0] for row in conn.execute('''
            SELECT s.id FROM sessions s
            LEFT JOIN system_prompts p ON p.hash=s.system_prompt_hash
            WHERE s.source IN ('whatsapp','telegram')
              AND length(coalesce(p.prompt,s.system_prompt,'')) > 0
              AND instr(coalesce(p.prompt,s.system_prompt,''),?) = 0
        ''', (POLICY_MARKER,))]


def refresh(path: Path) -> int:
    ids = candidates(path)
    if not ids:
        return 0
    sys.path.insert(0, '/usr/local/lib/hermes-agent')
    from hermes_state import SessionDB
    db = SessionDB(path)
    try:
        for sid in ids:
            db.update_system_prompt(sid, None)
    finally:
        db.close()
    if candidates(path):
        raise RuntimeError('stale appointment instruction snapshots remain')
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=['default', 'reno'])
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    home = ROOT if args.profile == 'default' else ROOT / 'profiles' / args.profile
    path = home / 'state.db'
    if not args.apply:
        print(json.dumps({'profile': args.profile, 'stale_snapshots': len(candidates(path))}))
        return
    if POLICY_MARKER not in (home / 'SOUL.md').read_text():
        raise RuntimeError('new appointment instructions must be installed first')
    unit = 'hermes-gateway.service' if args.profile == 'default' else 'hermes-gateway-reno.service'
    pid = subprocess.run(['systemctl', 'show', unit, '--property=MainPID', '--value'],
                         capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if pid != '0':
        raise RuntimeError('gateway must finish draining before refreshing instructions')
    print(json.dumps({'profile': args.profile, 'refreshed_snapshots': refresh(path),
                      'conversation_history': 'preserved'}))


if __name__ == '__main__':
    main()
