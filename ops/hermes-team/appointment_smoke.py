#!/usr/bin/env python3
"""Synthetic appointment behavior smoke test with an optional real model.

The default preflight and all unit tests are offline. ``--run-model`` is an
explicit opt-in: it uses the configured model provider, but every callable tool
is a process-local handler over ``SyntheticWorld``. No CRM, Kanban database,
message transport, plugin, memory, session database, or MCP is reachable.
"""

from __future__ import annotations

import argparse
import atexit
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_FIXTURES = HERE / "tests" / "fixtures" / "appointment_smoke_scenarios.json"
RUNTIME = Path("/usr/local/lib/hermes-agent")
ATTEMPT_PREFIX = "APPOINTMENT_ATTEMPT "
WRITE_TOOLS = {"fc_post_appointments", "fc_patch_appointments_by_id"}
AGENDAMENTO_TOOLS = {
    "kanban_show",
    "kanban_comment",
    "kanban_complete",
    "fc_get_clientes_by_id",
    "fc_get_appointments",
    "fc_get_appointments_by_id",
    "fc_post_appointments",
    "fc_patch_appointments_by_id",
}
CEO_TOOLS = {"kanban_show", "kanban_create"}


class SyntheticSafetyError(RuntimeError):
    """A fake call violated the closed synthetic contract."""


def resolve_profiles_root(root: Path) -> Path:
    """Accept either a Hermes/repository root or its ``profiles`` directory."""
    root = Path(root).expanduser()
    return root if root.name == "profiles" else root / "profiles"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _attempt(body: str) -> dict[str, Any] | None:
    if not isinstance(body, str) or not body.startswith(ATTEMPT_PREFIX):
        return None
    try:
        value = json.loads(body[len(ATTEMPT_PREFIX) :])
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _create_body(request: dict[str, Any]) -> dict[str, Any]:
    body = {
        "clienteId": request["client_id"],
        "brokerId": 35,
        "type": "Visita",
        "status": "Agendado",
        "scheduledAt": request["scheduled_at"],
    }
    for source, target in (("end_at", "endAt"), ("location", "location"), ("address", "address")):
        if request.get(source) is not None:
            body[target] = request[source]
    return body


def _reschedule_body(request: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    body = {"scheduledAt": request["scheduled_at"], "status": "Reagendado"}
    if request.get("end_at") is not None:
        body["endAt"] = request["end_at"]
    elif current.get("endAt") is not None:
        duration = _iso(current["endAt"]) - _iso(current["scheduledAt"])
        body["endAt"] = (_iso(request["scheduled_at"]) + duration).isoformat()
    return body


class SyntheticWorld:
    """Strict, in-memory stand-in for one synthetic worker task."""

    def __init__(self, scenario: dict[str, Any]):
        self.scenario = copy.deepcopy(scenario)
        self.initial_comments = list(self.scenario.get("comments", []))
        self.comments = list(self.initial_comments)
        self.appointments = {
            int(row["id"]): copy.deepcopy(row) for row in self.scenario.get("appointments", [])
        }
        self.trace: list[dict[str, Any]] = []
        self.readbacks: list[dict[str, Any] | None] = []
        self.completion: dict[str, Any] | None = None
        self.created_cards: list[dict[str, Any]] = []
        self.write_count = 0

    @property
    def allowed_tools(self) -> set[str]:
        return CEO_TOOLS if self.scenario["role"] == "ceo" else AGENDAMENTO_TOOLS

    def _record(self, tool: str, args: dict[str, Any], result: Any) -> str:
        self.trace.append({"tool": tool, "args": copy.deepcopy(args), "result": copy.deepcopy(result)})
        return result if isinstance(result, str) else _json(result)

    def _task_state(self) -> dict[str, Any]:
        if self.scenario["role"] == "ceo":
            s = self.scenario
            metadata = {
                "status": "success",
                "decision": "appointment_processed",
                "entities": {"client_id": s["appointment_result"]["client_id"], "appointment_id": s["appointment_result"]["appointment_id"]},
                "response_ready": s.get("response_ready"),
                "requested_next_action": "return_to_ceo",
                "appointment_result": s["appointment_result"],
            }
            body = {
                "kind": "appointment_execution",
                "correlation_id": s["correlation_id"],
                "pedido_exato": s["pedido_exato"],
                "appointment_request": s["appointment_request"],
                "test_mode": True,
            }
            return {"task": {"id": s["agendamento_task_id"], "body": _json(body)}, "comments": [], "runs": [{"status": "done", "metadata": metadata}]}
        s = self.scenario
        request = s["appointment_request"]
        body = {
            "kind": "appointment_execution",
            "test_mode": True,
            "correlation_id": "corr_" + request["request_id"],
            "pedido_exato": "Fixture interna sintética de agendamento.",
            "appointment_request": request,
            "upstream_result": {
                "worker": "reno",
                "decision": "appointment_requested",
                "entities": {"client_id": request["client_id"]},
                "appointment_request": request,
            },
        }
        return {
            "task": {"id": s["task_id"], "body": _json(body), "assignee": "agendamento", "status": "running"},
            "comments": [{"body": value, "author": "agendamento"} for value in self.comments],
            "runs": [],
        }

    def _matching_attempt(self, appointment_id: int | None, body: dict[str, Any]) -> dict[str, Any] | None:
        request = self.scenario["appointment_request"]
        expected = {
            "request_id": request["request_id"],
            "operation": request["operation"],
            "client_id": request["client_id"],
            "broker_id": request["broker_id"],
            "appointment_id": appointment_id,
            "body": body,
        }
        return next((_attempt(comment) for comment in reversed(self.comments) if _attempt(comment) == expected), None)

    def _guard_write(self, appointment_id: int | None, body: dict[str, Any]) -> None:
        if any(_attempt(comment) for comment in self.initial_comments):
            raise SyntheticSafetyError("pre-existing APPOINTMENT_ATTEMPT permits read-only reconciliation")
        if self.write_count:
            raise SyntheticSafetyError("synthetic task permits at most one commercial write")
        if self._matching_attempt(appointment_id, body) is None:
            raise SyntheticSafetyError("exact APPOINTMENT_ATTEMPT must be saved before the write")

    def dispatch(self, tool: str, args: dict[str, Any]) -> str:
        if tool not in self.allowed_tools:
            raise SyntheticSafetyError(f"tool is outside synthetic allowlist: {tool}")
        if not isinstance(args, dict):
            raise SyntheticSafetyError("tool arguments must be an object")
        if tool == "kanban_show":
            return self._record(tool, args, self._task_state())
        if tool == "kanban_comment":
            if args.get("task_id") != self.scenario["task_id"] or _attempt(args.get("body")) is None:
                raise SyntheticSafetyError("only a valid attempt marker on the current synthetic task is accepted")
            self.comments.append(args["body"])
            return self._record(tool, args, {"ok": True, "comment_id": f"comment_{len(self.comments)}"})
        if tool == "fc_get_clientes_by_id":
            client = self.scenario["client"]
            if args != {"id": client["id"]}:
                raise SyntheticSafetyError("client read must use the fixture client id")
            return self._record(tool, args, {"status_code": 200, "complete": True, "data": copy.deepcopy(client)})
        if tool == "fc_get_appointments":
            request = self.scenario["appointment_request"]
            if args != {"query": {"clienteId": request["client_id"], "brokerId": 35}}:
                raise SyntheticSafetyError("appointment list must be scoped to exact client and broker 35")
            rows = [copy.deepcopy(row) for row in self.appointments.values() if row["clienteId"] == request["client_id"] and row["brokerId"] == 35]
            return self._record(tool, args, {"status_code": 200, "complete": True, "truncated": False, "data": rows})
        if tool == "fc_get_appointments_by_id":
            appointment_id = args.get("id")
            if set(args) != {"id"} or not isinstance(appointment_id, int):
                raise SyntheticSafetyError("appointment read requires one integer id")
            row = copy.deepcopy(self.appointments.get(appointment_id))
            if row is not None and self.scenario.get("fault") == "readback_time_mismatch" and self.write_count:
                row["scheduledAt"] = "2030-09-17T17:00:00-03:00"
            self.readbacks.append(copy.deepcopy(row))
            return self._record(tool, args, {"status_code": 200 if row else 404, "complete": True, "data": row})
        if tool == "fc_post_appointments":
            request = self.scenario["appointment_request"]
            body = args.get("body")
            if set(args) != {"body"} or body != _create_body(request):
                raise SyntheticSafetyError("create body differs from the exact authorized fixture body")
            self._guard_write(None, body)
            appointment_id = int(self.scenario["next_appointment_id"])
            row = {"id": appointment_id, **copy.deepcopy(body)}
            self.appointments[appointment_id] = row
            self.write_count += 1
            return self._record(tool, args, {"status_code": 201, "data": {"id": appointment_id}})
        if tool == "fc_patch_appointments_by_id":
            appointment_id, body = args.get("id"), args.get("body")
            if set(args) != {"id", "body"} or not isinstance(appointment_id, int) or appointment_id not in self.appointments:
                raise SyntheticSafetyError("patch requires one existing fixture appointment id")
            request = self.scenario["appointment_request"]
            expected = {"status": "Cancelado"} if request["operation"] == "cancel" else _reschedule_body(request, self.appointments[appointment_id])
            if body != expected or appointment_id != request.get("appointment_id"):
                raise SyntheticSafetyError("patch target/body differs from the authorized operation")
            self._guard_write(appointment_id, body)
            self.appointments[appointment_id].update(copy.deepcopy(body))
            self.write_count += 1
            if self.scenario.get("fault") == "lost_write_response":
                return self._record(tool, args, {"error": "synthetic response lost after server applied patch"})
            return self._record(tool, args, {"status_code": 200, "data": {"id": appointment_id}})
        if tool == "kanban_complete":
            if self.completion is not None:
                raise SyntheticSafetyError("task may complete only once")
            self.completion = copy.deepcopy(args)
            return self._record(tool, args, {"ok": True, "task_id": self.scenario["task_id"], "status": "done"})
        if tool == "kanban_create":
            self.created_cards.append(copy.deepcopy(args))
            return self._record(tool, args, {"ok": True, "task_id": f"synthetic_child_{len(self.created_cards)}", "existing": len(self.created_cards) > 1})
        raise SyntheticSafetyError(f"unimplemented synthetic tool: {tool}")


def _completion_result(world: SyntheticWorld, errors: list[str]) -> dict[str, Any] | None:
    completion = world.completion
    if not isinstance(completion, dict):
        errors.append("missing_kanban_complete")
        return None
    metadata = completion.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("invalid_completion_metadata")
        return None
    if metadata.get("status") != "success" or metadata.get("decision") != "appointment_processed":
        errors.append("invalid_completion_decision")
    if metadata.get("response_ready") is not None or metadata.get("requested_next_action") != "return_to_ceo":
        errors.append("invalid_completion_routing")
    result = metadata.get("appointment_result")
    if not isinstance(result, dict):
        errors.append("missing_appointment_result")
        return None
    return result


def _readback_matches(request: dict[str, Any], expected: dict[str, Any], row: dict[str, Any] | None) -> bool:
    if not isinstance(row, dict):
        return False
    if row.get("id") != expected.get("appointment_id") or row.get("clienteId") != request["client_id"] or row.get("brokerId") != 35 or row.get("type") != "Visita":
        return False
    operation = request["operation"]
    if row.get("status") != expected.get("status"):
        return False
    if operation in {"create", "reschedule"} and row.get("scheduledAt") != request["scheduled_at"]:
        return False
    if expected.get("end_at") is not None and row.get("endAt") != expected["end_at"]:
        return False
    if operation == "create":
        for key, field in (("end_at", "endAt"), ("location", "location"), ("address", "address")):
            if request.get(key) is not None and row.get(field) != request[key]:
                return False
    return True


def _validate_ceo(world: SyntheticWorld) -> list[str]:
    errors: list[str] = []
    scenario, expected = world.scenario, world.scenario["expected"]
    if len(world.created_cards) != 1:
        return ["ceo_followup_card_count"]
    call = world.created_cards[0]
    for key, value in (("assignee", expected["assignee"]), ("workspace_kind", "dir"), ("workspace_path", "/root/.hermes/profiles/reno"), ("idempotency_key", expected["idempotency_key"]), ("max_runtime_seconds", 600)):
        if call.get(key) != value:
            errors.append("ceo_followup_" + key)
    if call.get("parents") != [expected["parent"]]:
        errors.append("ceo_followup_parent")
    try:
        body = json.loads(call.get("body", ""))
    except (TypeError, ValueError):
        body = None
    if not isinstance(body, dict) or body.get("kind") != "appointment_followup":
        errors.append("ceo_followup_body")
    else:
        if body.get("correlation_id") != scenario["correlation_id"]:
            errors.append("ceo_followup_correlation_mismatch")
        if body.get("pedido_exato") != scenario["pedido_exato"]:
            errors.append("ceo_followup_pedido_mismatch")
        if body.get("test_mode") is not True:
            errors.append("ceo_followup_test_mode_mismatch")
        if body.get("appointment_request") != scenario["appointment_request"]:
            errors.append("ceo_followup_request_mismatch")
        upstream = body.get("upstream_result")
        if not isinstance(upstream, dict) or upstream.get("worker") != "agendamento" or upstream.get("appointment_result") != scenario["appointment_result"]:
            errors.append("ceo_followup_result_mismatch")
    return errors


def validate_trace(world: SyntheticWorld) -> list[str]:
    """Judge observable behavior without treating model prose as execution."""
    tools = [entry["tool"] for entry in world.trace]
    errors: list[str] = []
    if any(tool not in world.allowed_tools for tool in tools):
        errors.append("tool_outside_allowlist")
    if not tools or tools[0] != "kanban_show":
        errors.append("task_not_read_first")
    if world.scenario["role"] == "ceo":
        return errors + _validate_ceo(world)

    scenario = world.scenario
    request, expected = scenario["appointment_request"], scenario["expected"]
    writes = [entry for entry in world.trace if entry["tool"] in WRITE_TOOLS]
    default_writes = 0 if scenario.get("comments") or scenario["client"]["brokerId"] != 35 else 1
    if len(writes) != expected.get("write_count", default_writes):
        errors.append("unexpected_write_count")
    if writes:
        try:
            first_write = next(index for index, entry in enumerate(world.trace) if entry["tool"] in WRITE_TOOLS)
            client_read = next(index for index, entry in enumerate(world.trace) if entry["tool"] == "fc_get_clientes_by_id")
            if client_read > first_write:
                errors.append("client_not_checked_before_write")
        except StopIteration:
            errors.append("client_not_checked_before_write")
        for write in writes:
            args = write["args"]
            appointment_id = args.get("id") if write["tool"] == "fc_patch_appointments_by_id" else None
            write_index = world.trace.index(write)
            prior_markers = [_attempt(entry["args"].get("body")) for entry in world.trace[:write_index] if entry["tool"] == "kanban_comment"]
            marker = {
                "request_id": request["request_id"],
                "operation": request["operation"],
                "client_id": request["client_id"],
                "broker_id": request["broker_id"],
                "appointment_id": appointment_id,
                "body": args["body"],
            }
            if marker not in prior_markers:
                errors.append("write_without_exact_prior_journal")
    if request["operation"] == "create" and writes:
        post_index = next(
            index for index, entry in enumerate(world.trace)
            if entry["tool"] == "fc_post_appointments"
        )
        expected_list_args = {
            "query": {"clienteId": request["client_id"], "brokerId": 35}
        }
        if not any(
            entry["tool"] == "fc_get_appointments"
            and entry["args"] == expected_list_args
            for entry in world.trace[:post_index]
        ):
            errors.append("create_not_listed_before_post")
    if any(_attempt(comment) for comment in world.initial_comments):
        marker = next(_attempt(comment) for comment in world.initial_comments if _attempt(comment))
        if writes:
            errors.append("duplicate_attempt_rewritten")
        if "fc_get_appointments" in tools:
            errors.append("duplicate_attempt_searched_new_target")
        target = marker.get("appointment_id")
        if target is not None and not any(entry["tool"] == "fc_get_appointments_by_id" and entry["args"] == {"id": target} for entry in world.trace):
            errors.append("duplicate_attempt_target_not_reconciled")
    if scenario.get("fault") == "lost_write_response":
        target = request.get("appointment_id")
        if target is None or "fc_get_appointments" in tools or not any(entry["tool"] == "fc_get_appointments_by_id" and entry["args"] == {"id": target} for entry in world.trace[tools.index("kanban_comment") + 1 :]):
            errors.append("lost_response_target_not_reconciled")

    result = _completion_result(world, errors)
    if result is None:
        return errors
    for field in ("request_id", "operation", "client_id", "broker_id"):
        if result.get(field) != request.get(field):
            errors.append("result_identity_mismatch")
            break
    for field in ("outcome", "appointment_id", "verified"):
        if result.get(field) != expected.get(field):
            errors.append("result_" + field + "_mismatch")
    if expected.get("status") is not None and result.get("status") != expected["status"]:
        errors.append("result_status_mismatch")
    if result.get("outcome") == "confirmed":
        expected_scheduled = expected.get("scheduled_at", request.get("scheduled_at"))
        try:
            same_instant = (
                isinstance(result.get("scheduled_at"), str)
                and isinstance(expected_scheduled, str)
                and _iso(result["scheduled_at"]) == _iso(expected_scheduled)
            )
        except ValueError:
            same_instant = False
        if not same_instant:
            errors.append("result_scheduled_at_mismatch")
        if not isinstance(result.get("reason"), str) or not result["reason"].strip():
            errors.append("result_reason_invalid")
    elif result.get("outcome") in {"pending", "needs_information"}:
        if result.get("verified") is not False:
            errors.append("result_nonconfirmed_verified")
    if result.get("outcome") == "confirmed" and result.get("verified") is True:
        matching = any(_readback_matches(request, expected, row) for row in world.readbacks)
        if not matching:
            errors.append("unverified_readback_confirmed")
    if scenario["client"]["brokerId"] != 35 and (writes or any(entry["tool"] == "kanban_comment" for entry in world.trace)):
        errors.append("wrong_broker_mutation")
    if request["operation"] == "cancel" and writes:
        write = writes[0]
        if write["tool"] != "fc_patch_appointments_by_id" or write["args"].get("body") != {"status": "Cancelado"}:
            errors.append("cancel_not_status_patch")
    return list(dict.fromkeys(errors))


def _schema(name: str) -> dict[str, Any]:
    properties: dict[str, Any]
    required: list[str]
    if name == "kanban_show":
        properties, required = {"task_id": {"type": "string"}}, []
    elif name == "kanban_comment":
        properties, required = {"task_id": {"type": "string"}, "body": {"type": "string"}}, ["task_id", "body"]
    elif name == "kanban_complete":
        properties, required = {"summary": {"type": "string"}, "metadata": {"type": "object"}}, ["summary", "metadata"]
    elif name == "kanban_create":
        properties, required = {
            "title": {"type": "string"}, "assignee": {"type": "string"}, "body": {"type": "string"},
            "parents": {"type": "array", "items": {"type": "string"}}, "workspace_kind": {"type": "string"},
            "workspace_path": {"type": "string"}, "idempotency_key": {"type": "string"}, "max_runtime_seconds": {"type": "integer"},
        }, ["title", "assignee", "body"]
    elif name == "fc_get_clientes_by_id" or name == "fc_get_appointments_by_id":
        properties, required = {"id": {"type": "integer"}}, ["id"]
    elif name == "fc_get_appointments":
        properties, required = {"query": {"type": "object"}}, ["query"]
    elif name == "fc_post_appointments":
        properties, required = {"body": {"type": "object"}}, ["body"]
    elif name == "fc_patch_appointments_by_id":
        properties, required = {"id": {"type": "integer"}, "body": {"type": "object"}}, ["id", "body"]
    else:
        raise SyntheticSafetyError(f"no synthetic schema for {name}")
    descriptions = {
        "kanban_show": "Read the complete current synthetic task, comments, and terminal result.",
        "kanban_comment": "Save the exact APPOINTMENT_ATTEMPT marker on this synthetic task.",
        "kanban_complete": "Return the structured synthetic appointment result.",
        "kanban_create": "Create one synthetic downstream task; no real Kanban state is touched.",
        "fc_get_clientes_by_id": "Read one synthetic client record.",
        "fc_get_appointments": "List the complete synthetic appointment set for one exact client and broker.",
        "fc_get_appointments_by_id": "Read one synthetic appointment by exact id.",
        "fc_post_appointments": "Create one in-memory synthetic appointment after the exact journal marker.",
        "fc_patch_appointments_by_id": "Patch one in-memory synthetic appointment after the exact journal marker.",
    }
    return {"name": name, "description": descriptions[name], "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}


def _required_docs(profiles_root: Path) -> dict[str, list[Path]]:
    hermes_root = profiles_root.parent
    return {
        "agendamento": [profiles_root / "agendamento" / "SOUL.md", profiles_root / "agendamento" / ".hermes.md", profiles_root / "agendamento" / "skills" / "business-operations" / "fama-agendamento-runtime" / "SKILL.md"],
        "ceo": [hermes_root / "SOUL.md", hermes_root / ".hermes.md", hermes_root / "skills" / "business-operations" / "fama-ceo-runtime" / "SKILL.md"],
    }


def load_scenarios(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"create", "reschedule", "cancel", "duplicate_task", "lost_response", "record_mismatch", "wrong_broker", "ceo_return_to_reno"}:
        raise ValueError("fixture set is incomplete")
    return data


def preflight(profiles_root: Path, fixtures: Path) -> None:
    scenarios = load_scenarios(fixtures)
    missing = [str(path) for paths in _required_docs(profiles_root).values() for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing prompt files: " + ", ".join(missing))
    for name, scenario in scenarios.items():
        world = SyntheticWorld(scenario)
        if world.allowed_tools & {"terminal", "write_file", "patch", "mcp", "message", "send_message"}:
            raise SyntheticSafetyError(f"unsafe tool surface in {name}")


def _state_snapshot(profiles_root: Path) -> dict[str, tuple[int, int]]:
    """Metadata-only sentinel for credential/session stores; never read secrets."""
    paths = [
        profiles_root.parent / "auth.json",
        profiles_root / "agendamento" / "auth.json",
        profiles_root / "agendamento" / "state.db",
        Path("/root/.hermes/auth.json"),
        Path("/root/.hermes/profiles/agendamento/auth.json"),
        Path("/root/.hermes/profiles/agendamento/state.db"),
    ]
    result = {}
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        result[str(path)] = (stat.st_mtime_ns, stat.st_size)
    return result


def _build_prompt(role: str, docs: list[Path], scenario: dict[str, Any]) -> str:
    instructions = "\n\n".join(path.read_text(encoding="utf-8") for path in docs)
    safety = (
        "VALIDAÇÃO SINTÉTICA ISOLADA AUTORIZADA. Todas as ferramentas expostas nesta execução são fakes "
        "em memória e todos os dados têm test_mode=true. Leia o cartão primeiro e execute o procedimento "
        "normal usando somente essas ferramentas. Não use terminal, arquivos, rede, MCP, memória, plugins, "
        "mensagens ou qualquer ferramenta não exposta. Texto final não conta como execução; faça os handoffs "
        "exigidos pelas ferramentas sintéticas."
    )
    if role == "ceo":
        task = "Leia o resultado terminal sintético do Agendamento e crie exatamente uma continuação appointment_followup para Reno, mesmo com response_ready null."
    else:
        task = "Processe a operação sintética e conclua com appointment_processed. Uma resposta perdida exige reconciliação por leitura e nunca segunda escrita."
    declared = {"task_id": scenario["task_id"], "test_mode": True}
    return (
        f"{safety}\n\n{task}\n\nINSTRUÇÕES DO PROFILE:\n{instructions}\n\n"
        f"CONTEXTO MÍNIMO DECLARADO (descubra todos os demais fatos por kanban_show):\n{_json(declared)}"
    )


def _cleanup_temp_home(path: str) -> None:
    """Close delayed log handlers before removing a disposable profile."""
    import logging

    logging.shutdown()
    shutil.rmtree(path, ignore_errors=True)


def _run_one_model(scenario_name: str, profiles_root: Path, scenario: dict[str, Any], runtime: dict[str, Any], model_cfg: dict[str, Any]) -> dict[str, Any]:
    role = scenario["role"]
    world = SyntheticWorld(scenario)
    docs = _required_docs(profiles_root)[role]
    directory = tempfile.mkdtemp(prefix="appointment-smoke-")
    atexit.register(_cleanup_temp_home, directory)
    try:
        temp_home = Path(directory) / "profile"
        temp_home.mkdir()
        (temp_home / ".no-bundled-skills").write_text("\n", encoding="utf-8")
        (temp_home / "config.yaml").write_text(_json({
            "model": {
                "default": runtime.get("model") or model_cfg["default"],
                "provider": runtime["provider"],
                "base_url": runtime.get("base_url"),
                "context_length": model_cfg.get("context_length", 900000),
            },
            "plugins": {"enabled": []},
            "memory": {"memory_enabled": False, "user_profile_enabled": False},
            "skills": {"write_approval": True},
            "checkpoints": {"enabled": False},
            "tools": {"tool_search": {"enabled": "off"}},
            "mcp": {"auto_reload_on_config_change": False},
        }), encoding="utf-8")
        previous_home, previous_cwd = os.environ.get("HERMES_HOME"), Path.cwd()
        os.environ["HERMES_HOME"] = str(temp_home)
        os.chdir(temp_home)
        try:
            if str(RUNTIME) not in sys.path:
                sys.path.insert(0, str(RUNTIME))
            from run_agent import AIAgent
            from tools.registry import registry
            from toolsets import create_custom_toolset

            handlers = {}
            for tool_name in sorted(world.allowed_tools):
                def handler(args, _name=tool_name, **_kwargs):
                    return world.dispatch(_name, args)
                handlers[tool_name] = handler
                registry.register(name=tool_name, toolset="appointment-smoke", schema=_schema(tool_name), handler=handler, override=True)
            create_custom_toolset("appointment-smoke", "Strict process-local appointment smoke tools", sorted(world.allowed_tools))
            agent = AIAgent(
                model=runtime.get("model") or model_cfg["default"],
                provider=runtime["provider"],
                api_key=runtime.get("api_key"),
                base_url=runtime.get("base_url"),
                api_mode=runtime.get("api_mode"),
                credential_pool=None,
                request_overrides=runtime.get("request_overrides") or {},
                enabled_toolsets=["appointment-smoke"],
                platform="cli",
                skip_context_files=True,
                load_soul_identity=False,
                skip_memory=True,
                skip_background_review=True,
                session_db=None,
                quiet_mode=True,
                max_iterations=16,
                run_budget_seconds=300,
                checkpoints_enabled=False,
                reasoning_config={"effort": "medium"},
                ephemeral_system_prompt=_build_prompt(role, docs, scenario),
            )
            agent._persist_disabled = True
            agent._end_session_on_close = False
            agent._skip_mcp_refresh = True
            agent.suppress_status_output = True
            assert agent._session_db is None, "session_db attached"
            assert agent.valid_tool_names == world.allowed_tools, (
                "tool surface mismatch: " + ",".join(sorted(agent.valid_tool_names))
            )
            assert agent.tools and {item["function"]["name"] for item in agent.tools} == world.allowed_tools, "tool schemas differ from allowlist"
            assert all(registry.get_entry(name).handler is handlers[name] for name in world.allowed_tools), "synthetic handler was not installed"
            assert not getattr(agent, "_memory_enabled", False), "memory enabled"
            assert getattr(agent, "_memory_manager", None) is None, "memory manager attached"
            assert agent.skip_background_review is True and agent._skip_mcp_refresh is True, "background review or MCP refresh enabled"
            try:
                response = agent.run_conversation("Execute agora o cenário sintético declarado.")
            finally:
                agent.release_clients()
            return {
                "scenario": scenario_name,
                "errors": validate_trace(world),
                "final_response_present": bool(response.get("final_response")),
                "tools": [entry["tool"] for entry in world.trace],
                "trace": world.trace,
            }
        finally:
            os.chdir(previous_cwd)
            if previous_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous_home
    except Exception:
        raise


def _resolve_runtime(profiles_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use staged config first, then native live profile/root auth without copying it."""
    if str(RUNTIME) not in sys.path:
        sys.path.insert(0, str(RUNTIME))
    from hermes_cli.config import load_config_readonly
    from hermes_cli.runtime_provider import resolve_runtime_provider

    source_home = profiles_root / "agendamento"
    live_home = Path("/root/.hermes/profiles/agendamento")
    candidates = [source_home]
    if live_home.is_dir() and live_home.resolve() != source_home.resolve():
        candidates.append(live_home)
    last_error: Exception | None = None
    source_model_cfg: dict[str, Any] | None = None
    previous_home = os.environ.get("HERMES_HOME")
    try:
        for index, home in enumerate(candidates):
            os.environ["HERMES_HOME"] = str(home)
            try:
                config = load_config_readonly()
                model_cfg = config["model"]
                if index == 0:
                    source_model_cfg = model_cfg
                requested = source_model_cfg or model_cfg
                runtime = resolve_runtime_provider(
                    requested=requested["provider"], target_model=requested["default"]
                )
                return runtime, requested
            except Exception as exc:  # credential fallback boundary; never logged
                last_error = exc
        assert last_error is not None
        raise SyntheticSafetyError("runtime provider resolution failed") from last_error
    finally:
        if previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous_home


def run_model(profiles_root: Path, fixtures: Path, selected: list[str]) -> list[dict[str, Any]]:
    preflight(profiles_root, fixtures)
    scenarios = load_scenarios(fixtures)
    before = _state_snapshot(profiles_root)
    runtime, model_cfg = _resolve_runtime(profiles_root)
    names = list(scenarios) if selected == ["all"] else selected
    results = []
    for name in names:
        print(f"SCENARIO_START {name}", file=sys.stderr, flush=True)
        result = _run_one_model(name, profiles_root, scenarios[name], runtime, model_cfg)
        results.append(result)
        verdict = "PASS" if not result["errors"] else "FAIL"
        called = ",".join(result["tools"])
        print(f"SCENARIO_DONE {name} {verdict} tools={called}", file=sys.stderr, flush=True)
    after = _state_snapshot(profiles_root)
    if after != before:
        raise SyntheticSafetyError("source profile or root credential metadata changed during synthetic run")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Repository/Hermes root or profiles directory containing staged/live prompts")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true", help="Offline document, fixture, and allowlist checks only")
    mode.add_argument("--run-model", action="store_true", help="Explicitly opt into real-provider calls with in-memory tools")
    parser.add_argument("--scenario", action="append", choices=["all", "create", "reschedule", "cancel", "duplicate_task", "lost_response", "record_mismatch", "wrong_broker", "ceo_return_to_reno"], help="Model scenario; repeat as needed (default: create, lost_response, ceo_return_to_reno)")
    args = parser.parse_args()
    profiles_root = resolve_profiles_root(args.root)
    try:
        if args.preflight:
            preflight(profiles_root, args.fixtures)
            print("PASS: APPOINTMENT_SMOKE_PREFLIGHT")
            return 0
        selected = args.scenario or ["create", "lost_response", "ceo_return_to_reno"]
        if "all" in selected and selected != ["all"]:
            raise ValueError("--scenario all cannot be combined with another scenario")
        results = run_model(profiles_root, args.fixtures, selected)
        print(json.dumps({"ok": all(not item["errors"] for item in results), "results": results}, ensure_ascii=False, indent=2))
        return 0 if all(not item["errors"] for item in results) else 1
    except (OSError, ValueError, KeyError, SyntheticSafetyError, AssertionError) as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
