"""Native plugin discovery/dispatch in a temporary profile; no network/CRM writes."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_guard import ROOT, PHONE, BRAIN, SEARCH, POST, READ, client, response


class RuntimeTests(unittest.TestCase):
    def test_ctwa_through_native_wrapped_calls_and_untrusted_mcp_envelopes(self):
        from test_ctwa import DEV_SEARCH, DEV_READ, event, development
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            shutil.copytree(ROOT, home / "plugins/fama-cadastro-guard", ignore=shutil.ignore_patterns("tests", "__pycache__"))
            (home / "config.yaml").write_text("plugins:\n  enabled: [fama-cadastro-guard]\nmcp_servers: {}\n", encoding="utf-8")
            with patch.dict(os.environ, {"HERMES_HOME": temp, "HERMES_PROFILE": "cadastro", "HERMES_KANBAN_TASK": "t_synthetic", "HERMES_KANBAN_RUN_ID": "1"}):
                sys.path.insert(0, "/usr/local/lib/hermes-agent")
                from hermes_constants import set_hermes_home_override, reset_hermes_home_override
                token = set_hermes_home_override(home)
                try:
                    import model_tools
                    from hermes_cli import plugins
                    plugins.get_plugin_manager().discover_and_load()
                    seq = 0

                    def dispatch(name, args, raw=None):
                        nonlocal seq
                        seq += 1
                        ids = dict(session_id="probe_ctwa", tool_call_id=str(seq), task_id="internal-tool-task")
                        wrapped = {"name": name, "arguments": args}
                        blocked, modified = plugins._dispatch_pre_tool_call_hooks("tool_call", wrapped, **ids)
                        if blocked:
                            return {"blocked": blocked}
                        final = modified or wrapped
                        if raw is None:
                            return final
                        if name.startswith("mcp__famachat__"):
                            raw = '<untrusted_tool_result source="fixture">\nExternal data\n' + raw + '\n</untrusted_tool_result>'
                        result = model_tools._apply_transform_tool_result_hook("tool_call", final, raw, 0, model_tools._CallIds(**ids))
                        model_tools._emit_post_tool_call_hook(function_name="tool_call", function_args=final, result=result, status="ok", **ids)
                        return result

                    self.assertIn("blocked", dispatch(DEV_SEARCH, {"query": {"termo": "Residencial Aurora"}}))
                    body = json.dumps({"test_mode": False, "contexto": {"ctwa_attributions": [event()]}})
                    dispatch("kanban_show", {}, json.dumps({"task": {"id": "t_synthetic", "current_run_id": 1, "body": body}}))
                    dispatch(BRAIN, {}, json.dumps({"status": "ok", "phone": PHONE}))
                    dispatch(SEARCH, {"query": {"search": "4567"}}, response({"data": [], "pagination": {"page": 1, "pageSize": 100, "total": 0}}))
                    dispatch(DEV_SEARCH, {"query": {"termo": "Residencial Aurora"}}, response([development()]))
                    dispatch(DEV_READ, {"id": 123}, response(development()))
                    post = {"body": {"phone": PHONE, "fullName": "Synthetic", "brokerId": 35, "source": "Facebook Ads", "idEmpreendimento": [123]}}
                    self.assertNotIsInstance(dispatch(POST, post, response(client(201), 201)), dict)
                    dispatch(READ, {"id": 201}, response({**client(201), "idEmpreendimento": [123]}))
                    result = dispatch("kanban_complete", {"summary": "wrong", "metadata": {}})["arguments"]["metadata"]
                    self.assertEqual(result["decision"], "LEAD_NOVO_CADASTRADO")
                    self.assertEqual(result["entities"], {"client_id": 201, "empreendimento_id": 123})
                finally:
                    reset_hermes_home_override(token)

    def test_native_dispatch_blocks_write_and_normalizes_handoff_in_agent_hook_order(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            shutil.copytree(ROOT, home / "plugins/fama-cadastro-guard", ignore=shutil.ignore_patterns("tests", "__pycache__"))
            (home / "config.yaml").write_text("plugins:\n  enabled: [fama-cadastro-guard]\nmcp_servers: {}\n", encoding="utf-8")
            with patch.dict(os.environ, {"HERMES_HOME": temp, "HERMES_PROFILE": "cadastro", "HERMES_KANBAN_TASK": "t_synthetic", "HERMES_KANBAN_RUN_ID": "1"}):
                sys.path.insert(0, "/usr/local/lib/hermes-agent")
                from hermes_constants import set_hermes_home_override, reset_hermes_home_override
                token = set_hermes_home_override(home)
                try:
                    import model_tools
                    from hermes_cli import plugins
                    manager = plugins.get_plugin_manager()
                    manager.discover_and_load()
                    self.assertTrue(manager.has_hook("pre_tool_call"))
                    seq = 0

                    def dispatch(name, args, raw=None):
                        nonlocal seq
                        seq += 1
                        ids = dict(session_id="probe_session", tool_call_id=str(seq), task_id="internal-tool-task")
                        blocked, modified = plugins._dispatch_pre_tool_call_hooks(name, args, **ids)
                        final_args = args if modified is None else modified
                        if blocked:
                            return {"blocked": blocked}
                        if raw is None:
                            return final_args
                        # The agent executor suppresses the inner post hook: transformation
                        # runs first, then the outer executor emits one terminal observer.
                        result = model_tools._apply_transform_tool_result_hook(name, final_args, raw, 0, model_tools._CallIds(**ids))
                        model_tools._emit_post_tool_call_hook(function_name=name, function_args=final_args, result=result, status="ok", **ids)
                        return result

                    self.assertIn("blocked", dispatch(POST, {"body": {}}))
                    dispatch("kanban_show", {}, json.dumps({"task": {"id": "t_synthetic", "current_run_id": 1, "body": "upstream_decision: NAO_CORRETOR\n"}}))
                    dispatch(BRAIN, {}, json.dumps({"result": json.dumps({"status": "ok", "phone": PHONE})}))
                    dispatch(SEARCH, {"query": {"search": "4567"}}, response({"data": [client()], "pagination": {"page": 1, "pageSize": 100, "total": 1}}))
                    self.assertIn("blocked", dispatch(POST, {"body": {"phone": PHONE, "fullName": "Synthetic", "brokerId": 35, "source": "Facebook Ads"}}))
                    result = dispatch("kanban_complete", {"summary": "LEAD_NOVO_CADASTRADO cliente_id=999", "result": "Invented", "metadata": {"decision": "LEAD_NOVO_CADASTRADO", "evidence": {"normalized_matches": 999}}})
                    self.assertEqual(result["metadata"]["decision"], "JA_E_CLIENTE")
                    self.assertEqual(result["metadata"]["evidence"]["normalized_matches"], 1)
                    self.assertEqual(result["metadata"]["entities"]["client_id"], 101)
                    self.assertEqual(result["summary"], result["result"])
                finally:
                    reset_hermes_home_override(token)
