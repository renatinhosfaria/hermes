"""Read-only, PII-free evidence for the cross-platform task binding incident."""
import json
import sqlite3
import subprocess


def connect(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def main():
    with connect('/root/.hermes/kanban.db') as kb, connect('/root/.hermes/state.db') as state:
        tasks = {}
        subscriptions = {}
        for tid in ('t_f22fff28', 't_e857fdfb', 't_d45cb831'):
            task = kb.execute('SELECT id, session_id, status, current_run_id FROM tasks WHERE id=?', (tid,)).fetchone()
            if task is None:
                raise RuntimeError('Expected task missing')
            tasks[tid] = task
            session = state.execute('SELECT source, chat_type FROM sessions WHERE id=?', (task['session_id'],)).fetchone()
            subs = kb.execute('SELECT platform, chat_id, chat_type, notifier_profile FROM kanban_notify_subs WHERE task_id=?', (tid,)).fetchall()
            subscriptions[tid] = subs
            wa = [s for s in subs if s['platform'] == 'whatsapp']
            eligible = []
            for sub in wa:
                rows = state.execute("SELECT id FROM sessions WHERE session_key IN (SELECT session_key FROM sessions WHERE chat_id=?) AND source='whatsapp' AND chat_type='dm'", (sub['chat_id'],)).fetchall()
                eligible.append(task['session_id'] in {row['id'] for row in rows})
            print(json.dumps({'task_id': tid, 'status': task['status'], 'current_run_id': task['current_run_id'], 'origin_source': session['source'] if session else None, 'origin_chat_type': session['chat_type'] if session else None, 'subscription_platforms': sorted({s['platform'] for s in subs}), 'whatsapp_subscriptions': len(wa), 'origin_in_whatsapp_longitudinal': eligible}))
        parent, child = 't_f22fff28', 't_e857fdfb'
        wa_targets = lambda tid: {s['chat_id'] for s in subscriptions[tid] if s['platform'] == 'whatsapp'}
        print(json.dumps({'parent_child_whatsapp_target_equal': wa_targets(parent) == wa_targets(child), 'parent_child_session_equal': tasks[parent]['session_id'] == tasks[child]['session_id']}))
        run = kb.execute('SELECT id, task_id, status FROM task_runs WHERE id=412').fetchone()
        print(json.dumps(dict(run)))
    journal = subprocess.run(['journalctl', '-u', 'brain.service', '--since', '2026-09-10 12:44:00 UTC', '--until', '2026-09-10 12:46:00 UTC', '--no-pager', '-o', 'cat'], capture_output=True, text=True, check=True)
    matches = []
    for line in journal.stdout.splitlines():
        if 't_e857fdfb' in line and 'AUTH_SESSION_MISMATCH' in line:
            matches.append({'task_id': 't_e857fdfb', 'code': 'AUTH_SESSION_MISMATCH', 'run_412_present': '412' in line})
    print(json.dumps({'brain_journal_matching_denials': matches}))


if __name__ == '__main__':
    main()
