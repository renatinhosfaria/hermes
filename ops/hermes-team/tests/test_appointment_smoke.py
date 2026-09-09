"""Offline tests for the appointment behavioral smoke harness."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "appointment_smoke.py"
FIXTURES = Path(__file__).parent / "fixtures" / "appointment_smoke_scenarios.json"


def load_harness():
    if not SCRIPT.is_file():
        raise AssertionError("appointment_smoke.py ainda não implementado")
    spec = importlib.util.spec_from_file_location("appointment_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AppointmentSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = load_harness()
        cls.scenarios = json.loads(FIXTURES.read_text(encoding="utf-8"))

    def world(self, name):
        return self.harness.SyntheticWorld(copy.deepcopy(self.scenarios[name]))

    def journal(self, world, appointment_id, body):
        request = world.scenario["appointment_request"]
        marker = {
            "request_id": request["request_id"],
            "operation": request["operation"],
            "client_id": request["client_id"],
            "broker_id": request["broker_id"],
            "appointment_id": appointment_id,
            "body": body,
        }
        world.dispatch(
            "kanban_comment",
            {"task_id": world.scenario["task_id"], "body": "APPOINTMENT_ATTEMPT " + json.dumps(marker, separators=(",", ":"))},
        )

    def complete(self, world, **overrides):
        expected = world.scenario["expected"]
        request = world.scenario["appointment_request"]
        result = {
            "request_id": request["request_id"],
            "operation": request["operation"],
            "client_id": request["client_id"],
            "broker_id": 35,
            "outcome": expected["outcome"],
            "appointment_id": expected.get("appointment_id"),
            "scheduled_at": expected.get("scheduled_at", request.get("scheduled_at")),
            "status": expected.get("status"),
            "verified": expected["verified"],
            "reason": "Resultado sintético conferido.",
        }
        result.update(overrides)
        world.dispatch(
            "kanban_complete",
            {
                "summary": "Operação sintética processada.",
                "metadata": {
                    "status": "success",
                    "decision": "appointment_processed",
                    "entities": {"client_id": request["client_id"], "appointment_id": result["appointment_id"]},
                    "response_ready": None,
                    "requested_next_action": "return_to_ceo",
                    "reason": result["reason"],
                    "evidence": ["Ferramentas sintéticas conferidas."],
                    "appointment_result": result,
                },
            },
        )

    def test_create_is_journaled_written_once_and_read_back(self):
        world = self.world("create")
        request = world.scenario["appointment_request"]
        body = {
            "clienteId": 7101,
            "brokerId": 35,
            "type": "Visita",
            "status": "Agendado",
            "scheduledAt": "2030-09-12T18:00:00-03:00",
            "location": "Plantão Centro",
        }
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7101})
        world.dispatch("fc_get_appointments", {"query": {"clienteId": 7101, "brokerId": 35}})
        self.journal(world, None, body)
        created = json.loads(world.dispatch("fc_post_appointments", {"body": body}))
        world.dispatch("fc_get_appointments_by_id", {"id": created["data"]["id"]})
        self.complete(world)
        self.assertEqual(self.harness.validate_trace(world), [])

    def test_reschedule_preserves_duration_and_same_id(self):
        world = self.world("reschedule")
        body = {"scheduledAt": "2030-09-13T19:00:00-03:00", "status": "Reagendado", "endAt": "2030-09-13T20:30:00-03:00"}
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7102})
        world.dispatch("fc_get_appointments_by_id", {"id": 8102})
        self.journal(world, 8102, body)
        world.dispatch("fc_patch_appointments_by_id", {"id": 8102, "body": body})
        world.dispatch("fc_get_appointments_by_id", {"id": 8102})
        self.complete(world)
        self.assertEqual(self.harness.validate_trace(world), [])
        self.assertEqual(world.appointments[8102]["location"], "Plantão Sul")
        self.assertEqual(world.appointments[8102]["address"], "Rua Sintética, 10")

    def test_cancel_patches_status_without_delete_or_date_change(self):
        world = self.world("cancel")
        before = world.appointments[8103]["scheduledAt"]
        body = {"status": "Cancelado"}
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7103})
        world.dispatch("fc_get_appointments_by_id", {"id": 8103})
        self.journal(world, 8103, body)
        world.dispatch("fc_patch_appointments_by_id", {"id": 8103, "body": body})
        world.dispatch("fc_get_appointments_by_id", {"id": 8103})
        self.complete(world, scheduled_at=before)
        self.assertEqual(self.harness.validate_trace(world), [])
        self.assertEqual(world.appointments[8103]["scheduledAt"], before)

    def test_duplicate_attempt_reconciles_without_another_write(self):
        world = self.world("duplicate_task")
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7104})
        world.dispatch("fc_get_appointments_by_id", {"id": 8104})
        self.complete(world)
        self.assertEqual(self.harness.validate_trace(world), [])

    def test_lost_cancel_response_reconciles_exact_marker_target_without_search(self):
        world = self.world("lost_response")
        body = {"status": "Cancelado"}
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7105})
        world.dispatch("fc_get_appointments_by_id", {"id": 8105})
        self.journal(world, 8105, body)
        failed = json.loads(world.dispatch("fc_patch_appointments_by_id", {"id": 8105, "body": body}))
        self.assertIn("error", failed)
        world.dispatch("fc_get_appointments_by_id", {"id": 8105})
        self.complete(world, scheduled_at="2030-09-16T14:00:00-03:00")
        self.assertEqual(self.harness.validate_trace(world), [])
        self.assertNotIn("fc_get_appointments", [entry["tool"] for entry in world.trace])

    def test_record_mismatch_cannot_be_reported_as_verified(self):
        world = self.world("record_mismatch")
        request = world.scenario["appointment_request"]
        body = {"clienteId": 7106, "brokerId": 35, "type": "Visita", "status": "Agendado", "scheduledAt": request["scheduled_at"]}
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7106})
        world.dispatch("fc_get_appointments", {"query": {"clienteId": 7106, "brokerId": 35}})
        self.journal(world, None, body)
        created = json.loads(world.dispatch("fc_post_appointments", {"body": body}))
        world.dispatch("fc_get_appointments_by_id", {"id": created["data"]["id"]})
        self.complete(world, status=None)
        self.assertEqual(self.harness.validate_trace(world), [])
        world.completion["metadata"]["appointment_result"].update(outcome="confirmed", verified=True, status="Agendado")
        self.assertIn("unverified_readback_confirmed", self.harness.validate_trace(world))

    def test_wrong_broker_allows_no_journal_or_business_write(self):
        world = self.world("wrong_broker")
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7107})
        self.complete(world)
        self.assertEqual(self.harness.validate_trace(world), [])

    def test_ceo_routes_valid_null_response_to_reno_followup(self):
        world = self.world("ceo_return_to_reno")
        scenario = world.scenario
        body = {
            "kind": "appointment_followup",
            "correlation_id": scenario["correlation_id"],
            "pedido_exato": scenario["pedido_exato"],
            "appointment_request": scenario["appointment_request"],
            "upstream_result": {
                "worker": "agendamento",
                "entities": {"client_id": 7108, "appointment_id": 8108},
                "appointment_result": scenario["appointment_result"],
            },
            "test_mode": True,
        }
        world.dispatch("kanban_show", {})
        world.dispatch(
            "kanban_create",
            {
                "title": "Continuar retorno de agendamento sintético",
                "assignee": "reno",
                "body": json.dumps(body, ensure_ascii=False),
                "parents": ["task_agendamento_origin"],
                "workspace_kind": "dir",
                "workspace_path": "/root/.hermes/profiles/reno",
                "idempotency_key": "appointment:task_reno_origin:followup:task_agendamento_origin",
                "max_runtime_seconds": 600,
            },
        )
        self.assertEqual(self.harness.validate_trace(world), [])

    def test_missing_or_inexact_attempt_marker_blocks_a_write(self):
        world = self.world("create")
        body = {"clienteId": 7101, "brokerId": 35, "type": "Visita", "status": "Agendado", "scheduledAt": "2030-09-12T18:00:00-03:00"}
        with self.assertRaises(self.harness.SyntheticSafetyError):
            world.dispatch("fc_post_appointments", {"body": body})

    def test_create_validator_requires_filtered_list_before_post(self):
        world = self.world("create")
        request = world.scenario["appointment_request"]
        body = {
            "clienteId": 7101,
            "brokerId": 35,
            "type": "Visita",
            "status": "Agendado",
            "scheduledAt": request["scheduled_at"],
            "location": "Plantão Centro",
        }
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7101})
        self.journal(world, None, body)
        created = json.loads(world.dispatch("fc_post_appointments", {"body": body}))
        world.dispatch("fc_get_appointments_by_id", {"id": created["data"]["id"]})
        self.complete(world)
        self.assertIn("create_not_listed_before_post", self.harness.validate_trace(world))

    def test_completion_cannot_change_confirmed_instant(self):
        world = self.world("create")
        request = world.scenario["appointment_request"]
        body = {
            "clienteId": 7101,
            "brokerId": 35,
            "type": "Visita",
            "status": "Agendado",
            "scheduledAt": request["scheduled_at"],
            "location": "Plantão Centro",
        }
        world.dispatch("kanban_show", {})
        world.dispatch("fc_get_clientes_by_id", {"id": 7101})
        world.dispatch("fc_get_appointments", {"query": {"clienteId": 7101, "brokerId": 35}})
        self.journal(world, None, body)
        created = json.loads(world.dispatch("fc_post_appointments", {"body": body}))
        world.dispatch("fc_get_appointments_by_id", {"id": created["data"]["id"]})
        self.complete(world, scheduled_at="2030-09-12T23:00:00-03:00")
        self.assertIn("result_scheduled_at_mismatch", self.harness.validate_trace(world))
        self.journal(world, None, {**body, "scheduledAt": "2030-09-12T19:00:00-03:00"})
        with self.assertRaises(self.harness.SyntheticSafetyError):
            world.dispatch("fc_post_appointments", {"body": body})

    def test_unknown_tool_and_delete_shape_fail_closed(self):
        world = self.world("cancel")
        with self.assertRaises(self.harness.SyntheticSafetyError):
            world.dispatch("fc_delete_appointments_by_id", {"id": 8103})
        with self.assertRaises(self.harness.SyntheticSafetyError):
            world.dispatch("fc_patch_appointments_by_id", {"id": 8103, "body": {"deleted": True}})

    def test_ceo_validator_preserves_correlation_request_text_and_test_mode(self):
        scenario = self.scenarios["ceo_return_to_reno"]
        for field, replacement, expected_error in (
            ("correlation_id", "corr_other", "ceo_followup_correlation_mismatch"),
            ("pedido_exato", "texto alterado", "ceo_followup_pedido_mismatch"),
            ("test_mode", False, "ceo_followup_test_mode_mismatch"),
        ):
            with self.subTest(field=field):
                world = self.world("ceo_return_to_reno")
                body = {
                    "kind": "appointment_followup",
                    "correlation_id": scenario["correlation_id"],
                    "pedido_exato": scenario["pedido_exato"],
                    "appointment_request": scenario["appointment_request"],
                    "upstream_result": {"worker": "agendamento", "entities": {"client_id": 7108, "appointment_id": 8108}, "appointment_result": scenario["appointment_result"]},
                    "test_mode": True,
                }
                body[field] = replacement
                world.dispatch("kanban_show", {})
                world.dispatch("kanban_create", {
                    "title": "Continuação sintética",
                    "assignee": "reno",
                    "body": json.dumps(body, ensure_ascii=False),
                    "parents": ["task_agendamento_origin"],
                    "workspace_kind": "dir",
                    "workspace_path": "/root/.hermes/profiles/reno",
                    "idempotency_key": "appointment:task_reno_origin:followup:task_agendamento_origin",
                    "max_runtime_seconds": 600,
                })
                self.assertIn(expected_error, self.harness.validate_trace(world))

    def test_root_resolution_accepts_repo_or_profiles_parent(self):
        repo = Path("/tmp/synthetic-repo")
        self.assertEqual(self.harness.resolve_profiles_root(repo), repo / "profiles")
        profiles = Path("/tmp/profiles")
        self.assertEqual(self.harness.resolve_profiles_root(profiles), profiles)

    def test_model_prompt_hides_expected_seed_records_and_fault(self):
        scenario = self.scenarios["record_mismatch"]
        prompt = self.harness._build_prompt("agendamento", [], scenario)
        self.assertIn("task_agendamento_mismatch", prompt)
        self.assertIn('"test_mode":true', prompt)
        self.assertNotIn("readback_time_mismatch", prompt)
        self.assertNotIn('"expected"', prompt)
        self.assertNotIn('"appointments"', prompt)

    def test_cli_preflight_is_offline_and_does_not_echo_fixture_payloads(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(Path(__file__).resolve().parents[3]), "--preflight"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: APPOINTMENT_SMOKE_PREFLIGHT", result.stdout)
        self.assertNotIn("Quero visitar", result.stdout + result.stderr)
        self.assertNotIn("7101", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
