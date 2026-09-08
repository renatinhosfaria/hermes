"""Observe Reno tools and require transport evidence for post-send stage changes."""

import json
import os
import threading

from .delivery import task_document, verify_receipt

VERSION = "1.0.0"
READ = "mcp__famachat__fc_get_clientes_by_id"
PATCH = "mcp__famachat__fc_patch_clientes_by_id"
HISTORY = "mcp__brain__conversation_recent"
RUNTIME_SKILL = "fama-reno-runtime"
EARLY = {"Sem Atendimento", "Não Respondeu", "Em Atendimento"}


def decode(raw):
    value = raw
    for _ in range(5):
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("<untrusted_tool_result "):
                lines = value.splitlines()
                start = next(
                    i for i, line in enumerate(lines) if line.startswith(("{", "["))
                )
                value, _ = json.JSONDecoder().raw_decode("\n".join(lines[start:]))
            else:
                value = json.loads(value)
        elif isinstance(value, dict) and set(value) == {"result"}:
            value = value["result"]
        else:
            break
    if not isinstance(value, dict):
        raise ValueError("invalid_result")
    return value


def normalized(text):
    # One WhatsApp envelope can repeat the same initial ad line more than once.
    return " ".join(
        dict.fromkeys(line.strip() for line in str(text).splitlines() if line.strip())
    ).casefold()


def later_message(messages, initial):
    """Minimum evidence bound; commercial classification stays in Reno's conduct."""
    if not initial:
        return False
    clients = [
        m
        for m in messages
        if m.get("speaker") == "cliente"
        and m.get("ref")
        and isinstance(m.get("timestamp"), (int, float))
        and m.get("text")
    ]
    origins = [m for m in clients if normalized(m["text"]) == normalized(initial)]
    if not origins:
        return False
    origin = max(origins, key=lambda m: m["timestamp"])
    return any(
        m["timestamp"] > origin["timestamp"]
        and m["ref"] != origin["ref"]
        and normalized(m["text"]) != normalized(initial)
        for m in clients
    )


def block(reason):
    return {"action": "block", "message": "Reno: " + reason}


class RenoGuard:
    def __init__(self, task_id, run_id, receipt_verifier=verify_receipt):
        self.task_id, self.run_id = task_id, str(run_id)
        self.receipt_verifier = receipt_verifier
        self.lock = threading.RLock()
        self.session_id = None
        self.doc = None
        self.pending = {}
        self.client = None
        self.fresh = False
        self.messages = []
        self.attempted = False
        self.patch_ok = False
        self.patched_status = None
        self.receipt = False
        self.skill_loaded = False

    @staticmethod
    def unwrap(name, args):
        return (
            (args["name"], args.get("arguments", {}))
            if name == "tool_call"
            else (name, args)
        )

    def reply_after_delivery(self, proof):
        return any(
            m.get("speaker") == "cliente"
            and isinstance(m.get("timestamp"), (int, float))
            and m["timestamp"] > proof["delivered_at"]
            for m in self.messages
        )

    def before(self, *, tool_name, args, session_id="", tool_call_id="", **_):
        try:
            name, payload = self.unwrap(tool_name, args)
            business = name.startswith(("mcp__famachat__", "mcp__brain__"))
            if not business and name not in {
                "kanban_show",
                "kanban_complete",
                "skill_view",
            }:
                return None
            with self.lock:
                if not session_id or (
                    self.session_id and self.session_id != session_id
                ):
                    return block("sessao_incompativel")
                self.session_id = session_id
                if name == "skill_view":
                    if not payload.get("file_path"):
                        if not tool_call_id:
                            return block("identificador_de_chamada_ausente")
                        self.pending[tool_call_id] = name
                    return None
                if (business or name == "kanban_complete") and not self.skill_loaded:
                    return block(
                        'Antes de atender, chame skill_view(name="fama-reno-runtime") '
                        "e aguarde a leitura bem-sucedida do manual completo. "
                        "Se a leitura falhar, registre o bloqueio com kanban_block."
                    )
                if payload.get("task_id", self.task_id) != self.task_id or payload.get(
                    "board"
                ):
                    return block("use_o_cartao_atual")
                writes = name.startswith(
                    (
                        "mcp__famachat__fc_post_",
                        "mcp__famachat__fc_patch_",
                        "mcp__famachat__fc_put_",
                        "mcp__famachat__fc_delete_",
                    )
                )
                if self.pending and (
                    writes
                    or name in {"kanban_show", "kanban_complete"}
                    or PATCH in self.pending.values()
                ):
                    return block("aguarde_a_ferramenta_em_andamento")
                if name in {READ, HISTORY} and name in self.pending.values():
                    return block("aguarde_a_leitura_em_andamento")
                if name != "kanban_show" and self.doc is None:
                    return block("leia_kanban_show_do_cartao_atual")
                if business and self.doc.get("test_mode", False) is not False:
                    return block("modo_sintetico_sem_MCP")
                if self.receipt and business and name not in {READ, PATCH, HISTORY}:
                    return block(
                        "confirmacao_envio_permite_apenas_leitura_cliente_historico_e_etapa"
                    )
                if name == "kanban_complete":
                    if not self.receipt:
                        return None
                    proof = self.receipt_verifier(self.task_id)
                    client = self.client
                    if not client or not self.fresh:
                        return block("leia_o_cliente_antes_de_concluir")
                    replied = self.reply_after_delivery(proof)
                    if (
                        client["status"] == "Sem Atendimento"
                        and client["brokerId"] == 35
                        and not replied
                    ):
                        return block("etapa_ainda_nao_atualizada_nao_declare_sucesso")
                    confirmed = (
                        self.patch_ok and client["status"] == self.patched_status
                    )
                    data = {
                        "status": "success",
                        "decision": "ETAPA_POS_ENVIO_CONFIRMADA"
                        if confirmed
                        else "ETAPA_POS_ENVIO_PRESERVADA",
                        "entities": {"client_id": client["id"]},
                        "response_ready": None,
                        "evidence": {
                            "status_readback": client["status"],
                            "delivery_confirmed": True,
                            "validator_version": VERSION,
                        },
                        "reason": "envio_confirmado_e_etapa_conferida"
                        if confirmed
                        else "etapa_ou_responsavel_atual_preservado",
                        "requested_next_action": "return_to_ceo",
                    }
                    if replied and not confirmed:
                        data["reason"] = (
                            "mensagem_posterior_ao_envio_preservar_para_atendimento_comercial"
                        )
                    output = {
                        "summary": data["decision"],
                        "result": data["decision"],
                        "metadata": data,
                        "artifacts": [],
                        "created_cards": [],
                    }
                    if tool_name == "tool_call":
                        return {
                            "action": "modify",
                            "args": {"name": name, "arguments": {**payload, **output}},
                        }
                    return {"action": "modify", "args": output}
                if name == PATCH:
                    body = payload.get("body", {})
                    if set(body) != {"status", "expectedStatus"}:
                        return block(
                            "PATCH_de_etapa_exige_somente_status_e_expectedStatus"
                        )
                    if not self.fresh or not self.client:
                        return block("leia_o_cliente_imediatamente_antes_do_PATCH")
                    client = self.client
                    if (
                        str(payload.get("id")) != str(client["id"])
                        or client["brokerId"] != 35
                    ):
                        return block("cliente_ou_responsavel_incompativel")
                    old, new = client["status"], body["status"]
                    if body["expectedStatus"] != old:
                        return block("expectedStatus_diverge_da_leitura")
                    if self.attempted:
                        return block(
                            "escrita_ja_tentada_na_execucao_nao_force_nem_repita"
                        )
                    allowed = (old, new) in {
                        ("Sem Atendimento", "Não Respondeu"),
                        ("Sem Atendimento", "Em Atendimento"),
                        ("Não Respondeu", "Em Atendimento"),
                    }
                    if not self.receipt and new == "Arquivado" and old in EARLY:
                        allowed = True
                    if not allowed:
                        return block("transicao_nao_autorizada_ou_retrocesso")
                    if new == "Não Respondeu":
                        if not self.receipt:
                            return block(
                                "aguarde_task_CONFIRMACAO_ENVIO_apos_envio_real_do_CEO"
                            )
                        proof = self.receipt_verifier(self.task_id)
                        if proof["client_id"] != client["id"]:
                            return block("recibo_de_outro_cliente")
                        if self.reply_after_delivery(proof):
                            return block(
                                "ha_mensagem_posterior_ao_envio_nao_marque_Nao_Respondeu"
                            )
                    if new == "Em Atendimento":
                        if self.receipt:
                            return block(
                                "preserve_etapa_e_devolva_ao_CEO_para_tratar_resposta_no_cartao_comercial"
                            )
                        upstream = self.doc.get("upstream_result", {})
                        initial = "LEAD_NOVO_CADASTRADO" in (
                            upstream.get("verdict"),
                            upstream.get("decision"),
                        )
                        if initial and not later_message(
                            self.messages, self.doc.get("pedido_exato")
                        ):
                            return block(
                                "anuncio_inicial_nao_comprova_resposta_posterior_preserve_etapa"
                            )
                    self.attempted = True
                    self.patched_status = new
                    self.fresh = False
                elif name == READ:
                    if str(payload.get("id")) != str(
                        self.doc.get("upstream_result", {}).get("client_id")
                    ):
                        return block("leia_o_cliente_do_cartao")
                    self.client = None
                    self.fresh = False
                elif business:
                    if writes:
                        self.fresh = False
                    if name == HISTORY:
                        self.messages = []
                elif name == "kanban_show":
                    self.doc = None
                    self.client = None
                    self.fresh = False
                if name in {"kanban_show", READ, PATCH, HISTORY}:
                    if not tool_call_id:
                        return block("identificador_de_chamada_ausente")
                    self.pending[tool_call_id] = name
                return None
        except Exception:
            return block("evidencia_ausente_ou_invalida_preserve_etapa")

    def after(
        self,
        *,
        tool_name,
        args,
        result,
        session_id="",
        tool_call_id="",
        status="ok",
        **_,
    ):
        try:
            name, payload = self.unwrap(tool_name, args)
            with self.lock:
                if (
                    session_id != self.session_id
                    or self.pending.get(tool_call_id) != name
                ):
                    return
                del self.pending[tool_call_id]
                if status != "ok":
                    return
                value = decode(result)
                if name == "skill_view":
                    if (
                        not payload.get("file_path")
                        and value.get("success") is True
                        and value.get("name") == RUNTIME_SKILL
                        and isinstance(value.get("content"), str)
                        and value["content"].strip()
                    ):
                        self.skill_loaded = True
                elif name == "kanban_show":
                    task = value["task"]
                    if (
                        task["id"] != self.task_id
                        or str(task.get("current_run_id")) != self.run_id
                    ):
                        raise ValueError("wrong_task")
                    doc = task_document(task["body"])
                    self.receipt = doc.get("operation") == "CONFIRMACAO_ENVIO"
                    if self.receipt:
                        proof = self.receipt_verifier(self.task_id)
                        if proof["client_id"] != doc["upstream_result"]["client_id"]:
                            raise ValueError("wrong_client")
                    self.doc = doc
                elif name == READ:
                    body = value.get("body")
                    if (
                        value.get("status") != 200
                        or value.get("truncated") is not False
                        or not isinstance(body, dict)
                    ):
                        return
                    if (
                        str(body.get("id")) != str(payload.get("id"))
                        or type(body.get("brokerId")) is not int
                        or not isinstance(body.get("status"), str)
                    ):
                        return
                    self.client = {k: body[k] for k in ("id", "brokerId", "status")}
                    self.fresh = True
                elif name == PATCH:
                    self.patch_ok = (
                        value.get("status") == 200 and value.get("truncated") is False
                    )
                elif name == HISTORY:
                    if (
                        value.get("history_scope") == "authorized_whatsapp_dm"
                        and value.get("truncated") is False
                    ):
                        self.messages = value.get("messages", [])
        except Exception:
            if name == "kanban_show":
                self.doc = None


def register(ctx):
    task, run = (
        os.environ.get("HERMES_KANBAN_TASK"),
        os.environ.get("HERMES_KANBAN_RUN_ID"),
    )
    if os.environ.get("HERMES_PROFILE") != "reno" or not task or not run:
        return
    guard = RenoGuard(task, run)
    ctx.register_hook("pre_tool_call", guard.before)
    ctx.register_hook("post_tool_call", guard.after)
