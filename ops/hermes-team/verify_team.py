#!/usr/local/lib/hermes-agent/venv/bin/python
from __future__ import annotations

import argparse
import stat
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path("/root/.hermes")
EXPECTED_NAMED = {"porteiro", "cadastro", "famaagent", "reno", "dev"}
EXPECTED_ALL = ["default", "porteiro", "cadastro", "famaagent", "reno", "dev"]
MINIMAL_WORKERS = {"porteiro", "cadastro", "famaagent", "reno"}
MESSAGING_PREFIXES = ("TELEGRAM_", "WHATSAPP_", "DISCORD_", "SLACK_", "SIGNAL_")
MODEL = "gpt-5.6-luna-900k"


def home(name: str) -> Path:
    return ROOT if name == "default" else ROOT / "profiles" / name


def read_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"YAML não é objeto: {path}")
    return data


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def systemctl(prop: str, unit: str) -> str:
    result = subprocess.run(
        ["systemctl", "show", unit, f"--property={prop}", "--value"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("core", "full"))
    args = parser.parse_args()
    errors: list[str] = []

    named = {p.name for p in (ROOT / "profiles").iterdir() if p.is_dir()}
    check(named == EXPECTED_NAMED, f"Profiles nomeados: {sorted(named)}", errors)
    check(not (ROOT / "profiles" / "ceo").exists(), "profiles/ceo não pode existir", errors)

    for name in EXPECTED_ALL:
        profile_home = home(name)
        for required in ("config.yaml", "SOUL.md", "profile.yaml"):
            check((profile_home / required).is_file(), f"{name}: falta {required}", errors)
        if not (profile_home / "config.yaml").is_file():
            continue
        config = read_yaml(profile_home / "config.yaml")
        model = config.get("model") or {}
        check(model.get("default") == MODEL, f"{name}: modelo incorreto", errors)
        check(model.get("provider") == "openai-codex", f"{name}: provider incorreto", errors)

        meta_path = profile_home / "profile.yaml"
        if meta_path.is_file():
            meta = read_yaml(meta_path)
            bot = ((meta.get("ui_meta") or {}).get("hermes-bots") or {})
            check(bool(meta.get("display_name")), f"{name}: display_name ausente", errors)
            check(bool(meta.get("description")), f"{name}: description ausente", errors)
            check(bool(bot.get("title")), f"{name}: ui_meta.hermes-bots.title ausente", errors)

        if name in MINIMAL_WORKERS:
            check(config.get("toolsets") == [], f"{name}: toolsets deve ser []", errors)
        if name == "dev":
            check(config.get("toolsets") == ["hermes-cli"], "dev: toolsets inesperado", errors)
        if name != "default":
            enabled_platforms = [
                key
                for key, value in (config.get("platforms") or {}).items()
                if isinstance(value, dict) and value.get("enabled") is True
            ]
            check(not enabled_platforms, f"{name}: plataformas habilitadas {enabled_platforms}", errors)
            env_path = profile_home / ".env"
            if env_path.is_file():
                env = read_env(env_path)
                leaked = sorted(key for key in env if key.startswith(MESSAGING_PREFIXES))
                check(not leaked, f"{name}: chaves de mensageria presentes {leaked}", errors)

    root_config = read_yaml(ROOT / "config.yaml")
    kanban = root_config.get("kanban") or {}
    check(kanban.get("orchestrator_profile") == "default", "orchestrator_profile != default", errors)
    check(kanban.get("dispatch_in_gateway") is True, "dispatch_in_gateway != true", errors)
    check(kanban.get("auto_decompose") is False, "auto_decompose != false", errors)

    check(systemctl("ActiveState", "hermes-gateway.service") == "active", "gateway default inativo", errors)
    check(systemctl("UnitFileState", "hermes-gateway.service") == "enabled", "gateway default não habilitado", errors)
    check(systemctl("ActiveState", "hermes-gateway-dev.service") != "active", "gateway dev ainda ativo", errors)
    check(systemctl("UnitFileState", "hermes-gateway-dev.service") != "enabled", "gateway dev ainda habilitado", errors)

    root_env = read_env(ROOT / ".env")
    check(root_env.get("TELEGRAM_ALLOWED_USERS") == "8564576789", "allowlist Telegram incorreta", errors)

    if args.mode == "full":
        check(root_env.get("WHATSAPP_ENABLED", "").lower() == "true", "WhatsApp não habilitado", errors)
        check(root_env.get("WHATSAPP_MODE") == "bot", "WHATSAPP_MODE != bot", errors)
        check(root_env.get("WHATSAPP_ALLOWED_USERS") == "*", "WhatsApp não aberto por wildcard", errors)
        wa = root_config.get("whatsapp") or {}
        check(wa.get("dm_policy") == "open", "dm_policy != open", errors)
        check(wa.get("group_policy") == "disabled", "group_policy != disabled", errors)
        session = ROOT / "platforms" / "whatsapp" / "session"
        check((session / "creds.json").is_file(), "creds.json do Baileys ausente", errors)
        if session.is_dir():
            mode = stat.S_IMODE(session.stat().st_mode)
            check(mode == 0o700, f"modo da sessão WhatsApp é {oct(mode)}", errors)
        check(
            systemctl("ActiveState", "hermes-whatsapp-healthcheck.timer") == "active",
            "timer de health do WhatsApp inativo",
            errors,
        )
        check(
            systemctl("UnitFileState", "hermes-whatsapp-healthcheck.timer") == "enabled",
            "timer de health do WhatsApp não habilitado",
            errors,
        )

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: equipe Hermes validada em modo {args.mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
