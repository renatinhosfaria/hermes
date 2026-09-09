import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_team


class TelegramRuntimeStateTests(unittest.TestCase):
    def test_only_explicitly_disabled_agendamento_is_pending(self):
        disabled = {'platforms': {'telegram': {'enabled': False}}}
        missing = {'platforms': {'telegram': {}}}
        enabled = {'platforms': {'telegram': {'enabled': True}}}

        self.assertEqual(verify_team.telegram_runtime_state(disabled, 'agendamento'), 'pending')
        self.assertEqual(verify_team.telegram_runtime_state(disabled, 'reno'), 'invalid')
        self.assertEqual(verify_team.telegram_runtime_state(missing, 'agendamento'), 'invalid')
        self.assertEqual(verify_team.telegram_runtime_state(enabled, 'agendamento'), 'enabled')

    def test_enabled_agendamento_scopes_destination_without_chat_wide_grant(self):
        telegram = {
            'allow_from': 8564576789,
            'allowed_chats': '-100123',
            'group_allowed_chats': [],
        }
        self.assertEqual(
            verify_team.telegram_destination_scope_errors(
                telegram, 'agendamento', '-100123'
            ),
            [],
        )
        telegram['group_allowed_chats'] = [-100123]
        errors = verify_team.telegram_destination_scope_errors(
            telegram, 'agendamento', '-100123'
        )
        self.assertTrue(any('group_allowed_chats' in error for error in errors))

    def test_json_string_allowed_chats_is_rejected_like_the_runtime_rejects_it(self):
        telegram = {
            'allow_from': 8564576789,
            'allowed_chats': '["-100123"]',
            'group_allowed_chats': [],
        }
        errors = verify_team.telegram_destination_scope_errors(
            telegram, 'agendamento', '-100123'
        )
        self.assertTrue(any('allowed_chats' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
