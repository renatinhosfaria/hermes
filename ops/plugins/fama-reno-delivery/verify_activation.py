"""Verify installed Fama extension/config and native hooks; no business tool execution."""

import hashlib
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
    print(
        "PASS: installed Reno code matches source; 2 native hooks loaded; unproven PATCH blocked. No business tools executed."
    )


if __name__ == "__main__":
    main()
