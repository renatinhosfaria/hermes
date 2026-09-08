"""Verify installed Fama extension/config and native hooks; no business tool execution."""

import hashlib
import json
import os
import sys
from pathlib import Path

import yaml


def main():
    home = Path("/root/.hermes/profiles/reno")
    source = Path(__file__).resolve().parent
    config = yaml.safe_load((home / "config.yaml").read_text())
    enabled = config.get("plugins", {}).get("enabled", [])
    disabled = config.get("plugins", {}).get("disabled", [])
    assert "fama-reno-delivery" in enabled and "fama-reno-delivery" not in disabled, (
        "plugin_not_enabled"
    )
    for name in ("__init__.py", "delivery.py", "plugin.yaml"):
        assert (
            hashlib.sha256((source / name).read_bytes()).digest()
            == hashlib.sha256(
                (home / "plugins/fama-reno-delivery" / name).read_bytes()
            ).digest()
        ), "installed_code_differs"
    os.environ.update(
        HERMES_HOME=str(home),
        HERMES_PROFILE="reno",
        HERMES_KANBAN_TASK="t_activation_probe",
        HERMES_KANBAN_RUN_ID="1",
    )
    sys.path.insert(0, "/usr/local/lib/hermes-agent")
    from hermes_cli import plugins
    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import (
        _emit_post_tool_call_hook,
        get_tool_definitions,
        handle_function_call,
    )
    from toolsets import resolve_multiple_toolsets

    assert "skill_view" in resolve_multiple_toolsets(
        _get_platform_tools(config, "cli")
    ), "skill_tool_unavailable"
    schemas = get_tool_definitions(
        enabled_toolsets=["skills"], quiet_mode=True, skip_tool_search_assembly=True
    )
    assert any(t["function"]["name"] == "skill_view" for t in schemas), (
        "skill_schema_missing"
    )

    manager = plugins.get_plugin_manager()
    manager.discover_and_load()
    assert all(manager.has_hook(h) for h in ("pre_tool_call", "post_tool_call")), (
        "guard_hooks_missing"
    )
    message, _ = plugins._dispatch_pre_tool_call_hooks(
        "mcp__famachat__fc_patch_clientes_by_id",
        {
            "id": 101,
            "body": {"status": "Não Respondeu", "expectedStatus": "Sem Atendimento"},
        },
        session_id="activation_probe",
        tool_call_id="probe",
    )
    assert message and message.startswith("Reno:"), "unguarded_patch"
    assert "skill_view" in message, "missing_skill_not_blocked"
    ids = dict(session_id="activation_probe", tool_call_id="show_probe")
    message, _ = plugins._dispatch_pre_tool_call_hooks("kanban_show", {}, **ids)
    assert not message, "cannot_read_task"
    _emit_post_tool_call_hook(
        function_name="kanban_show",
        function_args={},
        status="ok",
        **ids,
        result=json.dumps(
            {
                "task": {
                    "id": "t_activation_probe",
                    "current_run_id": 1,
                    "body": "upstream_result:\n  client_id: 101\ntest_mode: false\n",
                }
            }
        ),
    )
    result = handle_function_call(
        "skill_view",
        {"name": "fama-reno-runtime"},
        task_id="activation_probe",
        session_id="activation_probe",
        tool_call_id="skill_probe",
        enabled_tools=["skill_view"],
    )
    assert "# Workflow comercial do Reno" in result, "runtime_skill_not_read"
    message, _ = plugins._dispatch_pre_tool_call_hooks(
        "mcp__brain__conversation_recent",
        {},
        session_id="activation_probe",
        tool_call_id="history_probe",
    )
    assert not message, "attendance_still_blocked_after_skill"
    print(
        "PASS: installed Reno code matches source; native skill_view available and runtime skill read; "
        "attendance blocked before reading and released after reading. No business tools executed."
    )


if __name__ == "__main__":
    main()
