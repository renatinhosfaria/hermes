import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import lifecycle

NOW = 2000000000.0
DAY = 86400


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        with sqlite3.connect(self.home / "state.db") as db:
            db.executescript("""
            CREATE TABLE sessions(id TEXT PRIMARY KEY, source TEXT, chat_type TEXT,
              chat_id TEXT, profile_name TEXT, session_key TEXT, ended_at REAL,
              handoff_state TEXT, pinned INTEGER);
            CREATE TABLE messages(id INTEGER PRIMARY KEY,session_id TEXT,role TEXT,
              content TEXT,tool_calls TEXT,tool_name TEXT,display_kind TEXT,
              platform_message_id TEXT,timestamp REAL);
            CREATE TABLE delivery_obligations(obligation_id TEXT,session_key TEXT,
              platform TEXT,chat_id TEXT,content TEXT,state TEXT,created_at REAL,updated_at REAL);
            CREATE TABLE session_turn_leases(conversation_id TEXT, holder TEXT, expires_at REAL);
            CREATE TABLE compression_locks(session_id TEXT, holder TEXT, expires_at REAL);
            INSERT INTO sessions VALUES('s','whatsapp','dm','synthetic@lid','default','key',NULL,NULL,0);
            """)
        with sqlite3.connect(self.home / "kanban.db") as db:
            db.executescript("""CREATE TABLE tasks(id TEXT,session_id TEXT,status TEXT);
            CREATE TABLE kanban_notify_subs(task_id TEXT,platform TEXT,chat_id TEXT);""")
        self.msg("user", NOW - 90 * DAY)

    def msg(self, role, at, text="synthetic", kind=None, platform_id="fixture"):
        with sqlite3.connect(self.home / "state.db") as db:
            db.execute(
                "INSERT INTO messages(session_id,role,content,display_kind,platform_message_id,timestamp) VALUES(?,?,?,?,?,?)",
                ("s", role, text, kind, platform_id, at),
            )

    def scan(self):
        return lifecycle.scan(self.home, NOW)

    def test_exactly_90_days_is_candidate(self):
        self.assertEqual([x.session_id for x in self.scan()], ["s"])

    def test_new_inbound_resets_clock(self):
        self.msg("user", NOW - 89 * DAY)
        self.assertEqual(self.scan(), [])

    def test_silence_and_classified_notification_do_not_count(self):
        self.msg("assistant", NOW, "[SILENT]", platform_id=None)
        self.msg(
            "user", NOW, "internal", kind="internal_notification", platform_id=None
        )
        self.assertEqual(len(self.scan()), 1)

    def test_unconfirmed_recent_final_defers_conservatively(self):
        self.msg("assistant", NOW - 1, "answer", platform_id=None)
        self.assertEqual(self.scan(), [])

    def test_pending_delivery_blocks(self):
        with sqlite3.connect(self.home / "state.db") as db:
            db.execute(
                "INSERT INTO delivery_obligations VALUES('o','key','whatsapp','synthetic@lid','x','pending',?,?)",
                (NOW - 100 * DAY, NOW),
            )
        self.assertEqual(self.scan(), [])

    def test_confirmed_delivery_resets_clock(self):
        with sqlite3.connect(self.home / "state.db") as db:
            db.execute(
                "INSERT INTO delivery_obligations VALUES('o','key','whatsapp','synthetic@lid','x','delivered',?,?)",
                (NOW - 10, NOW - 5),
            )
        self.assertEqual(self.scan(), [])

    def test_delivery_timestamp_survives_ledger_pruning(self):
        with sqlite3.connect(self.home / "state.db") as db:
            db.execute(
                "INSERT INTO delivery_obligations VALUES('o','key','whatsapp','synthetic@lid','x','delivered',?,?)",
                (NOW - 10, NOW - 5),
            )
        lifecycle.capture_deliveries(self.home)
        with sqlite3.connect(self.home / "state.db") as db:
            db.execute("DELETE FROM delivery_obligations")
        self.assertEqual(self.scan(), [])
        self.assertEqual(len(lifecycle.scan(self.home, NOW + 90 * DAY)), 1)

    def test_real_human_pause_store_blocks_by_session_key(self):
        path = self.home / "plugin-data/fama-whatsapp-human-handover/handover.db"
        path.parent.mkdir(parents=True)
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE paused_contacts(contact_id TEXT,session_key TEXT)")
            db.execute("INSERT INTO paused_contacts VALUES('alias@lid','key')")
        self.assertEqual(self.scan(), [])

    def test_busy_is_distinct_from_no_candidates(self):
        with sqlite3.connect(self.home / "state.db") as db:
            db.execute(
                "INSERT INTO session_turn_leases VALUES('other','holder',?)",
                (NOW + 10,),
            )
        with self.assertRaises(lifecycle.Busy):
            self.scan()

    def test_final_recheck_selects_only_requested_session(self):
        self.assertEqual(lifecycle.scan(self.home, NOW, only_session_id="other"), [])
        self.assertEqual(len(lifecycle.scan(self.home, NOW, only_session_id="s")), 1)

    def test_nonterminal_task_blocks_by_chat(self):
        with sqlite3.connect(self.home / "kanban.db") as db:
            db.execute("INSERT INTO tasks VALUES('t','other','blocked')")
            db.execute(
                "INSERT INTO kanban_notify_subs VALUES('t','whatsapp','synthetic@lid')"
            )
        self.assertEqual(self.scan(), [])

    def test_handoff_pinned_and_wrong_scope_excluded(self):
        for column, value in [
            ("handoff_state", "paused"),
            ("pinned", 1),
            ("source", "telegram"),
            ("profile_name", "reno"),
            ("chat_type", "group"),
        ]:
            with self.subTest(column=column):
                with sqlite3.connect(self.home / "state.db") as db:
                    old = db.execute("SELECT " + column + " FROM sessions").fetchone()[
                        0
                    ]
                    db.execute("UPDATE sessions SET " + column + "=?", (value,))
                self.assertEqual(self.scan(), [])
                with sqlite3.connect(self.home / "state.db") as db:
                    db.execute("UPDATE sessions SET " + column + "=?", (old,))

    def test_old_session_already_ended_excluded(self):
        with sqlite3.connect(self.home / "state.db") as db:
            db.execute("UPDATE sessions SET ended_at=?", (NOW,))
        self.assertEqual(self.scan(), [])

    def test_scan_is_read_only(self):
        before = (self.home / "state.db").read_bytes()
        self.scan()
        self.assertEqual((self.home / "state.db").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
