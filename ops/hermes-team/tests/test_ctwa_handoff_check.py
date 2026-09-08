"""Offline contract checks; these do not claim to enforce an LLM at runtime."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ctwa_handoff_check.py"
FIXTURES = Path(__file__).parent / "fixtures" / "ctwa_handoff_scenarios.json"


def complete_card():
    # Hand-written expected transfer, independent of the checker implementation.
    return {
        "contact": {"phone_e164": "15550000001"},
        "contexto": {
            "context_resolution_failed": False,
            "ctwa_attributions": [
                {
                    "event_id": "waevt_synthetic_a",
                    "source_app": "facebook",
                    "meta_attribution": {
                        "status": "confirmed",
                        "ad_id": "900101",
                        "ad_name": "[TESTE][JARDIM DAS FLORES][IMAGEM][V3]",
                        "campaign_id": "900201",
                        "campaign_name": "[TESTE][JARDIM DAS FLORES]",
                    },
                }
            ],
        },
    }


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "verificador offline ainda não implementado")
        spec = importlib.util.spec_from_file_location("ctwa_check", SCRIPT)
        self.checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.checker)
        self.fixtures = json.loads(FIXTURES.read_text())
        self.context = self.fixtures["confirmed"]["context"]
        self.card = complete_card()

    def test_complete_transfer_is_accepted(self):
        self.assertEqual(self.checker.check_handoff(self.context, self.card), [])

    def test_id_only_transfer_reproduces_real_omission(self):
        self.card["contexto"]["ctwa_attributions"][0]["meta_attribution"] = {
            "status": "confirmed",
            "ad_id": "900101",
        }
        self.assertIn(
            "attribution_mismatch", self.checker.check_handoff(self.context, self.card)
        )

    def test_each_confirmed_field_must_remain_exact(self):
        for field in ("ad_id", "ad_name", "campaign_id", "campaign_name"):
            with self.subTest(field=field):
                card = complete_card()
                card["contexto"]["ctwa_attributions"][0]["meta_attribution"][field] = (
                    "changed"
                )
                self.assertIn(
                    "attribution_mismatch",
                    self.checker.check_handoff(self.context, card),
                )

    def test_integer_id_is_not_a_copy_of_string_id(self):
        self.card["contexto"]["ctwa_attributions"][0]["meta_attribution"]["ad_id"] = (
            900101
        )
        self.assertIn(
            "attribution_mismatch", self.checker.check_handoff(self.context, self.card)
        )

    def test_wrong_contact_is_rejected(self):
        self.card["contact"]["phone_e164"] = "15550000002"
        self.assertIn(
            "contact_mismatch", self.checker.check_handoff(self.context, self.card)
        )

    def test_event_from_other_contact_is_rejected(self):
        self.card["contexto"]["ctwa_attributions"][0]["event_id"] = "waevt_synthetic_b"
        self.assertIn(
            "attribution_mismatch", self.checker.check_handoff(self.context, self.card)
        )

    def test_multiple_events_preserved_independently_and_order_is_irrelevant(self):
        other = copy.deepcopy(self.fixtures["other_contact"]["context"]["events"][0])
        # In this scenario Brain returned both events for A; no reuse across contacts.
        self.context["events"].append(other)
        self.card["contexto"]["ctwa_attributions"].insert(
            0,
            {
                "event_id": "waevt_synthetic_b",
                "source_app": "instagram",
                "meta_attribution": {
                    "status": "confirmed",
                    "ad_id": "900102",
                    "ad_name": "[TESTE][VILA DAS ARARAS][VIDEO]",
                    "campaign_id": "900202",
                    "campaign_name": "[TESTE][VILA DAS ARARAS]",
                },
            },
        )
        self.assertEqual(self.checker.check_handoff(self.context, self.card), [])
        self.card["contexto"]["ctwa_attributions"].pop()
        self.assertIn(
            "attribution_mismatch", self.checker.check_handoff(self.context, self.card)
        )

    def test_duplicate_event_is_not_a_valid_transfer(self):
        self.card["contexto"]["ctwa_attributions"] *= 2
        self.assertIn(
            "attribution_mismatch", self.checker.check_handoff(self.context, self.card)
        )

    def test_pending_and_unavailable_meta_are_copied_without_inventing_names(self):
        context = self.fixtures["pending"]["context"]
        for status in ("pending", "unavailable"):
            with self.subTest(status=status):
                context["events"][0]["meta_attribution"]["status"] = status
                self.card["contexto"]["ctwa_attributions"] = [
                    {
                        "event_id": "waevt_synthetic_pending",
                        "source_app": "instagram",
                        "meta_attribution": {
                            "status": status,
                            "reason": "meta_timeout",
                        },
                    }
                ]
                self.assertEqual(self.checker.check_handoff(context, self.card), [])
                self.card["contexto"]["ctwa_attributions"][0]["meta_attribution"][
                    "ad_name"
                ] = "invented"
                self.assertIn(
                    "attribution_mismatch",
                    self.checker.check_handoff(context, self.card),
                )

    def test_legacy_event_without_meta_is_explicit_null(self):
        del self.context["events"][0]["meta_attribution"]
        self.card["contexto"]["ctwa_attributions"][0]["meta_attribution"] = None
        self.assertEqual(self.checker.check_handoff(self.context, self.card), [])

    def test_ordinary_conversation_has_empty_attributions(self):
        self.context["events"] = [
            {
                "event_id": "waevt_ordinary",
                "transport_kind": "ordinary_inbound",
                "source_app": None,
                "inbound_kind": None,
            }
        ]
        self.card["contexto"]["ctwa_attributions"] = []
        self.assertEqual(self.checker.check_handoff(self.context, self.card), [])

    def test_brain_unavailable_does_not_require_an_ad_or_fabricated_phone(self):
        card = {
            "contexto": {"context_resolution_failed": True, "ctwa_attributions": []}
        }
        self.assertEqual(
            self.checker.check_handoff(self.fixtures["unavailable"]["context"], card),
            [],
        )
        card["contact"] = {"phone_e164": "15550000001"}
        self.assertIn(
            "unverified_contact",
            self.checker.check_handoff(self.fixtures["unavailable"]["context"], card),
        )

    def test_resolution_flag_cannot_hide_omission(self):
        self.card["contexto"]["context_resolution_failed"] = True
        self.assertIn(
            "resolution_flag_mismatch",
            self.checker.check_handoff(self.context, self.card),
        )

    def test_raw_fields_cannot_be_copied_elsewhere_in_card(self):
        self.card["contexto"]["extra"] = [{"external_ad_reply": {"sourceId": "900101"}}]
        self.assertIn(
            "raw_field_in_card", self.checker.check_handoff(self.context, self.card)
        )

    def test_absent_body_or_context_is_not_accepted_as_empty(self):
        for card in (None, [], {}, {"contexto": {}}):
            with self.subTest(card=card):
                self.assertTrue(self.checker.check_handoff(self.context, card))

    def test_invalid_source_is_not_treated_as_no_attribution(self):
        for context in ({}, {"status": "ok"}, {"status": "unknown"}):
            with self.subTest(context=context):
                self.assertEqual(
                    self.checker.check_handoff(context, self.card), ["invalid_context"]
                )

    def test_checker_keeps_inputs_unchanged_and_no_cross_call_state(self):
        before = copy.deepcopy((self.context, self.card))
        self.checker.check_handoff(self.context, self.card)
        self.checker.check_handoff(self.fixtures["other_contact"]["context"], self.card)
        self.assertEqual(self.checker.check_handoff(self.context, self.card), [])
        self.assertEqual((self.context, self.card), before)

    def test_cli_exit_codes_and_no_input_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory) / "context.json"
            card = Path(directory) / "card.json"
            context.write_text(json.dumps(self.context))
            card.write_text(json.dumps(self.card))
            command = [
                sys.executable,
                str(SCRIPT),
                "--context",
                str(context),
                "--card",
                str(card),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(
                (result.returncode, result.stdout.strip()), (0, "PASS: CTWA_HANDOFF")
            )
            self.card["contexto"]["ctwa_attributions"] = []
            card.write_text(json.dumps(self.card))
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("attribution_mismatch", result.stdout)
            context.write_text('{"private": "SYNTHETIC-DO-NOT-ECHO"')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("SYNTHETIC-DO-NOT-ECHO", result.stdout + result.stderr)
            self.assertNotIn("15550000001", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
