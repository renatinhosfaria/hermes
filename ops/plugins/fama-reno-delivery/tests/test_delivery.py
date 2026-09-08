import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "/usr/local/lib/hermes-agent")
from hermes_cli import kanban_db as kb
from hermes_cli.kanban_db_connect import connect
from hermes_cli.kanban_db_notify import add_notify_sub, list_notify_subs

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reno_delivery", ROOT / "delivery.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.board = self.home / "kanban.db"
        self.state = self.home / "state.db"
        self.receipts = self.home / "receipts.db"
        self.pause = self.home / "pause.db"
        self.k = connect(self.board)
        self.addCleanup(self.k.close)
        self.s = sqlite3.connect(self.state)
        self.addCleanup(self.s.close)
        self.s.executescript("""
          CREATE TABLE sessions (id TEXT, session_key TEXT, started_at REAL);
          CREATE TABLE delivery_obligations (obligation_id TEXT PRIMARY KEY,
            session_key TEXT, platform TEXT, chat_id TEXT, thread_id TEXT,
            content TEXT, state TEXT, created_at REAL, updated_at REAL, adapter_profile TEXT);
          INSERT INTO sessions VALUES ('s1','agent:default:whatsapp:dm:synthetic',100);
        """)
        with sqlite3.connect(self.pause) as p:
            p.execute(
                "CREATE TABLE paused_contacts (contact_id TEXT, session_key TEXT)"
            )
        self.task = kb.create_task(
            self.k,
            title="synthetic initial response",
            body="upstream_result:\n  verdict: LEAD_NOVO_CADASTRADO\n  client_id: 101\ntest_mode: false\n",
            assignee="reno",
            session_id="s1",
            created_by="default",
        )
        add_notify_sub(
            self.k,
            task_id=self.task,
            platform="whatsapp",
            chat_id="synthetic",
            chat_type="dm",
            notifier_profile="default",
            delivery_mode="wake",
        )
        self.k.execute(
            "UPDATE tasks SET status='done',completed_at=150 WHERE id=?", (self.task,)
        )
        self.k.execute(
            """INSERT INTO task_runs (task_id,profile,status,started_at,ended_at,outcome,metadata)
            VALUES (?, 'reno','done',110,150,'completed',?)""",
            (
                self.task,
                json.dumps(
                    {
                        "response_ready": "Resposta sintética.",
                        "entities": {"client_id": 101},
                    }
                ),
            ),
        )
        self.run = self.k.execute("SELECT max(id) FROM task_runs").fetchone()[0]
        self.k.commit()
        self.add_ledger()

    def add_ledger(
        self,
        oid="d1",
        state="delivered",
        chat="synthetic",
        content="Resposta sintética.",
        created=160,
    ):
        self.s.execute(
            "INSERT INTO delivery_obligations VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                oid,
                "agent:default:whatsapp:dm:synthetic",
                "whatsapp",
                chat,
                "",
                content,
                state,
                created,
                170,
                "default",
            ),
        )
        self.s.commit()

    def reconcile(self, **kw):
        return delivery.reconcile(
            self.board, self.state, self.receipts, self.pause, cutoff=100, **kw
        )

    def children(self):
        return self.k.execute(
            "SELECT * FROM tasks WHERE created_by='fama-reno-delivery'"
        ).fetchall()

    def test_confirmed_send_creates_one_internal_reno_task_with_exact_session_and_wake(
        self,
    ):
        self.reconcile()
        rows = self.children()
        self.assertEqual(len(rows), 1)
        t = rows[0]
        self.assertEqual(t["assignee"], "reno")
        self.assertEqual(t["session_id"], "s1")
        self.assertIn("CONFIRMACAO_ENVIO", t["body"])
        self.assertNotIn("Resposta sintética.", t["body"])
        subs = list_notify_subs(self.k, t["id"])
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["delivery_mode"], "wake")
        self.assertEqual(subs[0]["chat_id"], "synthetic")
        proof = delivery.verify_receipt(
            t["id"], self.board, self.state, self.receipts, self.pause
        )
        self.assertEqual(proof["client_id"], 101)

    def test_failed_pending_or_attempting_send_never_creates_a_task(self):
        for state in ("failed", "pending", "attempting", "abandoned"):
            self.s.execute("UPDATE delivery_obligations SET state=?", (state,))
            self.s.commit()
            self.reconcile()
            self.assertEqual(len(self.children()), 0)

    def test_same_text_to_another_contact_is_not_evidence(self):
        self.s.execute("UPDATE delivery_obligations SET chat_id='another'")
        self.s.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_changed_text_is_not_evidence(self):
        self.s.execute("UPDATE delivery_obligations SET content='Reescrita pelo CEO'")
        self.s.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_pre_activation_delivery_does_not_mutate_historical_cards(self):
        self.s.execute("UPDATE delivery_obligations SET created_at=99")
        self.s.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_repeated_delivery_restart_and_archived_followup_do_not_duplicate(self):
        self.reconcile()
        self.reconcile()
        self.assertEqual(len(self.children()), 1)
        self.k.execute(
            "UPDATE tasks SET status='archived' WHERE created_by='fama-reno-delivery'"
        )
        self.k.commit()
        self.add_ledger(oid="d2", created=180)
        self.reconcile()
        self.assertEqual(len(self.children()), 1)

    def test_ambiguous_matching_runs_fail_closed(self):
        self.k.execute(
            """INSERT INTO task_runs (task_id,profile,status,started_at,ended_at,outcome,metadata)
          SELECT task_id,profile,status,started_at,ended_at,outcome,metadata FROM task_runs WHERE id=?""",
            (self.run,),
        )
        self.k.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_missing_source_session_resolves_uniquely_but_multiple_sessions_do_not(
        self,
    ):
        self.k.execute("UPDATE tasks SET session_id=NULL WHERE id=?", (self.task,))
        self.k.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 1)

    def test_source_session_must_match_ledger_session(self):
        self.k.execute("UPDATE tasks SET session_id='other' WHERE id=?", (self.task,))
        self.k.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_session_reset_between_response_and_send_is_ambiguous(self):
        self.s.execute(
            "INSERT INTO sessions VALUES ('s2','agent:default:whatsapp:dm:synthetic',155)"
        )
        self.s.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_missing_origin_and_multiple_sessions_are_ambiguous(self):
        self.k.execute("UPDATE tasks SET session_id=NULL WHERE id=?", (self.task,))
        self.k.commit()
        self.s.execute(
            "INSERT INTO sessions VALUES ('s0','agent:default:whatsapp:dm:synthetic',50)"
        )
        self.s.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_crash_after_receipt_reservation_recovers_without_duplicate_task(self):
        from unittest.mock import patch

        with patch.object(
            kb, "create_task", side_effect=RuntimeError("simulated_crash")
        ):
            with self.assertRaises(RuntimeError):
                self.reconcile()
        self.assertEqual(len(self.children()), 0)
        self.reconcile()
        self.reconcile()
        self.assertEqual(len(self.children()), 1)

    def test_archived_original_card_is_not_reopened(self):
        self.k.execute("UPDATE tasks SET status='archived' WHERE id=?", (self.task,))
        self.k.commit()
        self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_notification_route_changed_after_scan_is_not_inherited(self):
        from unittest.mock import patch

        def mutate_route(*_):
            self.k.execute(
                "UPDATE kanban_notify_subs SET delivery_mode='notify' WHERE task_id=?",
                (self.task,),
            )
            self.k.commit()
            return False

        with patch.object(delivery, "paused", side_effect=mutate_route):
            self.reconcile()
        self.assertEqual(len(self.children()), 0)

    def test_receipt_rejects_changed_child_destination_or_delivery_mode(self):
        self.reconcile()
        task = self.children()[0]["id"]
        self.k.execute(
            "UPDATE kanban_notify_subs SET delivery_mode='notify' WHERE task_id=?",
            (task,),
        )
        self.k.commit()
        with self.assertRaises(ValueError):
            delivery.verify_receipt(
                task, self.board, self.state, self.receipts, self.pause
            )

    def test_pause_blocks_creation_and_later_receipt_validation(self):
        with sqlite3.connect(self.pause) as p:
            p.execute(
                "INSERT INTO paused_contacts VALUES ('synthetic','agent:default:whatsapp:dm:synthetic')"
            )
        self.reconcile()
        self.assertEqual(len(self.children()), 0)
        with sqlite3.connect(self.pause) as p:
            p.execute("DELETE FROM paused_contacts")
        self.reconcile()
        self.assertEqual(len(self.children()), 1)
        with sqlite3.connect(self.pause) as p:
            p.execute(
                "INSERT INTO paused_contacts VALUES ('synthetic','agent:default:whatsapp:dm:synthetic')"
            )
        with self.assertRaises(ValueError):
            delivery.verify_receipt(
                self.children()[0]["id"],
                self.board,
                self.state,
                self.receipts,
                self.pause,
            )

    def test_forged_card_or_revoked_ledger_does_not_authorize_status_write(self):
        with self.assertRaises(ValueError):
            delivery.verify_receipt(
                self.task, self.board, self.state, self.receipts, self.pause
            )
        self.reconcile()
        t = self.children()[0]
        self.s.execute("UPDATE delivery_obligations SET state='failed'")
        self.s.commit()
        with self.assertRaises(ValueError):
            delivery.verify_receipt(
                t["id"], self.board, self.state, self.receipts, self.pause
            )

    def test_dry_run_performs_no_writes(self):
        self.reconcile(dry_run=True)
        self.assertEqual(len(self.children()), 0)
        self.assertFalse(self.receipts.exists())


if __name__ == "__main__":
    unittest.main()
