"""Read-only evidence of interrupted WhatsApp attendance; no customer content leaves here."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

WAIT_SECONDS = 15 * 60
QUEUE_SECONDS = 5 * 60
RUNTIME_GRACE = 60
STAGES = {'porteiro', 'cadastro', 'reno', 'famaagent'}
MARKER = 'INCIDENTE_ATENDIMENTO '
CLOSED_MARKER = 'INCIDENTE_ENCERRADO '


def connect(path: Path):
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    conn.execute('PRAGMA query_only=ON')
    conn.row_factory = sqlite3.Row
    return conn


def response(content, tool_calls=None):
    return (isinstance(content, str) and bool(content.strip())
            and content.strip() not in {'[SILENT]', 'NO_REPLY', '[NO_REPLY]'}
            and tool_calls in (None, '', '[]', 'null'))


def incident(key, reason, at, timestamp, task_id=None, stage='ceo', session_ref=None):
    reasons = {
        'capability': 'etapa bloqueada por falta de capacidade',
        'blocked': 'etapa bloqueada após falha',
        'triage': 'etapa exige triagem humana',
        'runtime_exceeded': 'execução excedeu o limite da etapa',
        'queue_stalled': 'tarefa não iniciou no prazo de verificação',
        'missing_response': 'especialista concluiu sem resposta válida',
        'ceo_reported': 'CEO registrou impedimento de atendimento',
        'unanswered': 'mensagem recebida sem resposta registrada há mais de 15 minutos',
    }
    when = datetime.fromtimestamp(at, ZoneInfo('America/Sao_Paulo')).strftime('%d/%m %H:%M')
    reference = f'cartão {task_id}' if task_id else f'conversa {session_ref}'
    return {
        'sig': f'atendimento:{key}', 'severity': 'critical', 'area': 'atendimento',
        'immediate': True, 'reason': reason, 'task_id': task_id, 'stage': stage,
        'since': at, 'age_seconds': max(0, int(timestamp-at)),
        'message': f'{reference} | etapa {stage} | {reasons[reason]} ({reason}) | desde {when} (Brasília). '
                   'Ação: Dev investigar; Renato decidir correção e retomada. WhatsApp sem aviso automático.',
    }


def detect(root: Path, timestamp: float) -> list[dict]:
    """An unavailable source is explicit, never an empty successful detection."""
    try:
        return _detect(root, timestamp)
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
        return [{'sig': 'watchdog:attendance_source', 'severity': 'critical',
                 'area': 'watchdog', 'immediate': True, 'detection_unavailable': True,
                 'message': f'Detecção de atendimento indisponível ({type(exc).__name__}); '
                            'não concluir recuperação. Dev verificar acesso e esquema dos bancos.'}]


def _detect(root, timestamp):
    with closing(connect(root / 'state.db')) as state:
        sessions = {r['id']: dict(r) for r in state.execute(
            "SELECT id,session_key FROM sessions WHERE source='whatsapp' AND chat_type='dm'")}
        # Group session resets by the runtime-proven conversation key, never display names.
        keys = {sid: row['session_key'] or sid for sid, row in sessions.items()}
        messages = state.execute('''SELECT m.id,m.session_id,m.role,m.content,m.timestamp,
            m.display_kind,m.observed,m.tool_calls FROM messages m JOIN sessions s ON s.id=m.session_id
            WHERE s.source='whatsapp' AND s.chat_type='dm' AND m.role IN ('user','assistant')
              AND m.timestamp<=? ORDER BY m.timestamp,m.id''', (timestamp,)).fetchall()
    paused = set()
    hp = root / 'plugin-data/fama-whatsapp-human-handover/handover.db'
    # Absence of a handover store is valid before the first human intervention.
    if hp.exists():
        with closing(connect(hp)) as h:
            paused = {r['session_key'] for r in h.execute('SELECT session_key FROM paused_contacts')}
    latest_reply, waiting = {}, {}
    for m in messages:
        key = keys[m['session_id']]
        if m['display_kind'] == 'internal_notification':
            continue
        if m['role'] == 'assistant' and response(m['content'], m['tool_calls']):
            latest_reply[key] = m['timestamp']
            waiting.pop(key, None)
        elif m['role'] == 'user' and not m['observed']:
            waiting.setdefault(key, (m['timestamp'], m['id'], m['session_id']))
    with closing(connect(root / 'kanban.db')) as board:
        tasks = board.execute('''SELECT t.*,r.id AS run_id,r.outcome,r.metadata,
            r.started_at AS run_started_at,r.ended_at AS run_ended_at FROM tasks t LEFT JOIN task_runs r
            ON r.id=(SELECT max(id) FROM task_runs WHERE task_id=t.id)
            WHERE t.assignee IN ('porteiro','cadastro','reno','famaagent')''').fetchall()
        comments = board.execute('''SELECT task_id,body,created_at FROM task_comments
            WHERE body LIKE 'INCIDENTE_ATENDIMENTO %' OR body LIKE 'INCIDENTE_ENCERRADO %'
            ORDER BY id''').fetchall()
    markers = {}
    for c in comments:
        markers[c['task_id']] = (c['body'].startswith(MARKER), c['created_at'])
    out, task_conversations = [], set()
    for t in tasks:
        if t['session_id'] not in keys:
            continue
        key = keys[t['session_id']]
        # Human takeover does not fix the technical failure, but it ends automatic attendance duty.
        if key in paused:
            continue
        stage, status = t['assignee'], t['status']
        at = t['run_ended_at'] or t['started_at'] or t['created_at']
        reason = None
        if status == 'triage':
            reason = 'triage'
        elif status == 'blocked' and (t['block_kind'] == 'capability' or t['outcome'] in {'gave_up','crashed','timed_out','spawn_failed'}):
            reason = 'capability' if t['block_kind'] == 'capability' else 'blocked'
        elif status == 'running' and timestamp-(t['run_started_at'] or t['started_at'] or t['created_at']) > (t['max_runtime_seconds'] or 600)+RUNTIME_GRACE:
            reason, at = 'runtime_exceeded', t['run_started_at'] or t['started_at'] or t['created_at']
        elif status == 'ready' and timestamp-at > QUEUE_SECONDS:
            reason = 'queue_stalled'
        elif status == 'done' and stage in {'reno','famaagent'}:
            try:
                meta = json.loads(t['metadata'] or '{}') or {}
            except (ValueError, TypeError):
                meta = {}
            internal_delivery = (
                stage == 'reno' and dict(t).get('created_by') == 'fama-reno-delivery'
                and str(dict(t).get('idempotency_key') or '').startswith('reno-delivery:run:')
                and t['outcome'] == 'completed' and isinstance(meta,dict)
                and meta.get('decision') in {'ETAPA_POS_ENVIO_CONFIRMADA','ETAPA_POS_ENVIO_PRESERVADA'}
                and meta.get('response_ready') is None and isinstance(meta.get('evidence'),dict)
                and meta['evidence'].get('delivery_confirmed') is True
                and meta['evidence'].get('validator_version') == '1.0.0'
            )
            if not internal_delivery and (not isinstance(meta,dict) or not response(meta.get('response_ready'))):
                # Some archived cards were superseded by a subsequent response in the same chat.
                if latest_reply.get(key,0) < at:
                    reason = 'missing_response'
        active_marker, marked_at = markers.get(t['id'], (False,0))
        if active_marker and status not in {'running','ready','cancelled'}:
            reason, at = 'ceo_reported', marked_at
        if reason:
            out.append(incident(t['id'],reason,at,timestamp,t['id'],stage))
            task_conversations.add(key)
    for key, (at, message_id, sid) in waiting.items():
        if key in paused or key in task_conversations or timestamp-at < WAIT_SECONDS:
            continue
        # One incident per continuous unanswered conversation, stable when more messages arrive.
        ref = hashlib.sha256(key.encode()).hexdigest()[:12]
        out.append(incident(f'wait_{ref}_{message_id}','unanswered',at,timestamp,
                            session_ref=sid))
    return out
