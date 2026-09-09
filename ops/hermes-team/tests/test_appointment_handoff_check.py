import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import appointment_handoff_check as handoff


def request_payload(operation="create"):
    return {
        "status": "success",
        "decision": "appointment_requested",
        "requested_next_action": "return_to_ceo",
        "response_ready": None,
        "appointment_request": {
            "request_id": "reno-original",
            "operation": operation,
            "client_id": 123,
            "broker_id": 35,
            "customer_accepted": True,
            "appointment_id": None,
            "scheduled_at": (
                None if operation == "cancel" else "2030-09-12T18:00:00-03:00"
            ),
            "timezone": "America/Sao_Paulo",
            "end_at": None,
            "location": None,
            "address": None,
        },
    }


def result_payload(operation="create", outcome="confirmed"):
    status = {
        "create": "Agendado",
        "reschedule": "Reagendado",
        "cancel": "Cancelado",
    }[operation]
    confirmed = outcome == "confirmed"
    return {
        "status": "success",
        "decision": "appointment_processed",
        "requested_next_action": "return_to_ceo",
        "response_ready": None,
        "appointment_result": {
            "request_id": "reno-original",
            "operation": operation,
            "client_id": 123,
            "broker_id": 35,
            "outcome": outcome,
            "appointment_id": 456 if confirmed else None,
            "scheduled_at": "2030-09-12T18:00:00-03:00" if confirmed else None,
            "status": status if confirmed else None,
            "verified": confirmed,
            "reason": "Registro conferido pelo id." if confirmed else "Aguardando releitura.",
        },
    }


class RequestValidationTests(unittest.TestCase):
    def test_valid_create_and_cancel_requests_match_original_reno_task(self):
        self.assertEqual(handoff.validate_request(request_payload(), "reno-original"), [])
        self.assertEqual(
            handoff.validate_request(request_payload("cancel"), "reno-original"), []
        )

    def test_request_rejects_wrong_task_id_missing_offset_and_missing_acceptance(self):
        payload = request_payload()
        payload["appointment_request"]["request_id"] = "different-task"
        payload["appointment_request"]["scheduled_at"] = "2030-09-12T18:00:00"
        payload["appointment_request"]["customer_accepted"] = False
        errors = handoff.validate_request(payload, "reno-original")
        self.assertTrue(any("request_id" in error for error in errors))
        self.assertTrue(any("scheduled_at" in error for error in errors))
        self.assertTrue(any("customer_accepted" in error for error in errors))

    def test_cancel_requires_null_scheduled_at(self):
        payload = request_payload("cancel")
        payload["appointment_request"]["scheduled_at"] = "2030-09-12T18:00:00-03:00"
        self.assertTrue(
            any("scheduled_at" in error for error in handoff.validate_request(payload, "reno-original"))
        )

    def test_request_requires_strict_broker_and_end_after_start(self):
        payload = request_payload()
        payload["appointment_request"]["broker_id"] = 35.0
        payload["appointment_request"]["end_at"] = "2030-09-12T17:59:00-03:00"
        errors = handoff.validate_request(payload, "reno-original")
        self.assertTrue(any("broker_id" in error for error in errors))
        self.assertTrue(any("end_at" in error for error in errors))

    def test_request_reports_unhashable_operation_as_invalid(self):
        payload = request_payload()
        payload["appointment_request"]["operation"] = ["create"]
        errors = handoff.validate_request(payload, "reno-original")
        self.assertTrue(any("operation" in error for error in errors))

    def test_request_rejects_conflicting_entities_client_id_when_provided(self):
        payload = request_payload()
        payload["entities"] = {"client_id": 999}
        errors = handoff.validate_request(payload, "reno-original")
        self.assertTrue(any("entities.client_id" in error for error in errors))


class ResultValidationTests(unittest.TestCase):
    def test_confirmed_result_accepts_operation_specific_statuses(self):
        for operation in ("create", "reschedule", "cancel"):
            with self.subTest(operation=operation):
                request = request_payload(operation)["appointment_request"]
                self.assertEqual(handoff.validate_result(result_payload(operation), request), [])

    def test_create_may_reuse_any_active_appointment_status(self):
        request = request_payload()["appointment_request"]
        for status in ("Agendado", "Confirmado", "Reagendado"):
            payload = result_payload()
            payload["appointment_result"]["status"] = status
            with self.subTest(status=status):
                self.assertEqual(handoff.validate_result(payload, request), [])

    def test_confirmed_result_requires_verified_id_offset_and_matching_status(self):
        request = request_payload("reschedule")["appointment_request"]
        payload = result_payload("reschedule")
        payload["appointment_result"].update(
            verified=False,
            appointment_id=None,
            scheduled_at="2030-09-12T18:00:00",
            status="Agendado",
        )
        errors = handoff.validate_result(payload, request)
        self.assertTrue(any("verified" in error for error in errors))
        self.assertTrue(any("appointment_id" in error for error in errors))
        self.assertTrue(any("scheduled_at" in error for error in errors))
        self.assertTrue(any("status" in error for error in errors))

    def test_nonconfirmed_result_requires_verified_false(self):
        request = request_payload()["appointment_request"]
        payload = result_payload(outcome="pending")
        payload["appointment_result"]["verified"] = True
        self.assertTrue(
            any("verified" in error for error in handoff.validate_result(payload, request))
        )

    def test_result_must_match_original_request_identity_and_operation(self):
        request = request_payload()["appointment_request"]
        payload = result_payload()
        payload["appointment_result"].update(request_id="other", operation="cancel", client_id=999)
        errors = handoff.validate_result(payload, request)
        self.assertTrue(any("request_id" in error for error in errors))
        self.assertTrue(any("operation" in error for error in errors))
        self.assertTrue(any("client_id" in error for error in errors))

    def test_confirmed_result_matches_requested_instant_and_known_target(self):
        request = request_payload("reschedule")["appointment_request"]
        request["appointment_id"] = 777
        payload = result_payload("reschedule")
        payload["appointment_result"]["appointment_id"] = 456
        payload["appointment_result"]["scheduled_at"] = "2030-09-12T19:00:00-03:00"
        errors = handoff.validate_result(payload, request)
        self.assertTrue(any("appointment_id" in error for error in errors))
        self.assertTrue(any("scheduled_at" in error for error in errors))

    def test_same_instant_with_different_offset_is_accepted(self):
        request = request_payload()["appointment_request"]
        payload = result_payload()
        payload["appointment_result"]["scheduled_at"] = "2030-09-12T21:00:00+00:00"
        self.assertEqual(handoff.validate_result(payload, request), [])

    def test_result_reports_unhashable_enums_as_invalid(self):
        request = request_payload()["appointment_request"]
        payload = result_payload()
        payload["appointment_result"].update(
            operation=["create"], outcome={"confirmed": True}, status=["Agendado"]
        )
        errors = handoff.validate_result(payload, request)
        self.assertTrue(any("operation" in error for error in errors))
        self.assertTrue(any("outcome" in error for error in errors))
        self.assertTrue(any("status" in error for error in errors))

    def test_result_rejects_conflicting_entities_when_provided(self):
        request = request_payload()["appointment_request"]
        payload = result_payload()
        payload["entities"] = {"client_id": 999, "appointment_id": 777}
        errors = handoff.validate_result(payload, request)
        self.assertTrue(any("entities.client_id" in error for error in errors))
        self.assertTrue(any("entities.appointment_id" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
