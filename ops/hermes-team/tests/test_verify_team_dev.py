import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_team


class DevTelegramScopeTests(unittest.TestCase):
    def policy(self):
        return {
            'allow_from': verify_team.OPERATOR_ID,
            'group_allow_from': [verify_team.OPERATOR_ID],
            'allowed_chats': '-100123',
        }

    def errors(self, policy):
        return verify_team.telegram_destination_scope_errors(policy, 'dev', '-100123')

    def test_operator_only_policy_accepts_csv_and_list_chats(self):
        for chats in ('-100123', ['-100123']):
            with self.subTest(chats=chats):
                policy = self.policy()
                policy['allowed_chats'] = chats
                self.assertEqual(self.errors(policy), [])

    def test_rejects_legacy_collective_grant(self):
        policy = {'allow_from': verify_team.OPERATOR_ID, 'group_allowed_chats': '-100123'}
        self.assertTrue(self.errors(policy))

    def test_rejects_chat_grant_even_with_correct_restriction(self):
        policy = self.policy()
        policy['group_allowed_chats'] = ['-100123']
        self.assertTrue(any('group_allowed_chats' in e for e in self.errors(policy)))

    def test_rejects_wrong_or_missing_destination_and_literal_json(self):
        for chats in (None, '-100999', '-100123,-100999', '["-100123"]'):
            with self.subTest(chats=chats):
                policy = self.policy()
                policy['allowed_chats'] = chats
                self.assertTrue(any('allowed_chats' in e for e in self.errors(policy)))

    def test_rejects_missing_or_broader_group_sender_allowlist(self):
        for users in (None, ['*'], [verify_team.OPERATOR_ID, '999']):
            with self.subTest(users=users):
                policy = self.policy()
                policy['group_allow_from'] = users
                self.assertTrue(any('group_allow_from' in e for e in self.errors(policy)))

    def test_rejects_guest_mode(self):
        policy = self.policy()
        policy['guest_mode'] = True
        self.assertTrue(any('guest_mode' in e for e in self.errors(policy)))

    def test_other_profiles_keep_existing_policy(self):
        policy = {'group_allowed_chats': '-100123'}
        self.assertEqual(verify_team.telegram_destination_scope_errors(policy, 'reno', '-100123'), [])


if __name__ == '__main__':
    unittest.main()
