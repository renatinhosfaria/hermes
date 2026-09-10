import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle_runtime as runtime
from lifecycle import Candidate


def runner():
    adapter = NS(
        is_connected=True,
        _poll_task=NS(
            done=lambda: False,
            get_coro=lambda: NS(cr_code=NS(co_name="_poll_messages"), cr_await=None),
        ),
    )
    for field in runtime.ADAPTER_GUARDS + runtime.WHATSAPP_GUARDS:
        setattr(adapter, field, {})
    return NS(
        _running_agents={},
        _sessions={},
        _draining=False,
        _external_drain_active=False,
        _startup_restore_in_progress=False,
        _startup_restore_queue=[],
        adapters={"whatsapp": adapter},
        _session_db=NS(_db=Mock()),
    )


class RuntimeTests(unittest.TestCase):
    def test_missing_poller_coroutine_blocks(self):
        r = runner()
        r.adapters["whatsapp"]._poll_task.get_coro = lambda: None
        self.assertFalse(runtime.quiet(r))

    def test_second_worker_cannot_own_lock(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            first = runtime.acquire_worker_lock(Path(tmp))
            try:
                self.assertIsNone(runtime.acquire_worker_lock(Path(tmp)))
            finally:
                first.close()

    def test_unsafe_retention_prevents_promotion(self):
        r = runner()
        with patch.object(runtime, "retention_safe", return_value=False):
            runtime.close_one(r, Path("/synthetic"), Candidate("sid", 1, False))
        r._session_db._db.try_acquire_session_turn_lease.assert_not_called()

    def test_modified_core_fails_compatibility(self):
        import hashlib
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "module.py").write_text("reviewed")
            (root / "compatibility.json").write_text(
                json.dumps({"module.py": hashlib.sha256(b"reviewed").hexdigest()})
            )
            with (
                patch.object(runtime, "ROOT", root),
                patch.object(runtime, "CORE", root),
            ):
                self.assertTrue(runtime.compatible())
                (root / "module.py").write_text("changed")
                self.assertFalse(runtime.compatible())

    def test_idle_is_accepted(self):
        self.assertTrue(runtime.quiet(runner()))

    def test_every_pending_adapter_guard_blocks(self):
        for name in runtime.ADAPTER_GUARDS + runtime.WHATSAPP_GUARDS:
            with self.subTest(name=name):
                r = runner()
                setattr(r.adapters["whatsapp"], name, {"pending": True})
                self.assertFalse(runtime.quiet(r))

    def test_missing_field_fails_closed(self):
        r = runner()
        del r.adapters["whatsapp"]._pending_messages
        self.assertFalse(runtime.quiet(r))

    def test_running_and_overflow_block(self):
        r = runner()
        r._running_agents = {"key": object()}
        self.assertFalse(runtime.quiet(r))
        r = runner()
        r._sessions = {"key": NS(conversation=NS(queued_events=[object()]))}
        self.assertFalse(runtime.quiet(r))

    def test_media_being_received_blocks(self):
        async def _build_message_event():
            pass

        coro = _build_message_event()
        try:
            r = runner()
            r.adapters["whatsapp"]._poll_task.get_coro = lambda: coro
            self.assertFalse(runtime.quiet(r))
        finally:
            coro.close()

    def test_activity_between_scan_and_apply_prevents_promotion(self):
        r = runner()
        db = r._session_db._db
        db.try_acquire_session_turn_lease.return_value = True
        with (
            patch.object(runtime, "scan", return_value=[]),
            patch.object(runtime, "retention_safe", return_value=True),
        ):
            result = runtime.close_one(
                r, Path("/synthetic"), Candidate("sid", 1, False)
            )
        self.assertEqual(result, "changed_or_busy")
        db.promote_to_session_reset.assert_not_called()
        db.release_session_turn_lease.assert_called_once()

    def test_native_promotion_uses_idle_and_releases_lease(self):
        r = runner()
        db = r._session_db._db
        db.try_acquire_session_turn_lease.return_value = True
        db.promote_to_session_reset.return_value = True
        c = Candidate("sid", 1, False)
        with (
            patch.object(runtime, "scan", return_value=[c]),
            patch.object(runtime, "retention_safe", return_value=True),
        ):
            self.assertEqual(runtime.close_one(r, Path("/synthetic"), c), "closed")
        db.promote_to_session_reset.assert_called_once_with("sid", reason="idle")
        db.release_session_turn_lease.assert_called_once()

    def test_lease_unavailable_prevents_promotion(self):
        r = runner()
        db = r._session_db._db
        db.try_acquire_session_turn_lease.return_value = False
        with patch.object(runtime, "retention_safe", return_value=True):
            self.assertEqual(
                runtime.close_one(r, Path("/synthetic"), Candidate("sid", 1, False)),
                "lease_busy",
            )
        db.promote_to_session_reset.assert_not_called()


if __name__ == "__main__":
    unittest.main()
