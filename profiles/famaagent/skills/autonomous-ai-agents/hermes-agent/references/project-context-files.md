# Project Context Files

Use this reference when organizing or diagnosing Hermes instruction files.
Official reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files
Local implementation: `agent/prompt_builder.py` and `agent/subdirectory_hints.py`
in the installed Hermes source tree. Confirm these after an upgrade: the
public documentation and bundled skill references can describe different revisions.

## Responsibilities and discovery

`SOUL.md` is loaded independently from the active `HERMES_HOME` as the agent's
identity. Use it for durable identity, tone, communication and principles.
Use a project context file for environment conventions and a skill for
specialized procedures loaded on demand.

Only the first available project context type is loaded at startup. In the
installed loader inspected on 2026-09-09:

| File, in priority order | Discovery |
|---|---|
| `.hermes.md` / `HERMES.md` | Nearest matching file from cwd toward the Git root; ancestor files are not merged. |
| `AGENTS.md` / `agents.md` | Inside Git, merges files from repository root to cwd. Outside Git, checks cwd only. |
| `CLAUDE.md` / `claude.md` | Checks cwd. |
| `.cursorrules` / `.cursor/rules/*.mdc` | Checks cwd. |

Later directory access can trigger progressive context discovery. Inspect
`agent/subdirectory_hints.py` for the current supported filenames and limits;
startup discovery and progressive discovery are separate paths.

The public docs also describe `AGENTS.override.md`; do not assume support in
an installed revision without checking its loader. Do not use a parent
`.hermes.md` as an implicit shared policy when a nearer `.hermes.md` exists.

## Size and security

`context_file_max_chars`, when explicitly configured, supplies the cap.
Otherwise the cap scales with the model context window, with a 20,000-character
floor and 500,000-character ceiling. Oversized files are head/tail truncated;
keep specialized procedures in skills instead of relying on a large cap.

Context files are scanned before injection. If the scanner reports a threat,
the entire scanned content is replaced by a `[BLOCKED: ...]` marker; it does
not merely remove the offending sentence. A missing or blocked policy must
be diagnosed through the loader result, not by assuming the file reached the model.

## Verify the actual session

Resolve the active profile home and actual working directory. A profile home
is not automatically the workspace; `terminal.cwd` controls the configured
starting directory and session overrides can select another directory.

For a local read-only check, call `load_soul_md(home_override=...)` and
`build_context_files_prompt(cwd=..., skip_soul=True)` in the installed Python
environment bound to the target `HERMES_HOME`. Check that the intended content
is present and that there are no blocked or truncated markers. In normal
runtime assembly, `skip_soul=True` avoids duplicating the identity section.

`--ignore-rules` bypasses context injection, including SOUL identity. Inspect
the installed command's help and implementation before relying on any broader
isolation behavior; the flag is not a substitute for checking resolved tools,
plugins, configuration or MCP connections.
