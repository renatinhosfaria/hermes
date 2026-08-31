#!/usr/bin/env python3
"""Generate Reno's exact FamaChat allowlist from the live tool manifest.

Read-only by construction: it performs the MCP handshake and ``tools/list``
and never invokes a FamaChat tool. It exists because spec section 12.3 forbids
a production wildcard such as ``fc_get_*``, and the exact names may only come
from the server rather than from a guess.

The artifact is written only when every required scenario resolves to exactly
one selected tool. An ambiguous scenario is a hard failure: the operator picks
the name and records it in SELECTED_READ_TOOLS, so the choice is reviewable in
version control rather than made silently at runtime.

    python inventory_reno_famachat_tools.py --output reno-famachat-allowlist.json
    python inventory_reno_famachat_tools.py --list        # discovery only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import yaml

PROFILE = Path("/root/.hermes/profiles/reno")

REQUIRED_BRAIN_TOOLS = ["conversation_recent", "conversation_search"]
REQUIRED_WRITE_TOOLS = ["fc_post_appointments", "fc_post_clientes_by_id_notes"]

# Exact read tools, each selected from observed production use rather than
# guessed, and each justified. Selection evidence: Reno's own message history
# in profiles/reno/state.db, which records every MCP call by name. Every tool
# below was called on 2026-08-30, the most recent being the CTWA lead at 22:32.
SELECTED_READ_TOOLS = {
    # Client record and its notes: Reno receives the client id on the card.
    "fc_get_clientes_by_id": "GET /api/clientes/:id",
    "fc_get_clientes_by_id_notes": "GET /api/clientes/:id/notes",
    "fc_get_clientes_by_id_empreendimentos": "GET /api/clientes/:id/empreendimentos",
    # Development lookup: search by name, then read the chosen one.
    "fc_get_empreendimentos_buscar": "GET /api/empreendimentos/buscar",
    "fc_get_empreendimentos": "GET /api/empreendimentos",
    "fc_get_empreendimentos_by_id": "GET /api/empreendimentos/:id",
    "fc_get_empreendimentos_publico_by_id": "GET /api/empreendimentos/publico/:id",
    # Units of a development, to answer floor-plan and availability questions.
    "fc_get_apartamentos": "GET /api/apartamentos",
    "fc_get_apartamentos_empreendimento_by_id": (
        "GET /api/apartamentos/empreendimento/:id"
    ),
    "fc_get_apartamentos_publico_empreendimento_by_id": (
        "GET /api/apartamentos/publico/empreendimento/:id"
    ),
    # Appointment readback after booking, required by the Reno SOUL step 3.
    "fc_get_appointments_by_id": "GET /api/appointments/:id",
}

# Observed but deliberately excluded, with the reason each is refused. Recorded
# so the omission reads as a decision rather than an oversight.
EXCLUDED_READ_TOOLS = {
    "fc_get_clientes_all": "bulk dump of every client; Reno works one lead",
    "fc_get_clientes": "client search; Reno receives the exact id on its card",
    "fc_get_empreendimentos_page_buscar": (
        "duplicate of fc_get_empreendimentos_buscar"
    ),
}

FORBIDDEN_PREFIXES = ("fc_patch_", "fc_put_", "fc_delete_", "fc_del_", "db_")
_SECRET = re.compile(r"(Bearer\s+\S+|Authorization[^,}\s]*)", re.IGNORECASE)


def redact(text: object) -> str:
    """Never let a credential reach stdout, stderr, or the artifact."""
    return _SECRET.sub("<redacted>", str(text))


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_endpoint() -> tuple[str, dict[str, str]]:
    config = yaml.safe_load((PROFILE / "config.yaml").read_text(encoding="utf-8"))
    server = (config.get("mcp_servers") or {}).get("famachat") or {}
    url = server.get("url")
    if not url:
        raise RuntimeError("Reno's famachat MCP server has no url")

    environment = {**load_env(PROFILE / ".env"), **os.environ}
    headers: dict[str, str] = {}
    for name, raw in (server.get("headers") or {}).items():
        def substitute(match: re.Match[str]) -> str:
            key = match.group(1)
            value = environment.get(key)
            if not value:
                raise RuntimeError(f"secret {key} is not available")
            return value

        headers[name] = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", substitute, str(raw))
    return url, headers


async def fetch_tools(url: str, headers: dict[str, str]) -> list[dict]:
    from mcp import ClientSession
    from mcp.client.streamable_http import (
        create_mcp_http_client,
        streamable_http_client,
    )

    # Headers reach the transport through the HTTP client in this MCP version.
    async with create_mcp_http_client(headers=headers) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (
            read,
            write,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                return [
                    {
                        "name": tool.name,
                        "description": (tool.description or "").strip()[:200],
                    }
                    for tool in listed.tools
                ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--list", action="store_true", help="print candidates only")
    parser.add_argument("--filter", default="", help="substring filter for --list")
    args = parser.parse_args()

    try:
        url, headers = resolve_endpoint()
        tools = asyncio.run(fetch_tools(url, headers))
    except Exception as exc:  # noqa: BLE001 - CLI boundary, redacted
        print(f"FAIL: {type(exc).__name__}: {redact(exc)}", file=sys.stderr)
        return 1

    names = sorted(tool["name"] for tool in tools)
    print(f"tools/list devolveu {len(names)} ferramentas")

    if args.list:
        for tool in sorted(tools, key=lambda item: item["name"]):
            if args.filter and args.filter not in tool["name"]:
                continue
            print(f"  {tool['name']:44s} {tool['description'][:90]}")
        return 0

    available = set(names)
    errors: list[str] = []

    for selected, purpose in SELECTED_READ_TOOLS.items():
        if not purpose:
            errors.append(f"{selected}: seleção sem justificativa registrada")
        if selected not in available:
            errors.append(f"{selected} não existe no manifesto ao vivo")
    for excluded in EXCLUDED_READ_TOOLS:
        if excluded in SELECTED_READ_TOOLS:
            errors.append(f"{excluded} está simultaneamente selecionada e excluída")

    for tool in REQUIRED_WRITE_TOOLS:
        if tool not in available:
            errors.append(f"escrita obrigatória ausente no manifesto: {tool}")

    read_tools = sorted(SELECTED_READ_TOOLS)
    for tool in read_tools + REQUIRED_WRITE_TOOLS:
        if "*" in tool or tool.startswith(FORBIDDEN_PREFIXES):
            errors.append(f"ferramenta proibida selecionada: {tool}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    artifact = {
        "brain": REQUIRED_BRAIN_TOOLS,
        "famachat_read": read_tools,
        "famachat_write": sorted(REQUIRED_WRITE_TOOLS),
    }
    if args.output:
        args.output.write_text(
            json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"PASS: artefato escrito em {args.output}")
    else:
        print(json.dumps(artifact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
