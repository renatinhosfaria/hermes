#!/usr/local/lib/hermes-agent/venv/bin/python
from __future__ import annotations

import argparse
import stat
import unicodedata
import subprocess
import sys
from pathlib import Path

import yaml

from hermes_cli.tools_config import _get_platform_tools, enabled_mcp_server_names
from hermes_constants import reset_hermes_home_override, set_hermes_home_override

ROOT = Path("/root/.hermes")
EXPECTED_NAMED = {"porteiro", "cadastro", "famaagent", "reno", "dev"}
EXPECTED_ALL = ["default", "porteiro", "cadastro", "famaagent", "reno", "dev"]
OPERATOR_ID = "8564576789"

EXPECTED_PLATFORM_TOOLSETS = {
    "default": {
        "telegram": ["hermes-telegram", "kanban"],
        "cli": ["hermes-cli"],
    },
    "porteiro": {
        "telegram": ["clarify", "no_mcp"],
        "cli": ["clarify", "brain", "famachat"],
    },
    "cadastro": {
        "telegram": ["clarify", "no_mcp"],
        "cli": ["clarify", "brain", "famachat"],
    },
    "famaagent": {
        "telegram": ["clarify", "no_mcp"],
        "cli": ["clarify", "brain"],
    },
    "reno": {
        "telegram": ["clarify", "no_mcp"],
        "cli": ["clarify", "brain", "famachat"],
    },
    "dev": {
        "telegram": [
            "terminal",
            "file",
            "skills",
            "todo",
            "memory",
            "session_search",
            "clarify",
            "cronjob",
        ],
        "cli": [
            "terminal",
            "file",
            "skills",
            "todo",
            "memory",
            "session_search",
            "clarify",
            "cronjob",
        ],
    },
}

EXPECTED_HOME_CHANNELS = {
    "default": {"chat_id": "-1004374717222", "name": "New CEO"},
    "porteiro": {"chat_id": "-1004476890625", "name": "Porteiro"},
    "cadastro": {"chat_id": "-1003746861842", "name": "Cadastro"},
    "famaagent": {"chat_id": "-1003696068287", "name": "FamaAgent"},
    "reno": {"chat_id": "-1003859524818", "name": "Reno"},
    "dev": {"chat_id": "-1004365034436", "name": "Dev"},
}

GATEWAY_UNITS = {
    "default": "hermes-gateway.service",
    "porteiro": "hermes-gateway-porteiro.service",
    "cadastro": "hermes-gateway-cadastro.service",
    "famaagent": "hermes-gateway-famaagent.service",
    "reno": "hermes-gateway-reno.service",
    "dev": "hermes-gateway-dev.service",
}

KNOWN_MCP_SERVERS = {"brain", "famachat"}
EXPECTED_CONFIGURED_MCP = {
    "default": set(),
    "porteiro": {"brain", "famachat"},
    "cadastro": {"brain", "famachat"},
    "famaagent": {"brain"},
    "reno": {"brain", "famachat"},
    "dev": set(),
}
# Allowlists exatas da secao 12 da spec. Um servidor MCP sem entrada aqui e
# erro: nenhum profile pode expor um servidor sem contrato declarado.
EXPECTED_MCP_TOOLS = {
    ("porteiro", "brain"): ["conversation_phone"],
    ("porteiro", "famachat"): ["fc_get_users"],
    ("cadastro", "brain"): ["conversation_phone"],
    ("cadastro", "famachat"): [
        "fc_get_clientes",
        "fc_get_clientes_by_id",
        "fc_post_clientes",
    ],
    ("reno", "brain"): ["conversation_recent", "conversation_search"],
    ("reno", "famachat"): [
        "fc_get_apartamentos",
        "fc_get_apartamentos_empreendimento_by_id",
        "fc_get_apartamentos_publico_empreendimento_by_id",
        "fc_get_appointments_by_id",
        "fc_get_clientes_by_id",
        "fc_get_clientes_by_id_empreendimentos",
        "fc_get_clientes_by_id_notes",
        "fc_get_empreendimentos",
        "fc_get_empreendimentos_buscar",
        "fc_get_empreendimentos_by_id",
        "fc_get_empreendimentos_publico_by_id",
        "fc_patch_clientes_by_id",
        "fc_post_appointments",
        "fc_post_clientes_by_id_notes",
    ],
    ("famaagent", "brain"): ["conversation_recent", "conversation_search"],
}
# Vazio: todo servidor MCP exposto tem contrato declarado. Uma entrada aqui
# marca allowlist ainda nao gerada, reportada como pendencia e nao como erro,
# para o verificador seguir util enquanto a geracao nao roda.
PENDING_MCP_ALLOWLIST: set[tuple[str, str]] = set()
FORBIDDEN_TOOL_PREFIXES = ("fc_patch_", "fc_put_", "fc_delete_", "fc_del_", "db_")

# A Amendment 2 entregou as transicoes de etapa ao Reno, entao exatamente uma
# ferramenta sob prefixo proibido esta autorizada, para exatamente um profile.
# A excecao e nominal de proposito: afrouxar o prefixo autorizaria fc_patch_*
# inteiro, e uma excecao que vira prefixo deixa de ser excecao.
AUTHORIZED_FORBIDDEN_PREFIX_TOOLS = frozenset(
    {("reno", "fc_patch_clientes_by_id")}
)

# Trechos que precisam existir no prompt de cada profile. Sao contratos de
# comportamento: nao da para provar por teste automatico como codigo, entao o
# minimo e garantir que o texto que os define nao suma sem ninguem notar.
REQUIRED_PROMPT_MARKERS = {
    "default": [
        ("SOUL.md", "conversation_context()", "capability atual do CEO"),
        ("SOUL.md", "nao e identidade", "display name como dado nao confiavel"),
        ("SOUL.md", "context_resolution_failed", "politica de falha do Brain"),
        (
            "SOUL.md",
            "deixe a chave fora",
            "sem identificador tecnico a chave e omitida, nao improvisada",
        ),
        (
            "skills/business-operations/fama-ceo-runtime/SKILL.md",
            "deixe a chave fora",
            "skill alinhada a omissao da chave",
        ),
    ],
    "reno": [
        ("SOUL.md", "expectedStatus", "toda escrita de etapa carrega o predicado"),
        ("SOUL.md", "So para frente", "transicoes apenas progressivas"),
        ("SOUL.md", "uma vez, e exatamente uma", "conversation_recent unico no primeiro cartao"),
        ("SOUL.md", "LEAD_NOVO_CADASTRADO", "gatilho do primeiro cartao"),
        (
            "skills/business-operations/fama-reno-runtime/SKILL.md",
            "conversation_recent",
            "skill alinhada a regra de primeiro cartao",
        ),
    ],
    "cadastro": [
        ("SOUL.md", "fc_get_clientes_by_id", "readback por leitura independente"),
        ("SOUL.md", "Sem Atendimento", "status exigido no readback"),
        ("SOUL.md", "no maximo uma vez", "POST unico"),
        (
            "skills/business-operations/fama-cadastro-runtime/SKILL.md",
            "fc_get_clientes_by_id",
            "skill alinhada ao readback do SOUL",
        ),
    ],
}
FORBIDDEN_PROMPT_MARKERS = {
    "default": [
        ("SOUL.md", "conversation_phone()", "capability que o CEO nao possui mais"),
        (
            "skills/business-operations/fama-ceo-runtime/SKILL.md",
            "conversation_phone()",
            "capability que o CEO nao possui mais",
        ),
        (
            "skills/business-operations/fama-ceo-runtime/SKILL.md",
            "<canal>:<chat_id>:<message_id>",
            "formato de idempotencia superado",
        ),
        # A Amendment 2 removeu o wa_turn_id e o reconciliador que lia essas
        # chaves. Enquanto a regra existiu sem o dado que a alimentava, o CEO
        # escreveu `whatsapp-context-unavailable:<uuid>:porteiro` num cartao
        # real em 31/08. So aparece no prompt agora para ser negada, e as
        # entradas abaixo garantem que ela nao volte como instrucao.
        (
            "SOUL.md",
            "A `idempotency_key` dos cartoes de WhatsApp e",
            "formato de idempotencia removido pela Amendment 2",
        ),
        (
            "skills/business-operations/fama-ceo-runtime/SKILL.md",
            "use `idempotency_key` no formato",
            "formato de idempotencia removido pela Amendment 2",
        ),
        ("SOUL.md", "turn.wa_turn_id", "contrato de turno que nao existe mais"),
    ],
    "porteiro": [
        ("SOUL.md", "277 ferramentas", "contagem de ferramentas desatualizada"),
        ("SOUL.md", "db_query", "nome de ferramenta bloqueada citado no prompt"),
    ],
    "reno": [
        ("SOUL.md", "comeca com fc_get_", "wildcard de ferramenta proibido pela spec 12.3"),
    ],
    "cadastro": [
        ("SOUL.md", "277 ferramentas", "contagem de ferramentas desatualizada"),
        ("SOUL.md", "exatamente duas", "contagem que contradiz o readback"),
        (
            "skills/business-operations/fama-cadastro-runtime/SKILL.md",
            "brokerId == 35 no retorno",
            "readback antigo pela resposta do POST",
        ),
    ],
}

EXPECTED_MCP_EXPOSURE = {
    "default": {"cli": set(), "telegram": set(), "whatsapp": set()},
    "porteiro": {"cli": {"brain", "famachat"}, "telegram": set()},
    "cadastro": {"cli": {"brain", "famachat"}, "telegram": set()},
    "famaagent": {"cli": {"brain"}, "telegram": set()},
    "reno": {"cli": {"brain", "famachat"}, "telegram": set()},
    "dev": {"cli": set(), "telegram": set()},
}


def _normalize(text: str) -> str:
    """Compare prompt text without tripping on accents or spacing."""
    folded = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


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


def resolve_platform(config: dict, profile_name: str, platform: str) -> set[str]:
    """Use the same default-true platform resolver as the gateway."""
    token = set_hermes_home_override(home(profile_name))
    try:
        return set(
            _get_platform_tools(
                config,
                platform,
                include_default_mcp_servers=True,
            )
        )
    finally:
        reset_hermes_home_override(token)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("core", "full"))
    args = parser.parse_args()
    errors: list[str] = []
    mcp_report: list[str] = []
    pending: list[str] = []

    named = {p.name for p in (ROOT / "profiles").iterdir() if p.is_dir()}
    check(named == EXPECTED_NAMED, f"Profiles nomeados: {sorted(named)}", errors)
    check(not (ROOT / "profiles" / "ceo").exists(), "profiles/ceo não pode existir", errors)

    configs: dict[str, dict] = {}
    observed_home_ids: list[str] = []

    for name in EXPECTED_ALL:
        profile_home = home(name)
        for required in ("config.yaml", "SOUL.md", "profile.yaml"):
            check((profile_home / required).is_file(), f"{name}: falta {required}", errors)
        if not (profile_home / "config.yaml").is_file():
            continue

        config = read_yaml(profile_home / "config.yaml")
        configs[name] = config

        meta_path = profile_home / "profile.yaml"
        if meta_path.is_file():
            meta = read_yaml(meta_path)
            bot = ((meta.get("ui_meta") or {}).get("hermes-bots") or {})
            check(bool(meta.get("display_name")), f"{name}: display_name ausente", errors)
            check(bool(meta.get("description")), f"{name}: description ausente", errors)
            check(bool(bot.get("title")), f"{name}: ui_meta.hermes-bots.title ausente", errors)

        actual_platform_toolsets = config.get("platform_toolsets")
        check(
            isinstance(actual_platform_toolsets, dict),
            f"{name}: platform_toolsets ausente",
            errors,
        )
        if isinstance(actual_platform_toolsets, dict):
            for platform, expected_toolsets in EXPECTED_PLATFORM_TOOLSETS[name].items():
                actual_toolsets = actual_platform_toolsets.get(platform)
                check(
                    actual_toolsets == expected_toolsets,
                    f"{name}: platform_toolsets.{platform} incorreto: "
                    f"{actual_toolsets!r}",
                    errors,
                )

        telegram = config.get("telegram") or {}
        check(
            str(telegram.get("allow_from")) == OPERATOR_ID,
            f"{name}: telegram.allow_from incorreto",
            errors,
        )

        telegram_platform = ((config.get("platforms") or {}).get("telegram") or {})
        check(
            telegram_platform.get("enabled") is True,
            f"{name}: plataforma Telegram não habilitada",
            errors,
        )
        channel = telegram_platform.get("home_channel") or {}
        expected_channel = EXPECTED_HOME_CHANNELS[name]
        channel_id = str(channel.get("chat_id", ""))
        observed_home_ids.append(channel_id)
        check(channel.get("platform") == "telegram", f"{name}: home_channel não é Telegram", errors)
        check(channel_id == expected_channel["chat_id"], f"{name}: home_channel.chat_id incorreto", errors)
        check(channel.get("name") == expected_channel["name"], f"{name}: home_channel.name incorreto", errors)
        check(str(channel.get("thread_id")) == "1", f"{name}: home_channel.thread_id incorreto", errors)
        check(str(channel.get("user_id")) == OPERATOR_ID, f"{name}: home_channel.user_id incorreto", errors)

        if name != "default":
            check(
                (config.get("kanban") or {}).get("dispatch_in_gateway") is False,
                f"{name}: kanban.dispatch_in_gateway deve ser false",
                errors,
            )
            check(
                str(telegram.get("group_allowed_chats")) == expected_channel["chat_id"],
                f"{name}: telegram.group_allowed_chats não aponta para o grupo próprio",
                errors,
            )

        unit = GATEWAY_UNITS[name]
        check(systemctl("ActiveState", unit) == "active", f"{name}: gateway inativo", errors)
        check(systemctl("UnitFileState", unit) == "enabled", f"{name}: gateway não habilitado", errors)

        configured_mcp = set(enabled_mcp_server_names(config))
        check(
            configured_mcp == EXPECTED_CONFIGURED_MCP[name],
            f"{name}: mcp_servers habilitados incorretos: {sorted(configured_mcp)}",
            errors,
        )
        for relative, needle, purpose in REQUIRED_PROMPT_MARKERS.get(name, ()):
            document = profile_home / relative
            body = (
                document.read_text(encoding="utf-8", errors="replace")
                if document.is_file()
                else ""
            )
            check(
                _normalize(needle) in _normalize(body),
                f"{name}/{relative}: falta contrato '{purpose}'",
                errors,
            )
        for relative, needle, purpose in FORBIDDEN_PROMPT_MARKERS.get(name, ()):
            document = profile_home / relative
            body = (
                document.read_text(encoding="utf-8", errors="replace")
                if document.is_file()
                else ""
            )
            check(
                _normalize(needle) not in _normalize(body),
                f"{name}/{relative}: contrato superado presente '{purpose}'",
                errors,
            )

        for server, server_config in sorted((config.get("mcp_servers") or {}).items()):
            server_config = server_config or {}
            include = (server_config.get("tools") or {}).get("include")
            if (name, server) in PENDING_MCP_ALLOWLIST:
                pending.append(
                    f"{name}/{server}: allowlist FamaChat pendente "
                    f"(gerar do tools/list ao vivo)"
                )
                continue
            expected_tools = EXPECTED_MCP_TOOLS.get((name, server))
            check(
                expected_tools is not None,
                f"{name}/{server}: servidor MCP sem contrato declarado",
                errors,
            )
            if expected_tools is None:
                continue
            check(
                include == expected_tools,
                f"{name}/{server}: tools.include {include!r}, "
                f"esperado {expected_tools!r}",
                errors,
            )
            check(
                server_config.get("resources") is False,
                f"{name}/{server}: resources deve ser false",
                errors,
            )
            check(
                server_config.get("prompts") is False,
                f"{name}/{server}: prompts deve ser false",
                errors,
            )
            for tool in include or []:
                check(
                    not tool.startswith(FORBIDDEN_TOOL_PREFIXES)
                    or (name, tool) in AUTHORIZED_FORBIDDEN_PREFIX_TOOLS,
                    f"{name}/{server}: ferramenta proibida no allowlist: {tool}",
                    errors,
                )

        for platform, expected_present in EXPECTED_MCP_EXPOSURE[name].items():
            resolved = resolve_platform(config, name, platform)
            actual_present = resolved & KNOWN_MCP_SERVERS
            actual_absent = KNOWN_MCP_SERVERS - actual_present
            expected_absent = KNOWN_MCP_SERVERS - expected_present
            check(
                actual_present == expected_present,
                f"{name}/{platform}: MCP presentes {sorted(actual_present)}, "
                f"esperado {sorted(expected_present)}",
                errors,
            )
            check(
                actual_absent == expected_absent,
                f"{name}/{platform}: MCP ausentes {sorted(actual_absent)}, "
                f"esperado {sorted(expected_absent)}",
                errors,
            )
            mcp_report.append(
                f"MCP {name}/{platform}: presentes={sorted(actual_present)} "
                f"ausentes={sorted(actual_absent)}"
            )

    check(
        len(observed_home_ids) == len(set(observed_home_ids)) == len(EXPECTED_ALL),
        "home_channel Telegram não é exclusivo por profile",
        errors,
    )

    root_config = configs.get("default") or read_yaml(ROOT / "config.yaml")
    kanban = root_config.get("kanban") or {}
    check(kanban.get("orchestrator_profile") == "default", "orchestrator_profile != default", errors)
    check(kanban.get("dispatch_in_gateway") is True, "dispatch_in_gateway != true", errors)
    check(kanban.get("auto_decompose") is False, "auto_decompose != false", errors)

    if args.mode == "full":
        root_env = read_env(ROOT / ".env")
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

    for line in mcp_report:
        print(line)
    for line in pending:
        print(f"PENDENTE: {line}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: equipe Hermes validada em modo {args.mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
