#!/usr/bin/env python3
"""Check installed code/config and native worker hooks without running business tools."""
import hashlib
import os
from pathlib import Path
import sys

import yaml


def main():
    home = Path("/root/.hermes/profiles/cadastro")
    source = Path(__file__).resolve().parent
    config = yaml.safe_load((home / "config.yaml").read_text())
    plugins = config.get("plugins", {})
    assert "fama-cadastro-guard" in plugins.get("enabled", []), "plugin_not_enabled"
    assert "fama-cadastro-guard" not in plugins.get("disabled", []), "plugin_disabled"
    for name in ("__init__.py", "plugin.yaml"):
        assert hashlib.sha256((source / name).read_bytes()).digest() == hashlib.sha256((home / "plugins/fama-cadastro-guard" / name).read_bytes()).digest(), "installed_code_differs"
    os.environ.update(HERMES_HOME=str(home), HERMES_PROFILE="cadastro", HERMES_KANBAN_TASK="t_activation_probe", HERMES_KANBAN_RUN_ID="1")
    sys.path.insert(0, "/usr/local/lib/hermes-agent")
    from hermes_cli import plugins as native
    manager = native.get_plugin_manager()
    manager.discover_and_load()
    hooks = ("pre_tool_call", "post_tool_call", "transform_tool_result")
    assert all(manager.has_hook(hook) for hook in hooks), "guard_hooks_missing"
    # Only resolve policy: no tool dispatcher, board write, MCP call or notification.
    message, _modified = native._dispatch_pre_tool_call_hooks("mcp__famachat__fc_post_clientes", {"body": {}}, session_id="activation_probe", tool_call_id="probe")
    assert message and message.startswith("Cadastro:"), "unguarded_post"
    print("PASS: Cadastro plugin matches source; enabled; 3 native hooks loaded; POST without evidence blocked. No business tools executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
