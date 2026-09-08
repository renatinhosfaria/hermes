#!/usr/local/lib/hermes-agent/venv/bin/python
"""One-time native instruction refresh, run only before the CEO gateway starts."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

OLD_POLICY = 'Ninguém fica em silêncio porque um agente interno falhou.'
DB = Path('/root/.hermes/state.db')
MARKER = Path('/var/lib/hermes-fleet-watch/ceo-policy-20260908.applied')


def candidates(path):
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as c:
        return [r[0] for r in c.execute('''SELECT s.id FROM sessions s LEFT JOIN
            system_prompts p ON p.hash=s.system_prompt_hash
            WHERE s.source IN ('whatsapp','telegram','kanban')
              AND instr(coalesce(s.system_prompt,p.prompt,''),?)>0''',(OLD_POLICY,))]


def refresh(path):
    ids=candidates(path)
    if not ids:
        return 0
    sys.path.insert(0,'/usr/local/lib/hermes-agent')
    from hermes_state import SessionDB
    db=SessionDB(path)
    try:
        for sid in ids:
            db.update_system_prompt(sid,None)
    finally:
        db.close()
    if candidates(path):
        raise RuntimeError('old gateway policy remains')
    return len(ids)


def main():
    if '--apply' not in sys.argv:
        print(json.dumps({'old_instruction_snapshots':len(candidates(DB))}))
        return 0
    if MARKER.exists():
        print('CEO policy refresh already applied')
        return 0
    # ExecStartPre has no MainPID; a running gateway must first drain its turns.
    pid=subprocess.run(['systemctl','show','hermes-gateway.service','--property=MainPID','--value'],
                       check=True,capture_output=True,text=True,timeout=10).stdout.strip()
    if pid!='0':
        raise RuntimeError('CEO gateway must be stopped before instruction refresh')
    count=refresh(DB)
    MARKER.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with MARKER.open('x') as fh:
        import os
        os.chmod(MARKER,0o600)
        json.dump({'cleared_snapshots':count},fh)
    print(json.dumps({'cleared_snapshots':count,'history':'preserved'}))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
