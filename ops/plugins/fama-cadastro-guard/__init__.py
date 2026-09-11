"""Cadastro policy on observed tool results. No network, business DB reads or PII logs."""

import hashlib
import json
import os
import re
import threading
import unicodedata
from pathlib import Path

BRAIN = "mcp__brain__conversation_phone"
CONTEXT = "mcp__brain__conversation_context"
SEARCH = "mcp__famachat__fc_get_clientes"
POST = "mcp__famachat__fc_post_clientes"
READ = "mcp__famachat__fc_get_clientes_by_id"
DEV_SEARCH = "mcp__famachat__fc_get_empreendimentos_buscar"
DEV_READ = "mcp__famachat__fc_get_empreendimentos_by_id"
BUSINESS = {BRAIN, CONTEXT, SEARCH, POST, READ, DEV_SEARCH, DEV_READ}
WATCHED = BUSINESS | {"kanban_show", "kanban_complete"}
VERSION = "1.1.0"


def national_phone(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9+().\s-]+", value):
        raise ValueError("invalid_phone")
    digits = re.sub(r"[^0-9]", "", value)
    # A national DDD can itself be 55. Strip country only at international length.
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    if len(digits) not in (10, 11) or digits[0] == "0":
        raise ValueError("invalid_phone")
    return digits


def phones_match(left, right):
    try:
        left, right = national_phone(left), national_phone(right)
    except ValueError:
        return False
    if left == right:
        return True
    if len(left) < len(right):
        left, right = right, left
    return len(left) == 11 and len(right) == 10 and left[2] == "9" and left[:2] + left[3:] == right


def crm_phone(value):
    """Return FamaChat national format, restoring a legacy mobile ninth digit."""
    digits = national_phone(value)
    if len(digits) == 10 and digits[2] in "6789":
        return digits[:2] + "9" + digits[2:]
    return digits


def decode_result(raw):
    """Decode native MCP result and the Hermes external-data envelope, never arbitrary prose."""
    value = raw
    for _ in range(5):
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("<untrusted_tool_result "):
                # The adapter places the JSON payload on its own line after its warning.
                lines = text.splitlines()
                start = next(i for i, line in enumerate(lines) if line.startswith(("{", "[")))
                text = "\n".join(lines[start:])
                value, _end = json.JSONDecoder().raw_decode(text)
            else:
                value, end = json.JSONDecoder().raw_decode(text)
                tail = text[end:].strip()
                if tail and not (tail.startswith("<cadastro_validation_page>") and tail.endswith("</cadastro_validation_page>")):
                    raise ValueError("unexpected_response_suffix")
        elif isinstance(value, dict) and set(value) == {"result"}:
            value = value["result"]
        else:
            break
    if not isinstance(value, dict):
        raise ValueError("invalid_response")
    return value


def http_body(raw, expected=200, body_type=dict):
    value = decode_result(raw)
    if value.get("status") != expected or value.get("truncated") is not False:
        raise ValueError("incomplete_response")
    body = value.get("body")
    if not isinstance(body, body_type):
        raise ValueError("invalid_body")
    return body


def valid_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def evaluate(phone, records):
    """One source for eligibility and the three distinct counters."""
    national_phone(phone)
    matches, reno = [], []
    for row in records:
        if not isinstance(row, dict) or not valid_id(row.get("id")):
            raise ValueError("invalid_candidate")
        national_phone(row.get("phone"))
        if not valid_id(row.get("brokerId")) or not isinstance(row.get("status"), str) or not re.fullmatch(r"[^\W\d_][^\d\r\n]{0,79}", row["status"]):
            raise ValueError("invalid_candidate")
        if phones_match(phone, row["phone"]):
            matches.append(row)
            if row["brokerId"] == 35 and row["status"] != "Arquivado":
                reno.append(row)
    return {"candidates_returned": len(records), "normalized_matches": len(matches), "active_broker35_matches": len(reno)}, reno


def block(reason):
    return {"action": "block", "message": "Cadastro: " + reason}


def normalized_name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise ValueError("invalid_name")
    folded = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(re.findall(r"[^\W_]+", "".join(c for c in folded if not unicodedata.combining(c))))


def name_in(name, text):
    return bool(name) and (" " + name + " ") in (" " + text + " ")


class CtwaDevelopment:
    """Conservative attribution: every event must resolve to the same unique ID.

    Only observed, complete CRM reads establish IDs. The model chooses search
    terms, but cannot select among homonyms or invent an ID in the POST.
    """

    def __init__(self, document):
        self.names = []
        self.searches = {}
        self.verified = None
        self.read_failed = False
        try:
            events = document["contexto"]["ctwa_attributions"]
            if not isinstance(events, list) or not 0 < len(events) <= 100:
                raise ValueError("missing_attribution")
            seen = set()
            for event in events:
                if set(event) != {"event_id", "source_app", "meta_attribution"}:
                    raise ValueError("invalid_event")
                eid = event["event_id"]
                if not isinstance(eid, str) or not re.fullmatch(r"waevt_[A-Za-z0-9_-]{1,128}", eid) or eid in seen:
                    raise ValueError("invalid_event")
                seen.add(eid)
                meta = event["meta_attribution"]
                if not isinstance(meta, dict) or set(meta) != {"status", "ad_id", "ad_name", "campaign_id", "campaign_name"} or meta["status"] != "confirmed":
                    raise ValueError("unconfirmed_attribution")
                if not all(isinstance(meta[k], str) and re.fullmatch(r"[0-9]{1,64}", meta[k]) for k in ("ad_id", "campaign_id")):
                    raise ValueError("invalid_attribution_id")
                self.names.append(tuple(normalized_name(meta[k]) for k in ("ad_name", "campaign_name")))
        except (KeyError, TypeError, ValueError):
            self.names = []

    def begin_search(self, payload):
        query = payload.get("query", {})
        if set(payload) != {"query"} or set(query) != {"termo"}:
            raise ValueError("use_query_termo")
        term = normalized_name(query["termo"])
        if not 3 <= len(term) <= 160 or not any(name_in(term, text) for pair in self.names for text in pair):
            raise ValueError("search_not_in_attribution")
        self.searches[term] = None
        self.verified, self.read_failed = None, False

    def observe_search(self, payload, raw):
        rows = http_body(raw, body_type=list)
        if len(rows) > 1000:
            raise ValueError("too_many_candidates")
        candidates = {}
        term = normalized_name(payload["query"]["termo"])
        for row in rows:
            if not isinstance(row, dict) or not valid_id(row.get("id")) or row["id"] in candidates:
                raise ValueError("invalid_development")
            name = normalized_name(row.get("nomeEmpreendimento"))
            # The endpoint is a name substring search. A result outside that
            # contract is not evidence that this search was applied.
            if len(name) < 3 or term not in name:
                raise ValueError("invalid_development_name")
            candidates[row["id"]] = name
        self.searches[term] = candidates

    def candidate(self):
        if not self.names:
            return None, "no_confirmed_attribution"
        if not self.searches:
            return None, "not_searched"
        if any(rows is None for rows in self.searches.values()):
            return None, "lookup_unavailable"
        selected = set()
        for texts in self.names:
            matches = set()
            for text in texts:
                relevant = False
                text_matches = set()
                for term, rows in self.searches.items():
                    if not name_in(term, text):
                        continue
                    relevant = True
                    for did, name in rows.items():
                        if name_in(name, text):
                            text_matches.add((did, name))
                if not relevant:
                    return None, "not_searched"
                if not text_matches:
                    return None, "no_match"
                matches.update(text_matches)
            if len(matches) > 1:
                return None, "ambiguous"
            if not matches:
                return None, "no_match"
            selected.update(matches)
        if len(selected) != 1:
            return None, "ambiguous"
        return next(iter(selected)), "unverified"

    def begin_read(self, payload):
        candidate, _reason = self.candidate()
        if not candidate or set(payload) != {"id"} or isinstance(payload["id"], bool) or str(payload["id"]) != str(candidate[0]):
            raise ValueError("development_read_requires_unique_candidate")
        self.verified, self.read_failed = None, True

    def observe_read(self, raw):
        row = http_body(raw)
        candidate, _reason = self.candidate()
        if not candidate or not valid_id(row.get("id")) or (row["id"], normalized_name(row.get("nomeEmpreendimento"))) != candidate:
            raise ValueError("development_read_mismatch")
        self.verified, self.read_failed = candidate[0], False

    def resolution(self):
        if self.verified is not None:
            return self.verified, "verified"
        if self.read_failed:
            return None, "lookup_unavailable"
        return None, self.candidate()[1]


class CadastroGuard:
    """A fresh instance per worker. Hooks serialize mutations and bind one real session."""

    def __init__(self, task_id, run_id):
        self.task_id, self.run_id = task_id, str(run_id)
        self.lock = threading.RLock()
        self.session_id = None
        self.task_seen = False
        self.task_body_hash = None
        self.synthetic = False
        self.fixture = None
        self.phone = None
        self.pages = {}
        self.page_size = None
        self.search_complete = False
        self.pending = None
        self.post_attempted = False
        self.created_id = None
        self.readback_confirmed = False
        self.reads = 0
        self.error = None
        self.development = CtwaDevelopment({})
        self.requested_development = None

    @staticmethod
    def unwrap(tool_name, args):
        if tool_name == "tool_call":
            return args["name"], args.get("arguments", {})
        return tool_name, args

    def evidence(self):
        if not self.phone or not self.search_complete:
            raise ValueError("consulta_incompleta")
        records = [row for page in sorted(self.pages) for row in self.pages[page]]
        # Repeated IDs across pages can signal an unstable result set. Do not prove absence.
        if len({row.get("id") for row in records}) != len(records):
            raise ValueError("paginas_inconsistentes")
        return evaluate(self.phone, records)

    def before(self, *, tool_name, args, session_id="", tool_call_id="", **_):
        try:
            name, payload = self.unwrap(tool_name, args)
            if name not in WATCHED:
                return None
            with self.lock:
                if not session_id or (self.session_id and self.session_id != session_id):
                    return block("sessao_incompativel")
                self.session_id = session_id
                if payload.get("task_id", self.task_id) != self.task_id or payload.get("board"):
                    return block("use_o_cartao_e_board_do_worker")
                if self.pending:
                    return block("aguarde_a_ferramenta_em_andamento")
                if name == "kanban_complete":
                    if not self.task_seen:
                        return block("leia_kanban_show_do_cartao_atual_primeiro")
                    result = self.completion()
                    # Core merges modified arguments; explicitly clear alternate output channels.
                    result.update(result=result["summary"], artifacts=[], created_cards=[])
                    if tool_name == "tool_call":
                        return {"action": "modify", "args": {"name": name, "arguments": {**payload, **result}}}
                    return {"action": "modify", "args": result}
                if name != "kanban_show" and not self.task_seen:
                    return block("leia_kanban_show_do_cartao_atual_primeiro")
                if name == "kanban_show":
                    self.task_seen = False
                if name in BUSINESS and self.synthetic:
                    return block("modo_sintetico_nao_chama_MCP")
                if name in {DEV_SEARCH, DEV_READ}:
                    _counts, reno = self.evidence()
                    if reno or self.post_attempted:
                        return block("empreendimento_somente_para_novo_cliente_antes_do_POST")
                    if name == DEV_SEARCH:
                        self.development.begin_search(payload)
                    else:
                        self.development.begin_read(payload)
                if name == CONTEXT:
                    if payload or self.post_attempted:
                        return block("conversation_context_exige_argumentos_vazios_antes_do_POST")
                if name == BRAIN:
                    if payload or self.post_attempted:
                        return block("conversation_phone_exige_argumentos_vazios_antes_do_POST")
                    self.phone = None
                    self.pages, self.search_complete = {}, False
                    self.development.searches = {}
                    self.development.verified = None
                    self.development.read_failed = False
                if name == SEARCH:
                    if not self.phone or self.post_attempted:
                        return block("resolva_o_telefone_no_Brain_antes_da_busca")
                    query = payload.get("query", {})
                    if query.get("search") != national_phone(self.phone)[-4:] or set(query) - {"search", "page", "pageSize"}:
                        return block("busque_apenas_o_sufixo_de_quatro_digitos_com_paginacao")
                    page = query.get("page", 1)
                    if type(page) is not int or page < 1:
                        return block("pagina_invalida")
                    if page == 1:
                        self.pages, self.page_size, self.search_complete = {}, None, False
                    elif page != len(self.pages) + 1 or self.search_complete:
                        return block("consulte_as_paginas_em_ordem")
                    self.search_complete = False
                if name == POST:
                    if self.post_attempted:
                        return block("POST_ja_tentado_na_execucao_nao_repita")
                    _counts, reno = self.evidence()
                    if reno:
                        return block("telefone_ja_possui_cliente_Reno_nao_arquivado")
                    body = payload.get("body", {})
                    did, _resolution = self.development.resolution()
                    fields = {"phone", "fullName", "brokerId", "source"} | ({"idEmpreendimento"} if did is not None else set())
                    if set(payload) != {"body"} or set(body) != fields or body["phone"] != crm_phone(self.phone) or type(body["brokerId"]) is not int or body["brokerId"] != 35 or body["source"] != "Facebook Ads" or not isinstance(body["fullName"], str) or not body["fullName"].strip():
                        return block("POST_exige_telefone_exato_do_Brain_nome_broker35_source_sem_status")
                    if did is not None and (body["idEmpreendimento"] != [did] or not all(valid_id(v) for v in body["idEmpreendimento"])):
                        return block("POST_exige_array_com_empreendimento_verificado")
                    self.requested_development = did
                    # Reserve before dispatch: timeout/error must never authorize another POST.
                    self.post_attempted = True
                if name == READ:
                    if not self.created_id or str(payload.get("id")) != str(self.created_id) or self.reads >= 3:
                        return block("readback_exige_id_do_POST_e_no_maximo_tres_leituras")
                    self.reads += 1
                    self.readback_confirmed = False
                if not tool_call_id:
                    return block("identificador_de_chamada_ausente")
                self.pending = (name, tool_call_id)
                return None
        except Exception:
            return block("evidencia_ausente_ou_invalida_nao_execute_a_operacao")

    def after(self, *, tool_name, args, result, session_id="", tool_call_id="", status="ok", **_):
        try:
            name, payload = self.unwrap(tool_name, args)
            with self.lock:
                if session_id != self.session_id or self.pending != (name, tool_call_id):
                    return
                self.pending = None
                if status != "ok":
                    self.error = "ferramenta_falhou"
                    return
                if name == "kanban_show":
                    task = decode_result(result)["task"]
                    if task["id"] != self.task_id or str(task.get("current_run_id")) != self.run_id:
                        raise ValueError("wrong_task")
                    body = task.get("body")
                    if not isinstance(body, str) or not body.strip():
                        raise ValueError("missing_task_body")
                    import yaml
                    try:
                        node = yaml.compose(body)
                        if isinstance(node, yaml.MappingNode) and sum(key.value == "test_mode" for key, _value in node.value) > 1:
                            raise ValueError("duplicate_test_mode")
                        document = yaml.safe_load(body)
                    except yaml.YAMLError:
                        # Historical real tasks contain prose with unquoted colons.
                        # Ambiguous test-mode declarations must never fall back to real mode.
                        explicit_false = re.findall(r'''(?m)^(?:test_mode|"test_mode"|'test_mode')\s*:\s*(?:false|False|FALSE)[ \t]*(?:#[^\n]*)?$''', body)
                        if "test_mode" in body and not (len(explicit_false) == 1 and body.count("test_mode") == 1):
                            raise ValueError("ambiguous_test_mode")
                        document = {}
                    mode = document.get("test_mode", False) if isinstance(document, dict) else False
                    if type(mode) is not bool or (not isinstance(document, dict) and "test_mode" in body):
                        raise ValueError("invalid_test_mode")
                    self.synthetic = mode
                    body_hash = hashlib.sha256(body.encode()).hexdigest()
                    if not self.post_attempted and body_hash != self.task_body_hash:
                        self.development = CtwaDevelopment(document)
                    self.task_body_hash = body_hash
                    if self.synthetic:
                        self.fixture = document.get("fixture")
                        if isinstance(self.fixture, dict) and "cadastro" in self.fixture:
                            self.fixture = self.fixture["cadastro"]
                    self.task_seen = True
                elif name == BRAIN:
                    data = decode_result(result)
                    if data.get("status") != "ok":
                        raise ValueError("brain_unavailable")
                    national_phone(data.get("phone"))
                    self.phone = data["phone"]
                elif name == CONTEXT:
                    data = decode_result(result)
                    if data.get("status") != "ok" or not isinstance(data.get("events"), list):
                        raise ValueError("brain_context_unavailable")
                    events = []
                    for event in data["events"]:
                        if not isinstance(event, dict) or event.get("transport_kind") != "ctwa_candidate":
                            continue
                        meta = event.get("meta_attribution")
                        if meta is None:
                            continue
                        events.append({
                            "event_id": event.get("event_id"),
                            "source_app": event.get("source_app"),
                            "meta_attribution": meta,
                        })
                    self.development = CtwaDevelopment({"contexto": {"ctwa_attributions": events}})
                elif name == SEARCH:
                    body = http_body(result)
                    rows, pagination = body["data"], body["pagination"]
                    page, size = pagination["page"], pagination["pageSize"]
                    query = payload.get("query", {})
                    if not isinstance(rows, list) or type(page) is not int or page != query.get("page", 1) or type(size) is not int or size < 1 or len(rows) > size or (self.page_size and size != self.page_size) or ("pageSize" in query and query["pageSize"] != size):
                        raise ValueError("invalid_pagination")
                    evaluate(self.phone, rows)
                    self.page_size, self.pages[page] = size, rows
                    self.search_complete = len(rows) < size
                elif name == POST:
                    row = http_body(result, 201)
                    if not valid_id(row.get("id")):
                        raise ValueError("invalid_created_id")
                    self.created_id = row["id"]
                elif name == DEV_SEARCH:
                    self.development.observe_search(payload, result)
                elif name == DEV_READ:
                    self.development.observe_read(result)
                elif name == READ:
                    row = http_body(result)
                    self.readback_confirmed = (type(row.get("id")) is int and row["id"] == self.created_id and type(row.get("brokerId")) is int and row["brokerId"] == 35 and row.get("status") == "Sem Atendimento" and phones_match(self.phone, row.get("phone")))
                    if self.requested_development is not None:
                        ids = row.get("idEmpreendimento")
                        self.readback_confirmed = self.readback_confirmed and ids == [self.requested_development] and all(valid_id(v) for v in ids)
                    elif row.get("idEmpreendimento") not in (None, []):
                        self.readback_confirmed = False
                self.error = None
        except Exception:
            # Core observer hooks fail open. Keep dependent operations closed in our own state.
            with self.lock:
                self.error = "resposta_invalida_ou_incompleta"

    def completion(self):
        if self.synthetic:
            if not isinstance(self.fixture, dict) or self.fixture.get("decision") not in {"existing_client", "new_lead", "indeterminate"}:
                raise ValueError("invalid_fixture")
            entities = self.fixture.get("entities", {})
            if not isinstance(entities, dict) or any(key not in {"client_id", "lead_id"} or not isinstance(value, str) or not re.fullmatch(r"(?:client|lead|synthetic|test)[-_][a-zA-Z0-9_-]{1,80}", value) for key, value in entities.items()):
                raise ValueError("invalid_synthetic_entities")
            decision = self.fixture["decision"]
            return {"summary": "TEST_MODE " + decision, "metadata": {"status": "completed", "decision": decision, "entities": entities, "evidence": {"test_mode": True, "validator_version": VERSION}, "reason": "fixture_interna", "response_ready": None, "requested_next_action": "return_to_ceo"}}
        counts, reno = {}, []
        reason = "consulta_incompleta"
        try:
            counts, reno = self.evidence()
            reason = "multiplos_clientes_Reno" if len(reno) > 1 else "criacao_ou_readback_nao_confirmado"
        except (ValueError, TypeError):
            pass
        decision, entity = "INCONCLUSIVO", self.created_id
        if len(reno) == 1 and not self.post_attempted:
            decision, entity = "JA_E_CLIENTE", reno[0]["id"]
            reason = "telefone_completo_corresponde_a_cliente_Reno_nao_arquivado"
        elif counts and not reno and self.readback_confirmed:
            decision = "LEAD_NOVO_CADASTRADO"
            reason = "ausencia_de_cliente_Reno_e_criacao_confirmadas"
        summary = decision
        if decision == "INCONCLUSIVO":
            summary += " " + reason
        if entity:
            summary += " cliente_id=" + str(entity)
        if decision == "JA_E_CLIENTE":
            summary += " status=" + reno[0]["status"]
        summary += "\n" + (f"Candidatos: {counts['candidates_returned']}; telefones correspondentes: {counts['normalized_matches']}; clientes Reno nao arquivados: {counts['active_broker35_matches']}." if counts else "Consulta completa ainda nao comprovada.")
        entities = {"client_id": entity} if entity else {}
        if self.readback_confirmed and self.requested_development is not None:
            entities["empreendimento_id"] = self.requested_development
        readback_fields = ["id", "phone", "brokerId", "status"] if self.readback_confirmed else []
        if self.readback_confirmed and self.requested_development is not None:
            readback_fields.append("idEmpreendimento")
        return {"summary": summary, "metadata": {"status": "completed", "decision": decision, "entities": entities, "evidence": {**counts, "response_complete": bool(counts), "post_attempted": self.post_attempted, "readback_confirmed": self.readback_confirmed, "readback_fields": readback_fields, "empreendimento_resolution": self.development.resolution()[1] if not reno else "existing_client", "validator_version": VERSION}, "reason": reason, "response_ready": None, "requested_next_action": "return_to_ceo"}}

    def transform(self, *, tool_name, args, result, **_):
        """Advisory only; enforcement and handoff never depend on the model reading this."""
        try:
            name, _payload = self.unwrap(tool_name, args)
            if name != SEARCH:
                return None
            with self.lock:
                body = http_body(result)
                counts, _reno = evaluate(self.phone, body["data"])
                return str(result) + "\n<cadastro_validation_page>" + json.dumps(counts) + "</cadastro_validation_page>"
        except Exception:
            return None


def block_business_outside_worker(*, tool_name, args, **_):
    """Keep administrative tools available without unguarded CRM access."""
    try:
        name, _payload = CadastroGuard.unwrap(tool_name, args)
    except (KeyError, TypeError):
        return block("chamada_indireta_invalida")
    if name in BUSINESS:
        return block("operacao_de_negocio_exige_worker_Kanban_com_tarefa_e_execucao")
    return None


def register(ctx):
    # Preserve the installed 1.0.1 containment for native profile invocations.
    profile = os.environ.get("HERMES_PROFILE") or Path(os.environ.get("HERMES_HOME", "")).name
    if profile != "cadastro":
        return
    task, run = os.environ.get("HERMES_KANBAN_TASK"), os.environ.get("HERMES_KANBAN_RUN_ID")
    if not task or not run:
        ctx.register_hook("pre_tool_call", block_business_outside_worker)
        return
    guard = CadastroGuard(task, run)
    ctx.register_hook("pre_tool_call", guard.before)
    ctx.register_hook("post_tool_call", guard.after)
    ctx.register_hook("transform_tool_result", guard.transform)
