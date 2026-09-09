"""Exercise CLI review draining without model calls or production stores."""
import importlib.util
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch


PLUGIN = Path(__file__).parents[2] / "plugins/fama-learning-lifecycle/__init__.py"


class LearningLifecycleTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("learning_lifecycle", PLUGIN)
        self.plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.plugin)
        hooks = {}
        self.plugin.register(SimpleNamespace(register_hook=lambda name, callback: hooks.setdefault(name, callback)))
        self.assertEqual(set(hooks), {"on_session_finalize"})
        self.finalize = hooks["on_session_finalize"]

    def test_cli_finalize_waits_for_review_write(self):
        started, release, persisted = threading.Event(), threading.Event(), threading.Event()

        def review():
            started.set()
            release.wait(2)
            persisted.set()

        worker = threading.Thread(target=review, name="bg-review", daemon=True)
        worker.start()
        self.assertTrue(started.wait(1))
        timer = threading.Timer(0.05, release.set)
        timer.start()
        try:
            result = self.finalize(platform="cli", timeout_seconds=1)
            self.assertTrue(persisted.is_set(), "CLI finalized before the review persisted")
            self.assertEqual(result, {"waited": 1, "pending": 0})
        finally:
            release.set()
            worker.join(1)
            timer.join(1)

    def test_gateway_does_not_wait_and_cli_wait_is_bounded(self):
        release = threading.Event()
        worker = threading.Thread(target=lambda: release.wait(2), name="bg-review", daemon=True)
        worker.start()
        try:
            with patch.object(worker, "join", wraps=worker.join) as join:
                self.assertIsNone(self.finalize(platform="telegram"))
                join.assert_not_called()
                result = self.finalize(platform="cli", timeout_seconds=0.01)
                self.assertEqual(result, {"waited": 1, "pending": 1})
                join.assert_called_once()
                self.assertLessEqual(join.call_args.args[0], 0.01)
        finally:
            release.set()
            worker.join(1)


if __name__ == "__main__":
    unittest.main()
