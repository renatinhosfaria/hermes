"""Compatibility checks against installed Hermes, using only temporary state."""

import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

HERMES_SOURCE = Path("/usr/local/lib/hermes-agent")
sys.path.insert(0, str(HERMES_SOURCE))


class NativeSessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hermes-session-lifecycle-test-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"HERMES_HOME": str(self.home)})
        self.env.start()
        self.addCleanup(self.env.stop)
        from hermes_state import SessionDB

        self.db = SessionDB(db_path=self.home / "state.db")
        self.addCleanup(self.db.close)
        self.peer = {
            "source": "whatsapp",
            "user_id": "synthetic-client",
            "session_key": "agent:main:whatsapp:dm:synthetic-client",
            "chat_id": "synthetic-client@lid",
            "chat_type": "dm",
        }

    def create(self, sid):
        self.db.create_session(sid, **self.peer)
        self.db.append_message(sid, "user", "Pedido fictício de informações")
        self.db.append_message(sid, "assistant", "Resposta fictícia do CEO")

    def recover(self):
        return self.db.find_latest_gateway_session_for_peer(**self.peer)

    def test_idle_preserves_client_and_ceo_messages(self):
        self.create("original")
        before = self.db.get_messages("original")
        self.assertTrue(self.db.promote_to_session_reset("original", "idle"))
        self.assertEqual(self.db.get_messages("original"), before)
        row = self.db.get_session("original")
        self.assertEqual(row["end_reason"], "idle")
        self.assertIsNotNone(row["ended_at"])

    def test_repeated_idle_is_noop_without_changing_boundary(self):
        self.create("original")
        self.assertTrue(self.db.promote_to_session_reset("original", "idle"))
        ended_at = self.db.get_session("original")["ended_at"]
        self.assertFalse(self.db.promote_to_session_reset("original", "idle"))
        self.assertEqual(self.db.get_session("original")["ended_at"], ended_at)

    def test_idle_fences_older_recoverable_peer_in_both_lookup_paths(self):
        self.create("older")
        self.db.end_session("older", "agent_close")
        self.create("latest")
        self.assertTrue(self.db.promote_to_session_reset("latest", "idle"))
        self.assertIsNone(self.recover())
        tuple_fallback = {**self.peer, "session_key": "missing-routing-key"}
        self.assertIsNone(
            self.db.find_latest_gateway_session_for_peer(**tuple_fallback)
        )

    def test_accidental_end_is_promoted_to_intentional_idle(self):
        self.create("original")
        self.db.end_session("original", "agent_close")
        self.assertEqual(self.recover()["id"], "original")
        self.assertTrue(self.db.promote_to_session_reset("original", "idle"))
        self.assertIsNone(self.recover())

    def test_new_session_for_same_peer_is_recoverable_after_idle(self):
        self.create("original")
        self.assertTrue(self.db.promote_to_session_reset("original", "idle"))
        self.create("new-session")
        self.assertEqual(self.recover()["id"], "new-session")
        self.assertEqual(len(self.db.get_messages("original")), 2)

    def test_other_holder_cannot_acquire_active_turn_lease(self):
        self.create("original")
        owner = f"pid={os.getpid()}:turn=synthetic-owner"
        contender = f"pid={os.getpid()}:turn=synthetic-maintenance"
        self.assertTrue(self.db.try_acquire_session_turn_lease("original", owner))
        try:
            self.assertFalse(
                self.db.try_acquire_session_turn_lease("original", contender)
            )
        finally:
            self.db.release_session_turn_lease("original", owner)
        self.assertTrue(self.db.try_acquire_session_turn_lease("original", contender))
        self.db.release_session_turn_lease("original", contender)

    def test_executor_closes_real_schema_with_old_synthetic_messages(self):
        import lifecycle
        import lifecycle_runtime
        from test_runtime import runner

        self.create("original")
        self.home.joinpath("config.yaml").write_text("sessions:\n  auto_prune: false\n")
        with sqlite3.connect(self.home / "state.db") as conn:
            conn.execute("UPDATE messages SET timestamp=?", (time.time() - 91 * 86400,))
            conn.execute(
                "UPDATE messages SET platform_message_id='fixture' WHERE role='user'"
            )
        with sqlite3.connect(self.home / "kanban.db") as conn:
            conn.executescript(
                "CREATE TABLE tasks(id TEXT,session_id TEXT,status TEXT); CREATE TABLE kanban_notify_subs(task_id TEXT,platform TEXT,chat_id TEXT);"
            )
        from gateway.delivery_ledger import _initialize_schema

        with sqlite3.connect(self.home / "state.db") as conn:
            _initialize_schema(conn)
        candidates = lifecycle.scan(self.home)
        self.assertEqual(len(candidates), 1)
        gateway = runner()
        gateway._session_db._db = self.db
        before = self.db.get_messages("original")
        self.assertEqual(
            lifecycle_runtime.close_one(gateway, self.home, candidates[0]), "closed"
        )
        self.assertEqual(self.db.get_messages("original"), before)
        self.assertEqual(self.db.get_session("original")["end_reason"], "idle")

    def test_session_store_replaces_cached_idle_route(self):
        from gateway.config import GatewayConfig, Platform
        from gateway.session import SessionSource, SessionStore

        store = SessionStore(
            sessions_dir=self.home / "sessions", config=GatewayConfig()
        )
        # Pin the explicit temporary handle, avoiding profile-dependent lookup.
        existing_db = store._db
        if existing_db is not None and existing_db is not self.db:
            self.addCleanup(existing_db.close)
        store._db = self.db
        source = SessionSource(
            platform=Platform.WHATSAPP,
            chat_id="synthetic-client@lid",
            chat_type="dm",
            user_id="synthetic-client",
        )
        original = store.get_or_create_session(source)
        original_id = original.session_id
        self.db.append_message(original_id, "user", "Histórico sintético preservado")
        self.assertTrue(self.db.promote_to_session_reset(original_id, "idle"))
        current = store.get_or_create_session(source)
        self.assertNotEqual(current.session_id, original_id)
        self.assertIsNone(self.db.get_session(current.session_id)["ended_at"])
        self.assertEqual(self.db.get_session(original_id)["end_reason"], "idle")
        self.assertEqual(len(self.db.get_messages(original_id)), 1)


if __name__ == "__main__":
    unittest.main()
