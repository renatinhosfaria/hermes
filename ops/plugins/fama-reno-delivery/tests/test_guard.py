import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "reno_guard", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
)
guard = importlib.util.module_from_spec(spec)
import sys

sys.modules[spec.name] = guard
spec.loader.exec_module(guard)

READ = "mcp__famachat__fc_get_clientes_by_id"
PATCH = "mcp__famachat__fc_patch_clientes_by_id"
HISTORY = "mcp__brain__conversation_recent"


def http(body, status=200):
    return json.dumps(
        {"result": json.dumps({"status": status, "truncated": False, "body": body})}
    )


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.proof = {"client_id": 101, "delivered_at": 300}
        self.g = guard.RenoGuard("t_test", "1", receipt_verifier=lambda _: self.proof)
        self.seq = 0

    def call(self, name, args, result):
        self.seq += 1
        kw = dict(
            tool_name=name, args=args, session_id="s1", tool_call_id=str(self.seq)
        )
        verdict = self.g.before(**kw)
        if verdict and verdict.get("action") == "block":
            return verdict
        self.g.after(**kw, result=result, status="ok")
        return verdict

    def identify(self, receipt=False):
        body = "upstream_result:\n  client_id: 101\n  verdict: LEAD_NOVO_CADASTRADO\npedido_exato: Vi o anúncio, quero informações.\ntest_mode: false\n"
        if receipt:
            body += "operation: CONFIRMACAO_ENVIO\n"
        return self.call(
            "kanban_show",
            {},
            json.dumps({"task": {"id": "t_test", "current_run_id": 1, "body": body}}),
        )

    def read(self, status="Sem Atendimento", broker=35, cid=101):
        return self.call(
            READ, {"id": 101}, http({"id": cid, "brokerId": broker, "status": status})
        )

    def patch(self, status="Não Respondeu", expected="Sem Atendimento"):
        return self.g.before(
            tool_name=PATCH,
            args={"id": 101, "body": {"status": status, "expectedStatus": expected}},
            session_id="s1",
            tool_call_id="patch",
        )

    def finish(self):
        return self.g.before(
            tool_name="kanban_complete",
            args={
                "task_id": "t_test",
                "summary": "inventado",
                "metadata": {"response_ready": "não enviar", "decision": "inventado"},
            },
            session_id="s1",
            tool_call_id="finish",
        )

    def history(self, extra=()):
        rows = [
            {
                "ref": "m:1",
                "speaker": "cliente",
                "timestamp": 100,
                "text": "Vi o anúncio, quero informações.",
            },
            {"ref": "m:2", "speaker": "fama", "timestamp": 110, "text": "[SILENT]"},
        ] + list(extra)
        self.call(
            HISTORY,
            {},
            json.dumps(
                {
                    "result": json.dumps(
                        {
                            "messages": rows,
                            "truncated": False,
                            "history_scope": "authorized_whatsapp_dm",
                        }
                    )
                }
            ),
        )

    def test_normal_response_cannot_set_nao_respondeu_before_send(self):
        self.identify()
        self.read()
        self.assertEqual(self.patch()["action"], "block")

    def test_initial_ad_and_internal_silence_cannot_authorize_em_atendimento(self):
        self.identify()
        self.history()
        self.read()
        self.assertEqual(self.patch("Em Atendimento")["action"], "block")

    def test_independent_later_message_can_authorize_initial_em_atendimento(self):
        self.identify()
        self.history(
            [
                {
                    "ref": "m:3",
                    "speaker": "cliente",
                    "timestamp": 120,
                    "text": "Quero visitar no sábado.",
                }
            ]
        )
        self.read()
        self.assertIsNone(self.patch("Em Atendimento"))

    def test_duplicate_ad_or_older_message_does_not_authorize_initial_em_atendimento(
        self,
    ):
        for text, stamp in [
            ("Vi o anúncio, quero informações.", 120),
            ("Mensagem antiga", 90),
        ]:
            self.setUp()
            self.identify()
            self.history(
                [{"ref": "m:3", "speaker": "cliente", "timestamp": stamp, "text": text}]
            )
            self.read()
            self.assertEqual(self.patch("Em Atendimento")["action"], "block")

    def test_real_receipt_and_fresh_owned_client_read_authorize_patch(self):
        self.identify(True)
        self.read()
        self.assertIsNone(self.patch())

    def test_receipt_cannot_downgrade_or_mutate_another_broker(self):
        for stage, broker in [
            ("Em Atendimento", 35),
            ("Arquivado", 35),
            ("Sem Atendimento", 14),
        ]:
            self.setUp()
            self.identify(True)
            self.read(stage, broker)
            self.assertEqual(self.patch(expected=stage)["action"], "block")

    def test_mismatched_expected_status_and_missing_read_are_blocked(self):
        self.identify(True)
        self.assertEqual(self.patch()["action"], "block")
        self.read()
        self.assertEqual(self.patch(expected="Não Respondeu")["action"], "block")

    def test_receipt_revalidated_immediately_before_mutation(self):
        self.identify(True)
        self.read()
        self.g.receipt_verifier = lambda _: (_ for _ in ()).throw(
            ValueError("human_pause")
        )
        self.assertEqual(self.patch()["action"], "block")

    def test_receipt_requires_independent_readback_before_success_and_clears_external_payload(
        self,
    ):
        self.identify(True)
        self.read()
        self.assertEqual(self.finish()["action"], "block")
        self.call(
            PATCH,
            {
                "id": 101,
                "body": {
                    "status": "Não Respondeu",
                    "expectedStatus": "Sem Atendimento",
                },
            },
            http({"id": 101, "status": "Não Respondeu"}),
        )
        self.assertEqual(self.finish()["action"], "block")
        self.read("Não Respondeu")
        result = self.finish()["args"]
        self.assertIsNone(result["metadata"]["response_ready"])
        self.assertEqual(result["metadata"]["decision"], "ETAPA_POS_ENVIO_CONFIRMADA")
        self.assertEqual(result["artifacts"], [])

    def test_existing_advanced_status_is_successful_silent_noop(self):
        self.identify(True)
        self.read("Em Atendimento")
        result = self.finish()["args"]
        self.assertEqual(result["metadata"]["decision"], "ETAPA_POS_ENVIO_PRESERVADA")
        self.assertIsNone(result["metadata"]["response_ready"])

    def test_409_cannot_be_forced_and_readback_preserves_human_change(self):
        self.identify(True)
        self.read()
        self.call(
            PATCH,
            {
                "id": 101,
                "body": {
                    "status": "Não Respondeu",
                    "expectedStatus": "Sem Atendimento",
                },
            },
            http({}, 409),
        )
        self.read("Sem Atendimento")
        self.assertEqual(self.patch()["action"], "block")
        self.assertEqual(self.finish()["action"], "block")
        self.read("Em Atendimento")
        self.assertEqual(
            self.finish()["args"]["metadata"]["decision"], "ETAPA_POS_ENVIO_PRESERVADA"
        )

    def test_receipt_has_no_other_business_writes(self):
        self.identify(True)
        result = self.g.before(
            tool_name="mcp__famachat__fc_post_appointments",
            args={},
            session_id="s1",
            tool_call_id="visit",
        )
        self.assertEqual(result["action"], "block")

    def test_client_reply_after_delivery_preserves_stage_without_marking_no_response(
        self,
    ):
        self.identify(True)
        self.history(
            [
                {
                    "ref": "m:4",
                    "speaker": "cliente",
                    "timestamp": 310,
                    "text": "Pode marcar a visita.",
                }
            ]
        )
        self.read()
        self.assertEqual(self.patch()["action"], "block")
        result = self.finish()["args"]["metadata"]
        self.assertEqual(result["decision"], "ETAPA_POS_ENVIO_PRESERVADA")
        self.assertEqual(
            result["reason"],
            "mensagem_posterior_ao_envio_preservar_para_atendimento_comercial",
        )

    def test_new_lead_decision_alias_also_requires_later_message(self):
        self.identify()
        self.g.doc["upstream_result"]["decision"] = "LEAD_NOVO_CADASTRADO"
        self.g.doc["upstream_result"].pop("verdict")
        self.history()
        self.read()
        self.assertEqual((self.patch("Em Atendimento") or {}).get("action"), "block")

    def test_independent_reads_can_run_in_parallel_but_write_waits_for_evidence(self):
        self.identify()
        kw = dict(session_id="s1")
        self.assertIsNone(
            self.g.before(tool_name=READ, args={"id": 101}, tool_call_id="read", **kw)
        )
        self.assertIsNone(
            self.g.before(tool_name=HISTORY, args={}, tool_call_id="history", **kw)
        )
        self.assertIsNone(
            self.g.before(
                tool_name="mcp__famachat__fc_get_empreendimentos",
                args={},
                tool_call_id="property",
                **kw,
            )
        )
        self.assertEqual(self.patch("Em Atendimento")["action"], "block")
        self.g.after(
            tool_name=READ,
            args={"id": 101},
            tool_call_id="read",
            result=http({"id": 101, "brokerId": 35, "status": "Sem Atendimento"}),
            status="ok",
            **kw,
        )
        self.g.after(
            tool_name=HISTORY,
            args={},
            tool_call_id="history",
            result=json.dumps(
                {
                    "messages": [],
                    "truncated": False,
                    "history_scope": "authorized_whatsapp_dm",
                }
            ),
            status="ok",
            **kw,
        )
        self.assertIn("anuncio_inicial", self.patch("Em Atendimento")["message"])

    def test_tool_call_wrapper_and_changed_worker_session_cannot_bypass(self):
        self.identify()
        self.read()
        args = {
            "id": 101,
            "body": {"status": "Não Respondeu", "expectedStatus": "Sem Atendimento"},
        }
        result = self.g.before(
            tool_name="tool_call",
            args={"name": PATCH, "arguments": args},
            session_id="s1",
            tool_call_id="wrapped",
        )
        self.assertEqual(result["action"], "block")
        self.assertEqual(
            self.g.before(
                tool_name=PATCH, args=args, session_id="other", tool_call_id="x"
            )["action"],
            "block",
        )


if __name__ == "__main__":
    unittest.main()
