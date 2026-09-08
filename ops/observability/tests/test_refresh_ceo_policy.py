import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,'/usr/local/lib/hermes-agent')
from hermes_state import SessionDB
from refresh_ceo_policy import refresh

class RefreshTests(unittest.TestCase):
    def test_only_old_gateway_instruction_snapshots_change_history_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.db'
            db=SessionDB(path)
            try:
                for sid,source,prompt in [('old','whatsapp','Ninguém fica em silêncio porque um agente interno falhou.'),('new','whatsapp','new policy'),('cli','cli','Ninguém fica em silêncio porque um agente interno falhou.')]:
                    db.create_session(sid,source)
                    db.update_system_prompt(sid,prompt)
            finally: db.close()
            with sqlite3.connect(path) as c:
                c.execute("INSERT INTO messages(session_id,role,content,timestamp) VALUES ('old','user','preserve this',1)")
            self.assertEqual(refresh(path),1)
            self.assertEqual(refresh(path),0)
            db=SessionDB(path,read_only=True)
            try:
                self.assertIsNone(db.get_session('old')['system_prompt'])
                self.assertEqual(db.get_session('new')['system_prompt'],'new policy')
                self.assertIn('Ninguém',db.get_session('cli')['system_prompt'])
            finally: db.close()
            with sqlite3.connect(path) as c:
                self.assertEqual(c.execute('SELECT content FROM messages').fetchall(),[('preserve this',)])
