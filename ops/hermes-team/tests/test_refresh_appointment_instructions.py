import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, '/usr/local/lib/hermes-agent')
from hermes_state import SessionDB


class RefreshTests(unittest.TestCase):
    def test_apply_refuses_running_gateway_or_missing_policy_before_mutation(self):
        script = Path(__file__).resolve().parents[1] / 'refresh_appointment_instructions.py'
        spec = importlib.util.spec_from_file_location('appointment_refresh_guards', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for policy, pid, message in [
                ('old instructions', '0', 'installed first'),
                (module.POLICY_MARKER, '123', 'finish draining'),
            ]:
                with self.subTest(policy=policy, pid=pid):
                    (root / 'SOUL.md').write_text(policy)
                    with patch.object(module, 'ROOT', root), \
                         patch.object(sys, 'argv', ['refresh', 'default', '--apply']), \
                         patch.object(module.subprocess, 'run', return_value=SimpleNamespace(stdout=pid)), \
                         patch.object(module, 'refresh') as refresh:
                        with self.assertRaisesRegex(RuntimeError, message):
                            module.main()
                        refresh.assert_not_called()

    def test_only_stale_gateway_prompts_change_and_history_survives(self):
        script = Path(__file__).resolve().parents[1] / 'refresh_appointment_instructions.py'
        self.assertTrue(script.exists(), 'refresh helper not implemented')
        spec = importlib.util.spec_from_file_location('appointment_refresh', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.db'
            db = SessionDB(path)
            try:
                for sid, source, prompt in [
                    ('stale', 'whatsapp', 'old appointment instructions'),
                    ('admin', 'telegram', 'old admin instructions'),
                    ('current', 'whatsapp', module.POLICY_MARKER),
                    ('cli', 'cli', 'old appointment instructions'),
                ]:
                    db.create_session(sid, source, session_key=f'synthetic:{sid}')
                    db.update_system_prompt(sid, prompt)
            finally:
                db.close()
            with sqlite3.connect(path) as conn:
                conn.execute("INSERT INTO messages(session_id,role,content,timestamp) VALUES ('stale','user','synthetic history preserved',1)")
                before = conn.execute('SELECT id,source,session_key FROM sessions ORDER BY id').fetchall()
            self.assertEqual(set(module.candidates(path)), {'stale', 'admin'})
            self.assertEqual(module.refresh(path), 2)
            self.assertEqual(module.refresh(path), 0)
            db = SessionDB(path, read_only=True)
            try:
                self.assertIsNone(db.get_session('stale')['system_prompt'])
                self.assertIsNone(db.get_session('admin')['system_prompt'])
                self.assertEqual(db.get_session('current')['system_prompt'], module.POLICY_MARKER)
                self.assertEqual(db.get_session('cli')['system_prompt'], 'old appointment instructions')
            finally:
                db.close()
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute('SELECT content FROM messages').fetchall(), [('synthetic history preserved',)])
                self.assertEqual(conn.execute('SELECT id,source,session_key FROM sessions ORDER BY id').fetchall(), before)
