import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fleet_watch as fleet

class AlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.delivered=[]
        self.patches=[patch.object(fleet,'STATE_DIR',self.root),
                      patch.object(fleet,'send_telegram',side_effect=lambda msg:self.delivered.append(msg) or True),
                      patch.object(fleet,'INVESTIGATION_HOURLY_CAP',0)]
        for p in self.patches: p.start(); self.addCleanup(p.stop)
        self.f={'sig':'atendimento:t_one','area':'atendimento','severity':'critical',
                'message':'cartão t_one bloqueado','immediate':True}

    def test_immediate_incident_is_sent_once_with_durable_receipt(self):
        self.assertTrue(fleet.run_alerting([self.f]))
        self.assertEqual(len(self.delivered),1)
        self.assertIn('atendimento:t_one',json.loads((self.root/'alerted.json').read_text()))
        fleet.run_alerting([self.f])
        self.assertEqual(len(self.delivered),1)

    def test_failed_delivery_is_retried_and_not_marked_as_sent(self):
        with patch.object(fleet,'send_telegram',return_value=False):
            self.assertFalse(fleet.run_alerting([self.f]))
        self.assertNotIn('atendimento:t_one',fleet.load_state('alerted.json'))
        fleet.run_alerting([self.f])
        self.assertEqual(len(self.delivered),1)

    def test_failed_alert_survives_signal_disappearing(self):
        with patch.object(fleet,'send_telegram',return_value=False):
            fleet.run_alerting([self.f])
        fleet.run_alerting([])
        self.assertEqual(len(self.delivered),1)
        self.assertIn('t_one',self.delivered[0])
        self.assertEqual(fleet.load_state('pending.json'),{})

    def test_failed_alert_survives_detection_becoming_unavailable(self):
        with patch.object(fleet,'send_telegram',return_value=False):
            fleet.run_alerting([self.f])
        unknown={'sig':'watchdog:attendance_source','area':'watchdog','severity':'critical',
                 'message':'detecção indisponível','immediate':True,'detection_unavailable':True}
        fleet.run_alerting([unknown])
        self.assertTrue(any('t_one' in text for text in self.delivered))

    def test_regular_fleet_findings_still_require_three_scans(self):
        f=dict(self.f,immediate=False)
        fleet.run_alerting([f]); fleet.run_alerting([f])
        self.assertEqual(self.delivered,[])
        fleet.run_alerting([f])
        self.assertEqual(len(self.delivered),1)

    def test_unknown_detection_does_not_claim_recovery(self):
        fleet.run_alerting([self.f])
        unknown={'sig':'watchdog:attendance_source','area':'watchdog','severity':'critical',
                 'message':'detecção indisponível','immediate':True,'detection_unavailable':True}
        fleet.run_alerting([unknown])
        self.assertIn(self.f['sig'],fleet.load_state('alerted.json'))
        self.assertFalse(any('recuperado' in m.lower() for m in self.delivered))

    def test_cleared_signal_does_not_claim_customer_was_answered(self):
        fleet.run_alerting([self.f]);fleet.run_alerting([])
        self.assertEqual(len(self.delivered),2)
        self.assertIn('confirmar',self.delivered[-1].lower())
        self.assertNotIn(self.f['sig'],fleet.load_state('alerted.json'))

    def test_many_findings_are_batched_below_telegram_limit(self):
        findings=[dict(self.f,sig=f'atendimento:t_{i}',message='x'*700) for i in range(20)]
        fleet.run_alerting(findings)
        self.assertGreater(len(self.delivered),1)
        self.assertTrue(all(len(m.encode('utf-16-le'))//2<=4000 for m in self.delivered))
        self.assertEqual(len(fleet.load_state('alerted.json')),20)

    def test_persistence_failure_is_not_silently_accepted(self):
        with patch.object(fleet,'STATE_DIR',self.root/'missing'/'under-file'):
            (self.root/'missing').write_text('not a directory')
            with self.assertRaises(OSError):
                fleet.save_state('alerted.json',{})

    def test_telegram_uses_configured_dev_destination_without_secret_in_argv(self):
        cfg=self.root/'config.yaml';cfg.write_text('platforms:\n  telegram:\n    enabled: true\n    home_channel:\n      platform: telegram\n      chat_id: -100123\n      thread_id: 1\n')
        env=self.root/'.env';env.write_text('TELEGRAM_BOT_TOKEN=fake-secret\n')
        captured=[]
        class Resp:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self): return b'{"ok":true,"result":{"message_id":77}}'
        def send(req,**kwargs):
            captured.append(json.loads(req.data))
            return Resp()
        # Stop the outer fake sender: exercise production delivery, replacing HTTP only.
        self.patches[1].stop()
        with patch.object(fleet,'DEV_ENV',env),patch.object(fleet,'DEV_CONFIG',cfg),patch.object(fleet.urllib.request,'urlopen',side_effect=send),patch.object(fleet.subprocess,'run',side_effect=AssertionError('no subprocess with secret')):
            self.assertTrue(fleet.send_telegram('Activation check'))
        self.assertEqual(captured,[{'chat_id':'-100123','text':'Activation check'}])

if __name__=='__main__': unittest.main()
