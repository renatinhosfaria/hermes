"""Synthetic regression checks for the read-only grant diagnostic."""
import contextlib
import importlib.util
import io
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    "grant_probe", Path(__file__).with_name("verify_grant_t_d45cb831.py")
)
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class GrantProbeTests(unittest.TestCase):
    def fixture(self, expired=False, mismatch=False):
        dbs = [sqlite3.connect(":memory:") for _ in range(3)]
        for db in dbs:
            db.row_factory = sqlite3.Row
            self.addCleanup(db.close)
        runtime, board, state = dbs
        state.execute("CREATE TABLE sessions(id,session_key,source,chat_id,chat_type)")
        state.executemany("INSERT INTO sessions VALUES(?,?,?,?,?)", [
            ("CONTROL_SECRET", "KEY_CONTROL", "telegram", "CHAT_CONTROL", "group"),
            ("CONTEXT_SECRET", "KEY_CONTEXT", "whatsapp", "CHAT_CONTEXT", "dm"),
        ])
        board.executescript("""
            CREATE TABLE tasks(id,session_id,assignee,status,current_run_id);
            CREATE TABLE task_links(parent_id,child_id);
            CREATE TABLE task_runs(id,task_id);
            CREATE TABLE kanban_notify_subs(task_id,platform,chat_id,chat_type,notifier_profile);
        """)
        board.executemany("INSERT INTO tasks VALUES(?,?,?,?,?)", [
            ("t_e857fdfb", "CONTROL_SECRET", "reno", "blocked", None),
            ("t_f22fff28", "CONTEXT_SECRET", "reno", "done", None),
        ])
        board.execute("INSERT INTO task_links VALUES('t_f22fff28','t_e857fdfb')")
        for tid in ("t_e857fdfb", "t_f22fff28"):
            board.execute("INSERT INTO kanban_notify_subs VALUES(?,'whatsapp','CHAT_CONTEXT','dm','default')", (tid,))
        binding = {
            "task_id": "t_e857fdfb", "parent_id": "t_f22fff28", "principal": "reno",
            "control_session_id": "CONTROL_SECRET", "control_session_key": "KEY_CONTROL",
            "control_chat_id": "CHAT_CONTROL", "control_chat_type": "group",
            "context_session_id": "CONTEXT_SECRET", "context_session_key": "KEY_CONTEXT",
            "context_chat_id": "WRONG_SECRET" if mismatch else "CHAT_CONTEXT",
        }
        runtime.execute("CREATE TABLE conversation_resumptions(task_id,authorization_id,binding,run_watermark,issued_at,expires_at,bound_run_id,revoked_at)")
        runtime.execute("INSERT INTO conversation_resumptions VALUES(?,?,?,?,?,?,NULL,NULL)", (
            "t_e857fdfb", "f922bc7e-4d07-4053-937c-4179f2ae649c", json.dumps(binding),
            412, 1000, 1500 if expired else 4600,
        ))
        for db in dbs:
            db.commit()
            db.execute("PRAGMA query_only=ON")
        return dbs

    def run_case(self, **kwargs):
        output = io.StringIO()
        with patch.object(probe, "connect", side_effect=self.fixture(**kwargs)), patch.object(
            probe.time, "time", return_value=2000
        ), contextlib.redirect_stdout(output):
            if kwargs:
                with self.assertRaises(AssertionError):
                    probe.main()
            else:
                probe.main()
        text = output.getvalue()
        for sentinel in ("SECRET", "KEY_CONTROL", "KEY_CONTEXT", "CHAT_CONTROL", "CHAT_CONTEXT"):
            self.assertNotIn(sentinel, text)
        return json.loads(text)

    def test_valid_metadata_and_no_pii(self):
        self.assertTrue(self.run_case()["all_checks_passed"])

    def test_expired_grant_rejected(self):
        self.assertFalse(self.run_case(expired=True)["checks"]["grant_not_expired"])

    def test_changed_binding_rejected(self):
        self.assertFalse(self.run_case(mismatch=True)["checks"]["binding_matches_canonical_metadata"])

    def test_connector_is_read_only(self):
        conn = MagicMock()
        with patch.object(probe.sqlite3, "connect", return_value=conn) as connect:
            self.assertIs(probe.connect("/synthetic.db"), conn)
        connect.assert_called_once_with("file:/synthetic.db?mode=ro", uri=True)
        conn.execute.assert_called_once_with("PRAGMA query_only=ON")


if __name__ == "__main__":
    unittest.main()
