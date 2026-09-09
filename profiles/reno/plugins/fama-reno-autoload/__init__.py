"""Attach the canonical Reno instructions using Hermes's per-turn context hook."""
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
SKILL_PATH = Path("skills/business-operations/fama-reno-runtime")
DOCUMENTS = (
    "SKILL.md",
    "references/conversa.md",
    "references/fontes.md",
    "references/crm.md",
    "references/agendamento.md",
)


def load_context(home: Path) -> str:
    # Same content guard as SOUL.md; do not preprocess/execute skill commands.
    from agent.prompt_builder import _scan_context_content

    root = (home / SKILL_PATH).resolve()
    sections = []
    for name in DOCUMENTS:
        path = (root / name).resolve()
        if not root.is_relative_to(home) or not path.is_relative_to(root):
            raise ValueError(f"Instruction path outside the Reno skill: {name}")
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError(f"Empty instruction file: {name}")
        content = _scan_context_content(content, f"fama-reno-runtime/{name}")
        if content.startswith("[BLOCKED:"):
            raise ValueError(f"Instruction content blocked: {name}")
        sections.append(f"<document path=\"{name}\">\n{content}\n</document>")
    return (
        '<fama-reno-runtime-autoload status="complete">\n'
        "Conteúdo local atualizado, carregado automaticamente para este turno. "
        "Considere lidos a skill e os quatro documentos abaixo. "
        "Aplique o procedimento comercial somente quando a tarefa estiver nesse escopo; "
        "o SOUL.md continua definindo identidade, permissões e limites.\n\n"
        + "\n\n".join(sections)
        + "\n</fama-reno-runtime-autoload>"
    )


def register(ctx):
    import hermes_constants

    # Capture registration scope; another profile must not receive Reno's bundle.
    home = Path(hermes_constants.get_hermes_home()).resolve()

    def before_turn(**kwargs):
        if Path(hermes_constants.get_hermes_home()).resolve() != home:
            return None
        try:
            return {"context": load_context(home)}
        except Exception as exc:
            logger.error("Reno runtime autoload failed: %s", exc)
            return {"context": (
                '<fama-reno-runtime-autoload status="error">\n'
                "Não foi possível carregar integralmente fama-reno-runtime e suas "
                "referências. Não execute operações comerciais com procedimentos "
                "indisponíveis. Use a leitura obrigatória e o tratamento de falha "
                "definidos na skill; em manutenção, diagnostique o carregador local.\n"
                "</fama-reno-runtime-autoload>"
            )}

    def before_request(request, **kwargs):
        # The installed Hermes injects hook context into string messages only.
        # Use the official request-rewrite API for multimodal user content.
        key = "messages" if "messages" in request else "input"
        rows = request.get(key)
        if not isinstance(rows, list):
            return None
        for index in range(len(rows) - 1, -1, -1):
            row = rows[index]
            if not isinstance(row, dict) or row.get("role") != "user":
                continue
            content = row.get("content")
            if not isinstance(content, list):
                return None  # Text already receives the per-turn hook context.
            result = before_turn()
            if result is None:
                return None
            context = result["context"]
            if any(isinstance(part, dict) and isinstance(part.get("text"), str)
                   and context in part["text"] for part in content):
                return None
            text_type = "text" if key == "messages" else "input_text"
            updated = dict(row, content=[*content, {"type": text_type, "text": context}])
            return {"request": {**request, key: [*rows[:index], updated, *rows[index + 1:]]},
                    "source": "fama-reno-autoload", "reason": "multimodal runtime instructions"}
        return None

    ctx.register_hook("pre_llm_call", before_turn)
    ctx.register_middleware("llm_request", before_request)
