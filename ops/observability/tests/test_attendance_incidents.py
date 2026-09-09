import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import attendance_incidents as incidents

NOW = 1800000000

class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.k = sqlite3.connect(self.root / 'kanban.db')
        self.s = sqlite3.connect(self.root / 'state.db')
        self.addCleanup(self.k.close)
        self.addCleanup(self.s.close)
        self.k.executescript('''
        CREATE TABLE tasks(id TEXT,assignee TEXT,status TEXT,session_id TEXT,
          block_kind TEXT,consecutive_failures INTEGER,created_at REAL,started_at REAL,
          completed_at REAL,max_runtime_seconds INTEGER,body TEXT);
        CREATE TABLE task_runs(id INTEGER,task_id TEXT,outcome TEXT,metadata TEXT,
          started_at REAL,ended_at REAL);
        CREATE TABLE task_comments(id INTEGER,task_id TEXT,author TEXT,body TEXT,created_at REAL);
        ''')
        self.s.executescript('''
        CREATE TABLE sessions(id TEXT,source TEXT,chat_type TEXT,session_key TEXT);
        CREATE TABLE messages(id INTEGER,session_id TEXT,role TEXT,content TEXT,
          timestamp REAL,display_kind TEXT,observed INTEGER,tool_calls TEXT);
        INSERT INTO sessions VALUES ('s1','whatsapp','dm','agent:main:whatsapp:dm:test');
        ''')
        hp = self.root / 'plugin-data/fama-whatsapp-human-handover/handover.db'
        hp.parent.mkdir(parents=True)
        with sqlite3.connect(hp) as h:
            h.execute('CREATE TABLE paused_contacts(contact_id TEXT,session_key TEXT,paused_at REAL)')
        self.s.commit()

    def task(self, stage='reno', status='blocked', block='capability', failures=0, age=1800, payload=None, outcome='blocked', task='t_case', body=None):
        self.k.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (task,stage,status,'s1',block,failures,NOW-age,NOW-age,NOW-60 if status=='done' else None,600,json.dumps(body) if body else None))
        self.k.execute('INSERT INTO task_runs VALUES (?,?,?,?,?,?)',
                       (self.k.execute('SELECT count(*) FROM task_runs').fetchone()[0]+1,task,outcome,json.dumps(payload),NOW-age,NOW-60))
        self.k.commit()

    def message(self, role='user', content='PRIVATE CUSTOMER TEXT', age=1800, kind=None, observed=0, tools=None):
        self.s.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)',
                       (self.s.execute('SELECT count(*) FROM messages').fetchone()[0]+1,'s1',role,content,NOW-age,kind,observed,tools))
        self.s.commit()

    def detect(self):
        return incidents.detect(self.root, NOW)

    def test_capability_block_alerts_even_with_zero_failures_and_no_pii(self):
        self.task()
        self.message()
        result=self.detect()
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['task_id'],'t_case')
        self.assertTrue(result[0]['immediate'])
        self.assertIn('capability',result[0]['message'])
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_classifier_success_without_response_is_normal(self):
        for stage in ['porteiro','cadastro']:
            self.task(stage=stage,status='done',block=None,outcome='completed',payload={'response_ready':None},task='t_'+stage)
        self.assertEqual(self.detect(),[])

    def test_reno_completed_without_payload_is_incident(self):
        self.task(status='done',block=None,outcome='completed',payload={'response_ready':None})
        self.assertEqual(self.detect()[0]['reason'],'missing_response')

    def test_valid_reno_appointment_request_is_an_intermediate_not_missing_response(self):
        payload = self.appointment_request_metadata()
        self.task(status='done', block=None, outcome='completed', payload=payload)
        self.assertEqual(self.detect(), [])

    def test_reno_appointment_request_with_wrong_original_task_id_is_incident(self):
        payload = self.appointment_request_metadata()
        payload['appointment_request']['request_id'] = 'some-other-task'
        self.task(status='done', block=None, outcome='completed', payload=payload)
        self.assertEqual(self.detect()[0]['reason'], 'missing_response')

    def test_agendamento_confirmed_and_needs_information_results_are_valid_continuations(self):
        for outcome in ('confirmed', 'needs_information'):
            request = self.appointment_request_metadata()['appointment_request']
            result = self.appointment_result_metadata(outcome=outcome)
            self.task(stage='agendamento', status='done', block=None,
                      outcome='completed', payload=result,
                      task='t_' + outcome, body={'appointment_request': request})
        self.assertEqual(self.detect(), [])

    def test_agendamento_pending_result_requires_internal_attention(self):
        request = self.appointment_request_metadata()['appointment_request']
        result = self.appointment_result_metadata(outcome='pending')
        self.task(stage='agendamento', status='done', block=None,
                  outcome='completed', payload=result,
                  body={'appointment_request': request})
        self.assertEqual(self.detect()[0]['reason'], 'appointment_pending')

    def test_agendamento_stalled_and_failed_tasks_use_existing_incident_rules(self):
        self.task(stage='agendamento', status='ready', block=None,
                  outcome='timed_out', age=600, task='t_stalled')
        self.k.execute(
            'UPDATE task_runs SET ended_at=? WHERE task_id=?', (NOW-600, 't_stalled')
        )
        self.task(stage='agendamento', status='blocked', block='capability',
                  outcome='blocked', task='t_failed')
        reasons = {item['task_id']: item['reason'] for item in self.detect()}
        self.assertEqual(reasons['t_stalled'], 'queue_stalled')
        self.assertEqual(reasons['t_failed'], 'capability')

    def test_agendamento_malformed_result_is_incident(self):
        request = self.appointment_request_metadata()['appointment_request']
        result = self.appointment_result_metadata()
        result['appointment_result']['status'] = 'Agendado errado para remarcação'
        result['appointment_result']['operation'] = 'reschedule'
        request['operation'] = 'reschedule'
        self.task(stage='agendamento', status='done', block=None,
                  outcome='completed', payload=result,
                  body={'appointment_request': request})
        self.assertEqual(self.detect()[0]['reason'], 'appointment_result_invalid')

    def test_agendamento_accepts_upstream_request_fallback(self):
        request = self.appointment_request_metadata()['appointment_request']
        result = self.appointment_result_metadata()
        self.task(stage='agendamento', status='done', block=None,
                  outcome='completed', payload=result,
                  body={'upstream_result': {'appointment_request': request}})
        self.assertEqual(self.detect(), [])

    def test_agendamento_rejects_disagreeing_direct_and_upstream_requests(self):
        request = self.appointment_request_metadata()['appointment_request']
        upstream = dict(request, client_id=999)
        result = self.appointment_result_metadata()
        self.task(stage='agendamento', status='done', block=None,
                  outcome='completed', payload=result,
                  body={'appointment_request': request,
                        'upstream_result': {'appointment_request': upstream}})
        self.assertEqual(self.detect()[0]['reason'], 'appointment_result_invalid')

    def test_agendamento_unhashable_result_fields_are_invalid_not_watchdog_failure(self):
        request = self.appointment_request_metadata()['appointment_request']
        result = self.appointment_result_metadata()
        result['appointment_result']['operation'] = ['create']
        self.task(stage='agendamento', status='done', block=None,
                  outcome='completed', payload=result,
                  body={'appointment_request': request})
        detected = self.detect()
        self.assertEqual(detected[0]['reason'], 'appointment_result_invalid')
        self.assertNotEqual(detected[0]['area'], 'watchdog')

    @staticmethod
    def appointment_request_metadata():
        return {
            'status': 'success', 'decision': 'appointment_requested',
            'requested_next_action': 'return_to_ceo', 'response_ready': None,
            'appointment_request': {
                'request_id': 't_case', 'operation': 'create', 'client_id': 123,
                'broker_id': 35, 'customer_accepted': True, 'appointment_id': None,
                'scheduled_at': '2030-09-12T18:00:00-03:00',
                'timezone': 'America/Sao_Paulo', 'end_at': None,
                'location': None, 'address': None,
            },
        }

    @staticmethod
    def appointment_result_metadata(outcome='confirmed'):
        confirmed = outcome == 'confirmed'
        return {
            'status': 'success', 'decision': 'appointment_processed',
            'requested_next_action': 'return_to_ceo', 'response_ready': None,
            'appointment_result': {
                'request_id': 't_case', 'operation': 'create', 'client_id': 123,
                'broker_id': 35, 'outcome': outcome,
                'appointment_id': 456 if confirmed else None,
                'scheduled_at': '2030-09-12T18:00:00-03:00' if confirmed else None,
                'status': 'Agendado' if confirmed else None,
                'verified': confirmed, 'reason': 'Resultado sintético curto.',
            },
        }

    def test_ready_retry_and_recent_running_task_are_not_terminal_failures(self):
        self.task(status='ready',outcome='timed_out',age=30)
        self.assertEqual(self.detect(),[])
        self.k.execute("UPDATE tasks SET status='running'")
        self.k.commit()
        self.assertEqual(self.detect(),[])

    def test_recent_retry_uses_run_start_instead_of_first_attempt(self):
        self.task(status='running',age=7200)
        self.k.execute('UPDATE task_runs SET started_at=?,ended_at=NULL,outcome=NULL',(NOW-30,))
        self.k.commit()
        self.assertEqual(self.detect(),[])

    def test_overdue_task_is_detected(self):
        self.task(status='running',age=1800)
        self.assertEqual(self.detect()[0]['reason'],'runtime_exceeded')

    def test_internal_notifications_and_observed_messages_do_not_start_wait(self):
        self.message(kind='internal_notification')
        self.message(observed=1)
        self.assertEqual(self.detect(),[])

    def test_silent_and_tool_call_text_are_not_customer_responses(self):
        self.message()
        self.message(role='assistant',content='[SILENT]',age=600)
        self.message(role='assistant',content='processing',age=500,tools='[{"id":"call"}]')
        self.assertEqual(self.detect()[0]['reason'],'unanswered')

    def test_real_reply_and_human_takeover_suppress_wait_alert(self):
        self.message()
        self.message(role='assistant',content='Real answer',age=600)
        self.assertEqual(self.detect(),[])
        self.message(age=1000)
        self.s.execute("DELETE FROM messages WHERE role='assistant'")
        self.s.commit()
        hp=self.root / 'plugin-data/fama-whatsapp-human-handover/handover.db'
        with sqlite3.connect(hp) as h:
            h.execute("INSERT INTO paused_contacts VALUES ('test','agent:main:whatsapp:dm:test',?)",(NOW-300,))
        self.assertEqual(self.detect(),[])

    def test_wait_age_uses_first_unanswered_message_not_last(self):
        self.message(age=1800)
        self.message(age=30)
        self.assertEqual(self.detect()[0]['reason'],'unanswered')

    def test_needs_input_with_followup_is_not_failure(self):
        self.task(block='needs_input')
        self.message(role='assistant',content='Qual o melhor dia?',age=30)
        self.assertEqual(self.detect(),[])

    def test_needs_input_after_old_failure_is_still_a_valid_question(self):
        self.task(block='needs_input',failures=1)
        self.message(role='assistant',content='Qual o melhor dia?',age=30)
        self.assertEqual(self.detect(),[])

    def test_ceo_marker_is_recognized_without_copying_comment(self):
        self.task(status='done',stage='cadastro',payload={'response_ready':None})
        self.k.execute('INSERT INTO task_comments VALUES (1,?,?,?,?)',('t_case','default','INCIDENTE_ATENDIMENTO motivo=handoff_inconclusivo PRIVATE',NOW-30))
        self.k.commit()
        result=self.detect()
        self.assertEqual(result[0]['reason'],'ceo_reported')
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_db_error_is_unknown_not_empty_success(self):
        self.k.execute('DROP TABLE tasks')
        self.k.commit()
        result=self.detect()
        self.assertEqual(result[0]['area'],'watchdog')
        self.assertTrue(result[0]['detection_unavailable'])

if __name__=='__main__':
    unittest.main()
