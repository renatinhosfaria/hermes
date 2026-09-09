"""Real Hermes plugin loader/hook dispatcher in a temporary profile; no business tools."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from test_guard import HISTORY, PATCH, READ, ROOT, http


class RuntimeTests(unittest.TestCase):
    def test_native_hooks_block_initial_ad_promotion_and_unconfirmed_send(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            shutil.copytree(
                ROOT,
                home / "plugins/fama-reno-delivery",
                ignore=shutil.ignore_patterns("tests", "__pycache__"),
            )
            (home / "config.yaml").write_text(
                "plugins:\n  enabled: [fama-reno-delivery]\nmcp_servers: {}\n"
            )
            profile = ROOT.parents[2] / "profiles/reno"
            shutil.copytree(profile / "skills", home / "skills")
            with patch.dict(
                os.environ,
                {
                    "HERMES_HOME": temp,
                    "HERMES_PROFILE": "reno",
                    "HERMES_KANBAN_TASK": "t_probe",
                    "HERMES_KANBAN_RUN_ID": "1",
                },
            ):
                sys.path.insert(0, "/usr/local/lib/hermes-agent")
                from hermes_constants import (
                    reset_hermes_home_override,
                    set_hermes_home_override,
                )

                token = set_hermes_home_override(home)
                try:
                    import model_tools
                    from hermes_cli import plugins
                    from hermes_cli.tools_config import _get_platform_tools
                    from toolsets import resolve_multiple_toolsets

                    config = yaml.safe_load((profile / "config.yaml").read_text())
                    toolsets = _get_platform_tools(config, "cli")
                    self.assertIn("skill_view", resolve_multiple_toolsets(toolsets))

                    manager = plugins.get_plugin_manager()
                    manager.discover_and_load()
                    self.assertTrue(manager.has_hook("pre_tool_call"))
                    self.assertTrue(manager.has_hook("post_tool_call"))
                    seq = 0

                    def dispatch(name, args, raw=None):
                        nonlocal seq
                        seq += 1
                        ids = dict(
                            session_id="probe",
                            tool_call_id=str(seq),
                            task_id="internal-tool-task",
                        )
                        blocked, modified = plugins._dispatch_pre_tool_call_hooks(
                            name, args, **ids
                        )
                        if blocked:
                            return blocked
                        final = args if modified is None else modified
                        if raw is not None:
                            model_tools._emit_post_tool_call_hook(
                                function_name=name,
                                function_args=final,
                                result=raw,
                                status="ok",
                                **ids,
                            )
                        return None

                    body = "upstream_result:\n  entities:\n    client_id: 101\n  verdict: LEAD_NOVO_CADASTRADO\npedido_exato: Vi o anúncio.\n"
                    self.assertIsNone(
                        dispatch(
                            "kanban_show",
                            {},
                            json.dumps(
                                {
                                    "task": {
                                        "id": "t_probe",
                                        "current_run_id": 1,
                                        "body": body,
                                    }
                                }
                            ),
                        )
                    )
                    self.assertIn("skill_view", dispatch(HISTORY, {}))
                    raw = model_tools.handle_function_call(
                        "skill_view",
                        {"name": "business-operations/fama-reno-runtime"},
                        task_id="internal-tool-task",
                        session_id="probe",
                        tool_call_id="native-skill",
                        enabled_tools=["skill_view"],
                    )
                    self.assertIn("# Workflow comercial do Reno", raw)
                    cached = model_tools.handle_function_call(
                        "skill_view",
                        {"name": "fama-reno-runtime"},
                        task_id="internal-tool-task",
                        session_id="probe",
                        tool_call_id="native-skill-cached",
                        enabled_tools=["skill_view"],
                    )
                    self.assertNotIn("# Workflow comercial do Reno", cached)
                    self.assertIsNone(
                        dispatch(
                            HISTORY,
                            {},
                            json.dumps(
                                {
                                    "messages": [
                                        {
                                            "speaker": "cliente",
                                            "ref": "m:1",
                                            "timestamp": 1,
                                            "text": "Vi o anúncio.",
                                        }
                                    ],
                                    "truncated": False,
                                    "history_scope": "authorized_whatsapp_dm",
                                }
                            ),
                        )
                    )
                    self.assertIsNone(
                        dispatch(
                            READ,
                            {"id": 101},
                            http(
                                {"id": 101, "brokerId": 35, "status": "Sem Atendimento"}
                            ),
                        )
                    )
                    for stage in ["Em Atendimento", "Não Respondeu"]:
                        self.assertTrue(
                            dispatch(
                                PATCH,
                                {
                                    "id": 101,
                                    "body": {
                                        "status": stage,
                                        "expectedStatus": "Sem Atendimento",
                                    },
                                },
                            ).startswith("Reno:")
                        )
                finally:
                    reset_hermes_home_override(token)
