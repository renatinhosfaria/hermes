#!/usr/bin/env python3
"""Validate appointment handoff metadata without network or live data access."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

OPERATIONS = {"create", "reschedule", "cancel"}
OUTCOMES = {"confirmed", "pending", "needs_information"}
CREATE_CONFIRMED_STATUSES = {"Agendado", "Confirmado", "Reagendado"}
RESULT_FIELDS = {
    "request_id", "operation", "client_id", "broker_id", "outcome",
    "appointment_id", "scheduled_at", "status", "verified", "reason",
}
REQUEST_FIELDS = {
    "request_id", "operation", "client_id", "broker_id", "customer_accepted",
    "appointment_id", "scheduled_at", "timezone", "end_at", "location", "address",
}


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_iso_with_offset(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _parse_iso_with_offset(value: Any) -> datetime | None:
    if not _is_iso_with_offset(value):
        return None
    return datetime.fromisoformat(value)


def _require_fields(value: dict, required: set[str], prefix: str) -> list[str]:
    return [f"{prefix}.{field}: campo ausente" for field in sorted(required - value.keys())]


def _validate_entity_matches(metadata: dict, expected: dict, fields: tuple[str, ...]) -> list[str]:
    entities = metadata.get("entities")
    if entities is None:
        return []
    if not isinstance(entities, dict):
        return ["metadata.entities: deve ser objeto quando fornecido"]
    errors = []
    for field in fields:
        if field not in entities:
            continue
        actual = entities[field]
        wanted = expected.get(field)
        if actual != wanted or type(actual) is not type(wanted):
            errors.append(f"metadata.entities.{field}: diverge do contrato estruturado")
    return errors


def validate_request_data(request: Any, original_task_id: str | None = None) -> list[str]:
    """Validate the locked ``appointment_request`` shape and optional Reno task ID."""
    if not isinstance(request, dict):
        return ["appointment_request: deve ser objeto"]
    errors = _require_fields(request, REQUEST_FIELDS, "appointment_request")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        errors.append("appointment_request.request_id: deve ser string não vazia")
    elif original_task_id is not None and request_id != str(original_task_id):
        errors.append("appointment_request.request_id: diverge da tarefa original do Reno")

    operation = request.get("operation")
    valid_operation = isinstance(operation, str) and operation in OPERATIONS
    if not valid_operation:
        errors.append("appointment_request.operation: operação inválida")
    if not _is_positive_int(request.get("client_id")):
        errors.append("appointment_request.client_id: deve ser inteiro positivo")
    if type(request.get("broker_id")) is not int or request.get("broker_id") != 35:
        errors.append("appointment_request.broker_id: deve ser 35")
    if request.get("customer_accepted") is not True:
        errors.append("appointment_request.customer_accepted: deve ser true")

    appointment_id = request.get("appointment_id")
    if appointment_id is not None and not _is_positive_int(appointment_id):
        errors.append("appointment_request.appointment_id: deve ser inteiro positivo ou null")

    scheduled_at = request.get("scheduled_at")
    if valid_operation and operation in {"create", "reschedule"}:
        if not _is_iso_with_offset(scheduled_at):
            errors.append("appointment_request.scheduled_at: deve ser ISO 8601 com offset")
    elif valid_operation and operation == "cancel" and scheduled_at is not None:
        errors.append("appointment_request.scheduled_at: cancelamento exige null")

    if request.get("timezone") != "America/Sao_Paulo":
        errors.append("appointment_request.timezone: deve ser America/Sao_Paulo")
    end_at = request.get("end_at")
    if end_at is not None and not _is_iso_with_offset(end_at):
        errors.append("appointment_request.end_at: deve ser ISO 8601 com offset ou null")
    start_value = _parse_iso_with_offset(scheduled_at)
    end_value = _parse_iso_with_offset(end_at)
    if start_value is not None and end_value is not None and end_value <= start_value:
        errors.append("appointment_request.end_at: deve ser posterior a scheduled_at")
    for field in ("location", "address"):
        if request.get(field) is not None and not isinstance(request.get(field), str):
            errors.append(f"appointment_request.{field}: deve ser string ou null")
    return errors


def validate_request(metadata: Any, original_task_id: str) -> list[str]:
    """Validate Reno's terminal intermediate metadata against its task ID."""
    if not isinstance(metadata, dict):
        return ["metadata: deve ser objeto"]
    errors = []
    expected = {
        "status": "success",
        "decision": "appointment_requested",
        "requested_next_action": "return_to_ceo",
        "response_ready": None,
    }
    for field, value in expected.items():
        if field not in metadata or metadata.get(field) != value:
            errors.append(f"metadata.{field}: valor inválido")
    errors.extend(validate_request_data(metadata.get("appointment_request"), original_task_id))
    request = metadata.get("appointment_request")
    if isinstance(request, dict):
        errors.extend(_validate_entity_matches(metadata, request, ("client_id",)))
    return errors


def validate_result(metadata: Any, expected_request: Any) -> list[str]:
    """Validate Agendamento result metadata and its identity against the request."""
    if not isinstance(metadata, dict):
        return ["metadata: deve ser objeto"]
    errors = []
    expected_header = {
        "status": "success",
        "decision": "appointment_processed",
        "requested_next_action": "return_to_ceo",
        "response_ready": None,
    }
    for field, value in expected_header.items():
        if field not in metadata or metadata.get(field) != value:
            errors.append(f"metadata.{field}: valor inválido")

    if not isinstance(expected_request, dict):
        errors.append("expected_request: appointment_request ausente no corpo da tarefa")
        expected_request = {}
    else:
        errors.extend(validate_request_data(expected_request))

    result = metadata.get("appointment_result")
    if not isinstance(result, dict):
        return errors + ["appointment_result: deve ser objeto"]
    errors.extend(_require_fields(result, RESULT_FIELDS, "appointment_result"))
    errors.extend(
        _validate_entity_matches(metadata, result, ("client_id", "appointment_id"))
    )

    request_id = result.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        errors.append("appointment_result.request_id: deve ser string não vazia")
    operation = result.get("operation")
    valid_operation = isinstance(operation, str) and operation in OPERATIONS
    if not valid_operation:
        errors.append("appointment_result.operation: operação inválida")
    if not _is_positive_int(result.get("client_id")):
        errors.append("appointment_result.client_id: deve ser inteiro positivo")
    if type(result.get("broker_id")) is not int or result.get("broker_id") != 35:
        errors.append("appointment_result.broker_id: deve ser 35")
    for field in ("request_id", "operation", "client_id", "broker_id"):
        if field in expected_request and result.get(field) != expected_request.get(field):
            errors.append(f"appointment_result.{field}: diverge do pedido original")

    outcome = result.get("outcome")
    valid_outcome = isinstance(outcome, str) and outcome in OUTCOMES
    if not valid_outcome:
        errors.append("appointment_result.outcome: valor inválido")
    appointment_id = result.get("appointment_id")
    if appointment_id is not None and not _is_positive_int(appointment_id):
        errors.append("appointment_result.appointment_id: deve ser inteiro positivo ou null")
    scheduled_at = result.get("scheduled_at")
    if scheduled_at is not None and not _is_iso_with_offset(scheduled_at):
        errors.append("appointment_result.scheduled_at: deve ser ISO 8601 com offset ou null")
    status = result.get("status")
    if status is not None and not isinstance(status, str):
        errors.append("appointment_result.status: deve ser string ou null")
    if not isinstance(result.get("verified"), bool):
        errors.append("appointment_result.verified: deve ser booleano")
    reason = result.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        errors.append("appointment_result.reason: deve ser string curta não vazia")

    if valid_outcome and outcome == "confirmed":
        if result.get("verified") is not True:
            errors.append("appointment_result.verified: confirmação exige true")
        if not _is_positive_int(appointment_id):
            errors.append("appointment_result.appointment_id: confirmação exige inteiro positivo")
        if not _is_iso_with_offset(scheduled_at):
            errors.append("appointment_result.scheduled_at: confirmação exige ISO 8601 com offset")
        valid_statuses = ({
            "create": CREATE_CONFIRMED_STATUSES,
            "reschedule": {"Reagendado"},
            "cancel": {"Cancelado"},
        }.get(operation, set()) if valid_operation else set())
        if not isinstance(status, str) or status not in valid_statuses:
            errors.append("appointment_result.status: incompatível com operação confirmada")
        requested_at = _parse_iso_with_offset(expected_request.get("scheduled_at"))
        result_at = _parse_iso_with_offset(scheduled_at)
        if valid_operation and operation in {"create", "reschedule"} and requested_at is not None and result_at is not None:
            if result_at != requested_at:
                errors.append("appointment_result.scheduled_at: diverge do instante solicitado")
        requested_id = expected_request.get("appointment_id")
        if valid_operation and operation in {"reschedule", "cancel"} and _is_positive_int(requested_id):
            if appointment_id != requested_id:
                errors.append("appointment_result.appointment_id: diverge do alvo solicitado")
    elif valid_outcome and outcome in {"pending", "needs_information"} and result.get("verified") is not False:
        errors.append("appointment_result.verified: resultado não confirmado exige false")
    return errors


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="kind", required=True)
    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("metadata", type=Path)
    request_parser.add_argument("--original-task-id", required=True)
    result_parser = subparsers.add_parser("result")
    result_parser.add_argument("metadata", type=Path)
    result_parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.kind == "request":
            errors = validate_request(_read_json(args.metadata), args.original_task_id)
        else:
            request_doc = _read_json(args.request)
            expected_request = request_doc.get("appointment_request") if isinstance(request_doc, dict) else None
            errors = validate_result(_read_json(args.metadata), expected_request)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}")
        return 2
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: APPOINTMENT_{args.kind.upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
