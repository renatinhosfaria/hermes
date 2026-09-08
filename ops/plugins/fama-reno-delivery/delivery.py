"""CEO operational receipts. Read transport evidence; create internal Kanban tasks.

No transport sends, CRM credentials, Brain writes or changes to upstream Hermes.
"""

import argparse
import fcntl
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import yaml

CREATOR = "fama-reno-delivery"
ROOT = Path("/root/.hermes")
DATA = ROOT / "plugin-data" / CREATOR
PAUSE = ROOT / "plugin-data/fama-whatsapp-human-handover/handover.db"
ROUTE_FIELDS = (
    "platform",
    "chat_id",
    "thread_id",
    "user_id",
    "user_id_alt",
    "chat_type",
    "notifier_profile",
    "delivery_mode",
    "delivery_metadata",
)


def readonly(path):
    conn = sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def aliases(value):
    value = str(value)
    result = {value}
    if value.endswith("@lid"):
        return result
    digits = value.split("@")[0]
    if digits.isdigit():
        result.add(digits)
        if digits.startswith("55") and len(digits) in (12, 13):
            result.add(digits[2:])
    return result


def paused(path, chat_id, session_key):
    # The installed handover store must be readable; missing is not proof of no pause.
    with closing(readonly(path)) as conn:
        return any(
            row["session_key"] == session_key
            or aliases(chat_id) & aliases(row["contact_id"])
            for row in conn.execute(
                "SELECT contact_id,session_key FROM paused_contacts"
            )
        )


def task_document(body):
    doc = yaml.safe_load(body)
    if not isinstance(doc, dict) or doc.get("test_mode", False) is not False:
        raise ValueError("invalid_or_synthetic_task")
    return doc


def route_for(board, task_id):
    rows = board.execute(
        "SELECT * FROM kanban_notify_subs WHERE task_id=?", (task_id,)
    ).fetchall()
    if len(rows) != 1:
        return None
    return {key: rows[0][key] for key in ROUTE_FIELDS}


def candidates(board, state, cutoff):
    """Exact text + destination + chronology + source session. Ambiguity fails closed."""
    runs = board.execute(
        """SELECT r.id AS run_id,r.ended_at,r.metadata,t.id AS source_task_id,
        t.body,t.session_id FROM task_runs r JOIN tasks t ON t.id=r.task_id
        WHERE t.assignee='reno' AND t.status='done' AND COALESCE(t.created_by,'') != ? AND r.outcome='completed'
        AND r.status IN ('done','completed') AND r.ended_at>=?""",
        (CREATOR, cutoff - 86400),
    ).fetchall()
    deliveries = state.execute(
        """SELECT * FROM delivery_obligations WHERE state='delivered'
        AND platform='whatsapp' AND adapter_profile='default' AND created_at>=?
        ORDER BY created_at,obligation_id""",
        (cutoff,),
    ).fetchall()
    matches, ambiguous = [], 0
    for row in deliveries:
        found = []
        for run in runs:
            if not run["ended_at"] or not (
                run["ended_at"] <= row["created_at"] <= run["ended_at"] + 86400
            ):
                continue
            try:
                metadata = json.loads(run["metadata"] or "{}")
                text = metadata.get("response_ready")
                if (
                    not isinstance(text, str)
                    or not text.strip()
                    or text.strip() == "[SILENT]"
                    or text.strip() != row["content"].strip()
                ):
                    continue
                doc = task_document(run["body"])
                upstream = doc.get("upstream_result", {})
                client_id = upstream.get("client_id")
                if (
                    type(client_id) is not int
                    or client_id <= 0
                    or metadata.get("entities", {}).get("client_id") != client_id
                ):
                    continue
                subs = board.execute(
                    "SELECT * FROM kanban_notify_subs WHERE task_id=?",
                    (run["source_task_id"],),
                ).fetchall()
                # Parent inheritance must not introduce a passive external notification.
                if len(subs) != 1:
                    continue
                sub = subs[0]
                if (
                    sub["platform"] != "whatsapp"
                    or sub["chat_id"] != row["chat_id"]
                    or (sub["thread_id"] or "") != (row["thread_id"] or "")
                    or sub["delivery_mode"] != "wake"
                    or sub["chat_type"] != "dm"
                    or sub["notifier_profile"] not in (None, "default")
                ):
                    continue
                sessions = state.execute(
                    "SELECT id,started_at FROM sessions WHERE session_key=? AND started_at<=? ORDER BY started_at DESC",
                    (row["session_key"], row["created_at"]),
                ).fetchall()
                sid = run["session_id"]
                if sid:
                    if not sessions or sid != sessions[0]["id"]:
                        continue
                    if (
                        len(sessions) > 1
                        and sessions[0]["started_at"] == sessions[1]["started_at"]
                    ):
                        continue
                elif len(sessions) == 1:
                    sid = sessions[0]["id"]
                else:
                    continue
                found.append(
                    dict(
                        run_id=run["run_id"],
                        source_task_id=run["source_task_id"],
                        client_id=client_id,
                        session_id=sid,
                        obligation_id=row["obligation_id"],
                        chat_id=row["chat_id"],
                        session_key=row["session_key"],
                        delivered_at=row["updated_at"],
                        route={key: sub[key] for key in ROUTE_FIELDS},
                    )
                )
            except (ValueError, TypeError, AttributeError, yaml.YAMLError):
                continue
        if len(found) == 1:
            matches.append(found[0])
        elif len(found) > 1:
            ambiguous += 1
    return matches, ambiguous


def reconcile(
    board_path, state_path, receipt_path, pause_path, *, cutoff, dry_run=False
):
    with closing(readonly(board_path)) as b, closing(readonly(state_path)) as s:
        matches, ambiguous = candidates(b, s, cutoff)
    report = {
        "matched": len(matches),
        "ambiguous": ambiguous,
        "paused": 0,
        "created": 0,
        "existing": 0,
    }
    if dry_run:
        return report
    from hermes_cli import kanban_db as kb
    from hermes_cli.kanban_db_connect import connect, write_txn

    receipt_path = Path(receipt_path)
    receipt_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # One lock covers the reservation and native create; recovery finds all task statuses.
    with open(str(receipt_path) + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with (
            closing(sqlite3.connect(receipt_path)) as receipts,
            closing(connect(Path(board_path))) as board,
        ):
            receipts.execute(
                "CREATE TABLE IF NOT EXISTS receipts (run_id INTEGER PRIMARY KEY, proof TEXT NOT NULL)"
            )
            receipts.commit()
            receipt_path.chmod(0o600)
            for proof in matches:
                if paused(pause_path, proof["chat_id"], proof["session_key"]):
                    report["paused"] += 1
                    continue
                key = f"reno-delivery:run:{proof['run_id']}"
                if board.execute(
                    "SELECT id FROM tasks WHERE idempotency_key=?", (key,)
                ).fetchone():
                    report["existing"] += 1
                    continue
                receipts.execute(
                    "INSERT OR IGNORE INTO receipts VALUES (?,?)",
                    (proof["run_id"], json.dumps(proof, sort_keys=True)),
                )
                receipts.commit()  # Before task visibility; recoverable across either crash boundary.
                proof = json.loads(
                    receipts.execute(
                        "SELECT proof FROM receipts WHERE run_id=?", (proof["run_id"],)
                    ).fetchone()[0]
                )
                body = yaml.safe_dump(
                    {
                        "schema_version": "1.0",
                        "operation": "CONFIRMACAO_ENVIO",
                        "test_mode": False,
                        "upstream_result": {
                            "worker": "reno",
                            "client_id": proof["client_id"],
                        },
                        "delivery_receipt": {
                            k: proof[k]
                            for k in (
                                "obligation_id",
                                "run_id",
                                "source_task_id",
                                "delivered_at",
                            )
                        },
                        "objetivo": "Atualização interna após envio confirmado pelo transporte. Aplicar a seção CONFIRMACAO_ENVIO da conduta. Não responder ao cliente.",
                        "criterios_de_aceite": [
                            "Ler cliente atual; validar brokerId 35. Se Sem Atendimento, usar expectedStatus para Não Respondeu e conferir por leitura independente.",
                            "Consultar conversation_recent uma vez antes da leitura do cliente. Se houver mensagem posterior ao envio, preservar e devolver ao CEO para o atendimento comercial.",
                            "Se Em Atendimento ou outra etapa, preservar. Este cartão não promove para Em Atendimento nem envia mensagem externa.",
                            "Concluir sem texto externo: response_ready null; requested_next_action return_to_ceo.",
                        ],
                    },
                    allow_unicode=True,
                    sort_keys=False,
                )
                # Validation and native inheritance share one IMMEDIATE transaction.
                # create_task explicitly supports nested composition via savepoints.
                with write_txn(board):
                    source = board.execute(
                        "SELECT status FROM tasks WHERE id=?",
                        (proof["source_task_id"],),
                    ).fetchone()
                    if (
                        not source
                        or source["status"] != "done"
                        or route_for(board, proof["source_task_id"]) != proof["route"]
                    ):
                        report["ambiguous"] += 1
                        continue
                    if board.execute(
                        "SELECT id FROM tasks WHERE idempotency_key=?", (key,)
                    ).fetchone():
                        report["existing"] += 1
                        continue
                    kb.create_task(
                        board,
                        title="Reno: conferir etapa após envio confirmado",
                        body=body,
                        assignee="reno",
                        created_by=CREATOR,
                        parents=(proof["source_task_id"],),
                        session_id=proof["session_id"],
                        idempotency_key=key,
                        max_runtime_seconds=600,
                        skills=("fama-reno-runtime",),
                    )
                    report["created"] += 1
    return report


def verify_receipt(
    task_id,
    board_path=ROOT / "kanban.db",
    state_path=ROOT / "state.db",
    receipt_path=DATA / "receipts.db",
    pause_path=PAUSE,
):
    try:
        with (
            closing(readonly(board_path)) as b,
            closing(readonly(state_path)) as s,
            closing(readonly(receipt_path)) as r,
        ):
            task = b.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not task or task["assignee"] != "reno" or task["created_by"] != CREATOR:
                raise ValueError("untrusted_receipt_task")
            doc = task_document(task["body"])
            receipt = doc["delivery_receipt"]
            row = r.execute(
                "SELECT proof FROM receipts WHERE run_id=?", (receipt["run_id"],)
            ).fetchone()
            if not row:
                raise ValueError("receipt_not_registered")
            proof = json.loads(row["proof"])
            if (
                doc.get("operation") != "CONFIRMACAO_ENVIO"
                or doc["upstream_result"]["client_id"] != proof["client_id"]
                or task["idempotency_key"] != f"reno-delivery:run:{proof['run_id']}"
                or task["session_id"] != proof["session_id"]
                or any(
                    receipt.get(k) != proof[k]
                    for k in (
                        "obligation_id",
                        "run_id",
                        "source_task_id",
                        "delivered_at",
                    )
                )
            ):
                raise ValueError("receipt_binding_mismatch")
            if route_for(b, task_id) != proof["route"]:
                raise ValueError("receipt_notification_route_changed")
            ledger = s.execute(
                "SELECT * FROM delivery_obligations WHERE obligation_id=?",
                (proof["obligation_id"],),
            ).fetchone()
            if (
                not ledger
                or ledger["state"] != "delivered"
                or ledger["platform"] != "whatsapp"
                or ledger["adapter_profile"] != "default"
                or ledger["chat_id"] != proof["chat_id"]
                or ledger["session_key"] != proof["session_key"]
            ):
                raise ValueError("delivery_not_confirmed")
            if paused(pause_path, proof["chat_id"], proof["session_key"]):
                raise ValueError("human_pause")
            return proof
    except (OSError, sqlite3.Error, KeyError, TypeError, yaml.YAMLError) as exc:
        raise ValueError("receipt_unavailable") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cutoff", type=float)
    args = parser.parse_args()
    activation = DATA / "activation.json"
    cutoff = (
        args.cutoff
        if args.cutoff is not None
        else json.loads(activation.read_text())["cutoff"]
    )
    sys.path.insert(0, "/usr/local/lib/hermes-agent")
    print(
        json.dumps(
            reconcile(
                ROOT / "kanban.db",
                ROOT / "state.db",
                DATA / "receipts.db",
                PAUSE,
                cutoff=cutoff,
                dry_run=args.dry_run,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
